# BrandKrt — PRD & Status

## Original problem statement
Build BrandKrt — a premium SaaS influencer marketing marketplace connecting brands and creators. Manages verification, contracts, payments, collaboration, analytics, campaign tracking. Premium Stripe/Linear/Apple/Notion aesthetic. Brand palette: Royal Navy #0A1F44, Gold #D4AF37, white.

## Tech stack actually used (Emergent env)
- React 19 + Tailwind + shadcn/ui + framer-motion + recharts (frontend)
- FastAPI + Motor + MongoDB (backend)
- JWT auth (httpOnly cookies) + bcrypt
- Email service abstraction: console-only for now (Resend pluggable in 1B+)

## User personas
- **Influencer** — creator monetizing via brand campaigns
- **Brand** — company running creator campaigns
- **Admin** — BrandKrt operator (verification, payouts, moderation)

## Core requirements (static)
- Premium landing, role-aware auth, KYC/verification, escrow payments, contracts, real-time analytics, in-app messaging gated by payment, admin moderation.

## Implemented — Part 1A (Feb 2026)
- Landing page (Hero, Features, How-it-Works, Why-Choose, Testimonials, Pricing, FAQ, Contact)
- Auth: register (role select), login, forgot/reset, verify email, refresh, brute-force lockout (IP+email, X-Forwarded-For), logout
- Sticky navbar + dark-mode toggle, footer, profile, settings (account/password/notifications/appearance + delete account), legal (Privacy/Terms/Refund), 404
- Modular EmailService (console provider); admin user seeded from env
- SEO: title, description, Open Graph, Twitter cards, favicon

## Implemented — Part 1C (Feb 2026)
- Shared UI primitives: NotificationBell (live unread count, mark-read), Empty/Error/Success states, StatusChip, ErrorBoundary
- Notification Center wired into Navbar (auto-polls /api/notifications every 30s)
- HelpCenter page at /help (topics grid + FAQ)
- Email template system: `backend/email_templates.py` — Welcome, Verify, Reset, Verification Approved/Rejected, Campaign Invitation/Accepted/Completed, Payment Released, Deadline Reminder (HTML + text, brand-styled, Resend-ready)
- PWA-ready: manifest.json (navy theme + icon), branded splash colors
- SEO: robots.txt, sitemap.xml, OG/Twitter meta, canonical-ready
- Production setup: README.md (folder structure, API surface, deployment guide), .env.example, vercel.json (rewrites + security headers)
- ErrorBoundary wraps the entire app; 404 already present
- Collections + indexes: users, brands, influencers, social_accounts (planned), products (planned), campaigns, deals, contracts (planned), transactions, payments, notifications, messages, verification_requests, withdrawal_requests, reviews, reports, activity_logs, admin_logs
- REST APIs (all under /api):
  - /brands, /influencers (upsert/me, list, get)
  - /campaigns (CRUD + status)
  - /deals (create, list, status with 7-state lifecycle)
  - /payments (escrow create + release; 8% platform fee, txid generation)
  - /notifications (list, mark read) — emitted on deal offer + verification decision
  - /messages (gated: 403 until payment escrowed)
  - /verification (submit, mine) + /admin/verification (review with notes + schedule call)
  - /withdrawals (submit, mine) + admin approve/reject
  - /reviews, /reports
  - /uploads/{folder} — local storage stub (profiles/brand_logos/products/verification/contracts/invoices), served at /uploads
  - /admin/overview (cards: users/brands/influencers/revenue/pending KYC/pending payouts/running/completed/cancelled + 12-week growth charts)
  - /admin/users, /admin/withdrawals, /admin/reports, /admin/logs
- RBAC: require_role() guards; admin-only endpoints; brand/influencer-scoped queries
- Audit: activity_logs (user actions) + admin_logs (admin decisions)
- Admin Console UI shell at /admin: sidebar nav, Overview (stat cards + line + bar charts), Users (search/filter), Verification (approve/reject dialog with notes + scheduled call), Withdrawals, Reports, Logs
- Login auto-redirects admins to /admin

## Backlog — P0 (Part 1C)
- Influencer dashboard (profile builder, social analytics, deals inbox, earnings, withdrawal)
- Brand dashboard (campaign creator, influencer discovery, deals tracker, billing, escrow checkout)
- Resend integration for transactional emails (brandkrt.com domain)
- Stripe escrow integration (currently DB-stub)
- WebSocket layer for real-time notifications + deal status

## Backlog — P1
- Social account verification (Instagram/YouTube OAuth)
- Contract templates + e-signature
- Multi-currency payout rails (Wise/Razorpay)
- Object storage (S3/GCS) replacing local uploads
- 2FA, audit log export, GDPR data export

## Backlog — P2
- AI matchmaking (brand brief → creator shortlist)
- Campaign performance attribution (UTM + pixel)
- Agency multi-workspace
- Mobile apps

## Known limitations (current build)
- Email = console provider only (tokens in backend logs)
- Google login is "coming soon" toast
- Payments are escrow stub (no Stripe yet)
- File uploads = local disk (ephemeral)
