"""Protected evidence, correction, export, retention, and audit routes."""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
from typing import Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile

import security

from .evidence_storage import EvidenceStorage, LocalPrivateEvidenceStorage
from .evidence_validation import evidence_max_bytes, validate_evidence_file
from .hardening_models import (
    AuditReviewEvent, CampaignEvidenceRecord, CorrectionProposal, CorrectionProposalCreate,
    CorrectionReviewAction, EvidenceMetadataInput, EvidenceRejectAction, EvidenceReviewAction,
    EvidenceSupersedeAction,
    RetentionEvaluationResult, SoftDeleteAction, TenantExportArtifact, TenantExportRequest,
)
from .hardening_service import CommercialHardeningService


@lru_cache(maxsize=1)
def get_evidence_storage() -> EvidenceStorage:
    return LocalPrivateEvidenceStorage()


def create_hardening_routers(get_current_user: Callable, database_provider: Callable):
    performance = APIRouter(prefix="/campaign-performance", tags=["campaign-evidence"])
    evidence = APIRouter(prefix="/campaign-evidence", tags=["campaign-evidence"])
    corrections = APIRouter(prefix="/commercial-corrections", tags=["commercial-corrections"])
    commercial = APIRouter(prefix="/creator-commercial", tags=["creator-commercial-hardening"])

    def service(storage: EvidenceStorage = Depends(get_evidence_storage)) -> CommercialHardeningService:
        return CommercialHardeningService(database_provider(), storage)

    read_limit = security.limiter_dependency("commercial_hardening_read", limit=120, window=60)
    write_limit = security.limiter_dependency("commercial_hardening_write", limit=30, window=60)

    @performance.post("/{record_id}/evidence", response_model=CampaignEvidenceRecord, status_code=201)
    async def upload_evidence(
        record_id: str,
        evidence_type: str = Form(...), source_type: str = Form(...),
        supported_metrics: str = Form("[]"),
        measurement_period_start: datetime | None = Form(None),
        measurement_period_end: datetime | None = Form(None),
        captured_at: datetime | None = Form(None),
        internal_notes: str = Form("[]"),
        file: UploadFile = File(...),
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        try:
            metric_values = json.loads(supported_metrics)
            note_values = json.loads(internal_notes)
            metadata = EvidenceMetadataInput(
                evidence_type=evidence_type, source_type=source_type,
                supported_metrics=metric_values,
                measurement_period_start=measurement_period_start,
                measurement_period_end=measurement_period_end, captured_at=captured_at,
                internal_notes=note_values,
            )
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid evidence metadata") from None
        data = await file.read(evidence_max_bytes() + 1)
        await file.close()
        validated = validate_evidence_file(data, file.filename or "", file.content_type or "")
        return await manager.upload_evidence(user, record_id, metadata, validated)

    @performance.get("/{record_id}/evidence", response_model=list[CampaignEvidenceRecord])
    async def list_evidence(
        record_id: str, limit: int = Query(default=50, ge=1, le=100),
        user: dict = Depends(get_current_user), _limit: None = Depends(read_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.list_evidence(user, record_id, limit)

    @performance.post("/{record_id}/corrections", response_model=CorrectionProposal, status_code=201)
    async def create_correction(
        record_id: str, payload: CorrectionProposalCreate,
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.create_correction(user, record_id, payload)

    @performance.get("/{record_id}/corrections", response_model=list[CorrectionProposal])
    async def list_corrections(
        record_id: str, limit: int = Query(default=50, ge=1, le=100),
        user: dict = Depends(get_current_user), _limit: None = Depends(read_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.list_corrections(user, record_id, limit)

    @evidence.get("/{evidence_id}", response_model=CampaignEvidenceRecord)
    async def get_evidence(
        evidence_id: str, user: dict = Depends(get_current_user), _limit: None = Depends(read_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.get_evidence(user, evidence_id)

    @evidence.get("/{evidence_id}/download")
    async def download_evidence(
        evidence_id: str, user: dict = Depends(get_current_user), _limit: None = Depends(read_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        data, mime_type, filename = await manager.download_evidence(user, evidence_id)
        return Response(
            content=data, media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"},
        )

    @evidence.post("/{evidence_id}/verify", response_model=CampaignEvidenceRecord)
    async def verify_evidence(
        evidence_id: str, payload: EvidenceReviewAction,
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.verify_evidence(user, evidence_id, payload)

    @evidence.post("/{evidence_id}/reject", response_model=CampaignEvidenceRecord)
    async def reject_evidence(
        evidence_id: str, payload: EvidenceRejectAction,
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.reject_evidence(user, evidence_id, payload)

    @evidence.post("/{evidence_id}/supersede", response_model=CampaignEvidenceRecord)
    async def supersede_evidence(
        evidence_id: str, payload: EvidenceSupersedeAction,
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.supersede_evidence(user, evidence_id, payload)

    @evidence.delete("/{evidence_id}", response_model=CampaignEvidenceRecord)
    async def delete_evidence(
        evidence_id: str, payload: SoftDeleteAction,
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.delete_evidence(user, evidence_id, payload)

    @evidence.post("/{evidence_id}/restore", response_model=CampaignEvidenceRecord)
    async def restore_evidence(
        evidence_id: str, user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.restore_evidence(user, evidence_id)

    @corrections.get("/{correction_id}", response_model=CorrectionProposal)
    async def get_correction(
        correction_id: str, user: dict = Depends(get_current_user), _limit: None = Depends(read_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.get_correction(user, correction_id)

    @corrections.post("/{correction_id}/approve", response_model=CorrectionProposal)
    async def approve_correction(
        correction_id: str, payload: CorrectionReviewAction,
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.approve_correction(user, correction_id, payload)

    @corrections.post("/{correction_id}/reject", response_model=CorrectionProposal)
    async def reject_correction(
        correction_id: str, payload: CorrectionReviewAction,
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.reject_correction(user, correction_id, payload)

    @corrections.post("/{correction_id}/cancel", response_model=CorrectionProposal)
    async def cancel_correction(
        correction_id: str, payload: CorrectionReviewAction,
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.cancel_correction(user, correction_id, payload)

    @commercial.post("/exports", response_model=TenantExportArtifact, status_code=201)
    async def create_export(
        payload: TenantExportRequest,
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.create_export(user, payload)

    @commercial.get("/exports/{export_id}", response_model=TenantExportArtifact)
    async def get_export(
        export_id: str, user: dict = Depends(get_current_user), _limit: None = Depends(read_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.get_export(user, export_id)

    @commercial.get("/exports/{export_id}/download")
    async def download_export(
        export_id: str, user: dict = Depends(get_current_user), _limit: None = Depends(read_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        data, filename = await manager.download_export(user, export_id)
        return Response(
            content=data, media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"},
        )

    @commercial.delete("/exports/{export_id}", response_model=TenantExportArtifact)
    async def delete_export(
        export_id: str, payload: SoftDeleteAction,
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.delete_export(user, export_id, payload)

    @commercial.get("/audit-events", response_model=list[AuditReviewEvent])
    async def audit_events(
        start: datetime | None = None, end: datetime | None = None,
        limit: int = Query(default=100, ge=1, le=200),
        record_type: str | None = Query(default=None, max_length=100),
        record_id: str | None = Query(default=None, max_length=100),
        action: str | None = Query(default=None, max_length=120),
        user: dict = Depends(get_current_user), _limit: None = Depends(read_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        end_value = end or datetime.now(timezone.utc)
        start_value = start or end_value - timedelta(days=90)
        return await manager.audit_events(user, start_value, end_value, limit, record_type, record_id, action)

    @commercial.post("/retention/evaluate", response_model=RetentionEvaluationResult)
    async def evaluate_retention(
        user: dict = Depends(get_current_user), _limit: None = Depends(write_limit),
        manager: CommercialHardeningService = Depends(service),
    ):
        return await manager.evaluate_retention(user)

    return performance, evidence, corrections, commercial
