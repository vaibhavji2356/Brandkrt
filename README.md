# BrandKrt

> The premium influencer marketing marketplace — connecting brands with creators.
> Production domain: https://brandkrt.com · Support: support@brandkrt.com

## Stack

- **Frontend**: React 19 (CRA), Tailwind CSS, shadcn/ui, framer-motion, recharts, react-router 7, sonner, react-hook-form, zod
- **Backend**: FastAPI, Motor (async MongoDB), PyJWT, bcrypt
- **Database**: MongoDB
- **Auth**: JWT (httpOnly cookies) + Emergent Google OAuth (Part 2)
- **Email**: Modular `EmailService` with SMTP for `support@brandkrt.com` and safe console fallback in dev (templates in `backend/email_templates.py`)
- **Storage**: Local disk + `/uploads` static mount in dev; S3/GCS-ready abstraction

## Folder structure

```
/app
├── backend/
│   ├── server.py               # FastAPI app, auth, CORS, health and lifecycle
│   ├── database_setup.py       # Explicit indexes + one-time admin bootstrap
│   ├── domain.py               # Models + routes: brands, influencers, campaigns,
│   │                            #   deals, payments (escrow), notifications, messages,
│   │                            #   verification, withdrawals, reviews, reports, uploads, admin
│   ├── email_templates.py      # Branded HTML email templates
│   ├── requirements.txt
│   └── .env                    # MONGO_URL, JWT_SECRET, ADMIN_*, EMAIL_PROVIDER, FRONTEND_URL
├── frontend/
│   ├── public/                 # index.html, manifest.json, robots.txt, sitemap.xml
│   ├── vercel.json             # Vercel rewrites, SPA fallback and headers
│   ├── yarn.lock               # Frozen production dependency graph
│   └── src/
│       ├── App.js              # All routes
│       ├── index.css           # Tailwind + brand tokens (navy + gold)
│       ├── lib/                # api.js, brand.js (logo URLs, constants)
│       ├── context/            # AuthContext, ThemeContext
│       ├── components/         # Logo, Navbar, Footer, NotificationBell,
│       │                       #   ProtectedRoute, ErrorBoundary, State (Empty/Error/Success/StatusChip)
│       ├── components/ui/      # shadcn primitives (button, input, dialog, …)
│       └── pages/
│           ├── Landing.jsx     # Hero, Features, How-it-works, Pricing, FAQ, Contact
│           ├── About.jsx · Profile.jsx · Settings.jsx · HelpCenter.jsx · NotFound.jsx
│           ├── auth/           # Login, Register, Forgot/Reset, VerifyEmail
│           ├── legal/          # Privacy · Terms · Refund
│           └── admin/          # AdminLayout, AdminOverview, AdminSections (Users, Verification, Withdrawals, Reports, Logs)
├── memory/
│   ├── PRD.md
│   └── test_credentials.md
└── README.md
```

## Local development

```bash
# Backend
cd backend
pip install -r requirements.txt
# .env required (see .env.example)
python database_setup.py  # once for a new database or index release
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Frontend
cd frontend
yarn install
yarn start
```

In this Emergent pod, both services are supervisor-managed and hot-reloaded. Restart only after `.env` changes:
```
sudo supervisorctl restart backend
```

## Production deployment

### Frontend → Vercel
1. Connect the repo, set the project root to `frontend`.
2. Vercel will pick up `frontend/vercel.json` (rewrites all `/api/*` and `/uploads/*` to the API origin).
3. Leave `REACT_APP_BACKEND_URL` unset for the standard deployment so API calls use the same-origin Vercel rewrite. Set it only for a deliberate custom API origin.

