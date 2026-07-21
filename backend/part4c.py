"""Part 4C — Performance Tracking, Reviews, Completion Reports, Analytics.

Adds on top of Parts 1B + 4B without modifying them. Wired in server.py.
All endpoints under /api (via the parent api_router prefix in server.py).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional, List, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict

import domain as _domain

# Wired by init()
db = None  # type: ignore
get_current_user = None  # type: ignore


def init(database, current_user_dep):
    global db, get_current_user
    db = database
    get_current_user = current_user_dep


# ---------- helpers ----------
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


async def setup_part4c_indexes(database):
    await database.reviews.create_index([("target_user_id", 1), ("created_at", -1)])
    await database.reviews.create_index([("reviewer_id", 1), ("created_at", -1)])
    await database.reviews.create_index([("deal_id", 1)])
    # deal metrics live inside deals.metrics, no extra collection


# ---------- routers ----------
metrics_router = APIRouter(prefix="/deals", tags=["metrics"])
perf_router = APIRouter(prefix="/performance", tags=["performance"])
feedback_router = APIRouter(prefix="/feedback", tags=["reviews"])


# =============== MODELS ===============
class DealMetricsIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    instagram_reel_views: int = Field(0, ge=0)
    youtube_views: int = Field(0, ge=0)
    facebook_views: int = Field(0, ge=0)
    likes: int = Field(0, ge=0)
    comments: int = Field(0, ge=0)
    shares: int = Field(0, ge=0)
    saves: int = Field(0, ge=0)
    reach: int = Field(0, ge=0)
    clicks: int = Field(0, ge=0)
    estimated_sales: float = Field(0, ge=0)
    notes: Optional[str] = None


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    target_user_id: str
    deal_id: Optional[str] = None
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    would_work_again: bool = True
    kind: Literal["brand_to_influencer", "influencer_to_brand"] = "brand_to_influencer"


# =============== METRICS COMPUTATION ===============
def _compute_metrics(m: dict, deal_amount: float = 0) -> dict:
    """Pure function — returns metrics + derived KPIs."""
    m = m or {}
    total_views = int(
        (m.get("instagram_reel_views") or 0)
        + (m.get("youtube_views") or 0)
        + (m.get("facebook_views") or 0)
    )
    engagement_total = int(
        (m.get("likes") or 0)
        + (m.get("comments") or 0)
        + (m.get("shares") or 0)
        + (m.get("saves") or 0)
    )
    reach = int(m.get("reach") or 0)
    clicks = int(m.get("clicks") or 0)
    sales = float(m.get("estimated_sales") or 0)

    engagement_rate = round((engagement_total / reach) * 100, 2) if reach else 0.0
    ctr = round((clicks / total_views) * 100, 2) if total_views else 0.0
    roi_pct = round(((sales - deal_amount) / deal_amount) * 100, 1) if deal_amount else 0.0
    roi_x = round(sales / deal_amount, 2) if deal_amount else 0.0

    return {
        **{k: (m.get(k) or 0) for k in [
            "instagram_reel_views", "youtube_views", "facebook_views",
            "likes", "comments", "shares", "saves", "reach", "clicks",
        ]},
        "estimated_sales": float(sales),
        "notes": m.get("notes") or "",
        "total_views": total_views,
        "engagement_total": engagement_total,
        "engagement_rate": engagement_rate,
        "ctr": ctr,
        "roi_pct": roi_pct,
        "roi_x": roi_x,
        "updated_at": (m.get("updated_at").isoformat()
                       if isinstance(m.get("updated_at"), datetime)
                       else m.get("updated_at")),
    }


# Linear pipeline used in domain.py
PIPELINE = [
    "offer_sent", "offer_accepted", "product_shipped", "product_received",
    "content_in_progress", "content_submitted", "brand_review",
    "approved", "scheduled", "published", "completed",
]


def _completion_pct(status: str) -> int:
    if status == "cancelled":
        return 0
    if status not in PIPELINE:
        return 0
    idx = PIPELINE.index(status)
    return round((idx / (len(PIPELINE) - 1)) * 100)


# =============== HANDLERS ===============
def register_handlers():

    # ---------- DEAL METRICS ----------
    @metrics_router.post("/{deal_id}/metrics")
    async def _set_metrics(deal_id: str, payload: DealMetricsIn, user: dict = Depends(get_current_user)):
        deal = await db.deals.find_one({"_id": oid(deal_id)})
        if not deal:
            raise HTTPException(404, "Deal not found")
        await _domain.require_deal_access(db, deal, user)
        # only the assigned influencer (or admin) can submit metrics
        uid = str(user["_id"])
        inf = await db.influencers.find_one({"_id": oid(deal["influencer_id"])}) if deal.get("influencer_id") else None
        if user.get("role") != "admin" and not (inf and inf.get("user_id") == uid):
            raise HTTPException(403, "Only the creator on this deal can submit performance metrics")

        now = now_utc()
        metrics = payload.model_dump()
        metrics["updated_at"] = now
        await db.deals.update_one(
            {"_id": oid(deal_id)},
            {"$set": {"metrics": metrics, "metrics_updated_at": now, "updated_at": now}},
        )
        fresh = await db.deals.find_one({"_id": oid(deal_id)})
        return {
            "success": True,
            "metrics": _compute_metrics(fresh.get("metrics") or {}, float(fresh.get("amount") or 0)),
        }

    @metrics_router.get("/{deal_id}/metrics")
    async def _get_metrics(deal_id: str, user: dict = Depends(get_current_user)):
        deal = await db.deals.find_one({"_id": oid(deal_id)})
        if not deal:
            raise HTTPException(404, "Deal not found")
        await _domain.require_deal_access(db, deal, user)
        return {"metrics": _compute_metrics(deal.get("metrics") or {}, float(deal.get("amount") or 0))}

    # ---------- FEEDBACK / REVIEWS ----------
    @feedback_router.post("")
    async def _create_feedback(payload: FeedbackIn, user: dict = Depends(get_current_user)):
        if payload.target_user_id == str(user["_id"]):
            raise HTTPException(400, "You can't review yourself")
        try:
            target = await db.users.find_one({"_id": ObjectId(payload.target_user_id)}, {"role": 1})
        except Exception:
            raise HTTPException(400, "Invalid target_user_id")
        if not target:
            raise HTTPException(404, "Target user not found")
        if payload.deal_id:
            deal = await db.deals.find_one({"_id": oid(payload.deal_id)})
            if not deal:
                raise HTTPException(404, "Deal not found")
            await _domain.require_deal_access(db, deal, user)

        # one review per (reviewer, target, deal) — update if exists
        now = now_utc()
        criteria = {"reviewer_id": str(user["_id"]), "target_user_id": payload.target_user_id}
        if payload.deal_id:
            criteria["deal_id"] = payload.deal_id
        doc = {
            **payload.model_dump(),
            "reviewer_id": str(user["_id"]),
            "reviewer_name": user.get("name") or user.get("email", ""),
            "reviewer_role": user.get("role"),
            "status": "active",
            "updated_at": now,
        }
        existing = await db.reviews.find_one(criteria)
        if existing:
            await db.reviews.update_one({"_id": existing["_id"]}, {"$set": doc})
            saved = await db.reviews.find_one({"_id": existing["_id"]})
        else:
            doc["created_at"] = now
            res = await db.reviews.insert_one(doc)
            saved = await db.reviews.find_one({"_id": res.inserted_id})
        return {"review": doc_out(saved)}

    @feedback_router.get("/for/{user_id}")
    async def _reviews_for(user_id: str, user: dict = Depends(get_current_user)):
        cur = db.reviews.find({"target_user_id": user_id, "status": "active"}).sort("created_at", -1).limit(200)
        return {"reviews": [doc_out(x) async for x in cur]}

    @feedback_router.get("/mine")
    async def _reviews_mine(user: dict = Depends(get_current_user)):
        cur = db.reviews.find({"reviewer_id": str(user["_id"]), "status": "active"}).sort("created_at", -1).limit(200)
        return {"reviews": [doc_out(x) async for x in cur]}

    @feedback_router.get("/summary/{user_id}")
    async def _review_summary(user_id: str, user: dict = Depends(get_current_user)):
        return await _summary_for_user(user_id)

    @feedback_router.get("/for-deal/{deal_id}")
    async def _reviews_for_deal(deal_id: str, user: dict = Depends(get_current_user)):
        deal = await db.deals.find_one({"_id": oid(deal_id)})
        if not deal:
            raise HTTPException(404, "Deal not found")
        await _domain.require_deal_access(db, deal, user)
        cur = db.reviews.find({"deal_id": deal_id, "status": "active"}).sort("created_at", -1)
        return {"reviews": [doc_out(x) async for x in cur]}

    async def _summary_for_user(user_id: str) -> dict:
        cur = db.reviews.find({"target_user_id": user_id, "status": "active"})
        ratings = []
        wwa_yes = 0
        total = 0
        async for r in cur:
            ratings.append(int(r.get("rating") or 0))
            if r.get("would_work_again"):
                wwa_yes += 1
            total += 1
        avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
        return {
            "average_rating": avg,
            "total_reviews": total,
            "would_work_again_pct": round((wwa_yes / total) * 100) if total else 0,
        }

    # ---------- INFLUENCER PERFORMANCE ----------
    async def _influencer_perf(user_id: str) -> dict:
        # locate influencer doc
        inf_doc = await db.influencers.find_one({"user_id": user_id})
        # get this user's deals
        if not inf_doc:
            deals = []
        else:
            cur = db.deals.find({"influencer_id": str(inf_doc["_id"])})
            deals = [x async for x in cur]

        total = len(deals)
        completed = [d for d in deals if d.get("status") == "completed"]
        success_states = {"approved", "scheduled", "published", "completed"}
        successful = [d for d in deals if d.get("status") in success_states]

        # avg delivery time (created_at -> completed updated_at)
        delivery_days = []
        for d in completed:
            try:
                c = d.get("created_at")
                u = d.get("updated_at")
                if isinstance(c, datetime) and isinstance(u, datetime):
                    delivery_days.append((u - c).total_seconds() / 86400.0)
            except Exception:
                pass
        avg_delivery = round(sum(delivery_days) / len(delivery_days), 1) if delivery_days else 0.0

        # avg engagement rate across deals with metrics
        eng_rates = []
        total_reach = 0
        for d in deals:
            m = d.get("metrics") or {}
            cm = _compute_metrics(m, float(d.get("amount") or 0))
            if cm["engagement_rate"]:
                eng_rates.append(cm["engagement_rate"])
            total_reach += cm["reach"]
        avg_engagement = round(sum(eng_rates) / len(eng_rates), 2) if eng_rates else 0.0

        # total earnings (released payments)
        deal_ids = {str(d["_id"]) for d in deals}
        total_earnings = 0.0
        if deal_ids:
            pcur = db.payments.find({
                "deal_id": {"$in": list(deal_ids)},
                "$or": [{"release_status": "released"}, {"status": "released"}],
            })
            async for p in pcur:
                total_earnings += float(p.get("influencer_earning") or 0)

        # repeat brands
        brand_counts: dict = {}
        for d in deals:
            bid = d.get("brand_id")
            if bid:
                brand_counts[bid] = brand_counts.get(bid, 0) + 1
        repeat_brands = sum(1 for c in brand_counts.values() if c > 1)

        summary = await _summary_for_user(user_id)

        return {
            "influencer": doc_out(inf_doc) if inf_doc else None,
            "total_collaborations": total,
            "completion_rate": round((len(completed) / total) * 100) if total else 0,
            "success_rate": round((len(successful) / total) * 100) if total else 0,
            "average_delivery_days": avg_delivery,
            "average_engagement_rate": avg_engagement,
            "total_reach": total_reach,
            "total_earnings": round(total_earnings, 2),
            "repeat_brands": repeat_brands,
            "unique_brands": len(brand_counts),
            "verified": (inf_doc or {}).get("verification_status") in {"approved", "verified"},
            "verification_status": (inf_doc or {}).get("verification_status") or "pending",
            "overall_rating": summary["average_rating"],
            "total_reviews": summary["total_reviews"],
            "would_work_again_pct": summary["would_work_again_pct"],
        }

    @perf_router.get("/influencer/me")
    async def _my_inf_perf(user: dict = Depends(get_current_user)):
        return await _influencer_perf(str(user["_id"]))

    @perf_router.get("/influencer/{user_id}")
    async def _inf_perf(user_id: str, user: dict = Depends(get_current_user)):
        return await _influencer_perf(user_id)

    # ---------- BRAND PERFORMANCE ----------
    async def _brand_perf(user_id: str) -> dict:
        brand_doc = await db.brands.find_one({"user_id": user_id})
        if not brand_doc:
            cur_campaigns = []
            cur_deals = []
        else:
            cur_campaigns = [x async for x in db.campaigns.find({"brand_id": str(brand_doc["_id"])})]
            cur_deals = [x async for x in db.deals.find({"brand_id": str(brand_doc["_id"])})]

        total_campaigns = len(cur_campaigns)
        active_campaigns = sum(1 for c in cur_campaigns if c.get("status") == "active")
        completed_campaigns = sum(1 for c in cur_campaigns if c.get("status") == "completed")
        successful_campaigns = sum(1 for c in cur_campaigns if c.get("status") in {"completed"})

        # total spend (gross) + ROI
        deal_ids = {str(d["_id"]) for d in cur_deals}
        total_spend = 0.0
        total_sales = 0.0
        if deal_ids:
            pcur = db.payments.find({"deal_id": {"$in": list(deal_ids)}})
            async for p in pcur:
                total_spend += float(p.get("amount") or 0)
        for d in cur_deals:
            m = d.get("metrics") or {}
            total_sales += float(m.get("estimated_sales") or 0)
        avg_roi = round((total_sales / total_spend), 2) if total_spend else 0.0

        # avg creator rating: ratings creators gave this brand
        cur_rev = db.reviews.find({"target_user_id": user_id, "status": "active"})
        ratings = []
        async for r in cur_rev:
            ratings.append(int(r.get("rating") or 0))
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

        return {
            "brand": doc_out(brand_doc) if brand_doc else None,
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "completed_campaigns": completed_campaigns,
            "successful_campaigns": successful_campaigns,
            "total_deals": len(cur_deals),
            "total_spend": round(total_spend, 2),
            "estimated_sales": round(total_sales, 2),
            "average_roi": avg_roi,
            "average_creator_rating": avg_rating,
            "total_reviews": len(ratings),
            "verified": (brand_doc or {}).get("verification_status") in {"approved", "verified"},
        }

    @perf_router.get("/brand/me")
    async def _my_brand_perf(user: dict = Depends(get_current_user)):
        return await _brand_perf(str(user["_id"]))

    @perf_router.get("/brand/{user_id}")
    async def _brand_perf_ep(user_id: str, user: dict = Depends(get_current_user)):
        return await _brand_perf(user_id)

    # ---------- CAMPAIGN COMPLETION REPORT (per-deal) ----------
    @perf_router.get("/deal/{deal_id}/report")
    async def _deal_report(deal_id: str, user: dict = Depends(get_current_user)):
        deal = await db.deals.find_one({"_id": oid(deal_id)})
        if not deal:
            raise HTTPException(404, "Deal not found")
        await _domain.require_deal_access(db, deal, user)
        brand = await db.brands.find_one({"_id": oid(deal["brand_id"])}) if deal.get("brand_id") else None
        inf = await db.influencers.find_one({"_id": oid(deal["influencer_id"])}) if deal.get("influencer_id") else None

        campaign = await db.campaigns.find_one({"_id": oid(deal["campaign_id"])}) if deal.get("campaign_id") else None
        payment = await db.payments.find_one({"deal_id": deal_id})
        metrics = _compute_metrics(deal.get("metrics") or {}, float(deal.get("amount") or 0))

        # reviews exchanged on this deal
        rev_cur = db.reviews.find({"deal_id": deal_id, "status": "active"})
        reviews = [doc_out(x) async for x in rev_cur]

        return {
            "deal": doc_out(deal),
            "campaign": doc_out(campaign) if campaign else None,
            "brand": doc_out(brand) if brand else None,
            "influencer": doc_out(inf) if inf else None,
            "payment": doc_out(payment) if payment else None,
            "metrics": metrics,
            "completion_pct": _completion_pct(deal.get("status") or ""),
            "reviews": reviews,
            "history": [
                {
                    **h,
                    "at": h["at"].isoformat() if isinstance(h.get("at"), datetime) else h.get("at"),
                }
                for h in (deal.get("status_history") or [])
            ],
        }

    # ---------- TRENDS ----------
    def _week_start(d: datetime) -> datetime:
        d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        # Monday as week start
        dow = (d.weekday()) % 7
        ws = d - timedelta(days=dow)
        return ws.replace(hour=0, minute=0, second=0, microsecond=0)

    @perf_router.get("/trends")
    async def _trends(user: dict = Depends(get_current_user), weeks: int = 12):
        weeks = max(4, min(weeks, 26))
        now = now_utc()
        anchor = _week_start(now) - timedelta(weeks=weeks - 1)
        buckets = [(anchor + timedelta(weeks=i)) for i in range(weeks)]
        labels = [b.strftime("%b %d") for b in buckets]

        uid = str(user["_id"])
        # scope deals to current user
        if user.get("role") == "brand":
            brand = await db.brands.find_one({"user_id": uid})
            deal_q = {"brand_id": str(brand["_id"]) if brand else "__none__"}
        elif user.get("role") == "influencer":
            inf = await db.influencers.find_one({"user_id": uid})
            deal_q = {"influencer_id": str(inf["_id"]) if inf else "__none__"}
        else:
            deal_q = {}

        cur = db.deals.find(deal_q)
        deals = [x async for x in cur]

        # bucketize deals by created_at
        def _bidx(dt: datetime) -> int:
            if not isinstance(dt, datetime):
                return -1
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            for i in range(len(buckets) - 1, -1, -1):
                if dt >= buckets[i]:
                    return i
            return -1

        reach_series = [0] * weeks
        engagement_series = [0] * weeks
        views_series = [0] * weeks
        roi_series_num = [0.0] * weeks
        roi_series_den = [0.0] * weeks
        deals_per_week = [0] * weeks
        spend_per_week = [0.0] * weeks
        completed_per_week = [0] * weeks

        deal_ids = [str(d["_id"]) for d in deals]
        payments_by_deal = {}
        if deal_ids:
            pcur = db.payments.find({"deal_id": {"$in": deal_ids}})
            async for p in pcur:
                payments_by_deal.setdefault(p["deal_id"], []).append(p)

        for d in deals:
            i = _bidx(d.get("created_at"))
            if i < 0:
                continue
            m = d.get("metrics") or {}
            cm = _compute_metrics(m, float(d.get("amount") or 0))
            reach_series[i] += cm["reach"]
            engagement_series[i] += cm["engagement_total"]
            views_series[i] += cm["total_views"]
            deals_per_week[i] += 1
            if d.get("status") == "completed":
                completed_per_week[i] += 1

            spend = sum(float(p.get("amount") or 0) for p in payments_by_deal.get(str(d["_id"]), []))
            spend_per_week[i] += spend
            roi_series_num[i] += float(m.get("estimated_sales") or 0)
            roi_series_den[i] += spend

        series = []
        for i in range(weeks):
            roi = round((roi_series_num[i] / roi_series_den[i]), 2) if roi_series_den[i] else 0.0
            series.append({
                "label": labels[i],
                "reach": int(reach_series[i]),
                "engagement": int(engagement_series[i]),
                "views": int(views_series[i]),
                "deals": int(deals_per_week[i]),
                "completed": int(completed_per_week[i]),
                "spend": round(spend_per_week[i], 2),
                "roi": roi,
            })

        return {"weeks": weeks, "series": series}

    # ---------- TOP LISTS ----------
    @perf_router.get("/top-campaigns")
    async def _top_campaigns(user: dict = Depends(get_current_user), limit: int = 5):
        uid = str(user["_id"])
        if user.get("role") == "brand":
            brand = await db.brands.find_one({"user_id": uid})
            deal_q = {"brand_id": str(brand["_id"]) if brand else "__none__"}
        elif user.get("role") == "influencer":
            inf = await db.influencers.find_one({"user_id": uid})
            deal_q = {"influencer_id": str(inf["_id"]) if inf else "__none__"}
        else:
            deal_q = {}
        deals = [x async for x in db.deals.find(deal_q)]

        # aggregate by campaign
        by_campaign: dict = {}
        for d in deals:
            cid = d.get("campaign_id")
            if not cid:
                continue
            slot = by_campaign.setdefault(cid, {"deals": 0, "reach": 0, "engagement": 0, "views": 0, "completed": 0, "sales": 0.0})
            slot["deals"] += 1
            cm = _compute_metrics(d.get("metrics") or {}, float(d.get("amount") or 0))
            slot["reach"] += cm["reach"]
            slot["engagement"] += cm["engagement_total"]
            slot["views"] += cm["total_views"]
            slot["sales"] += float((d.get("metrics") or {}).get("estimated_sales") or 0)
            if d.get("status") == "completed":
                slot["completed"] += 1

        out = []
        for cid, stats in by_campaign.items():
            try:
                c = await db.campaigns.find_one({"_id": oid(cid)})
            except Exception:
                c = None
            score = stats["engagement"] + stats["views"] // 10 + int(stats["sales"])
            out.append({
                "campaign_id": cid,
                "title": (c or {}).get("title", "Campaign"),
                "platform": (c or {}).get("platform"),
                "status": (c or {}).get("status"),
                "score": score,
                **stats,
            })
        out.sort(key=lambda x: x["score"], reverse=True)
        return {"top_campaigns": out[: max(1, min(limit, 20))]}

    @perf_router.get("/top-creators")
    async def _top_creators(user: dict = Depends(get_current_user), limit: int = 5):
        uid = str(user["_id"])
        # if brand: top creators across THEIR deals; else global
        if user.get("role") == "brand":
            brand = await db.brands.find_one({"user_id": uid})
            deal_q = {"brand_id": str(brand["_id"]) if brand else "__none__"}
        else:
            deal_q = {}
        deals = [x async for x in db.deals.find(deal_q)]

        by_inf: dict = {}
        for d in deals:
            iid = d.get("influencer_id")
            if not iid:
                continue
            slot = by_inf.setdefault(iid, {"deals": 0, "engagement": 0, "reach": 0, "views": 0, "earnings": 0.0, "completed": 0})
            slot["deals"] += 1
            cm = _compute_metrics(d.get("metrics") or {}, float(d.get("amount") or 0))
            slot["engagement"] += cm["engagement_total"]
            slot["reach"] += cm["reach"]
            slot["views"] += cm["total_views"]
            if d.get("status") == "completed":
                slot["completed"] += 1

        # earnings from released payments
        deal_ids = [str(d["_id"]) for d in deals]
        if deal_ids:
            pcur = db.payments.find({
                "deal_id": {"$in": deal_ids},
                "$or": [{"release_status": "released"}, {"status": "released"}],
            })
            async for p in pcur:
                # find deal -> influencer
                d = next((x for x in deals if str(x["_id"]) == p["deal_id"]), None)
                if d and d.get("influencer_id") in by_inf:
                    by_inf[d["influencer_id"]]["earnings"] += float(p.get("influencer_earning") or 0)

        out = []
        for iid, stats in by_inf.items():
            try:
                inf = await db.influencers.find_one({"_id": oid(iid)})
            except Exception:
                inf = None
            uid2 = (inf or {}).get("user_id")
            rating_summary = await _summary_for_user(uid2) if uid2 else {"average_rating": 0, "total_reviews": 0}
            score = stats["engagement"] + stats["views"] // 10 + int(stats["earnings"])
            out.append({
                "influencer_id": iid,
                "user_id": uid2,
                "username": (inf or {}).get("username") or "Creator",
                "category": (inf or {}).get("category"),
                "profile_photo_url": (inf or {}).get("profile_photo_url"),
                "average_rating": rating_summary["average_rating"],
                "total_reviews": rating_summary["total_reviews"],
                "score": score,
                **stats,
            })
        out.sort(key=lambda x: x["score"], reverse=True)
        return {"top_creators": out[: max(1, min(limit, 20))]}


ALL_ROUTERS = [metrics_router, perf_router, feedback_router]
