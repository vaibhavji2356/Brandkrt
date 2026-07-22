"""Evidence, correction review, retention, export, and audit hardening rules."""

from datetime import datetime, timedelta, timezone
from enum import Enum
import json
from statistics import fmean
from typing import Any

from bson import ObjectId
from fastapi import HTTPException

from .evidence_storage import EvidenceStorage
from .evidence_validation import ValidatedEvidenceFile
from .hardening_models import (
    AuditReviewEvent, CampaignEvidenceRecord, CorrectionProposal, CorrectionProposalCreate,
    CorrectionReviewAction, CorrectionStatus, EvidenceMetadataInput, EvidenceRejectAction,
    EvidenceReviewAction, EvidenceStatus, EvidenceSupersedeAction, EvidenceType, EvidenceVerificationStatus,
    ExportCategory, RetentionEvaluationResult, SoftDeleteAction, SupportedMetric,
    TenantExportArtifact, TenantExportRequest,
)
from .hardening_repository import HardeningRepository
from .models import MetricEvidenceStatus, VerificationStatus
from .repository import CommercialRepository, public_document
from .retention import RetentionPolicy
from .service import CommercialService, require_commercial_role, tenant_scope, write_tenant, _deliverable_warnings


_EVIDENCE_METRIC_ALLOWLIST: dict[EvidenceType, set[SupportedMetric]] = {
    EvidenceType.ANALYTICS_SCREENSHOT: {
        SupportedMetric.REACH, SupportedMetric.VIEWS, SupportedMetric.IMPRESSIONS,
        SupportedMetric.LIKES, SupportedMetric.COMMENTS, SupportedMetric.SHARES, SupportedMetric.CLICKS,
    },
    EvidenceType.PLATFORM_EXPORT: {
        SupportedMetric.REACH, SupportedMetric.VIEWS, SupportedMetric.IMPRESSIONS,
        SupportedMetric.LIKES, SupportedMetric.COMMENTS, SupportedMetric.SHARES,
        SupportedMetric.CLICKS, SupportedMetric.CONVERSIONS,
    },
    EvidenceType.INVOICE_COPY: {SupportedMetric.AGREED_COST},
    EvidenceType.SIGNED_RATE_CARD: {SupportedMetric.AGREED_COST},
    EvidenceType.CONTRACT_REFERENCE: {SupportedMetric.AGREED_COST, SupportedMetric.DELIVERABLES},
    EvidenceType.DELIVERABLE_PROOF: {SupportedMetric.DELIVERABLES},
    EvidenceType.CAMPAIGN_REPORT: {
        SupportedMetric.REACH, SupportedMetric.VIEWS, SupportedMetric.IMPRESSIONS,
        SupportedMetric.LIKES, SupportedMetric.COMMENTS, SupportedMetric.SHARES,
        SupportedMetric.CLICKS, SupportedMetric.CONVERSIONS, SupportedMetric.REVENUE,
        SupportedMetric.DELIVERABLES,
    },
    EvidenceType.PAYMENT_REFERENCE: {SupportedMetric.AGREED_COST},
    EvidenceType.OTHER: set(),
}

_EXPORT_COLLECTIONS = {
    ExportCategory.PROFILES: "creator_commercial_profiles",
    ExportCategory.RATES: "creator_rate_history",
    ExportCategory.NEGOTIATIONS: "creator_negotiations",
    ExportCategory.PERFORMANCE: "campaign_performance_records",
    ExportCategory.EVIDENCE: "campaign_evidence_records",
    ExportCategory.CORRECTIONS: "commercial_correction_proposals",
    ExportCategory.AUDIT: "activity_logs",
}