### Backend → any Python host (Render, Fly, Railway, AWS)
1. Provide MongoDB connection string (Mongo Atlas recommended).
2. Set env per `.env.example` (`JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `FRONTEND_URL`, `CORS_ORIGINS`).
3. Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`.
4. Point `api.brandkrt.com` DNS at the backend.
5. Set `EMAIL_PROVIDER=smtp` and add the `support@brandkrt.com` SMTP settings (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`).

### Security checklist before launch
- [ ] `JWT_SECRET` rotated and ≥64 chars
- [ ] `ADMIN_PASSWORD` rotated
- [ ] `CORS_ORIGINS` set to exact production origins (no `*`)
- [ ] `APP_ENV=production` (enables `Secure` cookies)
- [ ] Browser authentication uses HTTP-only cookies; no access JWT is stored in Web Storage
- [ ] MongoDB IP allowlist + auth
- [ ] Run `frontend/vercel.json` security headers (X-Frame-Options, Permissions-Policy)
- [ ] Object storage migrated off local disk (S3/GCS)

## API surface (high-level)

| Group | Routes |
|---|---|
| Auth | `/api/auth/{register,login,logout,me,refresh,forgot-password,reset-password,verify-email,resend-verification}` |
| Profile | `/api/profile` (PATCH/DELETE), `/api/profile/change-password` |
| Brands | `/api/brands` (list, `/me` upsert/get, `/{id}`) |
| Influencers | `/api/influencers` (list, `/me` upsert/get, `/{id}`) |
| Campaigns | `/api/campaigns` (POST/GET, `/{id}`, `/{id}/status`) |
| Deals | `/api/deals` (POST/GET, `/{id}/status`) |
| Payments | `/api/payments/escrow`, `/api/payments/{id}/release`, `/api/payments` |
| Notifications | `/api/notifications`, `/api/notifications/{id}/read` |
| Messages | `/api/messages/{deal_id}`, `/api/messages` (POST) — gated by escrow |
| Verification | `/api/verification`, `/api/verification/mine` |
| Withdrawals | `/api/withdrawals`, `/api/withdrawals/mine` |
| Reviews/Reports | `/api/reviews`, `/api/reports` |
| Uploads | `/api/uploads/{folder}` (multipart) |
| Admin | `/api/admin/{overview,users,verification,verification/{id}/decision,withdrawals,withdrawals/{id}/decision,reports,logs}` |
| Contact | `/api/contact` |
| Health | `/api/health`, `/api/health/live`, `/api/health/ready` |
| Brand Discovery AI | `POST /api/ai/brand-discovery/preview` (authenticated brand/admin, non-persistent preview) |

### Brand Discovery AI — Phase 3A

The backend includes a vendor-neutral Brand Discovery preview package under
`backend/brand_discovery_ai/`. It supports deterministic mock results and an
OpenAI Responses API provider while preserving the same authenticated,
rate-limited, non-persistent endpoint. Configure it with `AI_PROVIDER`,
`AI_API_KEY`, `AI_ALLOWED_MODELS`, `AI_MODEL`, `AI_TIMEOUT_SECONDS`,
`AI_MAX_RETRIES`, `AI_MAX_OUTPUT_TOKENS`,
`AI_MAX_REQUESTS_PER_USER_PER_DAY`, `AI_MAX_REQUESTS_PER_IP_PER_MINUTE`,
`AI_DAILY_BUDGET_USD`, `AI_MAX_ESTIMATED_COST_PER_REQUEST_USD`, and
`AI_MOCK_MODE`. Keep `AI_PROVIDER=mock` and
`AI_MOCK_MODE=true` for zero-cost development without an API key. To enable
OpenAI staging, set both `AI_ALLOWED_MODELS=gpt-5.6-luna` and
`AI_MODEL=gpt-5.6-luna`, provide `AI_API_KEY`, and set `AI_MOCK_MODE=false`.
Unknown or non-allow-listed models fail closed; there is no model fallback.

Paid-provider requests reserve a retry-inclusive conservative maximum cost
before network access. Per-user daily, per-IP minute, per-request cost, and
daily application budget limits are enforced in memory. These counters are
isolated to one Python process and reset on restart; they are staging
guardrails, not multi-worker production billing controls. Mock requests do not
consume paid-provider counters or budget.

Offline calibration estimates approximately 531 prompt tokens plus 276 schema
tokens. Calibrated output fixtures estimate 201, 986, 1,968, and 3,931 tokens
for 1, 5, 10, and 20 results respectively. Keep the 4,000 output-token cap:
reducing it would make the 20-result contract unreliable. The provider uses
`reasoning.effort=none`, strict structured output, `store=false`, and at most
one retry.

After setting the OpenAI environment values, one explicitly authorized staging
call can be run from `backend/` with:

```powershell
.\.venv\Scripts\python.exe -m brand_discovery_ai.staging_call --allow-paid-call --result-limit 1
```

The command disables retries, caps that call at 1,200 output tokens, and prints
only provider/model, result count, duration, token usage, and cost summary. It
never prints credentials, prompts, headers, or raw provider output. No local
model, scraping, embeddings, persistence, or vector database is included.

## Default credentials

See `memory/test_credentials.md`. **Rotate before production.**

## Roadmap

- Part 2 — Influencer Dashboard (profile builder, deals inbox, earnings) ✅
- Part 3 — Brand Dashboard (campaign creator, discovery, billing) ✅
- Part 4 — Collaborations · Chat · Agreements · Performance · Reviews ✅
- **Part 5 — Production hardening ✅**
  - SMTP email provider (env-driven, safe console fallback in dev)
  - Google OAuth sign-in via Google Identity Services + ID-token verification
  - Cloudinary file storage with local fallback (`POST /api/uploads/{folder}` and `POST /api/chat/upload` unchanged)
  - Pluggable payment provider — `stub` (default), `razorpay`, or `stripe` via `PAYMENT_PROVIDER`
  - Security middleware: HSTS in prod, X-Frame-Options DENY, Permissions-Policy, Origin-based CSRF check
  - In-memory rate limiter on register / forgot-password / contact / OAuth
  - Production-safe logging with secret redaction
  - Cross-site cookie config (`COOKIE_SAMESITE=none` when Vercel↔Render are on different origins)
  - Expanded SEO: canonical, JSON-LD Organization + WebSite + Product, richer OG/Twitter, image sitemap
  - Vercel security headers + static asset immutable cache
  - `.env.example` for backend and frontend
  - Detailed `DEPLOYMENT.md` covering SMTP email, Google OAuth, Cloudinary, Razorpay/Stripe activation
