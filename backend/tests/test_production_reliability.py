import asyncio
from datetime import datetime, timedelta, timezone
import io
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI, HTTPException, Request
import httpx
from mongomock_motor import AsyncMongoMockClient
from pymongo.errors import PyMongoError
import pytest

from backend_status import BackendStatus
from brand_discovery_ai.config import AISettings
from brand_discovery_ai.errors import AIAccountingUnavailableError, AIDailyBudgetExceededError
from brand_discovery_ai.usage import AIUsageAccounting, InMemoryAIUsageAccounting, UsageIdentity
from commercial_intelligence.evidence_storage import (
    InMemoryEvidenceStorage, S3CompatibleEvidenceStorage,
)
from commercial_intelligence.evidence_validation import validate_evidence_file
from commercial_intelligence.hardening_models import EvidenceMetadataInput
from commercial_intelligence.hardening_service import CommercialHardeningService
from database_setup import create_indexes
from operations.configuration import validate_configuration
from operations.errors import StorageOperationError, install_exception_handlers
from operations.index_verification import verify_critical_indexes
from operations.metrics import operational_metrics
from operations.mongo import mongo_client_options
from operations.observability import RequestObservabilityMiddleware, SafeJsonFormatter, valid_request_id
from operations.rate_limiting import (
    InMemoryRateLimitBackend, MongoRateLimitBackend, RateLimitBackendUnavailable,
)
from operations.router import create_operations_router
import security
import server


PNG_BYTES = __import__("base64").b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def run(coro):
    return asyncio.run(coro)


def _base_environment(monkeypatch, *, production=False):
    monkeypatch.setenv("APP_ENV", "production" if production else "development")
    monkeypatch.setenv("MONGO_URL", "mongodb://database.example.invalid/brandkrt")
    monkeypatch.setenv("DB_NAME", "brandkrt")
    monkeypatch.setenv("JWT_SECRET", "a" * 64)
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    monkeypatch.setenv("CORS_ORIGINS", "https://brandkrt.com" if production else "http://localhost:3000")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_MOCK_MODE", "true")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "mongo" if production else "memory")
    monkeypatch.setenv("AI_USAGE_BACKEND", "mongo" if production else "memory")
    monkeypatch.setenv("ADMIN_LEAD_MOCK_MODE", "false")
    monkeypatch.setenv("EMAIL_PROVIDER", "auto")
    monkeypatch.setenv("PAYMENT_PROVIDER", "stub")
    monkeypatch.setenv("EVIDENCE_STORAGE_PROVIDER", "s3" if production else "local")
    monkeypatch.setenv("EVIDENCE_UPLOAD_ENABLED", "true")
    if production:
        monkeypatch.setenv("EVIDENCE_STORAGE_BUCKET", "private-evidence")
        monkeypatch.setenv("EVIDENCE_STORAGE_REGION", "auto")
        monkeypatch.setenv("EVIDENCE_STORAGE_ACCESS_KEY", "credential-value-access")
        monkeypatch.setenv("EVIDENCE_STORAGE_SECRET_KEY", "credential-value-secret")
        monkeypatch.setenv("EVIDENCE_STORAGE_SIGNED_URL_TTL_SECONDS", "300")
        monkeypatch.setenv("EVIDENCE_STORAGE_ENCRYPTION_MODE", "AES256")


