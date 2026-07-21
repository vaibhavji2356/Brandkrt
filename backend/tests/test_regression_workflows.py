"""Read-only-to-production regression coverage for core BrandKrt workflows.

The application routers are exercised against an isolated in-memory MongoDB
implementation. No configured Atlas data, email provider, or payment provider
is contacted by these tests.
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from mongomock_motor import AsyncMongoMockClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import domain
import part4b
import part4c
import payments
import server


async def _register(client, database, *, email, phone, role, name):
    sent = await client.post("/api/auth/register/send-otp", json={"email": email})
    assert sent.status_code == 200, sent.text
    otp = await database.registration_otps.find_one({"email": email})
    assert otp and otp["code"]
    registered = await client.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "phone": phone,
            "password": "RegressionPassword123!",
            "role": role,
            "otp_code": otp["code"],
            "accept_terms": True,
        },
    )
    assert registered.status_code == 200, registered.text
    assert registered.json()["user"]["role"] == role
    return registered.json()["user"]


def test_core_auth_dashboard_campaign_deal_payment_workflows(monkeypatch):
    async def scenario():
        mock_client = AsyncMongoMockClient()
        database = mock_client.brandkrt_regression
        monkeypatch.setattr(server, "db", database)
        monkeypatch.setattr(domain, "db", database)
        monkeypatch.setattr(part4b, "db", database)
        monkeypatch.setattr(part4c, "db", database)
        monkeypatch.setenv("PAYMENT_PROVIDER", "stub")
        monkeypatch.setattr(payments, "_PROVIDER", payments.StubProvider())

        async def no_email(*_args, **_kwargs):
            return None

        monkeypatch.setattr(server.email_service, "send_signup_otp", no_email)
        transport = httpx.ASGITransport(app=server.app)

        async with (
            httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com") as brand_client,
            httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com") as influencer_client,
            httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com") as google_client,
            httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com") as admin_client,
        ):
            # Protected APIs reject anonymous callers.
            anonymous = await google_client.get("/api/campaigns")
            assert anonymous.status_code == 401

            brand_user = await _register(
                brand_client,
                database,
                email="regression-brand@example.com",
                phone="+919000000001",
                role="brand",
                name="Regression Brand",
            )
            influencer_user = await _register(
                influencer_client,
                database,
                email="regression-creator@example.com",
                phone="+919000000002",
                role="influencer",
                name="Regression Creator",
            )

            # JWT cookies authenticate /me and refresh rotates the access token.
            assert (await brand_client.get("/api/auth/me")).status_code == 200
            brand_client.cookies.delete("access_token")
            refreshed = await brand_client.post("/api/auth/refresh")
            assert refreshed.status_code == 200, refreshed.text
            assert refreshed.json()["user"]["id"] == brand_user["id"]

            # Dashboard profile APIs still create and return both account types.
            brand_profile_response = await brand_client.put(
                "/api/brands/me",
                json={"company_name": "Regression Brand Private Limited"},
            )
            assert brand_profile_response.status_code == 200, brand_profile_response.text
            brand_profile = brand_profile_response.json()["brand"]
            await database.brands.update_one(
                {"user_id": brand_user["id"]},
                {"$set": {"verification_status": "approved"}},
            )

            influencer_profile_response = await influencer_client.put(
                "/api/influencers/me",
                json={"username": "regression_creator", "category": "technology", "followers": 25000},
            )
            assert influencer_profile_response.status_code == 200, influencer_profile_response.text
            influencer_profile = influencer_profile_response.json()["influencer"]

            # Campaign, deal, notification, and stub escrow happy paths.
            campaign_response = await brand_client.post(
                "/api/campaigns",
                json={
                    "title": "Regression Campaign",
                    "description": "Production readiness regression",
                    "platform": "instagram",
                    "budget": 5000,
                },
            )
            assert campaign_response.status_code == 200, campaign_response.text
            campaign = campaign_response.json()["campaign"]
            activated = await brand_client.patch(f"/api/campaigns/{campaign['id']}/status?status=active")
            assert activated.status_code == 200, activated.text

            visible_campaigns = await influencer_client.get("/api/campaigns")
            assert visible_campaigns.status_code == 200
            assert any(row["id"] == campaign["id"] for row in visible_campaigns.json()["campaigns"])

            deal_response = await brand_client.post(
                "/api/deals",
                json={
                    "campaign_id": campaign["id"],
                    "influencer_id": influencer_profile["id"],
                    "amount": 4000,
                    "note": "Regression offer",
                },
            )
            assert deal_response.status_code == 200, deal_response.text
            deal = deal_response.json()["deal"]
            influencer_deals = await influencer_client.get("/api/deals")
            assert any(row["id"] == deal["id"] for row in influencer_deals.json()["deals"])

            accepted = await influencer_client.patch(
                f"/api/deals/{deal['id']}/status",
                json={"status": "offer_accepted"},
            )
            assert accepted.status_code == 200, accepted.text

            payment_response = await brand_client.post(
                "/api/payments/escrow",
                json={"deal_id": deal["id"], "amount": 4000},
            )
            assert payment_response.status_code == 200, payment_response.text
            assert payment_response.json()["payment"]["status"] == "escrowed"

            notifications = await influencer_client.get("/api/notifications")
            assert notifications.status_code == 200
            assert any(row["type"] == "deal.offer" for row in notifications.json()["notifications"])

            # Email/password login and logout remain functional.
            logged_out = await influencer_client.post("/api/auth/logout")
            assert logged_out.status_code == 200
            assert (await influencer_client.get("/api/auth/me")).status_code == 401
            login = await influencer_client.post(
                "/api/auth/login",
                json={"email": "regression-creator@example.com", "password": "RegressionPassword123!"},
            )
            assert login.status_code == 200, login.text
            assert login.json()["user"]["id"] == influencer_user["id"]
            assert "access_token" not in login.json()

            # Google login uses the same application JWT/cookie flow.
            monkeypatch.setattr(
                server._oauth,
                "verify_google_id_token",
                lambda _credential: {
                    "email": "regression-google@example.com",
                    "name": "Regression Google",
                    "picture": None,
                    "sub": "google-regression-sub",
                    "email_verified": True,
                },
            )
            google_login = await google_client.post(
                "/api/auth/google",
                json={"credential": "regression-google-credential"},
            )
            assert google_login.status_code == 200, google_login.text
            assert google_login.json()["user"]["role"] == "influencer"
            assert "access_token" not in google_login.json()
            assert (await google_client.get("/api/auth/me")).status_code == 200

            # Existing admin authentication and overview RBAC still work.
            now = datetime.now(timezone.utc)
            await database.users.insert_one(
                {
                    "email": "regression-admin@example.com",
                    "name": "Regression Admin",
                    "role": "admin",
                    "password_hash": server.hash_password("RegressionAdmin123!"),
                    "email_verified": True,
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                }
            )
            admin_login = await admin_client.post(
                "/api/auth/login",
                json={"email": "regression-admin@example.com", "password": "RegressionAdmin123!"},
            )
            assert admin_login.status_code == 200, admin_login.text
            assert admin_login.json()["user"]["role"] == "admin"
            overview = await admin_client.get("/api/admin/overview")
            assert overview.status_code == 200, overview.text
            assert "cards" in overview.json()

            # Ensure brand dashboard identity remained connected to its profile.
            current_brand = await brand_client.get("/api/brands/me")
            assert current_brand.status_code == 200
            assert current_brand.json()["brand"]["id"] == brand_profile["id"]

        mock_client.close()

    asyncio.run(scenario())
