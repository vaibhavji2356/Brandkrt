"""Creator-owned Instagram OAuth and read-only analytics integration."""
import os
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import InvalidToken
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import RedirectResponse
import security

# OAuth exchange URLs contain credentials; suppress HTTP client URL logging.
logging.getLogger("httpx").setLevel(logging.WARNING)


def now():
    return datetime.now(timezone.utc)


def cipher():
    try:
        return Fernet(os.environ["INSTAGRAM_TOKEN_ENCRYPTION_KEY"].encode())
    except (KeyError, ValueError):
        raise HTTPException(503, "Instagram connection is not configured")


def configured():
    return all(os.getenv(k) for k in ("INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "INSTAGRAM_REDIRECT_URI", "INSTAGRAM_TOKEN_ENCRYPTION_KEY"))


async def graph(client, path, token, **params):
    version = os.getenv("INSTAGRAM_API_VERSION", "v25.0")
    response = await client.get(f"https://graph.instagram.com/{version}/{path}", params=params,
                                headers={"Authorization": f"Bearer {token}"})
    if response.status_code >= 400:
        raise HTTPException(502, "Instagram data unavailable. Check permissions or reconnect your account.")
    return response.json()


def metric_values(payload):
    return {row["name"]: row.get("total_value", {}).get("value", sum(v.get("value", 0) for v in row.get("values", []) if isinstance(v.get("value"), (int, float))))
            for row in payload.get("data", [])}


def create_router(get_current_user, db):
    router = APIRouter(prefix="/instagram", tags=["instagram"])

    async def creator(user=Depends(get_current_user)):
        if user.get("role") != "influencer":
            raise HTTPException(403, "Creator account required")
        return str(user["_id"])

    async def sync(uid, connection):
        try:
            token = cipher().decrypt(connection["token"].encode()).decode()
        except InvalidToken:
            raise HTTPException(409, "Please reconnect Instagram")
        async with httpx.AsyncClient(timeout=25) as client:
            if connection["expires_at"].replace(tzinfo=timezone.utc) < now() + timedelta(days=10):
                refreshed = await client.get("https://graph.instagram.com/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": token})
                if refreshed.status_code >= 400:
                    raise HTTPException(409, "Please reconnect Instagram")
                result = refreshed.json()
                token = result["access_token"]
                await db.instagram_connections.update_one({"_id": uid}, {"$set": {"token": cipher().encrypt(token.encode()).decode(), "expires_at": now() + timedelta(seconds=result["expires_in"])}})
            profile = await graph(client, "me", token, fields="user_id,username,name,biography,profile_picture_url,followers_count,media_count,website")
            ig_user_id = profile["user_id"]
            media = await graph(client, f"{ig_user_id}/media", token, fields="id,caption,media_type,media_product_type,permalink,thumbnail_url,timestamp,like_count,comments_count", limit=25)
            warnings, posts = [], []
            for item in media.get("data", []):
                item["insights"] = {}
                try:
                    item["insights"] = metric_values(await graph(client, f"{item['id']}/insights", token, metric="views,reach,saved,shares"))
                except HTTPException:
                    warnings.append(f"Insights unavailable for {item['id']}")
                try:
                    comments = await graph(client, f"{item['id']}/comments", token, fields="id,text,timestamp", limit=50)
                    item["comments"] = comments.get("data", [])
                    item["comments_sample_count"] = len(item["comments"])
                except HTTPException:
                    item["comments"] = []
                    warnings.append(f"Comment text unavailable for {item['id']}")
                posts.append(item)
            account = {}
            try:
                account = metric_values(await graph(client, f"{ig_user_id}/insights", token, metric="reach", period="day", metric_type="total_value", since=int((now()-timedelta(days=30)).timestamp()), until=int(now().timestamp())))
            except HTTPException:
                warnings.append("Account reach unavailable")
        reels = [p["insights"]["views"] for p in posts if p.get("media_product_type") == "REELS" and "views" in p["insights"]]
        update = {"instagram": f"https://www.instagram.com/{profile['username']}/", "bio": profile.get("biography", ""), "profile_photo_url": profile.get("profile_picture_url", ""), "followers": profile.get("followers_count", 0), "instagram_connected": True, "updated_at": now()}
        if reels:
            update["avg_reel_views"] = round(sum(reels)/len(reels))
        if "reach" in account:
            update["monthly_reach"] = account["reach"]
        existing = await db.influencers.find_one({"user_id": uid})
        if not existing:
            update["username"] = profile["username"]
        await db.influencers.update_one({"user_id": uid}, {"$set": update, "$setOnInsert": {"user_id": uid, "created_at": now(), "verification_status": "not_started", "status": "active"}}, upsert=True)
        followers = profile.get("followers_count", 0)
        eligible = [p for p in posts if p.get("like_count") is not None and p.get("comments_count") is not None]
        engagement = round(sum(p["like_count"]+p["comments_count"] for p in eligible)/len(eligible)/followers*100, 2) if followers and eligible else None
        analytics = {"username": profile["username"], "followers": followers, "engagement_rate": engagement, "account": account, "posts": posts, "warnings": warnings, "synced_at": now(), "sample_limit": 25}
        await db.instagram_connections.update_one({"_id": uid}, {"$set": {"analytics": analytics}})
        return analytics

    @router.get("/status")
    async def status(uid=Depends(creator)):
        row = await db.instagram_connections.find_one({"_id": uid})
        return {"configured": configured(), "connected": bool(row), "analytics": (row or {}).get("analytics")}

    @router.post("/connect", dependencies=[Depends(security.limiter_dependency("instagram_connect", limit=10, window=600))])
    async def connect(uid=Depends(creator)):
        if not configured():
            raise HTTPException(503, "Instagram connection is not configured yet")
        cipher()
        state = secrets.token_urlsafe(32)
        await db.instagram_oauth_states.insert_one({"_id": state, "user_id": uid, "expires_at": now()+timedelta(minutes=10)})
        params = {"client_id": os.environ["INSTAGRAM_APP_ID"], "redirect_uri": os.environ["INSTAGRAM_REDIRECT_URI"], "response_type": "code", "scope": "instagram_business_basic,instagram_business_manage_insights,instagram_business_manage_comments", "state": state}
        return {"url": "https://www.instagram.com/oauth/authorize?" + urlencode(params)}

    @router.get("/callback")
    async def callback(state: str, code: str = "", error: str = ""):
        pending = await db.instagram_oauth_states.find_one_and_delete({"_id": state})
        if not pending or pending["expires_at"].replace(tzinfo=timezone.utc) < now():
            raise HTTPException(400, "Invalid or expired Instagram connection request")
        target = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/") + "/influencer/profile"
        if error or not code:
            return RedirectResponse(target + "?instagram=cancelled", status_code=303)
        from bson import ObjectId
        owner = await db.users.find_one({"_id": ObjectId(pending["user_id"]), "role": "influencer"})
        if not owner:
            raise HTTPException(403, "Creator account no longer available")
        stage = "authorization_code_exchange"
        provider_code = None
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.post("https://api.instagram.com/oauth/access_token", data={"client_id": os.environ["INSTAGRAM_APP_ID"], "client_secret": os.environ["INSTAGRAM_APP_SECRET"], "grant_type": "authorization_code", "redirect_uri": os.environ["INSTAGRAM_REDIRECT_URI"], "code": code})
                if response.status_code >= 400:
                    try:
                        provider_code = response.json().get("error", {}).get("code")
                    except (ValueError, AttributeError):
                        pass
                    raise HTTPException(502, "Instagram authorization failed")
                short = response.json()["access_token"]
                stage = "long_lived_token_exchange"
                response = await client.get("https://graph.instagram.com/access_token", params={"grant_type": "ig_exchange_token", "client_secret": os.environ["INSTAGRAM_APP_SECRET"], "access_token": short})
                if response.status_code >= 400:
                    raise HTTPException(502, "Instagram token exchange failed")
                result = response.json()
            uid = pending["user_id"]
            connection = {"token": cipher().encrypt(result["access_token"].encode()).decode(), "expires_at": now()+timedelta(seconds=result["expires_in"])}
            await db.instagram_connections.update_one({"_id": uid}, {"$set": connection}, upsert=True)
            stage = "profile_import"
            await sync(uid, connection)
        except (HTTPException, httpx.HTTPError, KeyError) as exc:
            # Store only safe diagnostic categories, never provider text, URLs or credentials.
            await db.instagram_oauth_errors.update_one({"_id": pending["user_id"]}, {"$set": {"stage": stage, "exception": type(exc).__name__, "provider_code": provider_code, "updated_at": now()}}, upsert=True)
            return RedirectResponse(target + "?instagram=failed", status_code=303)
        return RedirectResponse(target + "?instagram=connected", status_code=303)

    @router.post("/sync")
    async def resync(uid=Depends(creator)):
        connection = await db.instagram_connections.find_one({"_id": uid})
        if not connection:
            raise HTTPException(409, "Connect Instagram first")
        if connection.get("analytics", {}).get("synced_at", now()-timedelta(days=1)).replace(tzinfo=timezone.utc) > now()-timedelta(minutes=5):
            return {"analytics": connection["analytics"]}
        return {"analytics": await sync(uid, connection)}

    @router.delete("/connection")
    async def disconnect(uid=Depends(creator)):
        await db.instagram_connections.delete_one({"_id": uid})
        await db.instagram_oauth_states.delete_many({"user_id": uid})
        await db.influencers.update_one({"user_id": uid}, {"$set": {"instagram_connected": False}})
        return {"disconnected": True}

    return router