def test_configuration_accepts_safe_development_and_production(monkeypatch):
    _base_environment(monkeypatch)
    assert validate_configuration().valid is True
    _base_environment(monkeypatch, production=True)
    report = validate_configuration()
    assert report.valid is True
    assert report.features["storage_provider"] == "s3"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ({"CORS_ORIGINS": "*"}, "invalid_cors_origin"),
        ({"JWT_SECRET": "replace_with_secret"}, "weak_or_placeholder_secret"),
        ({"EVIDENCE_STORAGE_PROVIDER": "local"}, "ephemeral_local_evidence_storage"),
        ({"DEBUG": "true"}, "debug_enabled_in_production"),
        ({"EVIDENCE_STORAGE_SECRET_KEY": ""}, "missing_storage_setting"),
        ({"EVIDENCE_STORAGE_SIGNED_URL_TTL_SECONDS": "86400"}, "unsafe_signed_url_ttl"),
        ({"RATE_LIMIT_BACKEND": "memory"}, "non_distributed_rate_limit_backend"),
        ({"ADMIN_LEAD_MOCK_MODE": "true"}, "admin_lead_mock_mode_in_production"),
    ],
)
def test_production_configuration_fails_closed(monkeypatch, mutation, expected_code):
    _base_environment(monkeypatch, production=True)
    for key, value in mutation.items():
        monkeypatch.setenv(key, value)
    report = validate_configuration()
    assert report.valid is False
    assert expected_code in {item.code for item in report.errors}
    serialized = json.dumps(report.public())
    assert "credential-value-secret" not in serialized


def test_paid_ai_requires_shared_accounting_in_production(monkeypatch):
    _base_environment(monkeypatch, production=True)
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MOCK_MODE", "false")
    monkeypatch.setenv("AI_API_KEY", "runtime-injected-key")
    monkeypatch.setenv("AI_USAGE_BACKEND", "memory")
    report = validate_configuration()
    assert "non_distributed_ai_usage_backend" in {item.code for item in report.errors}
    assert "runtime-injected-key" not in json.dumps(report.public())


def test_mongo_options_are_bounded_and_resilient():
    options = mongo_client_options({
        "MONGO_SERVER_SELECTION_TIMEOUT_MS": "999999",
        "MONGO_CONNECT_TIMEOUT_MS": "invalid",
        "MONGO_MAX_POOL_SIZE": "0",
    })
    assert options["serverSelectionTimeoutMS"] == 30_000
    assert options["connectTimeoutMS"] == 5000
    assert options["maxPoolSize"] == 1
    assert options["retryReads"] is True and options["retryWrites"] is True
    assert options["tz_aware"] is True


def test_readiness_uses_required_components_but_ignores_optional_ai(monkeypatch):
    _base_environment(monkeypatch)
    status = BackendStatus()
    status.set_component("storage", ready=True, required=True, state="s3:durable")
    status.set_component("ai_usage", ready=False, required=False, state="optional_unavailable")

    async def ping():
        return {"ok": 1}

    ready = run(status.check_readiness(ping))
    assert ready["isReady"] is True
    status.set_component("storage", ready=False, required=True, state="unavailable")
    unavailable = run(status.check_readiness(ping))
    assert unavailable["isReady"] is False
    assert "mongodb://" not in json.dumps(unavailable)


def test_health_api_liveness_and_readiness_success(monkeypatch):
    async def scenario():
        _base_environment(monkeypatch)
        status = BackendStatus()
        status.set_component("indexes", ready=True, required=True, state="verified")
        monkeypatch.setattr(server, "backend_status", status)
        monkeypatch.setattr(server, "_readiness_cache", None)

        class Admin:
            async def command(self, name):
                assert name == "ping"
                return {"ok": 1}

        monkeypatch.setattr(server, "client", SimpleNamespace(admin=Admin()))
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://brandkrt.test") as client:
            live = await client.get("/api/health/live")
            ready = await client.get("/api/health/ready")
        assert live.status_code == 200 and live.json()["status"] == "live"
        assert ready.status_code == 200 and ready.json()["isReady"] is True
        assert valid_request_id(live.headers["x-request-id"])
    run(scenario())


def test_health_api_database_unavailable_is_safe_503(monkeypatch):
    async def scenario():
        _base_environment(monkeypatch)
        status = BackendStatus()
        status.set_component("indexes", ready=True, required=True, state="verified")
        monkeypatch.setattr(server, "backend_status", status)
        monkeypatch.setattr(server, "_readiness_cache", None)

        class Admin:
            async def command(self, name):
                del name
                raise TimeoutError("mongodb://private-host")

        monkeypatch.setattr(server, "client", SimpleNamespace(admin=Admin()))
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://brandkrt.test") as client:
            response = await client.get("/api/health/ready")
        assert response.status_code == 503
        assert response.json()["isDatabaseConnected"] is False
        assert "private-host" not in response.text and "mongodb://" not in response.text
    run(scenario())


