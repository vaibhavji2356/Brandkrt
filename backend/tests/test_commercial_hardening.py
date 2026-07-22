import asyncio
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import httpx
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import security
import server
from commercial_intelligence.evidence_storage import InMemoryEvidenceStorage, LocalPrivateEvidenceStorage
from commercial_intelligence.evidence_validation import validate_evidence_file
from commercial_intelligence.hardening_models import (
    CorrectionProposalCreate, CorrectionReviewAction, EvidenceMetadataInput,
    EvidenceRejectAction, EvidenceReviewAction, EvidenceSupersedeAction, SoftDeleteAction,
    TenantExportRequest,
)
from commercial_intelligence.hardening_router import get_evidence_storage
from commercial_intelligence.hardening_service import CommercialHardeningService
from commercial_intelligence.models import CampaignPerformanceCreate, CommercialProfileCreate
from commercial_intelligence.service import CommercialService
from creator_intelligence.engine import CreatorIntelligenceEngine
from creator_intelligence.models import CreatorIntelligenceRequest
from creator_intelligence.narrative_prompting import build_narrative_prompt
from brand_discovery_ai.discovery_schemas import DiscoveryCriteria
from research_agent.agent import ResearchAgent


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"


def run(coro):
    return asyncio.run(coro)


def now():
    return datetime.now(timezone.utc)


def user(role="brand"):
    return {"_id": ObjectId(), "role": role, "email": f"{role}@example.com"}


async def fixture():
    mongo = AsyncMongoMockClient()
    database = mongo["commercial_hardening"]
    storage = InMemoryEvidenceStorage()
    brand = user()
    commercial = CommercialService(database)
    profile = await commercial.create_profile(brand, CommercialProfileCreate(
        platform="instagram", platform_id="evidence-creator", username="creator",
        currency="USD", internal_notes=["private profile note"],
    ))
    brand_doc = {"_id": ObjectId(), "user_id": str(brand["_id"]), "verification_status": "verified"}
    await database.brands.insert_one(brand_doc)
    campaign = {"_id": ObjectId(), "brand_id": str(brand_doc["_id"]), "title": "Evidence campaign"}
    await database.campaigns.insert_one(campaign)
    performance = await commercial.create_performance(brand, CampaignPerformanceCreate(
        campaign_id=str(campaign["_id"]), commercial_profile_id=profile.id,
        objective="Brand Awareness", agreed_cost=500, currency="USD",
        deliverable_type="video", deliverables_committed=2, deliverables_completed=2,
        observed_reach=10000, observed_likes=400, observed_comments=100,
        evidence_status="unverified", measurement_source="brand_report",
        measurement_period_start=now() - timedelta(days=7), measurement_period_end=now(),
        estimated_spend=450, estimated_reach=9000, estimated_engagements=450,
        internal_notes=["private performance note"],
    ))
    return mongo, database, storage, brand, profile, performance, CommercialHardeningService(database, storage)


def metadata(*, evidence_type="platform_export", metrics=None, start=None, end=None):
    return EvidenceMetadataInput(
        evidence_type=evidence_type, source_type="platform_export",
        supported_metrics=metrics or ["observed_reach"],
        measurement_period_start=start, measurement_period_end=end,
        internal_notes=["private evidence note"],
    )


def validated_png(filename="report.png"):
    return validate_evidence_file(PNG_BYTES, filename, "image/png")


def test_evidence_file_validation_rejects_empty_oversized_and_unsupported(monkeypatch):
    with pytest.raises(HTTPException) as empty:
        validate_evidence_file(b"", "empty.png", "image/png")
    assert empty.value.status_code == 400
    monkeypatch.setenv("EVIDENCE_MAX_UPLOAD_MB", "1")
    with pytest.raises(HTTPException) as large:
        validate_evidence_file(b"x" * (1024 * 1024 + 1), "large.pdf", "application/pdf")
    assert large.value.status_code == 413
    with pytest.raises(HTTPException) as unsupported:
        validate_evidence_file(b"<html><script>x</script></html>", "payload.html", "text/html")
    assert unsupported.value.status_code == 415


def test_evidence_file_validation_rejects_mismatch_traversal_double_extension_and_bad_pdf():
    with pytest.raises(HTTPException):
        validate_evidence_file(PNG_BYTES, "image.pdf", "application/pdf")
    with pytest.raises(HTTPException) as traversal:
        validate_evidence_file(PNG_BYTES, "../image.png", "image/png")
    assert traversal.value.status_code == 400
    with pytest.raises(HTTPException) as doubled:
        validate_evidence_file(PNG_BYTES, "proof.exe.png", "image/png")
    assert doubled.value.status_code == 415
    with pytest.raises(HTTPException):
        validate_evidence_file(b"%PDF-1.4\nmissing eof", "bad.pdf", "application/pdf")


