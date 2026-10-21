"""Adversarial regression tests; uses no production database or providers."""
import asyncio
import io
import sys
from pathlib import Path

import httpx
import jwt
import hmac
import hashlib
import payments
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_critical_security import _security_context, _seed_user, _authenticated_client
import server


def test_campaign_filters_cannot_reveal_private_drafts_or_unknown_role_data(monkeypatch):
    async def scenario():
        mongo, db = await _security_context(monkeypatch, "campaign_filter_privacy")
        creator = await _seed_user(db, role="influencer", email="creator@example.com")
        staff = await _seed_user(db, role="staff", email="staff@example.com")
        draft = (await db.campaigns.insert_one({"title": "private draft", "status": "draft"})).inserted_id
        await db.campaigns.insert_one({"title": "published", "status": "active"})
        transport = httpx.ASGITransport(app=server.app)
        async with _authenticated_client(transport, creator) as client:
            for status in ("draft", "cancelled", "paused", "active"):
                response = await client.get("/api/campaigns", params={"status": status})
                assert response.status_code == 200
                assert all(row["status"] == "active" for row in response.json()["campaigns"])
            assert (await client.get(f"/api/campaigns/{draft}")).status_code == 404
        async with _authenticated_client(transport, staff) as client:
            assert (await client.get("/api/campaigns")).status_code == 403
        mongo.close()
    asyncio.run(scenario())


def test_private_uploads_require_owner_or_real_chat_participation(monkeypatch):
    async def scenario():
        mongo, db = await _security_context(monkeypatch, "private_file_access")
        users = [await _seed_user(db, role="influencer", email=f"u{i}@example.com") for i in range(3)]
        transport = httpx.ASGITransport(app=server.app)
        clients = [_authenticated_client(transport, user) for user in users]
        image = io.BytesIO()
        Image.new("RGB", (2, 2)).save(image, format="PNG")
        try:
            for folder in ("contracts", "invoices", "chat", "verification"):
                file = ("test.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF", "application/pdf") if folder in {"contracts", "invoices"} else ("test.png", image.getvalue(), "image/png")
                upload = await clients[0].post(f"/api/uploads/{folder}", files={"file": file})
                assert upload.status_code == 200, upload.text
                path = httpx.URL(upload.json()["url"]).path
                assert (await clients[0].get(path)).status_code == 200
                assert (await clients[1].get(path)).status_code == 403
                async with httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com") as anonymous:
                    assert (await anonymous.get(path)).status_code == 401
                if folder == "chat":
                    conv = (await db.conversations.insert_one({"participants": [str(u["_id"]) for u in users[:2]]})).inserted_id
                    await db.chat_messages.insert_one({"conversation_id": str(conv), "sender_id": str(users[0]["_id"]), "attachments": [{"url": path}]})
                    shared = await clients[1].get(path)
                    assert shared.status_code == 200
                    assert shared.headers["cache-control"] == "private, no-store"
                    assert (await clients[2].get(path)).status_code == 403
            for folder in ("chat", "contracts", "invoices", "verification"):
                assert (await clients[0].get(f"/uploads/{folder}/test.png")).status_code in {404, 405}
        finally:
            for client in clients:
                await client.aclose()
            mongo.close()
    asyncio.run(scenario())


def test_refresh_rotation_logout_revocation_and_minimal_jwt(monkeypatch):
    async def scenario():
        mongo, db = await _security_context(monkeypatch, "session_replay")
        user = await _seed_user(db, role="brand", email="private@example.com")
        transport = httpx.ASGITransport(app=server.app)
        old_access = server.create_access_token(str(user["_id"]), user["email"], "admin")
        decoded = jwt.decode(old_access, server._jwt_secret(), algorithms=["HS256"])
        assert "email" not in decoded and "role" not in decoded
        refresh = server.create_refresh_token(str(user["_id"]))
        async with httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com") as client:
            first = await client.post("/api/auth/refresh", headers={"Cookie": f"refresh_token={refresh}"})
            assert first.status_code == 200
            replay = await client.post("/api/auth/refresh", headers={"Cookie": f"refresh_token={refresh}"})
            assert replay.status_code == 401
            assert (await client.get("/api/admin/users", headers={"Cookie": f"access_token={old_access}"})).status_code == 403
            assert (await client.post("/api/auth/logout", headers={"Cookie": f"access_token={old_access}"})).status_code == 200
            assert (await client.get("/api/auth/me", headers={"Cookie": f"access_token={old_access}"})).status_code == 401
            assert (await client.post("/api/auth/refresh", headers={"Cookie": f"refresh_token={refresh}"})).status_code == 401
        mongo.close()
    asyncio.run(scenario())


def test_google_auth_cannot_bypass_origin_guard(monkeypatch):
    async def scenario():
        monkeypatch.setenv("APP_ENV", "production")
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com") as client:
            for headers in ({"Origin": "https://evil.example"}, {}):
                result = await client.post("/api/auth/google", json={"credential": "x" * 30}, headers=headers)
                assert result.status_code == 403
    asyncio.run(scenario())