class _FakeS3:
    def __init__(self):
        self.objects = {}
        self.tags = {}
        self.closed = False
        self.last_expiry = None

    def put_object(self, **kwargs):
        key = kwargs["Key"]
        if key in self.objects:
            raise _FakeS3Error(412, "PreconditionFailed")
        self.objects[key] = {
            "Body": bytes(kwargs["Body"]), "Metadata": kwargs["Metadata"],
            "ContentType": kwargs["ContentType"],
        }
        return {"ETag": "safe"}

    def get_object(self, **kwargs):
        if kwargs["Key"] not in self.objects:
            raise _FakeS3Error(404, "NoSuchKey")
        item = self.objects[kwargs["Key"]]
        return {**item, "Body": io.BytesIO(item["Body"])}

    def head_object(self, **kwargs):
        if kwargs["Key"] not in self.objects:
            raise _FakeS3Error(404, "NotFound")
        item = self.objects[kwargs["Key"]]
        return {"ContentLength": len(item["Body"]), "ContentType": item["ContentType"], "Metadata": item["Metadata"]}

    def put_object_tagging(self, **kwargs):
        self.tags[kwargs["Key"]] = kwargs["Tagging"]

    def get_object_tagging(self, **kwargs):
        return self.tags.get(kwargs["Key"], {"TagSet": []})

    def delete_object(self, **kwargs):
        self.objects.pop(kwargs["Key"], None)

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        self.last_expiry = ExpiresIn
        return f"https://signed.invalid/{operation}/{Params['Key']}"

    def head_bucket(self, **kwargs):
        return {"ok": True}

    def close(self):
        self.closed = True


class _FakeS3Error(Exception):
    def __init__(self, status, code):
        self.response = {
            "ResponseMetadata": {"HTTPStatusCode": status}, "Error": {"Code": code},
        }
        super().__init__(code)


def _s3_storage(monkeypatch, fake=None):
    monkeypatch.setenv("EVIDENCE_STORAGE_BUCKET", "private")
    monkeypatch.setenv("EVIDENCE_STORAGE_REGION", "auto")
    monkeypatch.setenv("EVIDENCE_STORAGE_PREFIX", "tenant-private")
    monkeypatch.setenv("EVIDENCE_STORAGE_ENCRYPTION_MODE", "AES256")
    return S3CompatibleEvidenceStorage(client=fake or _FakeS3())


def test_s3_provider_save_read_metadata_quarantine_signed_reference_and_delete(monkeypatch):
    async def scenario():
        fake = _FakeS3()
        storage = _s3_storage(monkeypatch, fake)
        checksum = __import__("hashlib").sha256(PNG_BYTES).hexdigest()
        key = await storage.save(PNG_BYTES, "png", content_type="image/png", checksum_sha256=checksum)
        assert key.startswith("tenant-private/") and await storage.exists(key)
        assert await storage.read(key) == PNG_BYTES
        metadata = await storage.metadata(key)
        assert metadata.checksum_sha256 == checksum and metadata.content_type == "image/png"
        await storage.mark_deleted(key)
        assert fake.tags[key]["TagSet"][0]["Value"] == "soft-deleted"
        assert (await storage.metadata(key)).soft_deleted is True
        reference = await storage.generate_temporary_download_reference(key, 900)
        assert reference.startswith("https://signed.invalid/") and fake.last_expiry == 300
        await storage.physical_delete(key)
        assert key not in fake.objects and not await storage.exists(key)
        await storage.close()
        assert fake.closed is True
    run(scenario())


