"""Mongo persistence for admin research jobs, saved leads, and safe audit events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from .models import AdminResearchRequest, LeadPriority, LeadStatus, ResearchJobStatus


ADMIN_AUDIT_SCOPE = "brandkrt-admin-lead-intelligence"


class AdminLeadRepository:
    def __init__(self, database):
        self.db = database
        self.jobs = database.admin_research_jobs
        self.leads = database.admin_saved_leads
        self.audit = database.activity_logs

    async def create_job(self, request: AdminResearchRequest, actor_id: str) -> dict:
        now = datetime.now(timezone.utc)
        criteria = request.model_dump(mode="json", exclude_none=True)
        document = {
            "created_by": actor_id,
            "research_name": request.research_name,
            "entity_type": request.entity_type.value,
            "platforms": [item.value for item in request.platforms],
            "query_summary": _query_summary(request),
            "criteria": criteria,
            "status": ResearchJobStatus.QUEUED.value,
            "progress": 0,
            "result_count": 0,
            "confidence": 0.0,
            "reasoning_source": None,
            "degraded": False,
            "error_code": None,
            "results": [],
            "warnings": [],
            "missing_information": [],
            "source_summary": [],
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "updated_at": now,
        }
        inserted = await self.jobs.insert_one(document)
        document["_id"] = inserted.inserted_id
        await self.audit_event(actor_id, "admin_research_created", "admin_research_job", str(inserted.inserted_id), ["criteria"])
        return document

    async def active_job_count(self, actor_id: str) -> int:
        return await self.jobs.count_documents({
            "created_by": actor_id,
            "status": {"$in": [ResearchJobStatus.QUEUED.value, ResearchJobStatus.RUNNING.value]},
        })

    async def fail_stale_jobs(self, actor_id: str) -> int:
        """Release jobs left active by a terminated web process."""
        now = datetime.now(timezone.utc)
        result = await self.jobs.update_many(
            {
                "created_by": actor_id,
                "status": {"$in": [ResearchJobStatus.QUEUED.value, ResearchJobStatus.RUNNING.value]},
                "updated_at": {"$lt": now - timedelta(minutes=30)},
            },
            {"$set": {
                "status": ResearchJobStatus.FAILED.value, "progress": 100,
                "error_code": "worker_interrupted", "completed_at": now, "updated_at": now,
                "warnings": ["Research was interrupted by a process restart and can be rerun safely."],
            }},
        )
        return int(result.modified_count)

    async def get_job(self, job_id: str) -> dict | None:
        object_id = _object_id(job_id)
        return None if object_id is None else await self.jobs.find_one({"_id": object_id})

    async def update_job(self, job_id: str, values: dict) -> dict | None:
        object_id = _object_id(job_id)
        if object_id is None:
            return None
        values = dict(values)
        values["updated_at"] = datetime.now(timezone.utc)
        return await self.jobs.find_one_and_update(
            {"_id": object_id}, {"$set": values}, return_document=ReturnDocument.AFTER,
        )

    async def list_jobs(
        self, *, page: int, page_size: int, search: str | None,
        entity_type: str | None, platform: str | None, status: str | None,
        sort_by: str, sort_order: str,
    ) -> tuple[list[dict], int]:
        query: dict = {}
        if search:
            expression = re.compile(re.escape(search), re.IGNORECASE)
            query["$or"] = [{"research_name": expression}, {"query_summary": expression}]
        if entity_type:
            query["entity_type"] = entity_type
        if platform:
            query["platforms"] = platform
        if status:
            query["status"] = status
        fields = {"created_at": "created_at", "results": "result_count", "confidence": "confidence"}
        order = ASCENDING if sort_order == "asc" else DESCENDING
        total = await self.jobs.count_documents(query)
        cursor = self.jobs.find(query).sort([(fields.get(sort_by, "created_at"), order), ("_id", order)])
        items = await cursor.skip((page - 1) * page_size).limit(page_size).to_list(page_size)
        return items, total

    async def commercial_summary(self, platform: str, platform_id: str) -> dict | None:
        return await self.db.creator_commercial_profiles.find_one(
            {"platform": platform, "platform_id": platform_id},
            {
                "currency": 1, "current_known_rate": 1, "current_negotiated_rate": 1,
                "rate_verification_status": 1, "updated_at": 1,
            },
            sort=[("updated_at", DESCENDING)],
        )

    async def saved_fingerprints(self, entity_keys: list[str]) -> dict[str, str]:
        fingerprints = {_fingerprint(value): value for value in entity_keys}
        cursor = self.leads.find(
            {"fingerprint": {"$in": list(fingerprints)}}, {"fingerprint": 1},
        )
        rows = await cursor.to_list(len(fingerprints))
        return {row["fingerprint"]: str(row["_id"]) for row in rows}

    async def save_lead(self, job: dict, result: dict, actor_id: str) -> dict:
        now = datetime.now(timezone.utc)
        fingerprint = _fingerprint(result["entity_key"])
        existing = await self.leads.find_one({"fingerprint": fingerprint}, {"_id": 1})
        values = {
            "research_id": str(job["_id"]), "result": result,
            "last_seen_at": now, "updated_at": now,
        }
        try:
            document = await self.leads.find_one_and_update(
                {"fingerprint": fingerprint},
                {
                    "$set": values,
                    "$setOnInsert": {
                        "fingerprint": fingerprint, "status": LeadStatus.NEW.value,
                        "archived": False, "notes": [], "created_by": actor_id,
                        "created_at": now,
                    },
                },
                upsert=True, return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            document = await self.leads.find_one_and_update(
                {"fingerprint": fingerprint}, {"$set": values}, return_document=ReturnDocument.AFTER,
            )
            existing = document
        await self.audit_event(
            actor_id, "admin_lead_refreshed" if existing else "admin_lead_saved",
            "admin_saved_lead", str(document["_id"]), ["result"] if existing else ["status", "result"],
        )
        return document

    async def get_lead(self, lead_id: str) -> dict | None:
        object_id = _object_id(lead_id)
        return None if object_id is None else await self.leads.find_one({"_id": object_id})

    async def list_leads(
        self, *, page: int, page_size: int, search: str | None, entity_type: str | None,
        platform: str | None, status: str | None, priority: str | None,
        archived: bool, sort_by: str, sort_order: str,
    ) -> tuple[list[dict], int]:
        query: dict = {"archived": archived}
        if search:
            expression = re.compile(re.escape(search), re.IGNORECASE)
            query["$or"] = [
                {"result.display_name": expression}, {"result.username": expression},
                {"result.categories": expression}, {"result.keywords": expression},
            ]
        if entity_type:
            query["result.entity_type"] = entity_type
        if platform:
            query["result.platform"] = platform
        if status:
            query["status"] = status
        if priority:
            query["result.priority.priority"] = priority
        fields = {
            "updated_at": "updated_at", "created_at": "created_at",
            "priority": "result.priority.score", "recommendation": "result.recommendation_score",
        }
        order = ASCENDING if sort_order == "asc" else DESCENDING
        total = await self.leads.count_documents(query)
        cursor = self.leads.find(query).sort([(fields.get(sort_by, "updated_at"), order), ("_id", order)])
        items = await cursor.skip((page - 1) * page_size).limit(page_size).to_list(page_size)
        return items, total

    async def update_lead_status(self, lead_id: str, status: LeadStatus, actor_id: str) -> dict | None:
        object_id = _object_id(lead_id)
        if object_id is None:
            return None
        now = datetime.now(timezone.utc)
        document = await self.leads.find_one_and_update(
            {"_id": object_id}, {"$set": {"status": status.value, "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if document:
            await self.audit_event(actor_id, "admin_lead_status_changed", "admin_saved_lead", lead_id, ["status"])
        return document

    async def add_note(self, lead_id: str, note: str, actor_id: str) -> dict | None:
        object_id = _object_id(lead_id)
        if object_id is None:
            return None
        now = datetime.now(timezone.utc)
        document = await self.leads.find_one_and_update(
            {"_id": object_id},
            {"$push": {"notes": {"$each": [{"note": note, "created_at": now}], "$slice": -100}},
             "$set": {"updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if document:
            await self.audit_event(actor_id, "admin_lead_note_added", "admin_saved_lead", lead_id, ["notes"])
        return document

    async def archive_lead(self, lead_id: str, actor_id: str) -> dict | None:
        object_id = _object_id(lead_id)
        if object_id is None:
            return None
        now = datetime.now(timezone.utc)
        document = await self.leads.find_one_and_update(
            {"_id": object_id}, {"$set": {"archived": True, "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if document:
            await self.audit_event(actor_id, "admin_lead_archived", "admin_saved_lead", lead_id, ["archived"])
        return document

    async def lead_audit(self, lead_id: str, limit: int) -> list[dict]:
        cursor = self.audit.find({
            "tenant_id": ADMIN_AUDIT_SCOPE, "entity_type": "admin_saved_lead", "entity_id": lead_id,
        }).sort([("created_at", DESCENDING), ("_id", DESCENDING)]).limit(limit)
        return await cursor.to_list(limit)

    async def audit_event(
        self, actor_id: str, action: str, entity_type: str, entity_id: str,
        changed_fields: list[str],
    ) -> None:
        await self.audit.insert_one({
            "tenant_id": ADMIN_AUDIT_SCOPE, "actor_id": actor_id,
            "actor_category": "admin", "action": action,
            "entity_type": entity_type, "entity_id": entity_id,
            "changed_fields": changed_fields, "created_at": datetime.now(timezone.utc),
        })

    async def analytics(self) -> dict:
        completed = {"status": ResearchJobStatus.COMPLETED.value}
        active_leads = {"archived": False}
        result_counts = {
            item["_id"]: item["count"] for item in await self.jobs.aggregate([
                {"$match": completed}, {"$unwind": "$results"},
                {"$group": {"_id": "$results.entity_type", "count": {"$sum": 1}}},
            ]).to_list(10)
        }
        status_counts = {
            item["_id"]: item["count"] for item in await self.leads.aggregate([
                {"$match": active_leads},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            ]).to_list(20)
        }
        niches = await self.leads.aggregate([
            {"$match": active_leads}, {"$unwind": "$result.categories"},
            {"$group": {"_id": "$result.categories", "count": {"$sum": 1}}},
            {"$sort": {"count": -1, "_id": 1}}, {"$limit": 8},
        ]).to_list(8)
        platforms = await self.leads.aggregate([
            {"$match": active_leads},
            {"$group": {"_id": "$result.platform", "count": {"$sum": 1}}},
            {"$sort": {"count": -1, "_id": 1}}, {"$limit": 8},
        ]).to_list(8)
        recent = await self.audit.find({"tenant_id": ADMIN_AUDIT_SCOPE}).sort(
            "created_at", DESCENDING,
        ).limit(12).to_list(12)
        return {
            "brands_found": int(result_counts.get("brand", 0)),
            "creators_found": int(result_counts.get("creator", 0)),
            "high_priority_leads": await self.leads.count_documents({
                **active_leads, "result.priority.priority": LeadPriority.HIGH.value,
            }),
            "contacted": int(status_counts.get(LeadStatus.CONTACTED.value, 0)),
            "replies": int(status_counts.get(LeadStatus.REPLIED.value, 0)),
            "converted": int(status_counts.get(LeadStatus.CONVERTED.value, 0)),
            "research_volume": await self.jobs.count_documents(completed),
            "saved_leads": await self.leads.count_documents(active_leads),
            "top_niches": [{"name": item["_id"], "count": item["count"]} for item in niches if item.get("_id")],
            "top_platforms": [{"name": item["_id"], "count": item["count"]} for item in platforms if item.get("_id")],
            "recent_activity": [_public_activity(item) for item in recent],
        }

    async def ai_activity(self, page: int, page_size: int) -> tuple[list[dict], int]:
        query = {"status": {"$in": [ResearchJobStatus.COMPLETED.value, ResearchJobStatus.FAILED.value]}}
        total = await self.jobs.count_documents(query)
        rows = await self.jobs.find(query).sort([("completed_at", DESCENDING), ("_id", DESCENDING)]).skip(
            (page - 1) * page_size,
        ).limit(page_size).to_list(page_size)
        return [{
            "research_id": str(item["_id"]), "research_name": item.get("research_name"),
            "entity_type": item.get("entity_type"), "status": item.get("status"),
            "reasoning_source": item.get("reasoning_source"), "degraded": bool(item.get("degraded")),
            "result_count": int(item.get("result_count", 0)), "error_code": item.get("error_code"),
            "created_at": item.get("created_at"), "completed_at": item.get("completed_at"),
        } for item in rows], total


async def create_admin_lead_indexes(database) -> None:
    await database.admin_research_jobs.create_index(
        [("created_at", DESCENDING)], name="admin_research_created",
    )
    await database.admin_research_jobs.create_index(
        [("status", ASCENDING), ("created_at", DESCENDING)], name="admin_research_status_created",
    )
    await database.admin_saved_leads.create_index(
        [("fingerprint", ASCENDING)], unique=True, name="admin_saved_lead_fingerprint",
    )
    await database.admin_saved_leads.create_index(
        [("archived", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)],
        name="admin_saved_lead_workflow",
    )
    await database.admin_saved_leads.create_index(
        [("result.entity_type", ASCENDING), ("result.platform", ASCENDING), ("updated_at", DESCENDING)],
        name="admin_saved_lead_discovery",
    )


def _query_summary(request: AdminResearchRequest) -> str:
    parts = [request.industry, request.niche, *request.categories, *request.keywords, request.location]
    value = " · ".join(dict.fromkeys(item.strip() for item in parts if item and item.strip()))
    return value[:500] or "All available factual profiles"


def _fingerprint(entity_key: str) -> str:
    return hashlib.sha256(entity_key.strip().casefold().encode("utf-8")).hexdigest()


def _object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except Exception:
        return None


def _public_activity(item: dict) -> dict:
    return {
        "action": item.get("action", "unknown"),
        "entity_type": item.get("entity_type", "unknown"),
        "changed_fields": list(item.get("changed_fields", []))[:10],
        "created_at": item.get("created_at"),
    }
