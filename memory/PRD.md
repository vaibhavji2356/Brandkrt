# BrandKrt — PRD & Status

A creator marketplace where small/medium businesses meet nano & micro creators (1K–100K).
Stack: React (CRA + CRACO) + FastAPI + MongoDB Atlas. Frontend on Vercel, backend on Render.

---

## User personas
- **SMB / Small Business** — local shop, café, salon, D2C founder. Limited budget, needs reach via authentic local voices.
- **Nano / Micro Creator** — 1K–100K followers, lifestyle/fashion/food/fitness/etc., wants reliable paid collabs.
- **Admin / Operator** — BrandKrt internal staff approving verifications, withdrawals, moderating reports.

## Core requirements (stable)
- Verified two-sided marketplace (KYC + handle ownership)
- Flat 8% platform fee on every deal
- Escrow-style payment hold + release on delivery (PSP integration deferred — currently stub)
- Role-based dashboards (Influencer, Brand, Admin)
- In-app notifications + email
- Rupee-first (₹), India primary geo

---

## ✅ Implemented (Part 1 — pre-existing, untouched)
- **Auth**: register/login/logout/refresh, JWT in httpOnly cookies, bcrypt, brute-force lockout, email verification, password reset.
- **Profile & Settings** for all roles.
- **Admin console** at `/admin/*`: Overview, Users, Verification, Withdrawals, Reports, Logs.
- **Backend resources**: brands, influencers, campaigns, deals (7-state lifecycle), payments (escrow stub, 8% fee), notifications, messages (gated by escrow), verification requests, withdrawal requests, reviews, reports, uploads.
- **Reusable UI**: Navbar, Footer, Logo, SiteLayout, ProtectedRoute, NotificationBell (30s polling), ThemeToggle, ErrorBoundary, State helpers (EmptyState, ErrorState, SuccessState, StatusChip), 46 shadcn primitives.
- **Landing page** with Hero / Features / How-it-works / Why-choose / Testimonials / Pricing / FAQ / Contact (Part 1 UI structure).

## ✅ Implemented (Part 2 — this session, 2026-01-29)
- **Landing copy rewrite** (UI structure untouched) — re-positioned for SMBs + nano/micro creators across Hero (badge, headline, subtitle, CTAs, stats), Features overline + copy, How-it-works steps, Why-choose blurbs, Testimonials, Pricing plan names (Starter/SMB/Pro-Agency), FAQ, Contact intro.
- **Influencer Module** at `/influencer/*` with sidebar layout + mobile drawer:
  - `InfluencerLayout` — desktop sidebar, mobile drawer with hamburger + close, topbar logout (mobile), centralised `handleSignOut` using `window.location.replace('/')` to bypass ProtectedRoute race.
  - `InfluencerOverview` — KPI cards (Earned/Pending/Active Deals/Verification), profile-completion banner with progress bar, recent deals, recent activity.
  - `InfluencerProfile` — full form (basics, bio, socials, reach & pricing, payouts), PUT /influencers/me on save, POST /verification on "Submit for verification".
  - `InfluencerCampaigns` — tabbed by deal status, accept/decline + advance status, escrow-locked chat indicator.
  - `InfluencerEarnings` — Total/Pending/Requested/Available stats, 12-week recharts line chart, Request Withdrawal dialog (UPI/Bank), payments + withdrawals history.
  - `InfluencerNotifications` — full list, All/Unread tabs, per-row mark-read, mark-all-read.
  - `lib/influencerApi.js` — thin axios wrapper.
- **Role-based redirect after login/register** — admin → `/admin`, influencer → `/influencer`, brand → `/profile` (placeholder). Uses `requestAnimationFrame` to defer navigation one frame so AuthContext.setUser commits before ProtectedRoute mounts.
- **Navbar Dashboard link** in user dropdown for influencer + admin roles.
- **Mobile responsiveness** — hero headline collapses block on small screens, CTAs stack vertically, sidebar becomes drawer, KPI cards reflow 2-cols → 4-cols, charts pin explicit height, tabs wrap.
- **Backend additions** (approved scope only):
  - `JWT_SECRET` + `SEED_DEMO` + admin/demo credentials added to `/app/backend/.env` (dev only — production env on Render is untouched).
  - Idempotent demo seed (`_seed_demo_data`) creating 1 demo brand, 1 demo influencer, 1 campaign ("Glow Summer Launch"), 1 deal in `offer_sent`, 1 unread notification. Controlled by `SEED_DEMO=true`.
  - `CORS_ORIGINS` widened to include the preview URL so credentialed (cookie) requests succeed.

## 🧪 Verified
- `CI=true yarn build` → green (multiple runs).
- Backend pytest (testing agent ran): 13/13 PASS for Part 2 scope (auth, /influencers/me GET+PUT, /deals GET+PATCH, /notifications GET+/read, /verification POST, /withdrawals POST+/mine, seed idempotency).
- Frontend testing agent: all 7 fix-verifications PASS in iteration_8 (login redirect, desktop+mobile logout to /, hero copy, drawer testids, drawer logout reachable, dialog a11y, Recharts warnings gone).

---

## 🪲 Known pre-existing issues (out of Part 2 scope, deferred to Brand Module ticket)
- `GET /api/brands` and `GET /api/brands/me` return `null` due to placeholder stub handlers in `domain.py` lines 132–144 that shadow the real handlers registered later. Brand-side discovery/listing broken.
- `PUT /api/influencers/me` and `PUT /api/brands/me` use `model_dump()` without `exclude_unset=True` → partial updates overwrite unspecified fields. UI mitigates by sending the full profile.
- `POST /api/withdrawals` does not server-side-validate `amount ≤ available_balance`. UI validates.
- `/api/uploads/{folder}` has extension whitelist but no max-size enforcement.

## 🗂️ Backlog (next sessions)
- **P0** — Brand Module (Brand dashboard, Brand layout at `/brand`, campaign creation, deal management, escrow funding UI). Same role-based redirect pattern.
- **P0** — Fix the 4 backend gaps above (single PR alongside Brand Module).
- **P1** — Real payment provider (Stripe / Razorpay) replacing escrow stub; webhook handling.
- **P1** — Messaging real-time (currently polled, gated by escrow).
- **P2** — In-app email digest, analytics export for SMBs, agency multi-workspace.
- **P2** — Search & matching (recommended creators per brand).

---

## Architecture notes
- All backend routes prefixed with `/api`. Frontend uses `REACT_APP_BACKEND_URL` from `frontend/.env`.
- Cookies: `access_token` (15 min), `refresh_token` (7 d), httpOnly, `sameSite=lax`. Axios uses `withCredentials: true`.
- Notifications poll every 30 s via `NotificationBell`.
- Demo seed is idempotent — restarts won't duplicate.
- Logout uses `window.location.replace('/')` to perform a hard navigation that sidesteps `ProtectedRoute`'s synchronous `<Navigate to="/login?from=..." />` redirect. Same pattern recommended when Brand/Admin layouts add explicit logout buttons.