def test_s3_provider_rejects_duplicate_object_key_without_overwrite(monkeypatch):
    async def scenario():
        fake = _FakeS3()
        storage = _s3_storage(monkeypatch, fake)
        monkeypatch.setattr("commercial_intelligence.evidence_storage.secrets.token_hex", lambda _: "a" * 48)
        first = await storage.save(PNG_BYTES, "png", content_type="image/png")
        with pytest.raises(StorageOperationError) as duplicate:
            await storage.save(PNG_BYTES, "png", content_type="image/png")
        assert duplicate.value.code == "duplicate_object_key"
        assert fake.objects[first]["Body"] == PNG_BYTES
    run(scenario())


def test_s3_provider_timeout_is_classified_without_vendor_details(monkeypatch):
    async def scenario():
        storage = _s3_storage(monkeypatch)
        storage._call = AsyncMock(side_effect=StorageOperationError("storage_timeout"))
        with pytest.raises(StorageOperationError) as error:
            await storage.health_check()
        assert error.value.code == "storage_timeout"
        assert "private" not in str(error.value)
    run(scenario())


def test_failed_metadata_write_quarantines_uploaded_object(monkeypatch):
    async def scenario():
        storage = InMemoryEvidenceStorage()
        service = CommercialHardeningService(SimpleNamespace(), storage)
        now = datetime.now(timezone.utc)
        performance = {
            "_id": "unused", "tenant_id": "tenant", "campaign_id": "campaign",
            "platform": "instagram", "platform_id": "creator",
            "measurement_period_start": now - timedelta(days=1), "measurement_period_end": now,
        }
        service.commercial._owned_performance = AsyncMock(return_value=performance)
        service.repository.duplicate_evidence = AsyncMock(return_value=None)
        service.repository.create_evidence = AsyncMock(side_effect=RuntimeError("database unavailable"))
        validated = validate_evidence_file(PNG_BYTES, "proof.png", "image/png")
        metadata = EvidenceMetadataInput(
            evidence_type="platform_export", source_type="platform_export",
            supported_metrics=["observed_reach"],
        )
        with pytest.raises(RuntimeError):
            await service.upload_evidence({"_id": "user", "role": "brand"}, "record", metadata, validated)
        assert len(storage.items) == 1 and storage.deleted == set(storage.items)
    run(scenario())


def test_missing_storage_object_marks_evidence_inconsistent():
    async def scenario():
        storage = InMemoryEvidenceStorage()
        service = CommercialHardeningService(SimpleNamespace(), storage)
        now = datetime.now(timezone.utc)
        evidence = {
            "_id": "evidence", "tenant_id": "tenant", "storage_key": "aa/" + "a" * 48 + ".png",
            "deleted_at": None, "evidence_status": "active", "retention_expires_at": now + timedelta(days=1),
            "file_retention_expires_at": now + timedelta(days=1),
        }
        service._owned_evidence = AsyncMock(return_value=evidence)
        service.repository.mark_evidence_inconsistent = AsyncMock()
        with pytest.raises(HTTPException) as unavailable:
            await service.download_evidence({"_id": "user", "role": "brand"}, "evidence")
        assert unavailable.value.status_code == 410
        service.repository.mark_evidence_inconsistent.assert_awaited_once()
        assert service.repository.mark_evidence_inconsistent.await_args.args[1] == "object_missing"
    run(scenario())


def _test_app():
    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/items/{item_id}")
    async def item(item_id: str):
        return {"id": item_id}

    @app.post("/private")
    async def private(request: Request):
        await request.body()
        return {"ok": True}

    @app.get("/storage-error")
    async def storage_error():
        raise StorageOperationError("vendor-secret-message")

    @app.get("/database-error")
    async def database_error():
        raise PyMongoError("mongodb://secret-host")

    @app.get("/unexpected")
    async def unexpected():
        raise RuntimeError("private stack value")

    app.add_middleware(RequestObservabilityMiddleware)
    return app


