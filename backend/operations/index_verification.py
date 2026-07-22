"""Non-destructive verification of critical, deterministically declared indexes."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class IndexRequirement:
    collection: str
    keys: tuple[tuple[str, int], ...]
    unique: bool = False
    ttl: bool = False


@dataclass(frozen=True)
class IndexVerificationResult:
    ready: bool
    checked: int
    missing: tuple[str, ...]

    def public(self) -> dict:
        return asdict(self)


CRITICAL_INDEXES = (
    IndexRequirement("users", (("email", 1),), unique=True),
    IndexRequirement("campaign_performance_records", (("tenant_id", 1), ("measurement_period_end", -1))),
    IndexRequirement("campaign_evidence_records", (("tenant_id", 1), ("campaign_performance_record_id", 1), ("submitted_at", -1))),
    IndexRequirement("commercial_correction_proposals", (("tenant_id", 1), ("record_id", 1), ("status", 1), ("submitted_at", -1))),
    IndexRequirement("commercial_export_artifacts", (("tenant_id", 1), ("created_at", -1), ("expires_at", 1), ("deleted_at", 1))),
    IndexRequirement("activity_logs", (("tenant_id", 1), ("created_at", -1))),
    IndexRequirement("admin_research_jobs", (("created_at", -1),)),
    IndexRequirement("admin_saved_leads", (("fingerprint", 1),), unique=True),
    IndexRequirement("operational_rate_limits", (("expires_at", 1),), ttl=True),
    IndexRequirement("ai_usage_counters", (("expires_at", 1),), ttl=True),
    IndexRequirement("ai_usage_reservations", (("expires_at", 1),), ttl=True),
)


async def verify_critical_indexes(database) -> IndexVerificationResult:
    missing = []
    for requirement in CRITICAL_INDEXES:
        information = await database[requirement.collection].index_information()
        if not any(_matches(specification, requirement) for specification in information.values()):
            missing.append(f"{requirement.collection}:{','.join(key for key, _ in requirement.keys)}")
    return IndexVerificationResult(not missing, len(CRITICAL_INDEXES), tuple(missing))


async def create_operational_indexes(database) -> None:
    await database.operational_rate_limits.create_index(
        [("expires_at", 1)], expireAfterSeconds=0, name="operational_rate_limits_expiry",
    )
    await database.ai_usage_counters.create_index(
        [("expires_at", 1)], expireAfterSeconds=0, name="ai_usage_counters_expiry",
    )
    await database.ai_usage_reservations.create_index(
        [("expires_at", 1)], expireAfterSeconds=0, name="ai_usage_reservations_expiry",
    )


def _matches(specification: dict, requirement: IndexRequirement) -> bool:
    try:
        keys = tuple((str(key), int(direction)) for key, direction in specification.get("key", []))
    except (TypeError, ValueError):
        return False
    if keys != requirement.keys:
        return False
    if requirement.unique and not specification.get("unique"):
        return False
    if requirement.ttl and specification.get("expireAfterSeconds") != 0:
        return False
    return True
