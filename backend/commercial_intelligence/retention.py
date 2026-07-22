"""Configurable retention metadata and explicit idempotent policy evaluation."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os


def _days(name: str, default: int) -> int | None:
    raw = os.environ.get(name, str(default)).strip().casefold()
    if raw == "indefinite":
        return None
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, min(value, 36_500))


@dataclass(frozen=True)
class RetentionPolicy:
    evidence_metadata_days: int | None = 730
    evidence_file_days: int | None = 730
    correction_proposal_days: int | None = 1095
    export_artifact_days: int | None = 7
    audit_event_days: int | None = 2555

    @classmethod
    def from_env(cls) -> "RetentionPolicy":
        return cls(
            evidence_metadata_days=_days("COMMERCIAL_RETENTION_EVIDENCE_METADATA_DAYS", 730),
            evidence_file_days=_days("COMMERCIAL_RETENTION_EVIDENCE_FILE_DAYS", 730),
            correction_proposal_days=_days("COMMERCIAL_RETENTION_CORRECTION_DAYS", 1095),
            export_artifact_days=_days("COMMERCIAL_RETENTION_EXPORT_DAYS", 7),
            audit_event_days=_days("COMMERCIAL_RETENTION_AUDIT_DAYS", 2555),
        )

    def expiry(self, category: str, created_at: datetime | None = None) -> datetime | None:
        mapping = {
            "evidence_metadata": self.evidence_metadata_days,
            "evidence_file": self.evidence_file_days,
            "correction_proposal": self.correction_proposal_days,
            "export_artifact": self.export_artifact_days,
            "audit_event": self.audit_event_days,
        }
        days = mapping[category]
        if days is None:
            return None
        base = created_at or datetime.now(timezone.utc)
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        return base.astimezone(timezone.utc) + timedelta(days=days)