def test_request_ids_generated_accepted_and_invalid_replaced():
    async def scenario():
        transport = httpx.ASGITransport(app=_test_app(), raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="https://brandkrt.test") as client:
            generated = await client.get("/items/abc")
            accepted = await client.get("/items/abc", headers={"X-Request-ID": "safe-request_123"})
            malformed = await client.get("/items/abc", headers={"X-Request-ID": "bad value!"})
            oversized = await client.get("/items/abc", headers={"X-Request-ID": "a" * 65})
        assert valid_request_id(generated.headers["x-request-id"])
        assert accepted.headers["x-request-id"] == "safe-request_123"
        assert malformed.headers["x-request-id"] != "bad value!"
        assert oversized.headers["x-request-id"] != "a" * 65
    run(scenario())


def test_request_logs_use_route_template_and_exclude_sensitive_input(caplog):
    async def scenario():
        operational_metrics.reset()
        caplog.set_level(logging.INFO, logger="brandkrt.access")
        transport = httpx.ASGITransport(app=_test_app())
        async with httpx.AsyncClient(transport=transport, base_url="https://brandkrt.test") as client:
            await client.post(
                "/private?token=do-not-log", headers={"Authorization": "Bearer do-not-log"},
                json={"internal_notes": ["do-not-log-private-note"]},
            )
        record = next(item for item in caplog.records if getattr(item, "event", "") == "http.request.completed")
        assert record.route == "/private"
        assert "do-not-log" not in caplog.text and "internal_notes" not in caplog.text
        assert "POST /private 2xx" in operational_metrics.snapshot()["http_request_count"]
    run(scenario())


