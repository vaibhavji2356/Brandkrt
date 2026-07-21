import asyncio

from backend_status import BackendStatus


def _set_core_config(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("MONGO_URL", "mongodb://example")
    monkeypatch.setenv("DB_NAME", "brandkrt")
    monkeypatch.setenv("JWT_SECRET", "development-secret")
    monkeypatch.setenv("EMAIL_PROVIDER", "auto")
    monkeypatch.setenv("PAYMENT_PROVIDER", "stub")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("REACT_APP_GOOGLE_CLIENT_ID", raising=False)


def test_status_is_live_before_database_probe(monkeypatch):
    _set_core_config(monkeypatch)
    status = BackendStatus()
    status.mark_app_started()

    snapshot = status.snapshot()

    assert snapshot["isReady"] is False
    assert snapshot["isDatabaseConnected"] is False
    assert snapshot["uptime"] >= 0
    assert snapshot["startupTime"]
    assert snapshot["version"]
    assert snapshot["environment"]


def test_readiness_requires_database_and_configuration(monkeypatch):
    _set_core_config(monkeypatch)
    status = BackendStatus()

    async def ping():
        return {"ok": 1}

    result = asyncio.run(status.check_readiness(ping))

    assert result["isReady"] is True
    assert result["isDatabaseConnected"] is True
    assert result["configuration"]["valid"] is True
    assert result["timings"]["mongoConnectionMs"] is not None
    assert result["timings"]["readinessMs"] is not None


def test_startup_timings_are_not_rewritten_by_warm_health_checks(monkeypatch):
    _set_core_config(monkeypatch)
    status = BackendStatus()
    status.mark_app_started()

    async def cold_ping():
        await asyncio.sleep(0.01)

    async def warm_ping():
        return {"ok": 1}

    first = asyncio.run(status.check_readiness(cold_ping))
    second = asyncio.run(status.check_readiness(warm_ping))

    assert second["timings"]["mongoConnectionMs"] == first["timings"]["mongoConnectionMs"]
    assert second["timings"]["readinessMs"] == first["timings"]["readinessMs"]
    assert second["timings"]["lastMongoPingMs"] <= first["timings"]["lastMongoPingMs"]


def test_readiness_reports_database_failure(monkeypatch):
    _set_core_config(monkeypatch)
    status = BackendStatus()

    async def ping():
        raise TimeoutError("database unavailable")

    result = asyncio.run(status.check_readiness(ping))

    assert result["isReady"] is False
    assert result["isDatabaseConnected"] is False
    assert result["databaseError"] == "TimeoutError"


def test_readiness_reports_missing_required_configuration(monkeypatch):
    _set_core_config(monkeypatch)
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    status = BackendStatus()

    async def ping():
        return {"ok": 1}

    result = asyncio.run(status.check_readiness(ping))

    assert result["isReady"] is False
    assert result["isDatabaseConnected"] is True
    assert result["configuration"]["valid"] is False
