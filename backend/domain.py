"""BrandKrt domain models, services and routes - Part 1B foundation.

Includes: Brand/Influencer profile docs, Campaigns, Deals, Payments (escrow),
Notifications, Messages (gated), Verification, Withdrawal, Reviews, Reports,
ActivityLogs, AdminLogs. Plus admin analytics & RBAC."""

from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Optional, List, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# These are wired in server.py
db = None  # type: ignore  # populated by init()
get_current_user = None  # type: ignore


def init(database, current_user_dep):
    global db, get_current_user
    db = database
    get_current_user = current_user_dep


# ---------------- helpers ----------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def doc_out(doc: dict) -> dict:
    if not doc:
        return doc
    d = dict(doc)
    d["id"] = str(d.pop("_id"))
    for k, v in list(d.items()):
        if isinstance(v, ObjectId):
            d[k] = str(v)
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


async def require_role(user: dict, *roles: str) -> None:
    if user.get("role") not in roles:
        raise HTTPException(status_code=403, detail="Forbidden")


async def log_activity(user_id: Optional[str], action: str, entity: str, entity_id: Optional[str] = None, meta: Optional[dict] = None):
    await db.activity_logs.insert_one({
        "user_id": user_id, "action": action, "entity": entity, "entity_id": entity_id,
        "meta": meta or {}, "created_at": now_utc(),
    })


async def log_admin(admin_id: str, action: str, target: str, meta: Optional[dict] = None):
    await db.admin_logs.insert_one({
        "admin_id": admin_id, "action": action, "target": target,
        "meta": meta or {}, "created_at": now_utc(),
    })


async def notify(user_id: str, type_: str, title: str, body: str = "", meta: Optional[dict] = None):
    await db.notifications.insert_one({
        "user_id": user_id, "type": type_, "title": title, "body": body,
        "meta": meta or {}, "read": False, "status": "active",
        "created_at": now_utc(), "updated_at": now_utc(),
    })


async def setup_indexes(database):
    await database.brands.create_index("user_id", unique=True)
    await database.influencers.create_index("user_id", unique=True)
    await database.influencers.create_index([("category", 1), ("country", 1)])
    await database.campaigns.create_index([("brand_id", 1), ("status", 1)])
    await database.deals.create_index([("campaign_id", 1), ("status", 1)])
    await database.deals.create_index([("influencer_id", 1), ("status", 1)])
    await database.payments.create_index([("deal_id", 1)])
    await database.transactions.create_index([("user_id", 1), ("created_at", -1)])
    await database.notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])
    await database.messages.create_index([("deal_id", 1), ("created_at", 1)])
    await database.verification_requests.create_index([("user_id", 1), ("status", 1)])
    await database.withdrawal_requests.create_index([("user_id", 1), ("status", 1)])
    await database.reviews.create_index([("target_user_id", 1)])
    await database.reports.create_index([("reporter_id", 1), ("status", 1)])
    await database.activity_logs.create_index([("user_id", 1), ("created_at", -1)])
    await database.admin_logs.create_index([("created_at", -1)])