class CommercialHardeningService:
    def __init__(self, database, storage: EvidenceStorage, retention: RetentionPolicy | None = None):
        self.db = database
        self.storage = storage
        self.retention = retention or RetentionPolicy.from_env()
        self.repository = HardeningRepository(database)
        self.commercial_repository = CommercialRepository(database)
        self.commercial = CommercialService(database)

    async def upload_evidence(self, user: dict, performance_id: str, metadata: EvidenceMetadataInput,
                              validated: ValidatedEvidenceFile) -> CampaignEvidenceRecord:
        performance = await self.commercial._owned_performance(user, performance_id)
        allowed = _EVIDENCE_METRIC_ALLOWLIST[metadata.evidence_type]
        unsupported = set(metadata.supported_metrics) - allowed
        if unsupported:
            raise HTTPException(status_code=422, detail="Evidence type cannot support one or more requested metrics")
        self._validate_evidence_period(metadata, performance)
        duplicate = await self.repository.duplicate_evidence(
            performance["tenant_id"], performance_id, validated.checksum_sha256,
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Duplicate evidence content already exists for this performance record")
        now = _now()
        storage_key = await self.storage.save(validated.data, validated.extension)
        warnings = []
        if metadata.evidence_type == EvidenceType.ANALYTICS_SCREENSHOT:
            warnings.append("Screenshots require explicit review and remain limited evidence for metric verification.")
        document = {
            "tenant_id": performance["tenant_id"],
            "campaign_performance_record_id": performance_id,
            "campaign_id": performance.get("campaign_id"),
            "platform": performance["platform"], "platform_id": performance["platform_id"],
            "evidence_type": metadata.evidence_type.value, "source_type": metadata.source_type.value,
            "original_filename": validated.display_filename, "safe_filename": validated.safe_filename,
            "storage_key": storage_key, "mime_type": validated.mime_type,
            "size_bytes": validated.size_bytes, "checksum_sha256": validated.checksum_sha256,
            "evidence_status": EvidenceStatus.ACTIVE.value,
            "verification_status": EvidenceVerificationStatus.UNVERIFIED.value,
            "supported_metrics": [metric.value for metric in metadata.supported_metrics],
            "measurement_period_start": metadata.measurement_period_start,
            "measurement_period_end": metadata.measurement_period_end,
            "captured_at": metadata.captured_at, "internal_notes": metadata.internal_notes,
            "submitted_at": now, "submitted_by": str(user["_id"]),
            "verified_at": None, "verified_by": None, "review_reason": None,
            "created_at": now, "updated_at": now, "deleted_at": None, "deleted_by": None,
            "deletion_reason": None,
            "retention_expires_at": self.retention.expiry("evidence_metadata", now),
            "file_retention_expires_at": self.retention.expiry("evidence_file", now),
            "warnings": warnings,
        }
        try:
            evidence = await self.repository.create_evidence(document)
        except Exception:
            await self.storage.mark_deleted(storage_key)
            raise
        await self._audit(user, performance["tenant_id"], "campaign_evidence.upload",
                          "campaign_evidence", str(evidence["_id"]), list(document))
        return self._evidence_public(evidence)

    async def list_evidence(self, user: dict, performance_id: str, limit: int) -> list[CampaignEvidenceRecord]:
        await self.commercial._owned_performance(user, performance_id)
        records = await self.repository.list_evidence(performance_id, tenant_scope(user), limit=limit)
        return [self._evidence_public(item) for item in records if not _expired(item.get("retention_expires_at"))]

    async def get_evidence(self, user: dict, evidence_id: str) -> CampaignEvidenceRecord:
        evidence = await self._owned_evidence(user, evidence_id)
        self._ensure_evidence_available(evidence)
        return self._evidence_public(evidence)

    async def verify_evidence(self, user: dict, evidence_id: str,
                              action: EvidenceReviewAction) -> CampaignEvidenceRecord:
        self._require_reviewer(user)
        evidence = await self._owned_evidence(user, evidence_id)
        self._ensure_evidence_available(evidence)
        if evidence["verification_status"] != EvidenceVerificationStatus.UNVERIFIED.value:
            raise HTTPException(status_code=409, detail="Evidence is not in a reviewable state")
        now = _now()
        updated = await self.repository.transition_evidence(evidence, "unverified", {
            "verification_status": "verified", "verified_at": now, "verified_by": str(user["_id"]),
            "review_reason": action.reason, "updated_at": now,
        })
        if not updated:
            raise HTTPException(status_code=409, detail="Evidence state changed during review")
        await self._audit(user, evidence["tenant_id"], "campaign_evidence.verify",
                          "campaign_evidence", evidence_id, ["verification_status", "verified_at"])
        return self._evidence_public(updated)

    async def reject_evidence(self, user: dict, evidence_id: str,
                              action: EvidenceRejectAction) -> CampaignEvidenceRecord:
        self._require_reviewer(user)
        evidence = await self._owned_evidence(user, evidence_id)
        self._ensure_evidence_available(evidence)
        if evidence["verification_status"] != EvidenceVerificationStatus.UNVERIFIED.value:
            raise HTTPException(status_code=409, detail="Evidence is not in a reviewable state")
        now = _now()
        updated = await self.repository.transition_evidence(evidence, "unverified", {
            "verification_status": "rejected", "verified_at": now, "verified_by": str(user["_id"]),
            "review_reason": action.reason, "updated_at": now,
        })
        if not updated:
            raise HTTPException(status_code=409, detail="Evidence state changed during review")
        await self._audit(user, evidence["tenant_id"], "campaign_evidence.reject",
                          "campaign_evidence", evidence_id, ["verification_status", "verified_at"])
        return self._evidence_public(updated)

    async def supersede_evidence(self, user: dict, evidence_id: str,
                                 action: EvidenceSupersedeAction) -> CampaignEvidenceRecord:
        self._require_reviewer(user)
        evidence = await self._owned_evidence(user, evidence_id)
        replacement = await self._owned_evidence(user, action.replacement_evidence_id)
        self._ensure_evidence_available(evidence)
        self._ensure_evidence_available(replacement)
        if evidence_id == action.replacement_evidence_id:
            raise HTTPException(status_code=422, detail="Evidence cannot supersede itself")
        if evidence["tenant_id"] != replacement["tenant_id"] or evidence["campaign_performance_record_id"] != replacement["campaign_performance_record_id"]:
            raise HTTPException(status_code=422, detail="Replacement evidence must belong to the same performance record")
        if evidence["verification_status"] != "verified" or replacement["verification_status"] != "verified":
            raise HTTPException(status_code=409, detail="Both evidence records must be verified before superseding")
        updated = await self.repository.transition_evidence(evidence, "verified", {
            "verification_status": "superseded", "superseded_by_evidence_id": action.replacement_evidence_id,
            "review_reason": action.reason, "updated_at": _now(),
        })
        if not updated:
            raise HTTPException(status_code=409, detail="Evidence state changed during supersede review")
        await self._audit(user, evidence["tenant_id"], "campaign_evidence.supersede",
                          "campaign_evidence", evidence_id, ["verification_status", "superseded_by_evidence_id"])
        return self._evidence_public(updated)

    async def delete_evidence(self, user: dict, evidence_id: str,
                              action: SoftDeleteAction) -> CampaignEvidenceRecord:
        evidence = await self._owned_evidence(user, evidence_id)
        if evidence["verification_status"] == "verified" and user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Verified evidence requires admin deletion review")
        now = _now()
        updated = await self.repository.soft_delete_evidence(evidence, {
            "deleted_at": now, "deleted_by": str(user["_id"]), "deletion_reason": action.reason,
            "evidence_status": "deleted", "updated_at": now,
        })
        await self.storage.mark_deleted(evidence["storage_key"])
        await self._audit(user, evidence["tenant_id"], "campaign_evidence.soft_delete",
                          "campaign_evidence", evidence_id, ["deleted_at", "evidence_status"])
        return self._evidence_public(updated)

    async def restore_evidence(self, user: dict, evidence_id: str) -> CampaignEvidenceRecord:
        evidence = await self._owned_evidence(user, evidence_id, include_deleted=True)
        if evidence.get("deleted_at") is None:
            raise HTTPException(status_code=409, detail="Evidence is not deleted")
        if evidence["verification_status"] == "verified" and user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Verified evidence requires admin restore review")
        if _expired(evidence.get("retention_expires_at")):
            raise HTTPException(status_code=410, detail="Expired evidence cannot be restored")
        if _expired(evidence.get("file_retention_expires_at")):
            raise HTTPException(status_code=410, detail="Expired evidence file cannot be restored")
        if not await self.storage.exists(evidence["storage_key"]):
            raise HTTPException(status_code=410, detail="Evidence file is unavailable")
        updated = await self.repository.restore_evidence(evidence, {
            "deleted_at": None, "deleted_by": None, "deletion_reason": None,
            "evidence_status": "active", "updated_at": _now(),
        })
        await self._audit(user, evidence["tenant_id"], "campaign_evidence.restore",
                          "campaign_evidence", evidence_id, ["deleted_at", "evidence_status"])
        return self._evidence_public(updated)

    async def download_evidence(self, user: dict, evidence_id: str) -> tuple[bytes, str, str]:
        evidence = await self._owned_evidence(user, evidence_id)
        self._ensure_evidence_file_available(evidence)
        if not await self.storage.exists(evidence["storage_key"]):
            raise HTTPException(status_code=410, detail="Evidence file is unavailable")
        data = await self.storage.read(evidence["storage_key"])
        await self._audit(user, evidence["tenant_id"], "campaign_evidence.download",
                          "campaign_evidence", evidence_id, [])
        return data, evidence["mime_type"], evidence["safe_filename"]

    async def create_correction(self, user: dict, record_id: str,
                                payload: CorrectionProposalCreate) -> CorrectionProposal:
        performance = await self.commercial._owned_performance(user, record_id)
        current_version = int(performance.get("version", 1))
        if payload.base_version != current_version:
            raise HTTPException(status_code=409, detail="Correction base version is stale")
        changes = payload.proposed_changes.model_dump(exclude_unset=True, mode="python")
        self._validate_correction_period(performance, changes)
        now = _now()
        document = {
            "tenant_id": performance["tenant_id"], "record_type": "campaign_performance",
            "record_id": record_id, "base_version": payload.base_version,
            "proposed_changes": _enum_values(changes), "proposed_fields": sorted(changes),
            "reason": payload.reason, "internal_notes": payload.internal_notes,
            "status": CorrectionStatus.PENDING.value, "submitted_by": str(user["_id"]),
            "submitted_at": now, "reviewed_by": None, "reviewed_at": None,
            "review_reason": None, "approved_version_id": None,
            "retention_expires_at": self.retention.expiry("correction_proposal", now),
            "created_at": now,
        }
        proposal = await self.repository.create_correction(document)
        await self._audit(user, performance["tenant_id"], "commercial_correction.submit",
                          "commercial_correction", str(proposal["_id"]), list(document))
        return self._correction_public(proposal)

    async def list_corrections(self, user: dict, record_id: str, limit: int) -> list[CorrectionProposal]:
        await self.commercial._owned_performance(user, record_id)
        records = await self.repository.list_corrections(record_id, tenant_scope(user), limit)
        return [self._correction_public(item) for item in records]

    async def get_correction(self, user: dict, correction_id: str) -> CorrectionProposal:
        proposal = await self._owned_correction(user, correction_id)
        return self._correction_public(proposal)

    async def approve_correction(self, user: dict, correction_id: str,
                                 action: CorrectionReviewAction) -> CorrectionProposal:
        self._require_reviewer(user)
        proposal = await self._owned_correction(user, correction_id)
        if proposal["status"] != "pending":
            raise HTTPException(status_code=409, detail="Correction is not pending")
        performance = await self.commercial.repository.get_performance(proposal["record_id"], None)
        if not performance or performance["tenant_id"] != proposal["tenant_id"]:
            raise HTTPException(status_code=404, detail="Correction target not found")
        if int(performance.get("version", 1)) != proposal["base_version"]:
            raise HTTPException(status_code=409, detail="Correction base version is stale")
        changes = dict(proposal["proposed_changes"])
        changes["warnings"] = _deliverable_warnings(
            changes.get("deliverables_committed", performance.get("deliverables_committed")),
            changes.get("deliverables_completed", performance.get("deliverables_completed")),
        )
        decided = await self.repository.approve_correction(
            proposal, performance, changes, str(user["_id"]), _now(), action.reason,
        )
        if not decided:
            raise HTTPException(status_code=409, detail="Correction state or base version changed")
        updated_proposal, _ = decided
        await self._audit(user, proposal["tenant_id"], "commercial_correction.approve",
                          "commercial_correction", correction_id, ["status", "approved_version_id"])
        return self._correction_public(updated_proposal)

    async def reject_correction(self, user: dict, correction_id: str,
                                action: CorrectionReviewAction) -> CorrectionProposal:
        self._require_reviewer(user)
        return await self._decide_correction(user, correction_id, "rejected", action.reason)

    async def cancel_correction(self, user: dict, correction_id: str,
                                action: CorrectionReviewAction) -> CorrectionProposal:
        proposal = await self._owned_correction(user, correction_id)
        if user.get("role") != "admin" and str(proposal.get("submitted_by")) != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Only the submitter can cancel this correction")
        return await self._decide_correction(user, correction_id, "cancelled", action.reason, proposal)

    async def create_export(self, user: dict, payload: TenantExportRequest) -> TenantExportArtifact:
        require_commercial_role(user)
        tenant_id = write_tenant(user)
        datasets: dict[str, list[dict]] = {}
        for category in payload.record_categories:
            rows = await self.repository.export_rows(
                _EXPORT_COLLECTIONS[category], tenant_id, payload.date_from, payload.date_to,
                payload.row_limit, payload.include_deleted,
            )
            datasets[category.value] = [
                _redact_export_row(row, payload.include_private_notes) for row in rows
            ]
        now = _now()
        manifest = {
            "schema_version": "1.0", "exported_at": now.isoformat(),
            "date_range": {"from": payload.date_from.isoformat(), "to": payload.date_to.isoformat()},
            "record_categories": [item.value for item in payload.record_categories],
            "redacted_private_notes": not payload.include_private_notes,
            "include_deleted": payload.include_deleted,
            "data": datasets,
        }
        data = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(data) > 2 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Export exceeds the synchronous size limit")
        expires_at = self.retention.expiry("export_artifact", now)
        if expires_at is None:
            raise HTTPException(status_code=503, detail="Export retention must be finite")
        storage_key = await self.storage.save(data, "json")
        document = {
            "tenant_id": tenant_id, "schema_version": "1.0", "format": "json",
            "record_categories": [item.value for item in payload.record_categories],
            "row_counts": {key: len(value) for key, value in datasets.items()},
            "total_rows": sum(len(value) for value in datasets.values()),
            "size_bytes": len(data), "redacted_private_notes": not payload.include_private_notes,
            "include_deleted": payload.include_deleted, "storage_key": storage_key,
            "created_at": now, "created_by": str(user["_id"]), "expires_at": expires_at,
            "deleted_at": None, "deleted_by": None, "deletion_reason": None,
        }
        try:
            artifact = await self.repository.create_export(document)
        except Exception:
            await self.storage.mark_deleted(storage_key)
            raise
        await self._audit(user, tenant_id, "creator_commercial.export.create",
                          "commercial_export", str(artifact["_id"]), list(document))
        return self._export_public(artifact)

    async def get_export(self, user: dict, export_id: str) -> TenantExportArtifact:
        artifact = await self._owned_export(user, export_id)
        return self._export_public(artifact)

    async def download_export(self, user: dict, export_id: str) -> tuple[bytes, str]:
        artifact = await self._owned_export(user, export_id)
        if _expired(artifact["expires_at"]):
            raise HTTPException(status_code=410, detail="Export artifact has expired")
        if not await self.storage.exists(artifact["storage_key"]):
            raise HTTPException(status_code=410, detail="Export artifact is unavailable")
        data = await self.storage.read(artifact["storage_key"])
        await self._audit(user, artifact["tenant_id"], "creator_commercial.export.download",
                          "commercial_export", export_id, [])
        return data, f"brandkrt-commercial-export-{export_id}.json"

    async def delete_export(self, user: dict, export_id: str,
                            action: SoftDeleteAction) -> TenantExportArtifact:
        artifact = await self._owned_export(user, export_id)
        updated = await self.repository.soft_delete_export(artifact, {
            "deleted_at": _now(), "deleted_by": str(user["_id"]), "deletion_reason": action.reason,
        })
        await self.storage.mark_deleted(artifact["storage_key"])
        await self._audit(user, artifact["tenant_id"], "creator_commercial.export.soft_delete",
                          "commercial_export", export_id, ["deleted_at"])
        return self._export_public(updated)

    async def audit_events(self, user: dict, start: datetime, end: datetime, limit: int,
                           record_type: str | None, record_id: str | None,
                           action: str | None) -> list[AuditReviewEvent]:
        require_commercial_role(user)
        if start.tzinfo is None or end.tzinfo is None or start > end or end - start > timedelta(days=366):
            raise HTTPException(status_code=422, detail="Audit date range must be ordered, timezone-aware, and at most 366 days")
        records = await self.repository.audit_events(
            tenant_scope(user), start, end, limit, record_type, record_id, action,
        )
        return [AuditReviewEvent(
            id=str(item["_id"]), action=item.get("action", "unknown"),
            record_type=item.get("entity", "unknown"), record_id=item.get("entity_id"),
            changed_fields=sorted(set((item.get("meta") or {}).get("changed_fields", [])))[:100],
            actor_category=item.get("actor_category", "unknown") if item.get("actor_category") in {"brand", "admin", "system"} else "unknown",
            created_at=_aware(item["created_at"]),
        ) for item in records]

    async def evaluate_retention(self, user: dict) -> RetentionEvaluationResult:
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Retention evaluation requires admin role")
        now = _now()
        evidence_count, export_count, already, changed = await self.repository.evaluate_retention(
            now, str(user["_id"]),
        )
        for item in changed:
            await self._audit(user, item["tenant_id"], "commercial_retention.expire",
                              item["type"], item["id"], ["deleted_at"])
        return RetentionEvaluationResult(
            evaluated_at=now, evidence_marked_expired=evidence_count,
            exports_marked_expired=export_count, already_expired=already,
        )

    async def evidence_for_performance(self, tenant_id: str, performance_id: str) -> list[dict]:
        return await self.repository.active_evidence_for_performance(tenant_id, performance_id)

    def _validate_evidence_period(self, metadata: EvidenceMetadataInput, performance: dict) -> None:
        if metadata.measurement_period_start is None and metadata.measurement_period_end is None:
            return
        start = metadata.measurement_period_start or metadata.measurement_period_end
        end = metadata.measurement_period_end or metadata.measurement_period_start
        performance_start = _aware(performance["measurement_period_start"])
        performance_end = _aware(performance["measurement_period_end"])
        if end < performance_start or start > performance_end:
            raise HTTPException(status_code=422, detail="Evidence period does not overlap campaign measurement period")

    def _validate_correction_period(self, performance: dict, changes: dict) -> None:
        start = changes.get("measurement_period_start", performance["measurement_period_start"])
        end = changes.get("measurement_period_end", performance["measurement_period_end"])
        if start > end:
            raise HTTPException(status_code=422, detail="Correction measurement period is invalid")

    async def _owned_evidence(self, user: dict, evidence_id: str,
                              include_deleted: bool = False) -> dict:
        require_commercial_role(user)
        try:
            evidence = await self.repository.get_evidence(evidence_id, tenant_scope(user), include_deleted)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid evidence id") from None
        if not evidence:
            raise HTTPException(status_code=404, detail="Evidence not found")
        return evidence

    async def _owned_correction(self, user: dict, correction_id: str) -> dict:
        require_commercial_role(user)
        try:
            proposal = await self.repository.get_correction(correction_id, tenant_scope(user))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid correction id") from None
        if not proposal:
            raise HTTPException(status_code=404, detail="Correction proposal not found")
        return proposal

    async def _owned_export(self, user: dict, export_id: str) -> dict:
        require_commercial_role(user)
        try:
            artifact = await self.repository.get_export(export_id, tenant_scope(user))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid export id") from None
        if not artifact:
            raise HTTPException(status_code=404, detail="Export artifact not found")
        return artifact

    def _ensure_evidence_available(self, evidence: dict) -> None:
        if evidence.get("deleted_at") is not None or evidence.get("evidence_status") == "deleted":
            raise HTTPException(status_code=404, detail="Evidence not found")
        if _expired(evidence.get("retention_expires_at")):
            raise HTTPException(status_code=410, detail="Evidence has expired")

    def _ensure_evidence_file_available(self, evidence: dict) -> None:
        self._ensure_evidence_available(evidence)
        if _expired(evidence.get("file_retention_expires_at")):
            raise HTTPException(status_code=410, detail="Evidence file has expired")

    def _require_reviewer(self, user: dict) -> None:
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Evidence and correction review requires admin role")

    async def _decide_correction(self, user: dict, correction_id: str, status: str,
                                 reason: str, proposal: dict | None = None) -> CorrectionProposal:
        proposal = proposal or await self._owned_correction(user, correction_id)
        if proposal["status"] != "pending":
            raise HTTPException(status_code=409, detail="Correction is not pending")
        updated = await self.repository.decide_correction(proposal, status, {
            "reviewed_at": _now(), "reviewed_by": str(user["_id"]), "review_reason": reason,
        })
        if not updated:
            raise HTTPException(status_code=409, detail="Correction state changed")
        await self._audit(user, proposal["tenant_id"], f"commercial_correction.{status}",
                          "commercial_correction", correction_id, ["status"])
        return self._correction_public(updated)

    async def _audit(self, user: dict, tenant_id: str, action: str, record_type: str,
                     record_id: str, changed_fields: list[str]) -> None:
        await self.commercial_repository.audit(
            str(user["_id"]), action, record_type, record_id, changed_fields,
            tenant_id=tenant_id, actor_category=user.get("role", "unknown"),
        )

    def _evidence_public(self, evidence: dict) -> CampaignEvidenceRecord:
        expired = _expired(evidence.get("retention_expires_at"))
        file_expired = _expired(evidence.get("file_retention_expires_at"))
        deleted = evidence.get("deleted_at") is not None or evidence.get("evidence_status") == "deleted"
        retention_status = "deleted" if deleted else ("expired" if expired else (
            "indefinite" if evidence.get("retention_expires_at") is None else "active"
        ))
        review_message = evidence.get("review_reason") if evidence.get("verification_status") == "rejected" else None
        return CampaignEvidenceRecord(
            id=str(evidence["_id"]),
            campaign_performance_record_id=evidence["campaign_performance_record_id"],
            campaign_id=evidence.get("campaign_id"), platform=evidence["platform"],
            platform_id=evidence["platform_id"], evidence_type=evidence["evidence_type"],
            source_type=evidence["source_type"], display_filename=evidence["original_filename"],
            mime_type=evidence["mime_type"], size_bytes=evidence["size_bytes"], checksum_present=True,
            evidence_status=evidence["evidence_status"], verification_status=evidence["verification_status"],
            supported_metrics=evidence.get("supported_metrics", []),
            measurement_period_start=_maybe_aware(evidence.get("measurement_period_start")),
            measurement_period_end=_maybe_aware(evidence.get("measurement_period_end")),
            captured_at=_maybe_aware(evidence.get("captured_at")),
            submitted_at=_aware(evidence["submitted_at"]), verified_at=_maybe_aware(evidence.get("verified_at")),
            review_message=review_message, retention_expires_at=_maybe_aware(evidence.get("retention_expires_at")),
            retention_status=retention_status, download_available=not deleted and not expired and not file_expired,
            warnings=evidence.get("warnings", []),
        )

    def _correction_public(self, proposal: dict) -> CorrectionProposal:
        return CorrectionProposal(
            id=str(proposal["_id"]), record_type="campaign_performance",
            record_id=proposal["record_id"], base_version=proposal["base_version"],
            proposed_changes=proposal["proposed_changes"], proposed_fields=proposal["proposed_fields"],
            reason=proposal["reason"], status=proposal["status"],
            submitted_at=_aware(proposal["submitted_at"]), reviewed_at=_maybe_aware(proposal.get("reviewed_at")),
            review_message=proposal.get("review_reason"), approved_version_id=proposal.get("approved_version_id"),
            retention_expires_at=_maybe_aware(proposal.get("retention_expires_at")),
        )

    def _export_public(self, artifact: dict) -> TenantExportArtifact:
        deleted = artifact.get("deleted_at") is not None
        expired = _expired(artifact.get("expires_at"))
        status = "deleted" if deleted else ("expired" if expired else "ready")
        return TenantExportArtifact(
            id=str(artifact["_id"]), schema_version="1.0", format="json",
            record_categories=artifact["record_categories"], row_counts=artifact["row_counts"],
            total_rows=artifact["total_rows"], size_bytes=artifact["size_bytes"],
            redacted_private_notes=artifact["redacted_private_notes"],
            include_deleted=artifact["include_deleted"], created_at=_aware(artifact["created_at"]),
            expires_at=_aware(artifact["expires_at"]), status=status,
            download_available=not deleted and not expired,
        )


def metric_evidence_statuses(performance: dict, evidence_records: list[dict]) -> tuple[list[MetricEvidenceStatus], float]:
    metric_values = {
        "agreed_cost": performance.get("agreed_cost"),
        "deliverables": performance.get("deliverables_completed"),
        "observed_reach": performance.get("observed_reach"), "observed_views": performance.get("observed_views"),
        "observed_impressions": performance.get("observed_impressions"), "observed_likes": performance.get("observed_likes"),
        "observed_comments": performance.get("observed_comments"), "observed_shares": performance.get("observed_shares"),
        "observed_clicks": performance.get("observed_clicks"), "observed_conversions": performance.get("observed_conversions"),
        "revenue": performance.get("revenue"),
    }
    summaries: list[MetricEvidenceStatus] = []
    confidence_values = []
    for metric, value in metric_values.items():
        if value is None:
            summaries.append(MetricEvidenceStatus(
                metric=metric, observation_status="unavailable", evidence_status="missing",
                verification_level="none", confidence_note="The observed metric is unavailable.",
            ))
            continue
        candidates = [item for item in evidence_records if metric in item.get("supported_metrics", [])]
        active = [item for item in candidates if item.get("deleted_at") is None and item.get("evidence_status") == "active"]
        verified = [item for item in active if item.get("verification_status") == "verified"]
        unverified = [item for item in active if item.get("verification_status") == "unverified"]
        rejected = [item for item in active if item.get("verification_status") == "rejected"]
        authoritative = [item for item in verified if item.get("evidence_type") != "analytics_screenshot"]
        if authoritative:
            ids = [str(item["_id"]) for item in authoritative[:20]]
            summaries.append(MetricEvidenceStatus(
                metric=metric, observation_status="verified", evidence_status="verified",
                supporting_evidence_ids=ids, verification_level="reviewed",
                confidence_note="The supplied observation has explicitly reviewed, metric-mapped evidence.",
            ))
            confidence_values.append(1.0)
        elif verified:
            ids = [str(item["_id"]) for item in verified[:20]]
            summaries.append(MetricEvidenceStatus(
                metric=metric, observation_status="unverified", evidence_status="verified",
                supporting_evidence_ids=ids, verification_level="reviewed_limited",
                confidence_note="Reviewed screenshot evidence is limited and does not independently verify the metric.",
            ))
            confidence_values.append(0.6)
        elif unverified:
            ids = [str(item["_id"]) for item in unverified[:20]]
            summaries.append(MetricEvidenceStatus(
                metric=metric, observation_status="unverified", evidence_status="unverified",
                supporting_evidence_ids=ids, verification_level="unreviewed",
                confidence_note="The observation has metric-mapped evidence that has not been reviewed.",
            ))
            confidence_values.append(0.4)
        elif rejected:
            summaries.append(MetricEvidenceStatus(
                metric=metric, observation_status="unverified", evidence_status="rejected",
                verification_level="none", confidence_note="Rejected evidence is excluded from attribution support.",
            ))
            confidence_values.append(0.2)
        else:
            summaries.append(MetricEvidenceStatus(
                metric=metric, observation_status="unverified", evidence_status="missing",
                verification_level="none", confidence_note="No active metric-mapped evidence supports this observation.",
            ))
            confidence_values.append(0.2)
    return summaries, round(fmean(confidence_values), 4) if confidence_values else 0.0


_EXPORT_FORBIDDEN_FIELDS = {
    "tenant_id", "created_by", "updated_by", "submitted_by", "verified_by", "reviewed_by",
    "deleted_by", "storage_key", "checksum_sha256", "password", "password_hash", "token",
    "access_token", "refresh_token", "api_key", "client_secret", "credentials", "previous", "meta",
    "raw_prompt", "raw_response", "prompt_messages", "provider_response",
}
_EXPORT_NOTE_FIELDS = {
    "notes", "pricing_notes", "internal_notes", "review_notes", "review_reason", "deletion_reason",
}


def _redact_export_row(row: dict, include_private_notes: bool) -> dict:
    return _redact_export_value(row, include_private_notes)


def _redact_export_value(value: Any, include_private_notes: bool):
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            normalized_key = str(key).casefold()
            if normalized_key in _EXPORT_FORBIDDEN_FIELDS:
                continue
            if normalized_key in _EXPORT_NOTE_FIELDS and not include_private_notes:
                continue
            output["id" if key == "_id" else str(key)] = _redact_export_value(item, include_private_notes)
        return output
    if isinstance(value, list):
        return [_redact_export_value(item, include_private_notes) for item in value]
    return _json_safe(value)


def _json_safe(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return _aware(value).isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _enum_values(value):
    return _json_safe(value)


def _expired(value: datetime | None) -> bool:
    return value is not None and _aware(value) <= _now()


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _maybe_aware(value: datetime | None) -> datetime | None:
    return None if value is None else _aware(value)


def _now() -> datetime:
    return datetime.now(timezone.utc)