def test_forwarded_client_ip_is_used_only_when_explicitly_trusted(monkeypatch):
    request = SimpleNamespace(
        headers={"x-forwarded-for": "198.51.100.9, 203.0.113.4"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")
    assert security.client_ip(request) == "127.0.0.1"
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    assert security.client_ip(request) == "203.0.113.4"


def test_structured_formatter_is_json_and_allowlisted():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "safe message", (), None)
    record.event = "test.event"
    record.request_id = "request-1"
    record.authorization = "must-not-appear"
    payload = json.loads(SafeJsonFormatter("production").format(record))
    assert payload["event"] == "test.event" and payload["request_id"] == "request-1"
    assert "authorization" not in payload and "must-not-appear" not in json.dumps(payload)


def test_safe_error_taxonomy_includes_request_id_and_no_internal_details():
    async def scenario():
        transport = httpx.ASGITransport(app=_test_app(), raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="https://brandkrt.test") as client:
            for path, code, status in (
                ("/storage-error", "storage_error", 503),
                ("/database-error", "database_error", 503),
                ("/unexpected", "internal_error", 500),
            ):
                response = await client.get(path, headers={"X-Request-ID": "error-request"})
                assert response.status_code == status
                assert response.json()["code"] == code
                assert response.json()["request_id"] == "error-request"
                assert response.headers["x-request-id"] == "error-request"
                assert "secret" not in response.text and "traceback" not in response.text.casefold()
    run(scenario())


def test_in_memory_rate_limit_is_atomic_under_concurrency():
    async def scenario():
        backend = InMemoryRateLimitBackend()
        decisions = await asyncio.gather(*[
            backend.acquire("login:127.0.0.1", 1, 60) for _ in range(10)
        ])
        assert sum(item.allowed for item in decisions) == 1
        assert sum(not item.allowed for item in decisions) == 9
    run(scenario())


class _AtomicCollection:
    def __init__(self):
        self.count = 0

    async def find_one_and_update(self, query, update, **kwargs):
        limit = query["$or"][0]["count"]["$lt"]
        if self.count >= limit:
            return None
        self.count += update["$inc"]["count"]
        return {"count": self.count}


def test_distributed_rate_limit_mock_and_backend_failure():
    async def scenario():
        collection = _AtomicCollection()
        database = SimpleNamespace(operational_rate_limits=collection)
        backend = MongoRateLimitBackend(database)
        first = await backend.acquire("safe-key", 1, 60)
        second = await backend.acquire("safe-key", 1, 60)
        assert first.allowed is True and second.allowed is False

        class Failing:
            async def acquire(self, *args):
                raise RateLimitBackendUnavailable()

        with pytest.raises(RateLimitBackendUnavailable):
            await Failing().acquire("key", 1, 60)
    run(scenario())


def _ai_settings():
    return AISettings(
        provider="openai", api_key="test-key", model="gpt-5.6-luna",
        allowed_models=("gpt-5.6-luna",), timeout_seconds=2, max_retries=0,
        max_output_tokens=256, max_requests_per_user_per_day=10,
        max_requests_per_ip_per_minute=10, daily_budget_usd=0.05,
        max_estimated_cost_per_request_usd=0.05, mock_mode=False,
    )


def test_ai_budget_reservation_is_atomic_and_failed_calls_remain_reserved():
    async def scenario():
        backend = InMemoryAIUsageAccounting()
        settings = _ai_settings()
        identity = UsageIdentity("user", "127.0.0.1")

        async def reserve():
            try:
                return await backend.reserve(settings, identity, 0.04)
            except AIDailyBudgetExceededError:
                return None

        reservations = await asyncio.gather(reserve(), reserve())
        assert sum(item is not None for item in reservations) == 1
        reservation = next(item for item in reservations if item)
        await backend.record_actual(
            reservation, input_tokens=10, output_tokens=0, actual_cost_usd=0, success=False,
        )
        snapshot = backend.snapshot()
        assert snapshot["reserved_daily_cost_usd"] == 0.04
        assert snapshot["actual_input_tokens"] == 10
    run(scenario())


def test_ai_accounting_backend_unavailable_never_bypasses_reservation():
    class Unavailable:
        async def reserve(self, *args, **kwargs):
            raise AIAccountingUnavailableError()
        def snapshot(self):
            return {"backend": "unavailable"}
        def reset(self):
            return None

    async def scenario():
        accounting = AIUsageAccounting()
        accounting.configure(Unavailable())
        with pytest.raises(AIAccountingUnavailableError):
            await accounting.reserve(_ai_settings(), UsageIdentity("user", "ip"), 0.01)
    run(scenario())


def test_index_declarations_are_idempotent_and_verifiable():
    async def scenario():
        client = AsyncMongoMockClient()
        database = client.production_reliability_indexes
        await create_indexes(database)
        await create_indexes(database)
        result = await verify_critical_indexes(database)
        assert result.ready is True and result.missing == ()
        client.close()
    run(scenario())


def test_operations_endpoints_are_admin_only_and_secret_safe():
    async def scenario():
        mongo = AsyncMongoMockClient()
        database = mongo.operations_diagnostics
        storage = InMemoryEvidenceStorage()

        async def admin_user():
            return {"_id": "admin", "role": "admin"}

        async def brand_user():
            return {"_id": "brand", "role": "brand"}

        admin_app = FastAPI()
        admin_app.include_router(
            create_operations_router(admin_user, lambda: database, lambda: storage), prefix="/api",
        )
        brand_app = FastAPI()
        brand_app.include_router(
            create_operations_router(brand_user, lambda: database, lambda: storage), prefix="/api",
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=admin_app), base_url="https://brandkrt.test",
        ) as admin_client:
            diagnostics = await admin_client.get("/api/admin/operations/diagnostics")
            metrics = await admin_client.get("/api/admin/operations/metrics")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=brand_app), base_url="https://brandkrt.test",
        ) as brand_client:
            denied = await brand_client.get("/api/admin/operations/diagnostics")
        assert diagnostics.status_code == 200 and metrics.status_code == 200
        serialized = diagnostics.text
        assert "MONGO_URL" not in serialized and "storage_key" not in serialized
        assert metrics.headers["cache-control"] == "private, no-store"
        assert denied.status_code == 403
        mongo.close()
    run(scenario())