# ---------------- routers ----------------
brand_router = APIRouter(prefix="/brands", tags=["brands"])
influencer_router = APIRouter(prefix="/influencers", tags=["influencers"])
campaign_router = APIRouter(prefix="/campaigns", tags=["campaigns"])
deal_router = APIRouter(prefix="/deals", tags=["deals"])
payment_router = APIRouter(prefix="/payments", tags=["payments"])
notif_router = APIRouter(prefix="/notifications", tags=["notifications"])
msg_router = APIRouter(prefix="/messages", tags=["messages"])
verify_router = APIRouter(prefix="/verification", tags=["verification"])
withdraw_router = APIRouter(prefix="/withdrawals", tags=["withdrawals"])
review_router = APIRouter(prefix="/reviews", tags=["reviews"])
report_router = APIRouter(prefix="/reports", tags=["reports"])
upload_router = APIRouter(prefix="/uploads", tags=["uploads"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


# ============== BRAND PROFILE ==============
class BrandProfileIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company_name: str
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    gst_number: Optional[str] = None
    registration_number: Optional[str] = None
    registration_proof_url: Optional[str] = None
    company_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pin_code: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    youtube: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    cover_url: Optional[str] = None
    product_categories: List[str] = []
    product_images: List[str] = []
    documents: List[str] = []
    bank_details: Optional[dict] = None
    upi: Optional[str] = None


@brand_router.put("/me")
async def upsert_my_brand(payload: BrandProfileIn, user: dict = Depends(lambda: None)):
    pass  # bound below in init via closure


@brand_router.get("/me")
async def get_my_brand(user: dict = Depends(lambda: None)):
    pass


@brand_router.get("")
async def list_brands(user: dict = Depends(lambda: None)):
    pass


# ============== INFLUENCER PROFILE ==============
class InfluencerProfileIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    username: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    profile_photo_url: Optional[str] = None
    cover_photo_url: Optional[str] = None
    bio: Optional[str] = None
    instagram: Optional[str] = None
    youtube: Optional[str] = None
    facebook: Optional[str] = None
    linkedin: Optional[str] = None
    website: Optional[str] = None
    category: Optional[str] = None
    followers: Optional[int] = 0
    avg_reel_views: Optional[int] = 0
    monthly_reach: Optional[int] = 0
    collab_price: Optional[float] = 0
    premium_plan: bool = False
    bank_details: Optional[dict] = None
    upi: Optional[str] = None
    gst: Optional[str] = None
    portfolio: List[dict] = []


# ============== CAMPAIGN ==============
class CampaignIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    description: Optional[str] = None
    platform: Literal["instagram", "youtube", "facebook", "linkedin", "tiktok", "other"]
    content_type: Optional[str] = None
    required_followers: Optional[int] = 0
    required_avg_views: Optional[int] = 0
    budget: float = Field(ge=0)
    payment_type: Optional[str] = None
    deadline: Optional[str] = None
    deliverables: List[str] = []
    product_details: Optional[str] = None
    product_images: List[str] = []
    promotion_links: List[str] = []
    visibility: Optional[str] = None
    target_categories: List[str] = []
    preferred_language: Optional[str] = None
    preferred_location: Optional[str] = None


# ============== DEAL ==============
DEAL_STATUSES = [
    "offer_sent", "offer_accepted",
    "product_shipped", "product_received",
    "content_in_progress", "content_submitted", "brand_review",
    "approved", "scheduled", "published",
    # legacy statuses kept for backwards compatibility
    "promotion_pending", "promotion_live",
    "completed", "cancelled",
]


class DealCreateIn(BaseModel):
    campaign_id: str
    influencer_id: str
    amount: float = Field(ge=0)
    note: Optional[str] = None


class DealStatusIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Literal[
        "offer_sent", "offer_accepted",
        "product_shipped", "product_received",
        "content_in_progress", "content_submitted", "brand_review",
        "approved", "scheduled", "published",
        "promotion_pending", "promotion_live",
        "completed", "cancelled",
    ]
    deliverables: Optional[dict] = None
    note: Optional[str] = None


# ============== PAYMENT (escrow stub) ==============
class PaymentCreateIn(BaseModel):
    deal_id: str
    amount: float = Field(ge=0)


class RazorpayVerifyIn(BaseModel):
    payment_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# ============== VERIFICATION ==============
class VerificationIn(BaseModel):
    kind: Literal["brand", "influencer"]
    documents: List[Any] = []
    notes: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None


class VerificationDecisionIn(BaseModel):
    decision: Literal["in_progress", "verified", "rejected"]
    notes: Optional[str] = None
    schedule_call_at: Optional[str] = None
    call_completed: bool = False


# ============== WITHDRAWAL ==============
class WithdrawalIn(BaseModel):
    amount: float = Field(gt=0)
    method: Literal["bank", "upi"]
    details: dict


class WithdrawalDecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: Optional[str] = None


class AdminUserStatusIn(BaseModel):
    suspended: bool = True


# ============== REVIEW / REPORT ==============
class ReviewIn(BaseModel):
    target_user_id: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class ReportIn(BaseModel):
    target_user_id: str
    reason: str
    details: Optional[str] = None


# ============== MESSAGES ==============
class MessageIn(BaseModel):
    deal_id: str
    body: str = Field(min_length=1, max_length=2000)


# ============== Concrete handlers (registered after init) ==============
def register_handlers():
    """Bind handlers using db and get_current_user from init()."""

    # ----- BRAND -----
    @brand_router.put("/me", operation_id="upsert_my_brand")
    async def _upsert_my_brand(payload: BrandProfileIn, user: dict = Depends(get_current_user)):
        await require_role(user, "brand", "admin")
        now = now_utc()
        data = payload.model_dump()
        data.update({"user_id": str(user["_id"]), "status": "active", "updated_at": now})
        existing = await db.brands.find_one({"user_id": str(user["_id"])})
        if existing:
            await db.brands.update_one({"_id": existing["_id"]}, {"$set": data})
            doc = await db.brands.find_one({"_id": existing["_id"]})
        else:
            data["created_at"] = now
            data["verification_status"] = "not_started"
            res = await db.brands.insert_one(data)
            doc = await db.brands.find_one({"_id": res.inserted_id})
        await log_activity(str(user["_id"]), "brand.upsert", "brand", str(doc["_id"]))
        return {"brand": doc_out(doc)}

    @brand_router.get("/me", operation_id="get_my_brand")
    async def _get_my_brand(user: dict = Depends(get_current_user)):
        doc = await db.brands.find_one({"user_id": str(user["_id"])})
        return {"brand": doc_out(doc) if doc else None}

    @brand_router.get("", operation_id="list_brands")
    async def _list_brands(user: dict = Depends(get_current_user), q: Optional[str] = None, limit: int = 50):
        query = {"status": "active"}
        if q:
            query["company_name"] = {"$regex": q, "$options": "i"}
        cur = db.brands.find(query).limit(min(limit, 100))
        return {"brands": [doc_out(x) async for x in cur]}

    @brand_router.get("/{brand_id}", operation_id="get_brand")
    async def _get_brand(brand_id: str, user: dict = Depends(get_current_user)):
        doc = await db.brands.find_one({"_id": oid(brand_id)})
        if not doc:
            raise HTTPException(404, "Brand not found")
        return {"brand": doc_out(doc)}

    # ----- INFLUENCER -----
    @influencer_router.put("/me")
    async def _upsert_inf(payload: InfluencerProfileIn, user: dict = Depends(get_current_user)):
        await require_role(user, "influencer", "admin")
        now = now_utc()
        data = payload.model_dump()
        data.update({"user_id": str(user["_id"]), "status": "active", "updated_at": now})
        existing = await db.influencers.find_one({"user_id": str(user["_id"])})
        if existing:
            await db.influencers.update_one({"_id": existing["_id"]}, {"$set": data})
            doc = await db.influencers.find_one({"_id": existing["_id"]})
        else:
            data["created_at"] = now
            data["verification_status"] = "not_started"
            res = await db.influencers.insert_one(data)
            doc = await db.influencers.find_one({"_id": res.inserted_id})
        await log_activity(str(user["_id"]), "influencer.upsert", "influencer", str(doc["_id"]))
        return {"influencer": doc_out(doc)}

    @influencer_router.get("/me")
    async def _get_my_inf(user: dict = Depends(get_current_user)):
        doc = await db.influencers.find_one({"user_id": str(user["_id"])})
        return {"influencer": doc_out(doc) if doc else None}

    @influencer_router.get("")
    async def _list_inf(user: dict = Depends(get_current_user), q: Optional[str] = None, category: Optional[str] = None, limit: int = 50):
        query: dict = {"status": "active"}
        if q:
            query["username"] = {"$regex": q, "$options": "i"}
        if category:
            query["category"] = category
        cur = db.influencers.find(query).limit(min(limit, 100))
        return {"influencers": [doc_out(x) async for x in cur]}

    @influencer_router.get("/{inf_id}")
    async def _get_inf(inf_id: str, user: dict = Depends(get_current_user)):
        doc = await db.influencers.find_one({"_id": oid(inf_id)})
        if not doc:
            raise HTTPException(404, "Influencer not found")
        return {"influencer": doc_out(doc)}

    # ----- CAMPAIGN -----
    @campaign_router.post("")
    async def _create_campaign(payload: CampaignIn, user: dict = Depends(get_current_user)):
        await require_role(user, "brand", "admin")
        brand = await db.brands.find_one({"user_id": str(user["_id"])})
        if not brand and user.get("role") != "admin":
            raise HTTPException(400, "Create your brand profile first")
        now = now_utc()
        doc = {**payload.model_dump(), "brand_id": str(brand["_id"]) if brand else None,
               "status": "draft", "progress": 0, "analytics": {}, "created_at": now, "updated_at": now}
        res = await db.campaigns.insert_one(doc)
        await log_activity(str(user["_id"]), "campaign.create", "campaign", str(res.inserted_id))
        return {"campaign": doc_out(await db.campaigns.find_one({"_id": res.inserted_id}))}

    @campaign_router.get("")
    async def _list_campaigns(user: dict = Depends(get_current_user), status: Optional[str] = None, limit: int = 50):
        query = {}
        if user.get("role") == "brand":
            brand = await db.brands.find_one({"user_id": str(user["_id"])})
            query["brand_id"] = str(brand["_id"]) if brand else "__none__"
        if status:
            query["status"] = status
        cur = db.campaigns.find(query).sort("created_at", -1).limit(min(limit, 100))
        return {"campaigns": [doc_out(x) async for x in cur]}

    @campaign_router.get("/{cid}")
    async def _get_campaign(cid: str, user: dict = Depends(get_current_user)):
        doc = await db.campaigns.find_one({"_id": oid(cid)})
        if not doc:
            raise HTTPException(404, "Campaign not found")
        return {"campaign": doc_out(doc)}

    @campaign_router.patch("/{cid}/status")
    async def _campaign_status(cid: str, status: str, user: dict = Depends(get_current_user)):
        if status not in ["draft", "active", "paused", "completed", "cancelled"]:
            raise HTTPException(400, "Invalid status")
        await db.campaigns.update_one({"_id": oid(cid)}, {"$set": {"status": status, "updated_at": now_utc()}})
        return {"success": True}

    # ----- DEALS -----
    @deal_router.post("")
    async def _create_deal(payload: DealCreateIn, user: dict = Depends(get_current_user)):
        await require_role(user, "brand", "admin")
        campaign = await db.campaigns.find_one({"_id": oid(payload.campaign_id)})
        if not campaign:
            raise HTTPException(404, "Campaign not found")
        now = now_utc()
        doc = {"campaign_id": payload.campaign_id, "brand_id": campaign.get("brand_id"),
               "influencer_id": payload.influencer_id, "amount": payload.amount,
               "note": payload.note, "status": "offer_sent",
               "created_at": now, "updated_at": now}
        res = await db.deals.insert_one(doc)
        # notify influencer (best-effort)
        inf = await db.influencers.find_one({"_id": oid(payload.influencer_id)})
        if inf:
            await notify(inf["user_id"], "deal.offer", "New campaign offer", f"You received a new offer.", {"deal_id": str(res.inserted_id)})
        await log_activity(str(user["_id"]), "deal.create", "deal", str(res.inserted_id))
        return {"deal": doc_out(await db.deals.find_one({"_id": res.inserted_id}))}

    @deal_router.get("")
    async def _list_deals(user: dict = Depends(get_current_user), status: Optional[str] = None):
        query = {}
        if status:
            query["status"] = status
        if user.get("role") == "influencer":
            inf = await db.influencers.find_one({"user_id": str(user["_id"])})
            query["influencer_id"] = str(inf["_id"]) if inf else "__none__"
        elif user.get("role") == "brand":
            brand = await db.brands.find_one({"user_id": str(user["_id"])})
            query["brand_id"] = str(brand["_id"]) if brand else "__none__"
        cur = db.deals.find(query).sort("created_at", -1).limit(100)
        return {"deals": [doc_out(x) async for x in cur]}

    @deal_router.patch("/{did}/status")
    async def _deal_status(did: str, payload: DealStatusIn, user: dict = Depends(get_current_user)):
        deal = await db.deals.find_one({"_id": oid(did)})
        if not deal:
            raise HTTPException(404, "Deal not found")
        now = now_utc()
        update = {"status": payload.status, "updated_at": now}
        if payload.deliverables is not None:
            merged = {**(deal.get("deliverables_links") or {}), **{k: v for k, v in payload.deliverables.items() if v is not None}}
            update["deliverables_links"] = merged
        if payload.note is not None:
            update["last_note"] = payload.note
        # append a tiny history entry
        history_entry = {"status": payload.status, "by": str(user["_id"]), "role": user.get("role"), "at": now}
        await db.deals.update_one(
            {"_id": oid(did)},
            {"$set": update, "$push": {"status_history": history_entry}},
        )

        # ----- notifications on key transitions -----
        async def _brand_user_id():
            if not deal.get("brand_id"):
                return None
            brand = await db.brands.find_one({"_id": oid(deal["brand_id"])})
            return brand.get("user_id") if brand else None

        async def _inf_user_id():
            if not deal.get("influencer_id"):
                return None
            inf = await db.influencers.find_one({"_id": oid(deal["influencer_id"])})
            return inf.get("user_id") if inf else None

        prev = deal.get("status")
        meta = {"deal_id": did}
        try:
            if payload.status == "offer_accepted" and prev != "offer_accepted":
                buid = await _brand_user_id()
                if buid:
                    await notify(buid, "deal.accepted", "Offer accepted",
                                 "A creator accepted your campaign offer.", meta)
            elif payload.status == "cancelled" and prev != "cancelled":
                # treat rejection (creator side) vs general cancellation
                other = await _brand_user_id() if user.get("role") == "influencer" else await _inf_user_id()
                if other:
                    title = "Offer declined" if user.get("role") == "influencer" else "Deal cancelled"
                    await notify(other, "deal.cancelled", title, "The deal has been cancelled.", meta)
            elif payload.status == "product_shipped":
                iuid = await _inf_user_id()
                if iuid:
                    await notify(iuid, "deal.shipped", "Product shipped",
                                 "The brand has shipped the product for your campaign.", meta)
            elif payload.status == "content_submitted":
                buid = await _brand_user_id()
                if buid:
                    await notify(buid, "deal.submission", "Content submitted for review",
                                 "The creator has submitted content for your campaign.", meta)
            elif payload.status == "approved":
                iuid = await _inf_user_id()
                if iuid:
                    await notify(iuid, "deal.approved", "Content approved",
                                 "Great news — the brand approved your content.", meta)
            elif payload.status == "published":
                buid = await _brand_user_id()
                if buid:
                    await notify(buid, "deal.published", "Post is live",
                                 "The creator has published the campaign content.", meta)
            elif payload.status == "completed":
                iuid = await _inf_user_id()
                if iuid:
                    await notify(iuid, "deal.completed", "Deal completed",
                                 "Your campaign has been marked completed.", meta)
        except Exception:
            pass

        await log_activity(str(user["_id"]), "deal.status", "deal", did, {"to": payload.status})
        fresh = await db.deals.find_one({"_id": oid(did)})
        return {"success": True, "status": payload.status, "deal": doc_out(fresh)}

    # ----- PAYMENTS (pluggable provider — Part 5) -----
    @payment_router.post("/escrow")
    async def _escrow(payload: PaymentCreateIn, user: dict = Depends(get_current_user)):
        await require_role(user, "brand", "admin")
        deal = await db.deals.find_one({"_id": oid(payload.deal_id)})
        if not deal:
            raise HTTPException(404, "Deal not found")
        existing = await db.payments.find_one({
            "deal_id": payload.deal_id,
            "status": {"$in": ["pending", "escrowed", "released"]},
        })
        if existing:
            out = doc_out(existing)
            if existing.get("provider") == "razorpay" and existing.get("status") == "pending":
                out["checkout"] = {
                    "provider": "razorpay",
                    "key_id": existing.get("provider_key_id"),
                    "order_id": existing.get("transaction_id"),
                    "amount": existing.get("amount_subunits"),
                    "currency": existing.get("currency", "INR"),
                }
            return {"payment": out}
        now = now_utc()
        platform_fee = round(payload.amount * 0.08, 2)
        influencer_earning = round(payload.amount - platform_fee, 2)
        # delegate to provider (stub by default; razorpay/stripe when configured)
        try:
            import payments as _payments  # noqa: WPS433
            pr = _payments.get_provider().create_escrow(amount=payload.amount, deal_id=payload.deal_id)
            txid = pr.get("transaction_id") or secrets.token_hex(8).upper()
            client_secret = pr.get("client_secret")
            provider_name = pr.get("provider", "stub")
            provider_status = pr.get("status", "escrowed")
        except Exception as exc:
            configured_provider = (os.environ.get("PAYMENT_PROVIDER") or "stub").lower()
            if configured_provider in {"stripe", "razorpay"}:
                raise HTTPException(503, f"{configured_provider.title()} payment provider is not configured correctly") from exc
            txid = secrets.token_hex(8).upper()
            client_secret = None
            provider_name = "stub"
            provider_status = "escrowed"
            pr = {}
        is_razorpay_pending = provider_name == "razorpay" and provider_status == "pending"
        doc = {"deal_id": payload.deal_id, "amount": payload.amount,
               "platform_fee": platform_fee, "influencer_earning": influencer_earning,
               "release_status": "pending" if is_razorpay_pending else "held", "transaction_id": txid,
               "provider": provider_name, "client_secret": client_secret,
               "status": "pending" if is_razorpay_pending else "escrowed",
               "currency": pr.get("currency", "INR"),
               "amount_subunits": pr.get("amount_subunits"),
               "provider_key_id": pr.get("key_id"),
               "receipt": pr.get("receipt"),
               "created_at": now, "updated_at": now}
        res = await db.payments.insert_one(doc)
        await db.transactions.insert_one({
            "user_id": str(user["_id"]), "type": "escrow_in", "amount": payload.amount,
            "ref": str(res.inserted_id), "status": "pending" if is_razorpay_pending else "ok", "created_at": now,
        })
        payment_out = doc_out(await db.payments.find_one({"_id": res.inserted_id}))
        if is_razorpay_pending:
            payment_out["checkout"] = {
                "provider": "razorpay",
                "key_id": pr.get("key_id"),
                "order_id": txid,
                "amount": pr.get("amount_subunits"),
                "currency": pr.get("currency", "INR"),
            }
        return {"payment": payment_out}

    @payment_router.post("/razorpay/verify")
    async def _razorpay_verify(payload: RazorpayVerifyIn, user: dict = Depends(get_current_user)):
        await require_role(user, "brand", "admin")
        pay = await db.payments.find_one({"_id": oid(payload.payment_id)})
        if not pay:
            raise HTTPException(404, "Payment not found")
        if pay.get("provider") != "razorpay":
            raise HTTPException(400, "Payment is not a Razorpay payment")
        if pay.get("transaction_id") != payload.razorpay_order_id:
            raise HTTPException(400, "Razorpay order does not match this payment")
        try:
            import payments as _payments  # noqa: WPS433
            ok = _payments.get_provider().verify(
                order_id=payload.razorpay_order_id,
                payment_id=payload.razorpay_payment_id,
                signature=payload.razorpay_signature,
            )
        except Exception as exc:
            raise HTTPException(503, "Razorpay payment provider is not configured correctly") from exc
        if not ok:
            await db.payments.update_one(
                {"_id": oid(payload.payment_id)},
                {"$set": {"status": "verification_failed", "updated_at": now_utc()}},
            )
            raise HTTPException(400, "Razorpay signature verification failed")
        now = now_utc()
        await db.payments.update_one(
            {"_id": oid(payload.payment_id)},
            {"$set": {
                "status": "escrowed",
                "release_status": "held",
                "provider_payment_id": payload.razorpay_payment_id,
                "verified_at": now,
                "updated_at": now,
            }},
        )
        await db.transactions.update_one(
            {"ref": payload.payment_id, "type": "escrow_in"},
            {"$set": {"status": "ok", "provider_payment_id": payload.razorpay_payment_id, "updated_at": now}},
        )
        fresh = await db.payments.find_one({"_id": oid(payload.payment_id)})
        return {"success": True, "payment": doc_out(fresh)}

    @payment_router.post("/{pid}/release")
    async def _release(pid: str, user: dict = Depends(get_current_user)):
        await require_role(user, "admin", "brand")
        pay = await db.payments.find_one({"_id": oid(pid)})
        if not pay:
            raise HTTPException(404, "Payment not found")
        if pay.get("status") == "pending":
            raise HTTPException(400, "Payment must be completed before it can be released")
        # ask provider to capture (no-op for stub)
        try:
            import payments as _payments  # noqa: WPS433
            _payments.get_provider().release(transaction_id=pay.get("transaction_id") or "")
        except Exception:
            pass
        await db.payments.update_one(
            {"_id": oid(pid)},
            {"$set": {"release_status": "released", "status": "released", "updated_at": now_utc()}},
        )
        # notify the creator that funds are released
        try:
            deal = await db.deals.find_one({"_id": oid(pay["deal_id"])}) if pay.get("deal_id") else None
            if deal and deal.get("influencer_id"):
                inf = await db.influencers.find_one({"_id": oid(deal["influencer_id"])})
                if inf:
                    earning = pay.get("influencer_earning", 0)
                    await notify(
                        inf["user_id"],
                        "payment.released",
                        "Payment released",
                        f"Your earnings of \u20b9{earning} for this campaign are now in your wallet.",
                        {"deal_id": str(deal["_id"]), "payment_id": pid},
                    )
        except Exception:
            pass
        await log_admin(str(user["_id"]), "payment.release", pid)
        return {"success": True}

    @payment_router.get("")
    async def _list_payments(user: dict = Depends(get_current_user)):
        cur = db.payments.find({}).sort("created_at", -1).limit(100)
        return {"payments": [doc_out(x) async for x in cur]}

    # ----- NOTIFICATIONS -----
    @notif_router.get("")
    async def _list_notifs(user: dict = Depends(get_current_user)):
        cur = db.notifications.find({"user_id": str(user["_id"])}).sort("created_at", -1).limit(50)
        return {"notifications": [doc_out(x) async for x in cur]}

    @notif_router.post("/{nid}/read")
    async def _read_notif(nid: str, user: dict = Depends(get_current_user)):
        await db.notifications.update_one(
            {"_id": oid(nid), "user_id": str(user["_id"])}, {"$set": {"read": True}}
        )
        return {"success": True}

    # ----- MESSAGES (locked until payment) -----
    @msg_router.get("/{deal_id}")
    async def _list_msgs(deal_id: str, user: dict = Depends(get_current_user)):
        pay = await db.payments.find_one({"deal_id": deal_id, "status": {"$in": ["escrowed", "released"]}})
        if not pay:
            raise HTTPException(403, "Messaging is locked until payment is completed")
        cur = db.messages.find({"deal_id": deal_id}).sort("created_at", 1).limit(500)
        return {"messages": [doc_out(x) async for x in cur]}

    @msg_router.post("")
    async def _send_msg(payload: MessageIn, user: dict = Depends(get_current_user)):
        pay = await db.payments.find_one({"deal_id": payload.deal_id, "status": {"$in": ["escrowed", "released"]}})
        if not pay:
            raise HTTPException(403, "Messaging is locked until payment is completed")
        doc = {"deal_id": payload.deal_id, "user_id": str(user["_id"]),
               "body": payload.body, "status": "sent", "created_at": now_utc()}
        res = await db.messages.insert_one(doc)
        return {"message": doc_out(await db.messages.find_one({"_id": res.inserted_id}))}

    # ----- VERIFICATION -----
    @verify_router.post("")
    async def _submit_verif(payload: VerificationIn, user: dict = Depends(get_current_user)):
        if user.get("role") not in {payload.kind, "admin"}:
            raise HTTPException(403, "Verification kind does not match your account role")

        existing = await db.verification_requests.find_one({
            "user_id": str(user["_id"]),
            "kind": payload.kind,
            "status": {"$in": ["pending", "in_progress"]},
        })
        if existing:
            return {"request": doc_out(existing), "already_pending": True}

        now = now_utc()
        doc = {"user_id": str(user["_id"]), "kind": payload.kind,
               "documents": payload.documents, "notes": payload.notes,
               "contact_name": payload.contact_name, "contact_phone": payload.contact_phone,
               "status": "pending", "created_at": now, "updated_at": now}
        res = await db.verification_requests.insert_one(doc)
        collection = db.brands if payload.kind == "brand" else db.influencers
        await collection.update_one(
            {"user_id": str(user["_id"])},
            {"$set": {"verification_status": "pending", "updated_at": now}},
        )
        await log_activity(str(user["_id"]), "verification.submit", "verification", str(res.inserted_id))
        return {"request": doc_out(await db.verification_requests.find_one({"_id": res.inserted_id}))}

    @verify_router.get("/mine")
    async def _my_verif(user: dict = Depends(get_current_user)):
        cur = db.verification_requests.find({"user_id": str(user["_id"])}).sort("created_at", -1)
        return {"requests": [doc_out(x) async for x in cur]}

    # ----- WITHDRAWAL -----
    @withdraw_router.post("")
    async def _wd(payload: WithdrawalIn, user: dict = Depends(get_current_user)):
        now = now_utc()
        doc = {"user_id": str(user["_id"]), "amount": payload.amount,
               "method": payload.method, "details": payload.details,
               "status": "pending", "created_at": now, "updated_at": now}
        res = await db.withdrawal_requests.insert_one(doc)
        return {"request": doc_out(await db.withdrawal_requests.find_one({"_id": res.inserted_id}))}

    @withdraw_router.get("/mine")
    async def _my_wd(user: dict = Depends(get_current_user)):
        cur = db.withdrawal_requests.find({"user_id": str(user["_id"])}).sort("created_at", -1)
        return {"requests": [doc_out(x) async for x in cur]}

    # ----- REVIEWS / REPORTS -----
    @review_router.post("")
    async def _review(payload: ReviewIn, user: dict = Depends(get_current_user)):
        doc = {**payload.model_dump(), "reviewer_id": str(user["_id"]),
               "status": "active", "created_at": now_utc(), "updated_at": now_utc()}
        res = await db.reviews.insert_one(doc)
        return {"review": doc_out(await db.reviews.find_one({"_id": res.inserted_id}))}

    @report_router.post("")
    async def _report(payload: ReportIn, user: dict = Depends(get_current_user)):
        doc = {**payload.model_dump(), "reporter_id": str(user["_id"]),
               "status": "open", "created_at": now_utc(), "updated_at": now_utc()}
        res = await db.reports.insert_one(doc)
        return {"report": doc_out(await db.reports.find_one({"_id": res.inserted_id}))}

    # ----- UPLOADS (Cloudinary in prod, local fallback in dev — Part 5) -----
    UPLOAD_ROOT = os.environ.get("UPLOAD_ROOT", "./uploads")
    FOLDERS = ["profiles", "brand_logos", "products", "verification", "contracts", "invoices", "chat"]
    for f in FOLDERS:
        os.makedirs(os.path.join(UPLOAD_ROOT, f), exist_ok=True)

    @upload_router.post("/{folder}")
    async def _upload(folder: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
        if folder not in FOLDERS:
            raise HTTPException(400, "Unknown folder")
        data = await file.read()
        try:
            import storage  # noqa: WPS433
            res = await storage.save_upload(file_bytes=data, original_name=file.filename or "file", folder=folder)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Upload failed: {e}")
        return {
            "url": res["url"],
            "folder": folder,
            "filename": res.get("name") or file.filename,
            "kind": res.get("kind"),
            "size": res.get("size"),
            "provider": res.get("provider"),
        }

    # ----- ADMIN -----
    async def _ensure_admin(user: dict):
        await require_role(user, "admin")

    @admin_router.get("/overview")
    async def _admin_overview(user: dict = Depends(get_current_user)):
        await _ensure_admin(user)
        from datetime import timedelta
        now = now_utc()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today.replace(day=1)
        users_total = await db.users.count_documents({})
        brands_total = await db.brands.count_documents({})
        infs_total = await db.influencers.count_documents({})
        pending_verif = await db.verification_requests.count_documents({"status": "pending"})
        pending_wd = await db.withdrawal_requests.count_documents({"status": "pending"})
        running = await db.campaigns.count_documents({"status": "active"})
        completed = await db.campaigns.count_documents({"status": "completed"})
        cancelled = await db.campaigns.count_documents({"status": "cancelled"})

        # revenue from platform_fee
        pipeline_today = [{"$match": {"created_at": {"$gte": today}}},
                          {"$group": {"_id": None, "rev": {"$sum": "$platform_fee"}}}]
        pipeline_month = [{"$match": {"created_at": {"$gte": month_start}}},
                          {"$group": {"_id": None, "rev": {"$sum": "$platform_fee"}}}]
        td = await db.payments.aggregate(pipeline_today).to_list(1)
        mo = await db.payments.aggregate(pipeline_month).to_list(1)
        rev_today = (td[0]["rev"] if td else 0) or 0
        rev_month = (mo[0]["rev"] if mo else 0) or 0

        # 12-week growth charts
        weeks = []
        for i in range(11, -1, -1):
            start = now - timedelta(weeks=i + 1)
            end = now - timedelta(weeks=i)
            uc = await db.users.count_documents({"created_at": {"$gte": start, "$lt": end}})
            cc = await db.campaigns.count_documents({"created_at": {"$gte": start, "$lt": end}})
            rp = await db.payments.aggregate([
                {"$match": {"created_at": {"$gte": start, "$lt": end}}},
                {"$group": {"_id": None, "rev": {"$sum": "$platform_fee"}}}
            ]).to_list(1)
            weeks.append({
                "label": start.strftime("%b %d"),
                "users": uc,
                "campaigns": cc,
                "revenue": (rp[0]["rev"] if rp else 0) or 0,
            })

        return {
            "cards": {
                "total_users": users_total, "total_brands": brands_total,
                "total_influencers": infs_total,
                "revenue_today": rev_today, "revenue_month": rev_month,
                "pending_verification": pending_verif, "pending_withdrawals": pending_wd,
                "running_campaigns": running, "completed_campaigns": completed,
                "cancelled_campaigns": cancelled,
            },
            "charts": {"weekly": weeks},
        }

    @admin_router.get("/users")
    async def _admin_users(user: dict = Depends(get_current_user), role: Optional[str] = None, q: Optional[str] = None, limit: int = 50):
        await _ensure_admin(user)
        query: dict = {}
        if role:
            query["role"] = role
        if q:
            query["$or"] = [{"email": {"$regex": q, "$options": "i"}}, {"name": {"$regex": q, "$options": "i"}}]
        cur = db.users.find(query, {"password_hash": 0}).sort("created_at", -1).limit(min(limit, 200))
        rows = []
        async for row in cur:
            out = doc_out(row)
            out["status"] = out.get("status") or "active"
            rows.append(out)
        return {"users": rows}

    async def _admin_user_detail_out(uid: str) -> dict:
        target = await db.users.find_one({"_id": oid(uid)}, {"password_hash": 0})
        if not target:
            raise HTTPException(404, "User not found")
        target_out = doc_out(target)
        target_out["status"] = target_out.get("status") or "active"
        profile = None
        if target.get("role") == "brand":
            profile = await db.brands.find_one({"user_id": uid})
        elif target.get("role") == "influencer":
            profile = await db.influencers.find_one({"user_id": uid})

        activity = await db.activity_logs.find({"user_id": uid}).sort("created_at", -1).limit(100).to_list(100)
        admin_history = await db.admin_logs.find({"target": uid}).sort("created_at", -1).limit(100).to_list(100)
        verifications = await db.verification_requests.find({"user_id": uid}).sort("created_at", -1).limit(20).to_list(20)
        withdrawals = await db.withdrawal_requests.find({"user_id": uid}).sort("created_at", -1).limit(20).to_list(20)
        notifications = await db.notifications.find({"user_id": uid}).sort("created_at", -1).limit(20).to_list(20)
        deals = await db.deals.find({"$or": [{"brand_id": uid}, {"influencer_id": uid}, {"user_id": uid}]}).sort("created_at", -1).limit(20).to_list(20)
        campaigns = await db.campaigns.find({"$or": [{"brand_id": uid}, {"user_id": uid}]}).sort("created_at", -1).limit(20).to_list(20)
        payments = await db.payments.find({"$or": [{"brand_id": uid}, {"influencer_id": uid}, {"user_id": uid}]}).sort("created_at", -1).limit(20).to_list(20)

        return {
            "user": target_out,
            "profile": doc_out(profile) if profile else None,
            "history": {
                "activity_logs": [doc_out(x) for x in activity],
                "admin_logs": [doc_out(x) for x in admin_history],
                "verification_requests": [doc_out(x) for x in verifications],
                "withdrawals": [doc_out(x) for x in withdrawals],
                "notifications": [doc_out(x) for x in notifications],
                "deals": [doc_out(x) for x in deals],
                "campaigns": [doc_out(x) for x in campaigns],
                "payments": [doc_out(x) for x in payments],
            },
        }

    @admin_router.get("/users/{uid}")
    async def _admin_user_detail(uid: str, user: dict = Depends(get_current_user)):
        await _ensure_admin(user)
        return await _admin_user_detail_out(uid)

    @admin_router.post("/users/{uid}/suspend")
    async def _admin_user_suspend(uid: str, payload: AdminUserStatusIn, user: dict = Depends(get_current_user)):
        await _ensure_admin(user)
        if uid == str(user["_id"]):
            raise HTTPException(400, "You cannot suspend your own admin account")
        status = "suspended" if payload.suspended else "active"
        now = now_utc()
        res = await db.users.update_one({"_id": oid(uid)}, {"$set": {"status": status, "updated_at": now}})
        if not res.matched_count:
            raise HTTPException(404, "User not found")
        await db.brands.update_one({"user_id": uid}, {"$set": {"status": status, "updated_at": now}})
        await db.influencers.update_one({"user_id": uid}, {"$set": {"status": status, "updated_at": now}})
        await log_admin(str(user["_id"]), f"user.{status}", uid)
        return await _admin_user_detail_out(uid)

    @admin_router.delete("/users/{uid}")
    async def _admin_user_delete(uid: str, user: dict = Depends(get_current_user)):
        await _ensure_admin(user)
        if uid == str(user["_id"]):
            raise HTTPException(400, "You cannot delete your own admin account")
        target = await db.users.find_one({"_id": oid(uid)}, {"password_hash": 0})
        if not target:
            raise HTTPException(404, "User not found")
        email = (target.get("email") or "").lower().strip()
        email_match = {"email": email} if email else {"_id": None}
        await log_admin(str(user["_id"]), "user.delete", "erased-user", {"role": target.get("role")})

        await db.users.delete_many({"$or": [{"_id": oid(uid)}, email_match]})
        await db.brands.delete_many({"user_id": uid})
        await db.influencers.delete_many({"user_id": uid})
        await db.verification_requests.delete_many({"user_id": uid})
        await db.withdrawal_requests.delete_many({"user_id": uid})
        await db.notifications.delete_many({"user_id": uid})
        await db.activity_logs.delete_many({"user_id": uid})
        await db.admin_logs.delete_many({"target": uid})
        await db.password_reset_tokens.delete_many({"$or": [{"user_id": uid}, email_match]})
        await db.verification_tokens.delete_many({"$or": [{"user_id": uid}, email_match]})
        await db.registration_otps.delete_many(email_match)
        if email:
            await db.login_attempts.delete_many({"identifier": {"$regex": f":{re.escape(email)}$"}})
        await db.saved_influencers.delete_many({"$or": [{"user_id": uid}, {"influencer_id": uid}]})
        await db.campaigns.delete_many({"$or": [{"user_id": uid}, {"brand_id": uid}, {"creator_id": uid}, {"influencer_id": uid}]})
        await db.deals.delete_many({"$or": [{"user_id": uid}, {"brand_id": uid}, {"creator_id": uid}, {"influencer_id": uid}]})
        await db.payments.delete_many({"$or": [{"user_id": uid}, {"brand_id": uid}, {"creator_id": uid}, {"influencer_id": uid}]})
        await db.messages.delete_many({"user_id": uid})
        await db.conversations.delete_many({"$or": [{"user_id": uid}, {"participant_ids": uid}, {"participants": uid}]})
        await db.collaborations.delete_many({"$or": [{"user_id": uid}, {"from_user_id": uid}, {"to_user_id": uid}, {"creator_id": uid}]})
        await db.agreements.delete_many({"$or": [{"user_id": uid}, {"brand_id": uid}, {"influencer_id": uid}, {"creator_id": uid}]})
        await db.reviews.delete_many({"$or": [{"user_id": uid}, {"reviewer_id": uid}, {"target_user_id": uid}]})
        await db.reports.delete_many({"$or": [{"user_id": uid}, {"reporter_id": uid}, {"target_user_id": uid}]})
        remaining = await db.users.count_documents(email_match) if email else 0
        return {"success": True, "erased": True, "remaining_users_with_email": remaining}

    async def _verification_out(req: dict) -> dict:
        out = doc_out(req)
        target_user = await db.users.find_one({"_id": oid(req["user_id"])}, {"password_hash": 0})
        profile_collection = db.brands if req.get("kind") == "brand" else db.influencers
        profile = await profile_collection.find_one({"user_id": req["user_id"]})
        if target_user:
            out["user"] = {
                "id": str(target_user["_id"]),
                "name": req.get("contact_name") or target_user.get("name") or target_user.get("email", "").split("@")[0],
                "email": target_user.get("email"),
                "phone": req.get("contact_phone") or target_user.get("phone") or (profile or {}).get("phone"),
            }
        if profile:
            display_name = (
                profile.get("username")
                or profile.get("company_name")
                or profile.get("brand_name")
                or out.get("user", {}).get("name")
            )
            out["profile"] = {
                "name": display_name,
                "phone": profile.get("phone"),
                "city": profile.get("city"),
                "category": profile.get("category") or profile.get("industry"),
            }
            if out.get("user") and not out["user"].get("phone"):
                out["user"]["phone"] = profile.get("phone")
        return out

    @admin_router.get("/verification")
    async def _admin_verif(user: dict = Depends(get_current_user), status: str = "pending"):
        await _ensure_admin(user)
        cur = db.verification_requests.find({"status": status}).sort("created_at", -1).limit(100)
        rows = []
        async for req in cur:
            rows.append(await _verification_out(req))
        return {"requests": rows}

    @admin_router.post("/verification/{rid}/decision")
    async def _admin_decide(rid: str, payload: VerificationDecisionIn, user: dict = Depends(get_current_user)):
        await _ensure_admin(user)
        req = await db.verification_requests.find_one({"_id": oid(rid)})
        if not req:
            raise HTTPException(404, "Request not found")

        current_status = req.get("status")
        if payload.decision == "in_progress" and current_status not in {"pending", "in_progress"}:
            raise HTTPException(400, "Only pending requests can be moved to in progress")
        if payload.decision == "verified":
            if current_status != "in_progress":
                raise HTTPException(400, "Request must be in progress before it can be verified")
            if not payload.call_completed:
                raise HTTPException(400, "Confirm the WhatsApp video call is completed before verifying")

        now = now_utc()
        update = {"status": payload.decision, "updated_at": now}
        if payload.notes is not None:
            update["admin_notes"] = payload.notes
        if payload.schedule_call_at is not None:
            update["schedule_call_at"] = payload.schedule_call_at
        if payload.call_completed:
            update["call_completed"] = True
            update["call_completed_at"] = now

        await db.verification_requests.update_one({"_id": oid(rid)}, {"$set": update})
        # propagate to brand/influencer collection
        collection = db.brands if req["kind"] == "brand" else db.influencers
        await collection.update_one({"user_id": req["user_id"]},
                                    {"$set": {"verification_status": payload.decision, "updated_at": now_utc()}})
        if payload.decision == "in_progress" and payload.schedule_call_at:
            title = "WhatsApp verification call scheduled"
            body = f"Your WhatsApp video verification call is scheduled for {payload.schedule_call_at}."
        elif payload.decision == "in_progress":
            title = "Verification in progress"
            body = "Your verification request is now under admin review."
        elif payload.decision == "verified":
            title = "Verification complete"
            body = payload.notes or "Your insights and WhatsApp video call were approved. You're now verified."
        else:
            title = "Verification rejected"
            body = payload.notes or "Your verification request needs changes before approval."

        await notify(req["user_id"], "verification.decision", title, body, {"request_id": rid})
        await log_admin(str(user["_id"]), f"verification.{payload.decision}", rid, {"notes": payload.notes})
        fresh = await db.verification_requests.find_one({"_id": oid(rid)})
        return {"success": True, "request": await _verification_out(fresh)}

    @admin_router.get("/withdrawals")
    async def _admin_wd(user: dict = Depends(get_current_user), status: str = "pending"):
        await _ensure_admin(user)
        cur = db.withdrawal_requests.find({"status": status}).sort("created_at", -1).limit(100)
        return {"requests": [doc_out(x) async for x in cur]}

    @admin_router.post("/withdrawals/{rid}/decision")
    async def _admin_wd_decide(rid: str, payload: WithdrawalDecisionIn, user: dict = Depends(get_current_user)):
        await _ensure_admin(user)
        await db.withdrawal_requests.update_one({"_id": oid(rid)},
                                                {"$set": {"status": payload.decision, "admin_note": payload.note, "updated_at": now_utc()}})
        await log_admin(str(user["_id"]), f"withdrawal.{payload.decision}", rid)
        return {"success": True}

    @admin_router.get("/reports")
    async def _admin_reports(user: dict = Depends(get_current_user), status: str = "open"):
        await _ensure_admin(user)
        cur = db.reports.find({"status": status}).sort("created_at", -1).limit(100)
        return {"reports": [doc_out(x) async for x in cur]}

    @admin_router.get("/logs")
    async def _admin_logs(user: dict = Depends(get_current_user), kind: str = "admin", limit: int = 100):
        await _ensure_admin(user)
        col = db.admin_logs if kind == "admin" else db.activity_logs
        cur = col.find({}).sort("created_at", -1).limit(min(limit, 500))
        return {"logs": [doc_out(x) async for x in cur]}


ALL_ROUTERS = [
    brand_router, influencer_router, campaign_router, deal_router, payment_router,
    notif_router, msg_router, verify_router, withdraw_router, review_router,
    report_router, upload_router, admin_router,
]
