"""Tenant-filtered persistence for evidence, corrections, exports, and audit review."""

from datetime import datetime
from typing import Any

from bson import ObjectId

from .repository import _object_id, _restore_utc, _version_snapshot


class HardeningRepository:
    def __init__(self, database):
        self.db = database

    async def create_evidence(self, document: dict) -> dict:
        result = await self.db.campaign_evidence_records.insert_one(document)
        return await self.db.campaign_evidence_records.find_one({"_id": result.inserted_id})

    async def duplicate_evidence(self, tenant_id: str, performance_id: str, checksum: str) -> dict | None:
        return await self.db.campaign_evidence_records.find_one({
            "tenant_id": tenant_id, "campaign_performance_record_id": performance_id,
            "checksum_sha256": checksum, "deleted_at": None,
        })

    async def get_evidence(self, evidence_id: str, tenant_id: str | None,
                           include_deleted: bool = False) -> dict | None:
        query: dict[str, Any] = {"_id": _object_id(evidence_id)}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        if not include_deleted:
            query["deleted_at"] = None
        return await self.db.campaign_evidence_records.find_one(query)

    async def list_evidence(self, performance_id: str, tenant_id: str | None,
                            include_deleted: bool = False, limit: int = 100) -> list[dict]:
        query: dict[str, Any] = {"campaign_performance_record_id": performance_id}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        if not include_deleted:
            query["deleted_at"] = None
        return await self.db.campaign_evidence_records.find(query).sort("submitted_at", -1).limit(limit).to_list(limit)

    async def transition_evidence(self, evidence: dict, expected_verification: str,
                                  updates: dict) -> dict | None:
        result = await self.db.campaign_evidence_records.update_one(
            {"_id": evidence["_id"], "tenant_id": evidence["tenant_id"],
             "verification_status": expected_verification, "deleted_at": None},
            {"$set": updates},
        )
        if result.modified_count != 1:
            return None
        return await self.db.campaign_evidence_records.find_one({"_id": evidence["_id"]})

    async def soft_delete_evidence(self, evidence: dict, updates: dict) -> dict:
        await self.db.campaign_evidence_records.update_one(
            {"_id": evidence["_id"], "tenant_id": evidence["tenant_id"], "deleted_at": None},
            {"$set": updates},
        )
        return await self.db.campaign_evidence_records.find_one({"_id": evidence["_id"]})

    async def restore_evidence(self, evidence: dict, updates: dict) -> dict:
        await self.db.campaign_evidence_records.update_one(
            {"_id": evidence["_id"], "tenant_id": evidence["tenant_id"]}, {"$set": updates},
        )
        return await self.db.campaign_evidence_records.find_one({"_id": evidence["_id"]})

    async def active_evidence_for_performance(self, tenant_id: str, performance_id: str) -> list[dict]:
        return await self.db.campaign_evidence_records.find({
            "tenant_id": tenant_id, "campaign_performance_record_id": performance_id,
            "deleted_at": None, "evidence_status": "active",
            "verification_status": {"$in": ["unverified", "verified"]},
        }).sort("submitted_at", -1).limit(100).to_list(100)

    async def create_correction(self, document: dict) -> dict:
        result = await self.db.commercial_correction_proposals.insert_one(document)
        return await self.db.commercial_correction_proposals.find_one({"_id": result.inserted_id})

    async def get_correction(self, correction_id: str, tenant_id: str | None) -> dict | None:
        query: dict[str, Any] = {"_id": _object_id(correction_id)}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        return await self.db.commercial_correction_proposals.find_one(query)

    async def list_corrections(self, record_id: str, tenant_id: str | None,
                               limit: int = 100) -> list[dict]:
        query: dict[str, Any] = {"record_type": "campaign_performance", "record_id": record_id}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        return await self.db.commercial_correction_proposals.find(query).sort("submitted_at", -1).limit(limit).to_list(limit)

    async def decide_correction(self, proposal: dict, status: str, updates: dict) -> dict | None:
        result = await self.db.commercial_correction_proposals.update_one(
            {"_id": proposal["_id"], "tenant_id": proposal["tenant_id"], "status": "pending"},
            {"$set": {"status": status, **updates}},
        )
        if result.modified_count != 1:
            return None
        return await self.db.commercial_correction_proposals.find_one({"_id": proposal["_id"]})

    async def approve_correction(self, proposal: dict, performance: dict, changes: dict,
                                 actor_id: str, reviewed_at: datetime, review_reason: str) -> tuple[dict, dict] | None:
        next_version = int(performance.get("version", 1)) + 1
        update = {**changes, "version": next_version, "updated_at": reviewed_at, "updated_by": actor_id}
        result = await self.db.campaign_performance_records.update_one(
            {"_id": performance["_id"], "tenant_id": performance["tenant_id"],
             "version": performance.get("version", 1)},
            {"$set": update},
        )
        if result.modified_count != 1:
            return None
        version_result = await self.db.commercial_record_versions.insert_one({
            "tenant_id": performance["tenant_id"], "record_type": "campaign_performance",
            "record_id": str(performance["_id"]), "version": performance.get("version", 1),
            "previous": _version_snapshot(performance), "correction_proposal_id": str(proposal["_id"]),
            "created_at": reviewed_at, "created_by": actor_id,
        })
        decided = await self.decide_correction(proposal, "approved", {
            "reviewed_at": reviewed_at, "reviewed_by": actor_id,
            "review_reason": review_reason, "approved_version_id": str(version_result.inserted_id),
        })
        if decided is None:
            return None
        updated = await self.db.campaign_performance_records.find_one({"_id": performance["_id"]})
        return decided, updated

    async def create_export(self, document: dict) -> dict:
        result = await self.db.commercial_export_artifacts.insert_one(document)
        return await self.db.commercial_export_artifacts.find_one({"_id": result.inserted_id})

    async def get_export(self, export_id: str, tenant_id: str | None,
                         include_deleted: bool = False) -> dict | None:
        query: dict[str, Any] = {"_id": _object_id(export_id)}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        if not include_deleted:
            query["deleted_at"] = None
        return await self.db.commercial_export_artifacts.find_one(query)

    async def soft_delete_export(self, artifact: dict, updates: dict) -> dict:
        await self.db.commercial_export_artifacts.update_one(
            {"_id": artifact["_id"], "tenant_id": artifact["tenant_id"], "deleted_at": None},
            {"$set": updates},
        )
        return await self.db.commercial_export_artifacts.find_one({"_id": artifact["_id"]})

    async def export_rows(self, collection_name: str, tenant_id: str, start: datetime,
                          end: datetime, limit: int, include_deleted: bool) -> list[dict]:
        collection = getattr(self.db, collection_name)
        query: dict[str, Any] = {"tenant_id": tenant_id, "created_at": {"$gte": start, "$lte": end}}
        if not include_deleted and collection_name in {
            "campaign_evidence_records", "commercial_export_artifacts",
        }:
            query["deleted_at"] = None
        return await collection.find(query).sort("created_at", -1).limit(limit).to_list(limit)

    async def audit_events(self, tenant_id: str | None, start: datetime, end: datetime,
                           limit: int, record_type: str | None, record_id: str | None,
                           action: str | None) -> list[dict]:
        query: dict[str, Any] = {"created_at": {"$gte": start, "$lte": end}}
        if tenant_id is not None:
            query["$or"] = [{"tenant_id": tenant_id}, {"tenant_id": {"$exists": False}, "user_id": tenant_id}]
        if record_type:
            query["entity"] = record_type
        if record_id:
            query["entity_id"] = record_id
        if action:
            query["action"] = action
        return await self.db.activity_logs.find(query).sort([("created_at", -1), ("_id", -1)]).limit(limit).to_list(limit)

    async def evaluate_retention(self, now: datetime, actor_id: str) -> tuple[int, int, int, list[dict]]:
        evidence = await self.db.campaign_evidence_records.find({
            "retention_expires_at": {"$lte": now}, "deleted_at": None,
        }).to_list(1000)
        exports = await self.db.commercial_export_artifacts.find({
            "expires_at": {"$lte": now}, "deleted_at": None,
        }).to_list(1000)
        already = await self.db.campaign_evidence_records.count_documents({
            "retention_expires_at": {"$lte": now}, "deleted_at": {"$ne": None},
        }) + await self.db.commercial_export_artifacts.count_documents({
            "expires_at": {"$lte": now}, "deleted_at": {"$ne": None},
        })
        changed: list[dict] = []
        for item in evidence:
            await self.db.campaign_evidence_records.update_one(
                {"_id": item["_id"], "deleted_at": None},
                {"$set": {"deleted_at": now, "deleted_by": actor_id,
                          "deletion_reason": "retention_expired", "evidence_status": "deleted", "updated_at": now}},
            )
            changed.append({"tenant_id": item["tenant_id"], "type": "campaign_evidence", "id": str(item["_id"])})
        for item in exports:
            await self.db.commercial_export_artifacts.update_one(
                {"_id": item["_id"], "deleted_at": None},
                {"$set": {"deleted_at": now, "deleted_by": actor_id, "deletion_reason": "retention_expired"}},
            )
            changed.append({"tenant_id": item["tenant_id"], "type": "commercial_export", "id": str(item["_id"])})
        return len(evidence), len(exports), already, changed


def restored(document: dict) -> dict:
    return _restore_utc(document)