def test_evidence_validation_generates_checksum_and_safe_filename():
    result = validate_evidence_file(PNG_BYTES, "Campaign proof (final)!!.png", "image/png")
    assert len(result.checksum_sha256) == 64
    assert result.safe_filename == "Campaign proof _final.png"
    assert result.mime_type == "image/png"
    assert validate_evidence_file(PDF_BYTES, "report.pdf", "application/pdf").mime_type == "application/pdf"


def test_private_local_storage_rejects_traversal_and_does_not_overwrite(tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.setattr("commercial_intelligence.evidence_storage.secrets.token_hex", lambda _: "a" * 48)
        storage = LocalPrivateEvidenceStorage(tmp_path / "private")
        key = await storage.save(PNG_BYTES, "png")
        assert await storage.read(key) == PNG_BYTES
        assert await storage.exists(key) is True
        with pytest.raises(FileExistsError):
            await storage.save(PNG_BYTES, "png")
        with pytest.raises(ValueError):
            await storage.read("../outside.png")
        with pytest.raises(ValueError):
            await storage.read(key.replace("/", "/../", 1))
    run(scenario())


def test_authorized_upload_is_unverified_private_and_duplicate_is_rejected():
    async def scenario():
        mongo, database, storage, brand, _, performance, service = await fixture()
        evidence = await service.upload_evidence(brand, performance.id, metadata(), validated_png())
        dumped = evidence.model_dump()
        assert evidence.verification_status == "unverified"
        assert evidence.checksum_present is True
        assert evidence.download_available is True
        assert "storage_key" not in dumped and "checksum_sha256" not in dumped
        stored = await database.campaign_evidence_records.find_one({"_id": ObjectId(evidence.id)})
        assert stored["storage_key"] in storage.items
        assert storage.items[stored["storage_key"]] == PNG_BYTES
        with pytest.raises(HTTPException) as duplicate:
            await service.upload_evidence(brand, performance.id, metadata(), validated_png("other.png"))
        assert duplicate.value.status_code == 409
        mongo.close()
    run(scenario())


def test_cross_tenant_evidence_attachment_and_read_are_hidden():
    async def scenario():
        mongo, _, _, owner, _, performance, service = await fixture()
        other = user()
        with pytest.raises(HTTPException) as attach:
            await service.upload_evidence(other, performance.id, metadata(), validated_png())
        assert attach.value.status_code == 404
        evidence = await service.upload_evidence(owner, performance.id, metadata(), validated_png())
        with pytest.raises(HTTPException) as read:
            await service.get_evidence(other, evidence.id)
        assert read.value.status_code == 404
        mongo.close()
    run(scenario())


def test_evidence_period_and_metric_mapping_are_validated():
    async def scenario():
        mongo, _, _, brand, _, performance, service = await fixture()
        with pytest.raises(HTTPException) as period:
            await service.upload_evidence(
                brand, performance.id,
                metadata(start=now() - timedelta(days=30), end=now() - timedelta(days=20)),
                validated_png(),
            )
        assert period.value.status_code == 422
        with pytest.raises(HTTPException) as mapping:
            await service.upload_evidence(
                brand, performance.id,
                metadata(evidence_type="deliverable_proof", metrics=["observed_reach"]),
                validated_png(),
            )
        assert mapping.value.status_code == 422
        mongo.close()
    run(scenario())


def test_explicit_verification_supports_only_mapped_metric_and_transition_is_final():
    async def scenario():
        mongo, _, _, brand, _, performance, service = await fixture()
        evidence = await service.upload_evidence(brand, performance.id, metadata(metrics=["observed_reach"]), validated_png())
        admin = user("admin")
        verified = await service.verify_evidence(admin, evidence.id, EvidenceReviewAction(reason="Reviewed platform export"))
        assert verified.verification_status == "verified"
        with pytest.raises(HTTPException) as repeated:
            await service.verify_evidence(admin, evidence.id, EvidenceReviewAction())
        assert repeated.value.status_code == 409
        record = await CommercialService(service.db).get_performance(brand, performance.id)
        statuses = {item.metric: item for item in record.metric_evidence}
        assert statuses["observed_reach"].observation_status == "verified"
        assert statuses["observed_likes"].observation_status == "unverified"
        assert statuses["observed_reach"].supporting_evidence_ids == [evidence.id]
        mongo.close()
    run(scenario())


def test_verified_screenshot_remains_limited_evidence():
    async def scenario():
        mongo, _, _, brand, _, performance, service = await fixture()
        shot = await service.upload_evidence(
            brand, performance.id, metadata(evidence_type="analytics_screenshot"), validated_png(),
        )
        await service.verify_evidence(user("admin"), shot.id, EvidenceReviewAction(reason="Screenshot reviewed"))
        record = await CommercialService(service.db).get_performance(brand, performance.id)
        reach = next(item for item in record.metric_evidence if item.metric == "observed_reach")
        assert reach.observation_status == "unverified"
        assert reach.verification_level == "reviewed_limited"
        mongo.close()
    run(scenario())


def test_verified_evidence_can_be_explicitly_superseded_without_erasing_history():
    async def scenario():
        mongo, database, _, brand, _, performance, service = await fixture()
        first = await service.upload_evidence(brand, performance.id, metadata(), validated_png("first.png"))
        second_file = validate_evidence_file(PDF_BYTES, "second.pdf", "application/pdf")
        second = await service.upload_evidence(brand, performance.id, metadata(), second_file)
        admin = user("admin")
        await service.verify_evidence(admin, first.id, EvidenceReviewAction())
        await service.verify_evidence(admin, second.id, EvidenceReviewAction())
        superseded = await service.supersede_evidence(
            admin, first.id,
            EvidenceSupersedeAction(replacement_evidence_id=second.id, reason="Newer reviewed export"),
        )
        assert superseded.verification_status == "superseded"
        assert await database.campaign_evidence_records.count_documents({}) == 2
        record = await CommercialService(database).get_performance(brand, performance.id)
        reach = next(item for item in record.metric_evidence if item.metric == "observed_reach")
        assert reach.supporting_evidence_ids == [second.id]
        mongo.close()
    run(scenario())


def test_rejected_and_deleted_evidence_do_not_support_attribution():
    async def scenario():
        mongo, _, storage, brand, _, performance, service = await fixture()
        evidence = await service.upload_evidence(brand, performance.id, metadata(), validated_png())
        await service.reject_evidence(user("admin"), evidence.id, EvidenceRejectAction(reason="Metric cannot be confirmed"))
        comparison = await CommercialService(service.db).comparison(brand, performance.id)
        reach = next(item for item in comparison.evidence_summary if item.metric == "observed_reach")
        assert reach.observation_status == "unverified"
        assert reach.supporting_evidence_ids == []
        deleted = await service.delete_evidence(brand, evidence.id, SoftDeleteAction(reason="No longer needed"))
        assert deleted.retention_status == "deleted" and deleted.download_available is False
        with pytest.raises(HTTPException) as unavailable:
            await service.download_evidence(brand, evidence.id)
        assert unavailable.value.status_code == 404
        assert storage.items  # soft deletion does not physically erase bytes
        mongo.close()
    run(scenario())


def test_verified_evidence_requires_admin_delete_and_restore():
    async def scenario():
        mongo, _, _, brand, _, performance, service = await fixture()
        evidence = await service.upload_evidence(brand, performance.id, metadata(), validated_png())
        admin = user("admin")
        await service.verify_evidence(admin, evidence.id, EvidenceReviewAction())
        with pytest.raises(HTTPException) as protected:
            await service.delete_evidence(brand, evidence.id, SoftDeleteAction(reason="Brand deletion"))
        assert protected.value.status_code == 403
        await service.delete_evidence(admin, evidence.id, SoftDeleteAction(reason="Admin reviewed deletion"))
        with pytest.raises(HTTPException):
            await service.restore_evidence(brand, evidence.id)
        restored = await service.restore_evidence(admin, evidence.id)
        assert restored.retention_status == "active"
        mongo.close()
    run(scenario())


def test_correction_proposal_is_immutable_until_admin_approval_and_versions_record():
    async def scenario():
        mongo, database, _, brand, _, performance, service = await fixture()
        proposal = await service.create_correction(brand, performance.id, CorrectionProposalCreate(
            base_version=1, proposed_changes={"observed_reach": 12000},
            reason="Correct platform export", internal_notes=["private correction note"],
        ))
        before = await database.campaign_performance_records.find_one({"_id": ObjectId(performance.id)})
        assert before["observed_reach"] == 10000 and proposal.status == "pending"
        approved = await service.approve_correction(
            user("admin"), proposal.id, CorrectionReviewAction(reason="Evidence supports correction"),
        )
        after = await database.campaign_performance_records.find_one({"_id": ObjectId(performance.id)})
        assert approved.status == "approved"
        assert after["observed_reach"] == 12000 and after["version"] == 2
        version = await database.commercial_record_versions.find_one({"correction_proposal_id": proposal.id})
        assert version["previous"]["observed_reach"] == 10000
        assert await database.commercial_correction_proposals.count_documents({"_id": ObjectId(proposal.id)}) == 1
        mongo.close()
    run(scenario())


def test_correction_reject_cancel_stale_disallowed_and_cross_tenant_rules():
    async def scenario():
        mongo, _, _, brand, _, performance, service = await fixture()
        with pytest.raises(ValueError):
            CorrectionProposalCreate(
                base_version=1, proposed_changes={"currency": "EUR"}, reason="Unsafe currency change",
            )
        stale_payload = CorrectionProposalCreate(
            base_version=2, proposed_changes={"observed_reach": 1}, reason="Stale",
        )
        with pytest.raises(HTTPException) as stale:
            await service.create_correction(brand, performance.id, stale_payload)
        assert stale.value.status_code == 409
        proposal = await service.create_correction(brand, performance.id, CorrectionProposalCreate(
            base_version=1, proposed_changes={"observed_reach": 11000}, reason="Review",
        ))
        other = user()
        with pytest.raises(HTTPException) as hidden:
            await service.get_correction(other, proposal.id)
        assert hidden.value.status_code == 404
        rejected = await service.reject_correction(
            user("admin"), proposal.id, CorrectionReviewAction(reason="Insufficient evidence"),
        )
        assert rejected.status == "rejected"
        second = await service.create_correction(brand, performance.id, CorrectionProposalCreate(
            base_version=1, proposed_changes={"observed_views": 9000}, reason="Cancel me",
        ))
        cancelled = await service.cancel_correction(
            brand, second.id, CorrectionReviewAction(reason="Submitted in error"),
        )
        assert cancelled.status == "cancelled"
        mongo.close()
    run(scenario())


def test_retention_evaluation_is_idempotent_and_does_not_delete_active_items_early():
    async def scenario():
        mongo, database, _, brand, _, performance, service = await fixture()
        active = await service.upload_evidence(brand, performance.id, metadata(), validated_png())
        first = await service.evaluate_retention(user("admin"))
        assert first.evidence_marked_expired == 0
        assert (await database.campaign_evidence_records.find_one({"_id": ObjectId(active.id)}))["deleted_at"] is None
        await database.campaign_evidence_records.update_one(
            {"_id": ObjectId(active.id)}, {"$set": {"retention_expires_at": now() - timedelta(seconds=1)}},
        )
        expired = await service.evaluate_retention(user("admin"))
        repeated = await service.evaluate_retention(user("admin"))
        assert expired.evidence_marked_expired == 1
        assert repeated.evidence_marked_expired == 0 and repeated.already_expired >= 1
        with pytest.raises(HTTPException):
            await service.get_evidence(brand, active.id)
        mongo.close()
    run(scenario())


def test_expired_evidence_file_is_not_downloadable_before_retention_evaluation():
    async def scenario():
        mongo, database, _, brand, _, performance, service = await fixture()
        evidence = await service.upload_evidence(brand, performance.id, metadata(), validated_png())
        await database.campaign_evidence_records.update_one(
            {"_id": ObjectId(evidence.id)},
            {"$set": {"file_retention_expires_at": now() - timedelta(seconds=1)}},
        )
        public = await service.get_evidence(brand, evidence.id)
        assert public.download_available is False
        with pytest.raises(HTTPException) as expired:
            await service.download_evidence(brand, evidence.id)
        assert expired.value.status_code == 410
        mongo.close()
    run(scenario())


def test_tenant_export_is_bounded_redacted_and_does_not_mutate_sources():
    async def scenario():
        mongo, database, storage, brand, _, performance, service = await fixture()
        await service.upload_evidence(brand, performance.id, metadata(), validated_png())
        await database.campaign_performance_records.update_one(
            {"_id": ObjectId(performance.id)},
            {"$set": {"nested_private": {
                "access_token": "never-export-this-token",
                "internal_notes": ["never-export-this-note"],
                "safe_fact": 7,
            }}},
        )
        before = {
            "profiles": await database.creator_commercial_profiles.count_documents({}),
            "performance": await database.campaign_performance_records.count_documents({}),
            "evidence": await database.campaign_evidence_records.count_documents({}),
        }
        export = await service.create_export(brand, TenantExportRequest(
            date_from=now() - timedelta(days=30), date_to=now() + timedelta(minutes=1),
            record_categories=["profiles", "performance", "evidence", "audit"],
        ))
        data, filename = await service.download_export(brand, export.id)
        manifest = json.loads(data)
        serialized = json.dumps(manifest)
        assert export.redacted_private_notes is True and export.download_available is True
        assert filename.endswith(".json") and manifest["schema_version"] == "1.0"
        assert "private profile note" not in serialized
        assert "private performance note" not in serialized
        assert "private evidence note" not in serialized
        assert "tenant_id" not in serialized and "storage_key" not in serialized
        assert "submitted_by" not in serialized and "checksum_sha256" not in serialized
        assert "never-export-this-token" not in serialized and "never-export-this-note" not in serialized
        assert manifest["data"]["performance"][0]["nested_private"]["safe_fact"] == 7
        after = {
            "profiles": await database.creator_commercial_profiles.count_documents({}),
            "performance": await database.campaign_performance_records.count_documents({}),
            "evidence": await database.campaign_evidence_records.count_documents({}),
        }
        assert before == after
        assert any(value.startswith(b"{") for value in storage.items.values())
        mongo.close()
    run(scenario())


def test_export_rejects_csv_and_limits_and_is_tenant_scoped_expiring_and_soft_deletable():
    with pytest.raises(ValueError):
        TenantExportRequest(
            date_from=now() - timedelta(days=1), date_to=now(),
            record_categories=["profiles"], format="csv",
        )
    with pytest.raises(ValueError):
        TenantExportRequest(
            date_from=now() - timedelta(days=367), date_to=now(),
            record_categories=["profiles"],
        )

    async def scenario():
        mongo, database, _, brand, _, _, service = await fixture()
        artifact = await service.create_export(brand, TenantExportRequest(
            date_from=now() - timedelta(days=30), date_to=now() + timedelta(minutes=1),
            record_categories=["profiles"], row_limit=10,
        ))
        with pytest.raises(HTTPException) as hidden:
            await service.get_export(user(), artifact.id)
        assert hidden.value.status_code == 404
        await database.commercial_export_artifacts.update_one(
            {"_id": ObjectId(artifact.id)}, {"$set": {"expires_at": now() - timedelta(seconds=1)}},
        )
        with pytest.raises(HTTPException) as expired:
            await service.download_export(brand, artifact.id)
        assert expired.value.status_code == 410
        await database.commercial_export_artifacts.update_one(
            {"_id": ObjectId(artifact.id)}, {"$set": {"expires_at": now() + timedelta(days=1)}},
        )
        deleted = await service.delete_export(brand, artifact.id, SoftDeleteAction(reason="Export no longer needed"))
        assert deleted.status == "deleted"
        with pytest.raises(HTTPException):
            await service.get_export(brand, artifact.id)
        mongo.close()
    run(scenario())


def test_json_only_export_neutralizes_csv_formula_execution_surface():
    async def scenario():
        mongo, database, _, brand, profile, _, service = await fixture()
        await database.creator_commercial_profiles.update_one(
            {"_id": ObjectId(profile.id)}, {"$set": {"username": "=SUM(1,1)"}},
        )
        artifact = await service.create_export(brand, TenantExportRequest(
            date_from=now() - timedelta(days=30), date_to=now() + timedelta(minutes=1),
            record_categories=["profiles"],
        ))
        data, _ = await service.download_export(brand, artifact.id)
        assert json.loads(data)["data"]["profiles"][0]["username"] == "=SUM(1,1)"
        assert artifact.format == "json"  # JSON data is not interpreted as a spreadsheet formula.
        mongo.close()
    run(scenario())


def test_sensitive_internal_notes_are_absent_from_public_analytics_narrative_and_audit():
    async def scenario():
        mongo, _, _, brand, profile, _, service = await fixture()
        public = await CommercialService(service.db).get_profile(brand, profile.id)
        assert "internal_notes" not in public.model_dump()
        analytics = await CommercialService(service.db).analytics(
            brand, now() - timedelta(days=30), now() + timedelta(minutes=1), 100, "USD",
        )
        assert "private profile note" not in analytics.model_dump_json()
        package = (await ResearchAgent().research(DiscoveryCriteria(
            entity_type="creator", platforms=["instagram"], result_limit=2,
        ))).package
        request = CreatorIntelligenceRequest(
            research_package=package, campaign_budget=1000, number_of_creators=1,
            campaign_objective="Brand Awareness",
        )
        result = CreatorIntelligenceEngine().recommend(request)
        prompt = build_narrative_prompt(request, result)
        assert "private profile note" not in prompt.context_json
        audits = await service.audit_events(
            brand, now() - timedelta(days=30), now() + timedelta(minutes=1), 100, None, None, None,
        )
        assert "private profile note" not in json.dumps([item.model_dump(mode="json") for item in audits])
        mongo.close()
    run(scenario())


def test_audit_review_is_tenant_scoped_bounded_stable_and_payload_free():
    async def scenario():
        mongo, _, _, brand, _, _, service = await fixture()
        other = user()
        await service.commercial_repository.audit(
            str(other["_id"]), "private.other", "campaign_evidence", "other-id", ["notes"],
            tenant_id=str(other["_id"]), actor_category="brand",
        )
        events = await service.audit_events(
            brand, now() - timedelta(days=30), now() + timedelta(minutes=1), 10, None, None, None,
        )
        assert events
        assert all(item.action != "private.other" for item in events)
        assert all(not hasattr(item, "actor_id") and not hasattr(item, "payload") for item in events)
        assert [item.created_at for item in events] == sorted([item.created_at for item in events], reverse=True)
        with pytest.raises(HTTPException) as range_error:
            await service.audit_events(
                brand, now() - timedelta(days=367), now(), 10, None, None, None,
            )
        assert range_error.value.status_code == 422
        mongo.close()
    run(scenario())


async def api_fixture(monkeypatch, role="brand"):
    mongo = AsyncMongoMockClient()
    database = mongo["hardening_api"]
    storage = InMemoryEvidenceStorage()
    monkeypatch.setattr(server, "db", database)
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-with-more-than-32-characters")
    server.app.dependency_overrides[get_evidence_storage] = lambda: storage
    security._RL_BUCKETS.clear()
    user_doc = {"email": f"{role}-{ObjectId()}@example.com", "name": role, "role": role,
                "status": "active", "email_verified": True, "created_at": now(), "updated_at": now()}
    inserted = await database.users.insert_one(user_doc)
    current = {**user_doc, "_id": inserted.inserted_id}
    profile = await CommercialService(database).create_profile(current, CommercialProfileCreate(
        platform="instagram", platform_id="api-evidence", currency="USD",
    ))
    brand_doc = {"_id": ObjectId(), "user_id": str(inserted.inserted_id), "verification_status": "verified"}
    await database.brands.insert_one(brand_doc)
    campaign_id = ObjectId()
    await database.campaigns.insert_one({"_id": campaign_id, "brand_id": str(brand_doc["_id"])})
    performance = await CommercialService(database).create_performance(current, CampaignPerformanceCreate(
        campaign_id=str(campaign_id), commercial_profile_id=profile.id,
        objective="Brand Awareness", agreed_cost=100, currency="USD", deliverable_type="image",
        evidence_status="unverified", measurement_source="manual",
        measurement_period_start=now() - timedelta(days=1), measurement_period_end=now(),
    ))
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="https://brandkrt.test")
    client.cookies.set("access_token", server.create_access_token(str(inserted.inserted_id), user_doc["email"], role))
    return mongo, client, performance, storage


def test_evidence_upload_api_authorized_and_unauthenticated_rejected(monkeypatch):
    async def scenario():
        mongo, client, performance, storage = await api_fixture(monkeypatch)
        anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="https://brandkrt.test")
        try:
            form = {
                "evidence_type": "platform_export", "source_type": "platform_export",
                "supported_metrics": json.dumps(["observed_reach"]),
            }
            uploaded = await client.post(
                f"/api/campaign-performance/{performance.id}/evidence",
                data=form, files={"file": ("proof.png", PNG_BYTES, "image/png")},
            )
            assert uploaded.status_code == 201, uploaded.text
            body = uploaded.json()
            assert body["verification_status"] == "unverified"
            assert "storage_key" not in body and storage.items
            denied = await anonymous.post(
                f"/api/campaign-performance/{performance.id}/evidence",
                data=form, files={"file": ("proof2.png", PNG_BYTES, "image/png")},
            )
            assert denied.status_code == 401
        finally:
            server.app.dependency_overrides.pop(get_evidence_storage, None)
            await client.aclose(); await anonymous.aclose(); mongo.close()
    run(scenario())
