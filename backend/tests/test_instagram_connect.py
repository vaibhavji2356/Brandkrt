import asyncio
import sys
from pathlib import Path
from datetime import timedelta

import httpx
from fastapi import FastAPI
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instagram_connect import create_router, now, metric_values


def test_metrics_total_value_and_missing():
    assert metric_values({"data": [{"name": "reach", "total_value": {"value": 42}}]}) == {"reach": 42}
    assert metric_values({}) == {}


def test_oauth_state_expiry_replay_and_role():
    async def run():
        db = AsyncMongoMockClient().test
        user = {"_id": "creator-one", "role": "influencer"}
        async def current():
            return user
        app = FastAPI()
        app.include_router(create_router(current, db))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            await db.instagram_oauth_states.insert_one({"_id": "valid", "user_id": "creator-one", "expires_at": now()+timedelta(minutes=1)})
            assert (await client.get("/instagram/callback?state=valid&error=denied")).status_code == 303
            assert (await client.get("/instagram/callback?state=valid&error=denied")).status_code == 400
            await db.instagram_oauth_states.insert_one({"_id": "expired", "user_id": "creator-one", "expires_at": now()-timedelta(minutes=1)})
            assert (await client.get("/instagram/callback?state=expired&error=denied")).status_code == 400
            await db.instagram_connections.insert_one({"_id": "creator-two", "token": "secret"})
            result = (await client.get("/instagram/status")).json()
            assert result["connected"] is False
            assert "secret" not in str(result)
            user["role"] = "brand"
            assert (await client.get("/instagram/status")).status_code == 403
    asyncio.run(run())


def test_sync_import_preserves_payouts_and_missing_metrics(monkeypatch):
    from cryptography.fernet import Fernet
    import instagram_connect
    key = Fernet.generate_key()
    monkeypatch.setenv("INSTAGRAM_TOKEN_ENCRYPTION_KEY", key.decode())
    calls = []
    async def fake_graph(client, path, token, **params):
        calls.append(path)
        if path == "me":
            return {"id": "scoped-id", "user_id": "ig1", "username": "creator", "biography": "Real bio", "followers_count": 100}
        if path.endswith("/media"):
            return {"data": [{"id": "reel1", "media_product_type": "REELS", "like_count": 10, "comments_count": 2}]}
        if path.endswith("/comments"):
            return {"data": [{"id": "c1", "text": "Nice"}]}
        return {"data": []}
    monkeypatch.setattr(instagram_connect, "graph", fake_graph)
    async def run():
        db = AsyncMongoMockClient().test
        async def current():
            return {"_id": "u1", "role": "influencer"}
        await db.influencers.insert_one({"user_id": "u1", "username": "chosen", "upi": "private@bank", "avg_reel_views": 888})
        await db.instagram_connections.insert_one({"_id": "u1", "token": Fernet(key).encrypt(b"secret").decode(), "expires_at": now()+timedelta(days=50)})
        app = FastAPI()
        app.include_router(create_router(current, db))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/instagram/sync")
            assert response.status_code == 200
            data = response.json()["analytics"]
            assert data["engagement_rate"] == 12
            assert "ig1/media" in calls
            assert "ig1/insights" in calls
            assert not any("scoped-id" in path for path in calls)
            assert data["posts"][0]["insights"] == {}
            assert "secret" not in response.text
            profile = await db.influencers.find_one({"user_id": "u1"})
            assert profile["username"] == "chosen"
            assert profile["upi"] == "private@bank"
            assert profile["bio"] == "Real bio"
            assert profile["avg_reel_views"] == 888
            count = len(calls)
            await client.post("/instagram/sync")
            assert len(calls) == count
            await client.delete("/instagram/connection")
            assert await db.instagram_connections.find_one({"_id": "u1"}) is None
    asyncio.run(run())
