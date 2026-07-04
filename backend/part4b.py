"""Part 4B — Collaborations, Chat, Digital Agreements.

Adds on top of Part 1B (domain.py) without modifying it. Wired in server.py.
All endpoints under /api (via the parent api_router prefix in server.py).
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, List, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field, ConfigDict

# Wired by init()
db = None  # type: ignore
get_current_user = None  # type: ignore


def init(database, current_user_dep):
    global db, get_current_user
    db = database
    get_current_user = current_user_dep


# ---------- helpers (kept local; mirror domain.py patterns) ----------
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


async def notify(user_id: str, type_: str, title: str, body: str = "", meta: Optional[dict] = None):
    if not user_id:
        return
    await db.notifications.insert_one({
        "user_id": user_id, "type": type_, "title": title, "body": body,
        "meta": meta or {}, "read": False, "status": "active",
        "created_at": now_utc(), "updated_at": now_utc(),
    })


async def setup_part4b_indexes(database):
    await database.collaborations.create_index([("owner_user_id", 1), ("created_at", -1)])
    await database.collaborations.create_index([("invited_user_id", 1), ("status", 1)])
    await database.conversations.create_index([("participants", 1), ("updated_at", -1)])
    await database.conversations.create_index([("context_type", 1), ("context_id", 1)], unique=False)
    await database.chat_messages.create_index([("conversation_id", 1), ("created_at", 1)])
    try:
        await database.chat_messages.create_index([("conversation_id", 1), ("body", "text")])
    except Exception:
        # text index may already exist with different spec — ignore
        pass
    await database.chat_typing.create_index("updated_at", expireAfterSeconds=15)
    await database.chat_typing.create_index([("conversation_id", 1), ("user_id", 1)], unique=True)
    await database.agreements.create_index([("brand_user_id", 1), ("created_at", -1)])
    await database.agreements.create_index([("influencer_user_id", 1), ("status", 1)])


# ---------- routers ----------
collab_router = APIRouter(prefix="/collaborations", tags=["collaborations"])
conv_router = APIRouter(prefix="/conversations", tags=["chat"])
chat_router = APIRouter(prefix="/chat", tags=["chat"])
agreement_router = APIRouter(prefix="/agreements", tags=["agreements"])


# =============== COLLABORATIONS ===============
COLLAB_STATUSES = ["pending", "accepted", "rejected", "cancelled", "completed"]


class CollabIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    invited_user_id: Optional[str] = None  # target influencer's USER id (preferred)
    invited_influencer_id: Optional[str] = None  # OR target influencer document id
    title: str = Field(min_length=2, max_length=160)
    description: Optional[str] = None
    platform: Literal["instagram", "youtube", "facebook", "linkedin", "tiktok", "other"] = "instagram"
    budget: float = Field(ge=0)
    deadline: Optional[str] = None
    category: Optional[str] = None
    expected_views: Optional[int] = 0
    deliverables: List[str] = []


class CollabStatusIn(BaseModel):
    status: Literal["accepted", "rejected", "cancelled", "completed"]
    note: Optional[str] = None


# =============== CHAT ===============
class ConversationIn(BaseModel):
    """Create or fetch a conversation by (context_type, context_id) OR direct (peer_user_id)."""
    model_config = ConfigDict(extra="ignore")
    context_type: Literal["collab", "agreement", "deal", "direct"] = "direct"
    context_id: Optional[str] = None
    peer_user_id: Optional[str] = None
    title: Optional[str] = None


class ChatMessageIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    body: Optional[str] = ""
    attachments: List[dict] = []  # [{url, name, kind: image|file, size}]


# =============== AGREEMENTS ===============
AGREEMENT_STATUSES = ["draft", "pending_acceptance", "accepted", "rejected", "cancelled", "completed"]


class AgreementIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    influencer_user_id: str
    brand_name: str
    influencer_name: str
    campaign: Optional[str] = None  # campaign title or id text
    campaign_id: Optional[str] = None
    deliverables: List[str] = []
    timeline: Optional[str] = None
    payment_amount: float = Field(ge=0)
    platform_fee_pct: float = 8.0
    cancellation_policy: Optional[str] = None
    terms: Optional[str] = None


class AgreementSignIn(BaseModel):
    consent: bool
    signature_name: Optional[str] = None


# ---------- handler registration ----------
def register_handlers():
    # =========================================================
    # COLLABORATIONS
    # =========================================================
    @collab_router.post("")
    async def _create_collab(payload: CollabIn, user: dict = Depends(get_current_user)):
        await require_role(user, "influencer", "admin")

        invited_user_id = payload.invited_user_id
        if not invited_user_id and payload.invited_influencer_id:
            inf = await db.influencers.find_one({"_id": oid(payload.invited_influencer_id)})
            if not inf:
                raise HTTPException(404, "Target influencer not found")
            invited_user_id = inf.get("user_id")
        if not invited_user_id:
            raise HTTPException(400, "invited_user_id or invited_influencer_id is required")
        if invited_user_id == str(user["_id"]):
            raise HTTPException(400, "You can't collaborate with yourself")

        now = now_utc()
        doc = {
            "owner_user_id": str(user["_id"]),
            "owner_name": user.get("name") or user.get("email", "").split("@")[0],
            "invited_user_id": invited_user_id,
            "title": payload.title.strip(),
            "description": (payload.description or "").strip(),
            "platform": payload.platform,
            "budget": float(payload.budget),
            "deadline": payload.deadline,
            "category": payload.category,
            "expected_views": int(payload.expected_views or 0),
            "deliverables": payload.deliverables,
            "status": "pending",
            "history": [{"status": "pending", "by": str(user["_id"]), "at": now}],
            "created_at": now,
            "updated_at": now,
        }
        res = await db.collaborations.insert_one(doc)

        await notify(
            invited_user_id, "collab.requested",
            "New collaboration request",
            f"{doc['owner_name']} sent you a collaboration request: {doc['title']}",
            {"collab_id": str(res.inserted_id)},
        )

        return {"collaboration": doc_out(await db.collaborations.find_one({"_id": res.inserted_id}))}

    @collab_router.get("")
    async def _list_collabs(
        user: dict = Depends(get_current_user),
        box: Optional[str] = None,   # "inbox" | "sent" | "all"
        status: Optional[str] = None,
    ):
        uid = str(user["_id"])
        if box == "inbox":
            query: dict = {"invited_user_id": uid}
        elif box == "sent":
            query = {"owner_user_id": uid}
        else:
            query = {"$or": [{"owner_user_id": uid}, {"invited_user_id": uid}]}
        if status:
            query["status"] = status
        cur = db.collaborations.find(query).sort("created_at", -1).limit(200)
        return {"collaborations": [doc_out(x) async for x in cur]}

    @collab_router.get("/{cid}")
    async def _get_collab(cid: str, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.collaborations.find_one({"_id": oid(cid)})
        if not doc:
            raise HTTPException(404, "Collaboration not found")
        if uid not in (doc.get("owner_user_id"), doc.get("invited_user_id")) and user.get("role") != "admin":
            raise HTTPException(403, "Forbidden")
        return {"collaboration": doc_out(doc)}

    @collab_router.patch("/{cid}/status")
    async def _collab_status(cid: str, payload: CollabStatusIn, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.collaborations.find_one({"_id": oid(cid)})
        if not doc:
            raise HTTPException(404, "Collaboration not found")
        is_owner = doc.get("owner_user_id") == uid
        is_invited = doc.get("invited_user_id") == uid
        if not (is_owner or is_invited or user.get("role") == "admin"):
            raise HTTPException(403, "Forbidden")

        target = payload.status
        if target in ("accepted", "rejected") and not is_invited:
            raise HTTPException(403, "Only the invited creator can accept or reject")
        if target == "cancelled" and not is_owner:
            raise HTTPException(403, "Only the requester can cancel")

        now = now_utc()
        update = {"status": target, "updated_at": now}
        if payload.note:
            update["last_note"] = payload.note
        await db.collaborations.update_one(
            {"_id": oid(cid)},
            {"$set": update, "$push": {"history": {"status": target, "by": uid, "at": now}}},
        )

        # Notify the other party + auto-open a conversation when accepted
        other_id = doc["owner_user_id"] if is_invited else doc["invited_user_id"]
        if target == "accepted":
            await notify(other_id, "collab.accepted", "Collaboration accepted",
                         f"Your collaboration '{doc['title']}' was accepted.", {"collab_id": cid})
            # ensure a conversation exists
            await _ensure_conversation(
                participants=[doc["owner_user_id"], doc["invited_user_id"]],
                context_type="collab", context_id=cid, title=doc["title"],
            )
        elif target == "rejected":
            await notify(other_id, "collab.rejected", "Collaboration declined",
                         f"Your collaboration '{doc['title']}' was declined.", {"collab_id": cid})
        elif target == "cancelled":
            await notify(other_id, "collab.cancelled", "Collaboration cancelled",
                         f"Collaboration '{doc['title']}' was cancelled.", {"collab_id": cid})

        fresh = await db.collaborations.find_one({"_id": oid(cid)})
        return {"success": True, "collaboration": doc_out(fresh)}

    # =========================================================
    # CONVERSATIONS / CHAT
    # =========================================================
    async def _agreement_escrow_payment(agreement_id: str) -> Optional[dict]:
        return await db.payments.find_one({
            "agreement_id": agreement_id,
            "status": {"$in": ["escrowed", "released"]},
        })

    async def _conversation_lock_reason(conv: dict) -> Optional[str]:
        if conv.get("context_type") != "agreement" or not conv.get("context_id"):
            return None
        payment = await _agreement_escrow_payment(conv["context_id"])
        if payment:
            return None
        return "Messaging unlocks after the brand funds escrow for this agreement."

    async def _require_conversation_unlocked(conv: dict) -> None:
        reason = await _conversation_lock_reason(conv)
        if reason:
            raise HTTPException(403, reason)

    async def _ensure_conversation(participants: List[str], context_type: str, context_id: Optional[str],
                                   title: Optional[str] = None) -> dict:
        parts = sorted(list({p for p in participants if p}))
        if len(parts) < 2:
            raise HTTPException(400, "Need at least 2 participants")
        existing = None
        if context_id:
            existing = await db.conversations.find_one(
                {"context_type": context_type, "context_id": context_id}
            )
        if not existing and context_type == "direct":
            existing = await db.conversations.find_one(
                {"context_type": "direct", "participants": parts}
            )
        if existing:
            return existing
        now = now_utc()
        doc = {
            "participants": parts,
            "context_type": context_type,
            "context_id": context_id,
            "title": title,
            "last_message": "",
            "last_message_at": now,
            "unread": {uid: 0 for uid in parts},
            "created_at": now,
            "updated_at": now,
        }
        res = await db.conversations.insert_one(doc)
        return await db.conversations.find_one({"_id": res.inserted_id})

    async def _hydrate_conv(conv: dict, me_id: str) -> dict:
        out = doc_out(conv)
        # attach participant display info
        others = [p for p in conv.get("participants", []) if p != me_id]
        peers = []
        for pid in others:
            try:
                u = await db.users.find_one({"_id": ObjectId(pid)}, {"name": 1, "email": 1, "avatar_url": 1, "role": 1})
                if u:
                    peers.append({
                        "id": str(u["_id"]),
                        "name": u.get("name") or u.get("email", ""),
                        "email": u.get("email"),
                        "avatar_url": u.get("avatar_url"),
                        "role": u.get("role"),
                    })
            except Exception:
                pass
        out["peers"] = peers
        out["unread_count"] = (conv.get("unread") or {}).get(me_id, 0)
        lock_reason = await _conversation_lock_reason(conv)
        out["locked"] = bool(lock_reason)
        out["lock_reason"] = lock_reason
        out["next_step"] = "brand_fund_escrow" if lock_reason else None
        return out

    @conv_router.get("")
    async def _list_conversations(user: dict = Depends(get_current_user), q: Optional[str] = None):
        uid = str(user["_id"])
        query: dict = {"participants": uid}
        if q:
            query["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"last_message": {"$regex": q, "$options": "i"}},
            ]
        cur = db.conversations.find(query).sort("last_message_at", -1).limit(200)
        out = []
        async for c in cur:
            out.append(await _hydrate_conv(c, uid))
        return {"conversations": out}

    @conv_router.post("")
    async def _create_conv(payload: ConversationIn, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        parts = [uid]
        if payload.peer_user_id:
            parts.append(payload.peer_user_id)
        # Validate context (collab/agreement participants)
        if payload.context_type == "collab" and payload.context_id:
            collab = await db.collaborations.find_one({"_id": oid(payload.context_id)})
            if not collab:
                raise HTTPException(404, "Collaboration not found")
            if uid not in (collab.get("owner_user_id"), collab.get("invited_user_id")):
                raise HTTPException(403, "Forbidden")
            if collab.get("status") != "accepted":
                raise HTTPException(403, "Chat opens after the collaboration is accepted")
            parts = [collab["owner_user_id"], collab["invited_user_id"]]
        elif payload.context_type == "agreement" and payload.context_id:
            ag = await db.agreements.find_one({"_id": oid(payload.context_id)})
            if not ag:
                raise HTTPException(404, "Agreement not found")
            if uid not in (ag.get("brand_user_id"), ag.get("influencer_user_id")):
                raise HTTPException(403, "Forbidden")
            parts = [ag["brand_user_id"], ag["influencer_user_id"]]
        elif payload.context_type == "deal" and payload.context_id:
            # use existing deal infra; still create a thread for unified UI
            deal = await db.deals.find_one({"_id": oid(payload.context_id)})
            if not deal:
                raise HTTPException(404, "Deal not found")
            brand = await db.brands.find_one({"_id": oid(deal["brand_id"])}) if deal.get("brand_id") else None
            inf = await db.influencers.find_one({"_id": oid(deal["influencer_id"])}) if deal.get("influencer_id") else None
            parts = [x for x in [brand.get("user_id") if brand else None, inf.get("user_id") if inf else None] if x]
            if uid not in parts and user.get("role") != "admin":
                raise HTTPException(403, "Forbidden")

        conv = await _ensure_conversation(
            participants=parts,
            context_type=payload.context_type,
            context_id=payload.context_id,
            title=payload.title,
        )
        return {"conversation": await _hydrate_conv(conv, uid)}

    @conv_router.get("/{conv_id}")
    async def _get_conv(conv_id: str, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        conv = await db.conversations.find_one({"_id": oid(conv_id)})
        if not conv:
            raise HTTPException(404, "Conversation not found")
        if uid not in conv.get("participants", []) and user.get("role") != "admin":
            raise HTTPException(403, "Forbidden")
        return {"conversation": await _hydrate_conv(conv, uid)}

    @conv_router.get("/{conv_id}/messages")
    async def _list_messages(conv_id: str, q: Optional[str] = None, limit: int = 200,
                              user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        conv = await db.conversations.find_one({"_id": oid(conv_id)})
        if not conv:
            raise HTTPException(404, "Conversation not found")
        if uid not in conv.get("participants", []) and user.get("role") != "admin":
            raise HTTPException(403, "Forbidden")
        await _require_conversation_unlocked(conv)
        query: dict = {"conversation_id": conv_id}
        if q:
            query["body"] = {"$regex": q, "$options": "i"}
        cur = db.chat_messages.find(query).sort("created_at", 1).limit(min(limit, 500))
        return {"messages": [doc_out(x) async for x in cur]}

    @conv_router.post("/{conv_id}/messages")
    async def _send_message(conv_id: str, payload: ChatMessageIn, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        conv = await db.conversations.find_one({"_id": oid(conv_id)})
        if not conv:
            raise HTTPException(404, "Conversation not found")
        if uid not in conv.get("participants", []):
            raise HTTPException(403, "Forbidden")
        await _require_conversation_unlocked(conv)
        body = (payload.body or "").strip()
        attachments = payload.attachments or []
        if not body and not attachments:
            raise HTTPException(400, "Message body or attachment required")

        now = now_utc()
        msg = {
            "conversation_id": conv_id,
            "sender_id": uid,
            "sender_name": user.get("name") or user.get("email", ""),
            "body": body,
            "attachments": attachments,
            "read_by": [uid],
            "created_at": now,
        }
        res = await db.chat_messages.insert_one(msg)

        # Update conversation cache + bump unread for others
        unread = dict(conv.get("unread") or {})
        for p in conv.get("participants", []):
            if p != uid:
                unread[p] = int(unread.get(p, 0)) + 1
        preview = body if body else (f"📎 {attachments[0].get('name', 'Attachment')}" if attachments else "")
        await db.conversations.update_one(
            {"_id": conv["_id"]},
            {"$set": {
                "last_message": preview[:200],
                "last_message_at": now,
                "updated_at": now,
                "unread": unread,
            }},
        )
        # Clear typing for sender
        await db.chat_typing.delete_one({"conversation_id": conv_id, "user_id": uid})

        return {"message": doc_out(await db.chat_messages.find_one({"_id": res.inserted_id}))}

    @conv_router.post("/{conv_id}/read")
    async def _mark_read(conv_id: str, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        conv = await db.conversations.find_one({"_id": oid(conv_id)})
        if not conv:
            raise HTTPException(404, "Conversation not found")
        if uid not in conv.get("participants", []):
            raise HTTPException(403, "Forbidden")
        unread = dict(conv.get("unread") or {})
        unread[uid] = 0
        await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {"unread": unread}})
        await db.chat_messages.update_many(
            {"conversation_id": conv_id, "read_by": {"$ne": uid}},
            {"$addToSet": {"read_by": uid}},
        )
        return {"success": True}

    @conv_router.post("/{conv_id}/typing")
    async def _set_typing(conv_id: str, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        conv = await db.conversations.find_one({"_id": oid(conv_id)})
        if not conv:
            raise HTTPException(404, "Conversation not found")
        if uid not in conv.get("participants", []):
            raise HTTPException(403, "Forbidden")
        now = now_utc()
        await db.chat_typing.update_one(
            {"conversation_id": conv_id, "user_id": uid},
            {"$set": {"conversation_id": conv_id, "user_id": uid, "updated_at": now}},
            upsert=True,
        )
        return {"success": True}

    @conv_router.get("/{conv_id}/typing")
    async def _get_typing(conv_id: str, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        conv = await db.conversations.find_one({"_id": oid(conv_id)})
        if not conv:
            raise HTTPException(404, "Conversation not found")
        if uid not in conv.get("participants", []):
            raise HTTPException(403, "Forbidden")
        # consider typing if updated within last 8s
        cutoff = now_utc() - timedelta(seconds=8)
        cur = db.chat_typing.find({"conversation_id": conv_id, "updated_at": {"$gte": cutoff}})
        others = []
        async for t in cur:
            if t.get("user_id") and t["user_id"] != uid:
                others.append(t["user_id"])
        return {"typing": others}

    # ---- chat attachments upload (uses same /uploads static mount) ----
    CHAT_UPLOAD_ROOT = os.environ.get("UPLOAD_ROOT", "./uploads")
    os.makedirs(os.path.join(CHAT_UPLOAD_ROOT, "chat"), exist_ok=True)

    @chat_router.post("/upload")
    async def _chat_upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
        filename = (file.filename or "").strip() or "file"
        data = await file.read()
        try:
            import storage  # noqa: WPS433
            res = await storage.save_upload(file_bytes=data, original_name=filename, folder="chat")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Upload failed: {e}")
        return {"url": res["url"], "name": filename, "kind": res.get("kind", "file"), "size": res.get("size", len(data)), "provider": res.get("provider")}

    # =========================================================
    # AGREEMENTS (Digital Contracts)
    # =========================================================
    @agreement_router.post("")
    async def _create_agreement(payload: AgreementIn, user: dict = Depends(get_current_user)):
        await require_role(user, "brand", "admin")
        # Validate influencer user
        try:
            inf_user = await db.users.find_one({"_id": ObjectId(payload.influencer_user_id)})
        except Exception:
            raise HTTPException(400, "Invalid influencer_user_id")
        if not inf_user:
            raise HTTPException(404, "Influencer user not found")

        now = now_utc()
        amount = float(payload.payment_amount)
        fee_pct = float(payload.platform_fee_pct or 0)
        platform_fee = round(amount * fee_pct / 100.0, 2)
        net_to_influencer = round(amount - platform_fee, 2)

        doc = {
            "brand_user_id": str(user["_id"]),
            "influencer_user_id": payload.influencer_user_id,
            "brand_name": payload.brand_name.strip(),
            "influencer_name": payload.influencer_name.strip(),
            "campaign": payload.campaign,
            "campaign_id": payload.campaign_id,
            "deliverables": payload.deliverables,
            "timeline": payload.timeline,
            "payment_amount": amount,
            "platform_fee_pct": fee_pct,
            "platform_fee": platform_fee,
            "net_to_influencer": net_to_influencer,
            "cancellation_policy": payload.cancellation_policy or (
                "Either party may terminate this Agreement up to 48 hours before the campaign deadline "
                "in writing. If terminated by the Brand after content is approved, the agreed payment "
                "remains payable. Platform fee is non-refundable once the agreement is signed."
            ),
            "terms": payload.terms,
            "status": "pending_acceptance",
            "brand_signed_at": now,
            "brand_signature_name": user.get("name") or user.get("email"),
            "influencer_signed_at": None,
            "influencer_signature_name": None,
            "consent": False,
            "history": [{"status": "pending_acceptance", "by": str(user["_id"]), "at": now}],
            "created_at": now,
            "updated_at": now,
        }
        res = await db.agreements.insert_one(doc)

        await notify(
            payload.influencer_user_id, "contract.requested",
            "New digital agreement to review",
            f"{doc['brand_name']} sent you a campaign agreement to sign.",
            {"agreement_id": str(res.inserted_id)},
        )
        return {"agreement": doc_out(await db.agreements.find_one({"_id": res.inserted_id}))}

    @agreement_router.get("")
    async def _list_agreements(user: dict = Depends(get_current_user), status: Optional[str] = None):
        uid = str(user["_id"])
        query: dict = {"$or": [{"brand_user_id": uid}, {"influencer_user_id": uid}]}
        if user.get("role") == "admin":
            query = {}
        if status:
            query["status"] = status
        cur = db.agreements.find(query).sort("created_at", -1).limit(200)
        return {"agreements": [doc_out(x) async for x in cur]}

    @agreement_router.get("/{aid}")
    async def _get_agreement(aid: str, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.agreements.find_one({"_id": oid(aid)})
        if not doc:
            raise HTTPException(404, "Agreement not found")
        if uid not in (doc.get("brand_user_id"), doc.get("influencer_user_id")) and user.get("role") != "admin":
            raise HTTPException(403, "Forbidden")
        return {"agreement": doc_out(doc)}

    @agreement_router.post("/{aid}/accept")
    async def _accept_agreement(aid: str, payload: AgreementSignIn, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.agreements.find_one({"_id": oid(aid)})
        if not doc:
            raise HTTPException(404, "Agreement not found")
        if uid != doc.get("influencer_user_id"):
            raise HTTPException(403, "Only the named influencer can sign this agreement")
        if not payload.consent:
            raise HTTPException(400, "Digital consent is required")
        if doc.get("status") in ("accepted", "completed", "cancelled", "rejected"):
            raise HTTPException(400, f"Agreement is already {doc.get('status')}")
        now = now_utc()
        update = {
            "status": "accepted",
            "consent": True,
            "influencer_signed_at": now,
            "influencer_signature_name": payload.signature_name or user.get("name") or user.get("email"),
            "updated_at": now,
        }
        await db.agreements.update_one(
            {"_id": oid(aid)},
            {"$set": update, "$push": {"history": {"status": "accepted", "by": uid, "at": now}}},
        )
        await notify(
            doc["brand_user_id"], "contract.accepted",
            "Agreement accepted",
            f"{doc.get('influencer_name')} signed the agreement. Fund escrow to unlock messaging and start work.",
            {"agreement_id": aid},
        )
        # auto-open conversation between the two parties
        await _ensure_conversation(
            participants=[doc["brand_user_id"], doc["influencer_user_id"]],
            context_type="agreement", context_id=aid,
            title=f"Agreement · {doc.get('campaign') or doc.get('brand_name')}",
        )
        fresh = await db.agreements.find_one({"_id": oid(aid)})
        return {"success": True, "agreement": doc_out(fresh)}

    @agreement_router.post("/{aid}/fund")
    async def _fund_agreement(aid: str, user: dict = Depends(get_current_user)):
        await require_role(user, "brand", "admin")
        uid = str(user["_id"])
        agreement = await db.agreements.find_one({"_id": oid(aid)})
        if not agreement:
            raise HTTPException(404, "Agreement not found")
        if uid != agreement.get("brand_user_id") and user.get("role") != "admin":
            raise HTTPException(403, "Only the brand can fund this agreement")
        if agreement.get("status") not in ("accepted", "completed"):
            raise HTTPException(400, "Escrow can be funded after the creator signs the agreement")

        existing = await db.payments.find_one({
            "agreement_id": aid,
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

        amount = float(agreement.get("payment_amount") or 0)
        if amount <= 0:
            raise HTTPException(400, "Agreement amount must be greater than zero")

        now = now_utc()
        platform_fee = float(agreement.get("platform_fee") or round(amount * 0.08, 2))
        influencer_earning = float(agreement.get("net_to_influencer") or round(amount - platform_fee, 2))
        try:
            import payments as _payments  # noqa: WPS433
            pr = _payments.get_provider().create_escrow(amount=amount, deal_id=aid)
            txid = pr.get("transaction_id") or secrets.token_hex(8).upper()
            client_secret = pr.get("client_secret")
            provider_name = pr.get("provider", "stub")
            provider_status = pr.get("status", "escrowed")
        except Exception as exc:
            configured_provider = (os.environ.get("PAYMENT_PROVIDER") or "stub").lower()
            if configured_provider in {"stripe", "razorpay"}:
                raise HTTPException(503, f"{configured_provider.title()} payment provider is not configured correctly") from exc
            pr = {}
            txid = secrets.token_hex(8).upper()
            client_secret = None
            provider_name = "stub"
            provider_status = "escrowed"

        is_razorpay_pending = provider_name == "razorpay" and provider_status == "pending"
        payment_doc = {
            "deal_id": None,
            "agreement_id": aid,
            "amount": amount,
            "platform_fee": platform_fee,
            "influencer_earning": influencer_earning,
            "release_status": "pending" if is_razorpay_pending else "held",
            "transaction_id": txid,
            "provider": provider_name,
            "client_secret": client_secret,
            "status": "pending" if is_razorpay_pending else "escrowed",
            "currency": pr.get("currency", "INR"),
            "amount_subunits": pr.get("amount_subunits"),
            "provider_key_id": pr.get("key_id"),
            "receipt": pr.get("receipt"),
            "created_at": now,
            "updated_at": now,
        }
        res = await db.payments.insert_one(payment_doc)
        await db.transactions.insert_one({
            "user_id": uid,
            "type": "escrow_in",
            "amount": amount,
            "ref": str(res.inserted_id),
            "status": "pending" if is_razorpay_pending else "ok",
            "created_at": now,
        })
        await db.agreements.update_one(
            {"_id": oid(aid)},
            {"$set": {
                "payment_status": "pending" if is_razorpay_pending else "escrowed",
                "escrow_payment_id": str(res.inserted_id),
                "updated_at": now,
            }},
        )
        if not is_razorpay_pending:
            await notify(
                agreement["influencer_user_id"],
                "payment.escrowed",
                "Escrow funded",
                f"{agreement.get('brand_name')} funded escrow. Messaging is now unlocked.",
                {"agreement_id": aid, "payment_id": str(res.inserted_id)},
            )

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

    @agreement_router.post("/{aid}/reject")
    async def _reject_agreement(aid: str, payload: AgreementSignIn, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.agreements.find_one({"_id": oid(aid)})
        if not doc:
            raise HTTPException(404, "Agreement not found")
        if uid != doc.get("influencer_user_id"):
            raise HTTPException(403, "Only the named influencer can reject this agreement")
        if doc.get("status") in ("accepted", "completed", "cancelled", "rejected"):
            raise HTTPException(400, f"Agreement is already {doc.get('status')}")
        now = now_utc()
        await db.agreements.update_one(
            {"_id": oid(aid)},
            {"$set": {"status": "rejected", "updated_at": now},
             "$push": {"history": {"status": "rejected", "by": uid, "at": now}}},
        )
        await notify(
            doc["brand_user_id"], "contract.rejected",
            "Agreement declined",
            f"{doc.get('influencer_name')} declined the agreement.",
            {"agreement_id": aid},
        )
        fresh = await db.agreements.find_one({"_id": oid(aid)})
        return {"success": True, "agreement": doc_out(fresh)}

    @agreement_router.post("/{aid}/cancel")
    async def _cancel_agreement(aid: str, user: dict = Depends(get_current_user)):
        uid = str(user["_id"])
        doc = await db.agreements.find_one({"_id": oid(aid)})
        if not doc:
            raise HTTPException(404, "Agreement not found")
        if uid not in (doc.get("brand_user_id"), doc.get("influencer_user_id")) and user.get("role") != "admin":
            raise HTTPException(403, "Forbidden")
        if doc.get("status") in ("cancelled", "completed", "rejected"):
            raise HTTPException(400, f"Agreement is already {doc.get('status')}")
        now = now_utc()
        await db.agreements.update_one(
            {"_id": oid(aid)},
            {"$set": {"status": "cancelled", "updated_at": now},
             "$push": {"history": {"status": "cancelled", "by": uid, "at": now}}},
        )
        other_id = doc["influencer_user_id"] if uid == doc["brand_user_id"] else doc["brand_user_id"]
        await notify(
            other_id, "contract.cancelled",
            "Agreement cancelled",
            "The digital agreement has been cancelled.",
            {"agreement_id": aid},
        )
        fresh = await db.agreements.find_one({"_id": oid(aid)})
        return {"success": True, "agreement": doc_out(fresh)}


ALL_ROUTERS = [collab_router, conv_router, chat_router, agreement_router]
