"""Mongo repository with mandatory tenant filters for non-admin access."""

from datetime import datetime
from typing import Any

from bson import ObjectId


class CommercialRepository:
    def __init__(self, database):
        self.db = database

    async def create_profile(self, tenant_id: str, actor_id: str, document: dict) -> dict:
        stored = {**document, "tenant_id": tenant_id, "created_by": actor_id, "updated_by": actor_id}
        result = await self.db.creator_commercial_profiles.insert_one(stored)
        return await self.db.creator_commercial_profiles.find_one({"_id": result.inserted_id})

    async def find_profile_by_identity(self, tenant_id: str, platform: str, platform_id: str) -> dict | None:
        return await self.db.creator_commercial_profiles.find_one({
            "tenant_id": tenant_id, "platform": platform, "platform_id": platform_id,
        })

    async def get_profile(self, profile_id: str, tenant_id: str | None) -> dict | None:
        query = {"_id": _object_id(profile_id)}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        return await self.db.creator_commercial_profiles.find_one(query)

    async def list_profiles(self, tenant_id: str | None, limit: int, platform: str | None = None) -> list[dict]:
        query: dict[str, Any] = {}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        if platform:
            query["platform"] = platform
        return await self.db.creator_commercial_profiles.find(query).sort("updated_at", -1).limit(limit).to_list(limit)

    async def patch_profile(self, profile: dict, actor_id: str, changes: dict) -> dict:
        await self.db.creator_commercial_profiles.update_one(
            {"_id": profile["_id"], "tenant_id": profile["tenant_id"]},
            {"$set": {**changes, "updated_by": actor_id}},
        )
        return await self.db.creator_commercial_profiles.find_one({"_id": profile["_id"]})

    async def append_rate(self, tenant_id: str, actor_id: str, profile_id: str, document: dict) -> dict:
        stored = {
            **document, "tenant_id": tenant_id, "commercial_profile_id": profile_id,
            "created_by": actor_id,
        }
        result = await self.db.creator_rate_history.insert_one(stored)
        return await self.db.creator_rate_history.find_one({"_id": result.inserted_id})

    async def list_rates(self, tenant_id: str | None, profile_id: str, limit: int = 100) -> list[dict]:
        query: dict[str, Any] = {"commercial_profile_id": profile_id}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        return await self.db.creator_rate_history.find(query).sort("effective_at", -1).limit(limit).to_list(limit)

    async def append_negotiation(self, tenant_id: str, actor_id: str, profile_id: str, document: dict) -> dict:
        stored = {
            **document, "tenant_id": tenant_id, "commercial_profile_id": profile_id,
            "created_by": actor_id,
        }
        result = await self.db.creator_negotiations.insert_one(stored)
        return await self.db.creator_negotiations.find_one({"_id": result.inserted_id})

    async def list_negotiations(self, tenant_id: str | None, profile_id: str, limit: int = 100) -> list[dict]:
        query: dict[str, Any] = {"commercial_profile_id": profile_id}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        return await self.db.creator_negotiations.find(query).sort("occurred_at", -1).limit(limit).to_list(limit)

    async def create_performance(self, tenant_id: str, actor_id: str, document: dict) -> dict:
        stored = {**document, "tenant_id": tenant_id, "created_by": actor_id, "updated_by": actor_id}
        result = await self.db.campaign_performance_records.insert_one(stored)
        return await self.db.campaign_performance_records.find_one({"_id": result.inserted_id})

    async def get_performance(self, record_id: str, tenant_id: str | None) -> dict | None:
        query = {"_id": _object_id(record_id)}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        return await self.db.campaign_performance_records.find_one(query)

    async def list_performance(self, tenant_id: str | None, limit: int, start: datetime | None = None,
                               end: datetime | None = None, currency: str | None = None) -> list[dict]:
        query: dict[str, Any] = {}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        if start or end:
            period: dict[str, datetime] = {}
            if start:
                period["$gte"] = start
            if end:
                period["$lte"] = end
            query["measurement_period_end"] = period
        if currency:
            query["currency"] = currency
        return await self.db.campaign_performance_records.find(query).sort("measurement_period_end", -1).limit(limit).to_list(limit)

    async def patch_performance(self, record: dict, actor_id: str, changes: dict,
                                correction_reason: str | None) -> dict:
        await self.db.commercial_record_versions.insert_one({
            "tenant_id": record["tenant_id"], "record_type": "campaign_performance",
            "record_id": str(record["_id"]), "previous": _version_snapshot(record),
            "correction_reason": correction_reason, "created_at": changes["updated_at"],
            "created_by": actor_id,
        })
        await self.db.campaign_performance_records.update_one(
            {"_id": record["_id"], "tenant_id": record["tenant_id"]},
            {"$set": {**changes, "updated_by": actor_id}},
        )
        return await self.db.campaign_performance_records.find_one({"_id": record["_id"]})

    async def audit(self, actor_id: str, action: str, record_type: str,
                    record_id: str, changed_fields: list[str]) -> None:
        await self.db.activity_logs.insert_one({
            "user_id": actor_id, "action": action, "entity": record_type,
            "entity_id": record_id, "meta": {"changed_fields": sorted(set(changed_fields))},
            "created_at": _utc_now(),
        })

    async def latest_rates_for_profiles(self, tenant_id: str, profile_ids: list[str]) -> dict[str, list[dict]]:
        if not profile_ids:
            return {}
        records = await self.db.creator_rate_history.find({
            "tenant_id": tenant_id, "commercial_profile_id": {"$in": profile_ids},
            "verification_status": {"$ne": "rejected"},
        }).sort("effective_at", -1).to_list(1000)
        grouped: dict[str, list[dict]] = {}
        for record in records:
            grouped.setdefault(record["commercial_profile_id"], []).append(record)
        return grouped

    async def analytics_records(self, tenant_id: str | None, start: datetime, end: datetime,
                                limit: int, currency: str | None) -> tuple[list[dict], list[dict], list[dict]]:
        query: dict[str, Any] = {"created_at": {"$gte": start, "$lte": end}}
        if tenant_id is not None:
            query["tenant_id"] = tenant_id
        if currency:
            query["currency"] = currency
        rates = await self.db.creator_rate_history.find(query).sort("effective_at", -1).limit(limit).to_list(limit)
        negotiations = await self.db.creator_negotiations.find(query).sort("occurred_at", -1).limit(limit).to_list(limit)
        performance_query = dict(query)
        performance_query.pop("created_at", None)
        performance_query["measurement_period_end"] = {"$gte": start, "$lte": end}
        performance = await self.db.campaign_performance_records.find(performance_query).sort("measurement_period_end", -1).limit(limit).to_list(limit)
        return rates, negotiations, performance


