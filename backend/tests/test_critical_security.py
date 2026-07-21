import asyncio
import io
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient
from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import domain
import part4b
import part4c
import payments
import server


async def _security_context(monkeypatch, name):
    mongo = AsyncMongoMockClient()
    database = mongo[name]
    monkeypatch.setattr(server, "db", database)
    monkeypatch.setattr(domain, "db", database)
    monkeypatch.setattr(part4b, "db", database)
    monkeypatch.setattr(part4c, "db", database)
    monkeypatch.setenv("PAYMENT_PROVIDER", "stub")
    monkeypatch.setattr(payments, "_PROVIDER", payments.StubProvider())
    return mongo, database


async def _seed_user(database, *, role, email):
    now = datetime.now(timezone.utc)
    result = await database.users.insert_one({
        "email": email,
        "name": email.split("@", 1)[0],
        "role": role,
        "password_hash": "not-used-by-cookie-tests",
        "email_verified": True,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    return await database.users.find_one({"_id": result.inserted_id})


def _authenticated_client(transport, user):
    client = httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com")
    client.cookies.set(
        "access_token",
        server.create_access_token(str(user["_id"]), user["email"], user["role"]),
    )
    return client


def test_cross_tenant_deals_payments_and_legacy_messages_are_blocked(monkeypatch):
    async def scenario():
        mongo, database = await _security_context(monkeypatch, "critical_tenant_security")
        brand_one = await _seed_user(database, role="brand", email="brand-one@example.com")
        brand_two = await _seed_user(database, role="brand", email="brand-two@example.com")
        creator_one = await _seed_user(database, role="influencer", email="creator-one@example.com")
        creator_two = await _seed_user(database, role="influencer", email="creator-two@example.com")
        admin = await _seed_user(database, role="admin", email="admin@example.com")

        brand_one_profile = (await database.brands.insert_one({"user_id": str(brand_one["_id"]), "company_name": "One"})).inserted_id
        brand_two_profile = (await database.brands.insert_one({"user_id": str(brand_two["_id"]), "company_name": "Two"})).inserted_id
        creator_one_profile = (await database.influencers.insert_one({"user_id": str(creator_one["_id"]), "username": "one"})).inserted_id
        creator_two_profile = (await database.influencers.insert_one({"user_id": str(creator_two["_id"]), "username": "two"})).inserted_id
        campaign_one = (await database.campaigns.insert_one({"brand_id": str(brand_one_profile), "title": "One", "status": "active"})).inserted_id
        campaign_two = (await database.campaigns.insert_one({"brand_id": str(brand_two_profile), "title": "Two", "status": "active"})).inserted_id
        deal_one = (await database.deals.insert_one({
            "campaign_id": str(campaign_one), "brand_id": str(brand_one_profile),
            "influencer_id": str(creator_one_profile), "amount": 4000.0,
            "status": "offer_accepted", "created_at": datetime.now(timezone.utc),
        })).inserted_id
        deal_two = (await database.deals.insert_one({
            "campaign_id": str(campaign_two), "brand_id": str(brand_two_profile),
            "influencer_id": str(creator_two_profile), "amount": 7000.0,
            "status": "offer_accepted", "created_at": datetime.now(timezone.utc),
        })).inserted_id

        transport = httpx.ASGITransport(app=server.app)
        clients = [
            _authenticated_client(transport, user)
            for user in (brand_one, brand_two, creator_one, creator_two, admin)
        ]
        brand_one_client, brand_two_client, creator_one_client, creator_two_client, admin_client = clients
        bearer_only_client = httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com")
        try:
            bearer_only = await bearer_only_client.get("/api/auth/me", headers={
                "Authorization": f"Bearer {server.create_access_token(str(brand_one['_id']), brand_one['email'], 'brand')}"
            })
            assert bearer_only.status_code == 401
            foreign_create = await brand_one_client.post("/api/deals", json={
                "campaign_id": str(campaign_two), "influencer_id": str(creator_one_profile), "amount": 100,
            })
            assert foreign_create.status_code == 403
            own_offer = await brand_one_client.post("/api/deals", json={
                "campaign_id": str(campaign_one), "influencer_id": str(creator_one_profile), "amount": 1250,
            })
            assert own_offer.status_code == 200
            assert (await brand_one_client.post("/api/payments/escrow", json={
                "deal_id": own_offer.json()["deal"]["id"], "amount": 1250,
            })).status_code == 400

            foreign_status = await brand_two_client.patch(
                f"/api/deals/{deal_one}/status", json={"status": "product_shipped"}
            )
            assert foreign_status.status_code == 403
            foreign_report = await creator_two_client.get(f"/api/performance/deal/{deal_one}/report")
            assert foreign_report.status_code == 403
            assert (await admin_client.get(f"/api/performance/deal/{deal_one}/report")).status_code == 200

            foreign_escrow = await brand_two_client.post(
                "/api/payments/escrow", json={"deal_id": str(deal_one), "amount": 1}
            )
            assert foreign_escrow.status_code == 403
            funded = await brand_one_client.post(
                "/api/payments/escrow", json={"deal_id": str(deal_one), "amount": 1}
            )
            assert funded.status_code == 200, funded.text
            payment = funded.json()["payment"]
            assert payment["amount"] == 4000.0
            assert payment["platform_fee"] == 400.0

            assert len((await brand_one_client.get("/api/payments")).json()["payments"]) == 1
            assert len((await creator_one_client.get("/api/payments")).json()["payments"]) == 1
            assert (await brand_two_client.get("/api/payments")).json()["payments"] == []
            assert (await creator_two_client.get("/api/payments")).json()["payments"] == []
            assert len((await admin_client.get("/api/payments")).json()["payments"]) == 1

            sent = await brand_one_client.post("/api/messages", json={"deal_id": str(deal_one), "body": "secure"})
            assert sent.status_code == 200
            assert (await creator_one_client.get(f"/api/messages/{deal_one}")).status_code == 200
            assert (await brand_two_client.get(f"/api/messages/{deal_one}")).status_code == 403
            assert (await admin_client.get(f"/api/messages/{deal_one}")).status_code == 403
            assert (await creator_two_client.post(
                "/api/messages", json={"deal_id": str(deal_one), "body": "intrusion"}
            )).status_code == 403

            foreign_verify = await brand_two_client.post("/api/payments/razorpay/verify", json={
                "payment_id": payment["id"],
                "razorpay_order_id": "foreign-order",
                "razorpay_payment_id": "foreign-payment",
                "razorpay_signature": "foreign-signature",
            })
            assert foreign_verify.status_code == 403

            visible_to_brand_two = (await brand_two_client.get("/api/deals")).json()["deals"]
            assert {row["id"] for row in visible_to_brand_two} == {str(deal_two)}
        finally:
            for client in clients:
                await client.aclose()
            await bearer_only_client.aclose()
            mongo.close()

    asyncio.run(scenario())


def test_withdrawals_require_owned_available_creator_earnings(monkeypatch):
    async def scenario():
        mongo, database = await _security_context(monkeypatch, "critical_withdrawal_security")
        brand = await _seed_user(database, role="brand", email="brand@example.com")
        creator = await _seed_user(database, role="influencer", email="creator@example.com")
        other_creator = await _seed_user(database, role="influencer", email="other@example.com")
        admin = await _seed_user(database, role="admin", email="admin@example.com")
        creator_profile = (await database.influencers.insert_one({"user_id": str(creator["_id"]), "username": "creator"})).inserted_id
        await database.influencers.insert_one({"user_id": str(other_creator["_id"]), "username": "other"})
        await database.payments.insert_one({
            "influencer_id": str(creator_profile), "amount": 1000.0,
            "influencer_earning": 900.0, "status": "released", "release_status": "released",
            "created_at": datetime.now(timezone.utc),
        })

        transport = httpx.ASGITransport(app=server.app)
        clients = [_authenticated_client(transport, user) for user in (brand, creator, other_creator, admin)]
        brand_client, creator_client, other_client, admin_client = clients
        payload = {"method": "upi", "details": {"upi": "creator@upi"}}
        try:
            assert (await brand_client.post("/api/withdrawals", json={**payload, "amount": 1})).status_code == 403
            assert (await other_client.post("/api/withdrawals", json={**payload, "amount": 1})).status_code == 400
            assert (await creator_client.post("/api/withdrawals", json={**payload, "amount": 901})).status_code == 400

            first = await creator_client.post("/api/withdrawals", json={**payload, "amount": 500})
            assert first.status_code == 200, first.text
            assert (await creator_client.post("/api/withdrawals", json={**payload, "amount": 1})).status_code == 409
            assert (await other_client.get("/api/withdrawals/mine")).json()["requests"] == []

            request_id = first.json()["request"]["id"]
            rejected = await admin_client.post(
                f"/api/admin/withdrawals/{request_id}/decision", json={"decision": "rejected", "note": "retry"}
            )
            assert rejected.status_code == 200

            second = await creator_client.post("/api/withdrawals", json={**payload, "amount": 700})
            assert second.status_code == 200, second.text
            second_id = second.json()["request"]["id"]
            paid = await admin_client.post(
                f"/api/admin/withdrawals/{second_id}/manual-payout", json={"reference": "SECURITY-TEST"}
            )
            assert paid.status_code == 200, paid.text
            assert (await creator_client.post("/api/withdrawals", json={**payload, "amount": 201})).status_code == 400
            assert (await creator_client.post("/api/withdrawals", json={**payload, "amount": 200})).status_code == 200
        finally:
            for client in clients:
                await client.aclose()
            mongo.close()

    asyncio.run(scenario())


def test_uploads_are_content_validated_and_verification_documents_are_private(monkeypatch):
    async def scenario():
        mongo, database = await _security_context(monkeypatch, "critical_upload_security")
        owner = await _seed_user(database, role="brand", email="owner@example.com")
        stranger = await _seed_user(database, role="brand", email="stranger@example.com")
        admin = await _seed_user(database, role="admin", email="admin@example.com")
        transport = httpx.ASGITransport(app=server.app)
        owner_client, stranger_client, admin_client = [
            _authenticated_client(transport, user) for user in (owner, stranger, admin)
        ]
        anonymous_client = httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com")

        image_buffer = io.BytesIO()
        Image.new("RGB", (2, 2), (255, 0, 0)).save(image_buffer, format="PNG")
        png = image_buffer.getvalue()
        try:
            uploaded = await owner_client.post(
                "/api/uploads/verification", files={"file": ("proof.png", png, "image/png")}
            )
            assert uploaded.status_code == 200, uploaded.text
            upload_path = urlsplit(uploaded.json()["url"]).path

            owner_read = await owner_client.get(upload_path)
            assert owner_read.status_code == 200
            assert owner_read.headers["content-type"].startswith("image/png")
            assert owner_read.headers["cache-control"] == "private, no-store"
            assert owner_read.headers["content-disposition"].startswith("attachment")
            assert (await stranger_client.get(upload_path)).status_code == 403
            assert (await anonymous_client.get(upload_path)).status_code == 401
            assert (await admin_client.get(upload_path)).status_code == 200

            svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
            assert (await owner_client.post(
                "/api/uploads/profiles", files={"file": ("avatar.svg", svg, "image/svg+xml")}
            )).status_code == 415
            assert (await owner_client.post(
                "/api/uploads/profiles", files={"file": ("avatar.png", b"MZ" + b"0" * 100, "image/png")}
            )).status_code == 415
            assert (await owner_client.post(
                "/api/uploads/profiles", files={"file": ("avatar.png", png, "application/pdf")}
            )).status_code == 415
        finally:
            await owner_client.aclose()
            await stranger_client.aclose()
            await admin_client.aclose()
            await anonymous_client.aclose()
            mongo.close()

    asyncio.run(scenario())


def test_cors_is_exact_and_frontend_does_not_persist_access_jwts():
    async def scenario():
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com") as client:
            allowed = await client.options("/api/auth/me", headers={
                "Origin": "https://brandkrt.com", "Access-Control-Request-Method": "GET",
            })
            unrelated = await client.options("/api/auth/me", headers={
                "Origin": "https://unrelated-project.vercel.app", "Access-Control-Request-Method": "GET",
            })
            assert allowed.status_code == 200
            assert allowed.headers.get("access-control-allow-origin") == "https://brandkrt.com"
            assert unrelated.status_code == 400
            assert unrelated.headers.get("access-control-allow-origin") is None

    asyncio.run(scenario())
    frontend = Path(__file__).resolve().parents[2] / "frontend" / "src"
    auth_source = (frontend / "context" / "AuthContext.jsx").read_text(encoding="utf-8")
    api_source = (frontend / "lib" / "api.js").read_text(encoding="utf-8")
    assert "localStorage.setItem(TOKEN_KEY" not in auth_source
    assert "localStorage.getItem(TOKEN_KEY" not in api_source
    assert "Authorization = `Bearer" not in api_source
    mounted_paths = {getattr(route, "path", None) for route in server.app.routes}
    assert "/uploads" not in mounted_paths
    assert "/uploads/verification" not in mounted_paths