def test_staff_permissions_are_explicit_and_not_frontend_controlled(monkeypatch):
    async def scenario():
        mongo, db = await _security_context(monkeypatch, "staff_permission_scope")
        staff = await _seed_user(db, role="staff", email="staff@example.com")
        transport = httpx.ASGITransport(app=server.app)
        async with _authenticated_client(transport, staff) as client:
            assert (await client.get("/api/admin/users", params={"permissions": "users:read", "role": "admin"})).status_code == 403
            await db.users.update_one({"_id": staff["_id"]}, {"$set": {"permissions": ["users:read"]}})
            assert (await client.get("/api/admin/users")).status_code == 200
            assert (await client.get(f"/api/admin/users/{staff['_id']}")).status_code == 403
            assert (await client.get("/api/admin/withdrawals")).status_code == 403
            assert (await client.patch("/api/profile", json={"role": "admin", "permissions": ["*"]})).status_code in {200, 422}
            assert (await db.users.find_one({"_id": staff["_id"]}))["role"] == "staff"
            assert await db.admin_logs.count_documents({"admin_id": str(staff["_id"]), "action": "admin.api_access"}) >= 4
        mongo.close()
    asyncio.run(scenario())


def test_razorpay_requires_capture_and_paid_order_not_only_signature(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "test")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test-secret")
    provider = payments.RazorpayProvider()
    signature = hmac.new(b"test-secret", b"order_1|pay_1", hashlib.sha256).hexdigest()
    status = {"payment": "authorized", "order": "created"}

    class Reply:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            pass
        def json(self):
            return self.payload

    def get(url, **kwargs):
        if "/payments/" in url:
            return Reply({"order_id": "order_1", "status": status["payment"], "amount": 10000, "currency": "INR"})
        return Reply({"status": status["order"], "amount": 10000, "currency": "INR"})

    monkeypatch.setattr(payments.requests, "get", get)
    assert not provider.verify(order_id="order_1", payment_id="pay_1", signature=signature)
    status.update(payment="captured", order="paid")
    assert provider.verify(order_id="order_1", payment_id="pay_1", signature=signature)
    assert not provider.verify(order_id="order_1", payment_id="pay_1", signature="invalid")


def test_production_cannot_use_fake_payments(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PAYMENT_PROVIDER", "stub")
    import pytest
    with pytest.raises(RuntimeError):
        payments.get_provider()


def test_every_private_get_route_rejects_anonymous_visitors(monkeypatch):
    async def scenario():
        import re
        from fastapi.routing import APIRoute
        mongo, db = await _security_context(monkeypatch, "anonymous_route_sweep")
        public = {"/api/auth/google/config", "/api/instagram/callback"}
        transport = httpx.ASGITransport(app=server.app)
        count = 0
        async with httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com") as client:
            for route in server.app.routes:
                if not isinstance(route, APIRoute) or "GET" not in route.methods:
                    continue
                if route.path in public or route.path.startswith(("/api/health", "/api/uploads/")):
                    continue
                path = re.sub(r"\{[^}]+\}", "012345678901234567890123", route.path)
                result = await client.get(path)
                assert result.status_code in {401, 403}, (route.path, result.status_code, result.text)
                count += 1
        assert count > 50
        mongo.close()
    asyncio.run(scenario())


def test_document_serializers_never_return_nested_credentials():
    from serialization import safe_document
    output = safe_document({"name": "Public", "password_hash": "secret", "nested": {"access_token": "secret", "bank_details": {"account_number": "owner-visible"}}})
    assert output == {"name": "Public", "nested": {"bank_details": {"account_number": "owner-visible"}}}


def test_financial_fields_are_authenticated_encrypted_and_api_still_works(monkeypatch):
    import base64
    from private_fields import protect_fields, reveal_field
    monkeypatch.setenv("PRIVATE_DATA_ENCRYPTION_KEY", base64.b64encode(b"a" * 32).decode())
    async def api_scenario():
        mongo, database = await _security_context(monkeypatch, "encrypted_profile_privacy")
        user = await _seed_user(database, role="brand", email="finance@example.com")
        stranger = await _seed_user(database, role="influencer", email="outsider@example.com")
        transport = httpx.ASGITransport(app=server.app)
        async with _authenticated_client(transport, user) as client:
            saved = await client.put("/api/brands/me", json={"company_name": "Acme", "bank_details": {"account_number": "private-account"}, "upi": "private@upi"})
            assert saved.status_code == 200, saved.text
            assert saved.json()["brand"]["bank_details"]["account_number"] == "private-account"
            record = await database.brands.find_one({"user_id": str(user["_id"])})
            assert "private-account" not in str(record)
            assert "private@upi" not in str(record)
            assert (await client.get("/api/brands/me")).json()["brand"]["upi"] == "private@upi"
        async with _authenticated_client(transport, stranger) as client:
            response = await client.get(f"/api/brands/{record['_id']}")
            assert response.status_code == 200
            assert "private-account" not in response.text and "private@upi" not in response.text
        mongo.close()
    asyncio.run(api_scenario())
    document = {"bank_details": {"account_number": "123456789"}, "upi": "creator@upi", "username": "public"}
    encrypted = protect_fields(document)
    assert "123456789" not in str(encrypted) and "creator@upi" not in str(encrypted)
    assert reveal_field("bank_details", encrypted["bank_details"]) == document["bank_details"]
    assert reveal_field("upi", encrypted["upi"]) == document["upi"]
    assert protect_fields(document)["bank_details"] != encrypted["bank_details"]
    import pytest
    from fastapi import HTTPException
    monkeypatch.setenv("PRIVATE_DATA_ENCRYPTION_KEY", base64.b64encode(b"b" * 32).decode())
    with pytest.raises(HTTPException):
        reveal_field("bank_details", encrypted["bank_details"])