async def setup_indexes(database) -> None:
    await database.creator_commercial_profiles.create_index(
        [("tenant_id", 1), ("platform", 1), ("platform_id", 1)], unique=True,
    )
    await database.creator_rate_history.create_index(
        [("tenant_id", 1), ("commercial_profile_id", 1), ("effective_at", -1)],
    )
    await database.creator_negotiations.create_index(
        [("tenant_id", 1), ("commercial_profile_id", 1), ("occurred_at", -1)],
    )
    await database.campaign_performance_records.create_index(
        [("tenant_id", 1), ("measurement_period_end", -1)],
    )
    await database.campaign_performance_records.create_index(
        [("tenant_id", 1), ("campaign_id", 1), ("commercial_profile_id", 1)],
    )
    await database.commercial_record_versions.create_index(
        [("tenant_id", 1), ("record_type", 1), ("record_id", 1), ("created_at", -1)],
    )


def public_document(document: dict) -> dict:
    output = {
        key: value for key, value in document.items()
        if key not in {"_id", "tenant_id", "created_by", "updated_by", "previous", "correction_reason"}
    }
    output["id"] = str(document["_id"])
    return _restore_utc(output)


def _object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise ValueError("invalid record id")
    return ObjectId(value)


def _version_snapshot(record: dict) -> dict:
    return {
        key: value for key, value in record.items()
        if key not in {"_id", "tenant_id", "created_by", "updated_by"}
    }


def _restore_utc(value):
    from datetime import datetime, timezone
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, dict):
        return {key: _restore_utc(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_restore_utc(item) for item in value]
    return value


def _utc_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
