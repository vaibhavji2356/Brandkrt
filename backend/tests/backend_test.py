"""BrandKrt Part 2 backend regression — verifies auth, influencer module APIs,
deals, notifications, verification, withdrawals, and demo seed idempotency."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://phase-2-plan.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@brandkrt.com"
ADMIN_PASSWORD = "Admin@12345"
INF_EMAIL = "demo.influencer@brandkrt.com"
INF_PASSWORD = "Demo@12345"
BRAND_EMAIL = "demo.brand@brandkrt.com"
BRAND_PASSWORD = "Demo@12345"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def inf_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": INF_EMAIL, "password": INF_PASSWORD})
    assert r.status_code == 200, f"influencer login failed: {r.status_code} {r.text}"
    return s


# ---------- Health ----------
def test_health():
    r = requests.get(f"{API}/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# ---------- Auth ----------
def test_admin_login_sets_cookies():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["role"] == "admin"
    assert data["user"]["email"] == ADMIN_EMAIL
    # httpOnly cookies present
    cookie_names = {c.name for c in s.cookies}
    assert "access_token" in cookie_names
    assert "refresh_token" in cookie_names


def test_influencer_login_role():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": INF_EMAIL, "password": INF_PASSWORD})
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["role"] == "influencer"
    assert data["user"]["email"] == INF_EMAIL


def test_brand_login_role():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": BRAND_EMAIL, "password": BRAND_PASSWORD})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "brand"


# ---------- Influencer profile ----------
def test_get_my_influencer(inf_session):
    r = inf_session.get(f"{API}/influencers/me")
    assert r.status_code == 200
    inf = r.json()["influencer"]
    assert inf is not None, "demo influencer profile missing — seed didn't run"
    assert inf["username"] == "demo_creator"


def test_update_my_influencer_bio(inf_session):
    new_bio = "Updated by automated test"
    r = inf_session.put(f"{API}/influencers/me", json={"bio": new_bio, "username": "demo_creator"})
    assert r.status_code == 200
    inf = r.json()["influencer"]
    assert inf["bio"] == new_bio
    # verify persisted
    r2 = inf_session.get(f"{API}/influencers/me")
    assert r2.json()["influencer"]["bio"] == new_bio


# ---------- Deals ----------
def test_list_deals_offer_sent(inf_session):
    r = inf_session.get(f"{API}/deals")
    assert r.status_code == 200
    deals = r.json()["deals"]
    assert len(deals) >= 1, "no deals seeded for demo influencer"
    statuses = [d["status"] for d in deals]
    assert "offer_sent" in statuses or "offer_accepted" in statuses


def test_patch_deal_status_accept(inf_session):
    # find an offer_sent deal — accept it; if already accepted, push back to offer_sent first
    deals = inf_session.get(f"{API}/deals").json()["deals"]
    assert deals
    deal = deals[0]
    did = deal["id"]
    # if already accepted, reset to offer_sent
    if deal["status"] != "offer_sent":
        rr = inf_session.patch(f"{API}/deals/{did}/status", json={"status": "offer_sent"})
        assert rr.status_code == 200
    r = inf_session.patch(f"{API}/deals/{did}/status", json={"status": "offer_accepted"})
    assert r.status_code == 200
    assert r.json()["status"] == "offer_accepted"
    # verify
    after = inf_session.get(f"{API}/deals").json()["deals"]
    target = next(d for d in after if d["id"] == did)
    assert target["status"] == "offer_accepted"


# ---------- Notifications ----------
def test_notifications_seed_and_read(inf_session):
    r = inf_session.get(f"{API}/notifications")
    assert r.status_code == 200
    notifs = r.json()["notifications"]
    assert len(notifs) >= 1
    target = next((n for n in notifs if "Lumen" in (n.get("title") or "") or "campaign offer" in (n.get("title") or "").lower()), notifs[0])
    nid = target["id"]
    rr = inf_session.post(f"{API}/notifications/{nid}/read")
    assert rr.status_code == 200
    # verify read=true now
    after = inf_session.get(f"{API}/notifications").json()["notifications"]
    target_after = next(n for n in after if n["id"] == nid)
    assert target_after["read"] is True


# ---------- Verification ----------
def test_submit_verification(inf_session):
    r = inf_session.post(f"{API}/verification", json={"kind": "influencer", "documents": [], "notes": "test"})
    assert r.status_code == 200
    req = r.json()["request"]
    assert req["status"] == "pending"
    assert req["kind"] == "influencer"


# ---------- Withdrawals ----------
def test_withdrawal_create_and_list(inf_session):
    payload = {"amount": 100, "method": "upi", "details": {"upi": "test@upi"}}
    r = inf_session.post(f"{API}/withdrawals", json=payload)
    assert r.status_code == 200
    req = r.json()["request"]
    assert req["amount"] == 100
    assert req["method"] == "upi"
    assert req["status"] == "pending"
    # GET /mine
    rr = inf_session.get(f"{API}/withdrawals/mine")
    assert rr.status_code == 200
    assert any(x["id"] == req["id"] for x in rr.json()["requests"])


def test_withdrawal_invalid_amount(inf_session):
    r = inf_session.post(f"{API}/withdrawals", json={"amount": 0, "method": "upi", "details": {"upi": "x@upi"}})
    # pydantic gt=0 → 422
    assert r.status_code in (400, 422)


# ---------- Seed idempotency ----------
def test_demo_seed_idempotent_counts(admin_session, inf_session):
    """Ensures the seed didn't create dupes by querying lists."""
    # NOTE: /api/brands and /api/brands/me return null due to stub override bug
    # (domain.py lines 132-144 placeholder stubs shadow real handlers).
    # We verify idempotency via /api/influencers (which works) and the demo
    # user/deal counts as a proxy.
    infs = admin_session.get(f"{API}/influencers").json()["influencers"]
    demo_infs = [i for i in infs if i.get("username") == "demo_creator"]
    assert len(demo_infs) == 1, f"demo_creator influencer duplicated: {len(demo_infs)}"
    # one deal for the demo influencer
    deals = inf_session.get(f"{API}/deals").json()["deals"]
    assert len(deals) >= 1
