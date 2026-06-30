# BrandKrt

> The premium influencer marketing marketplace — connecting brands with creators.
> Production domain: https://brandkrt.com · Support: support@brandkrt.com

## Stack

- **Frontend**: React 19 (CRA), Tailwind CSS, shadcn/ui, framer-motion, recharts, react-router 7, sonner, react-hook-form, zod
- **Backend**: FastAPI, Motor (async MongoDB), PyJWT, bcrypt
- **Database**: MongoDB
- **Auth**: JWT (httpOnly cookies) + Emergent Google OAuth (Part 2)
- **Email**: Modular `EmailService` — `console` in dev, `Resend` in production (templates in `backend/email_templates.py`)
- **Storage**: Local disk + `/uploads` static mount in dev; S3/GCS-ready abstraction

## Folder structure

```
/app
├── backend/
│   ├── server.py               # FastAPI app, auth, CORS, startup, admin seed
│   ├── domain.py               # Models + routes: brands, influencers, campaigns,
│   │                            #   deals, payments (escrow), notifications, messages,
│   │                            #   verification, withdrawals, reviews, reports, uploads, admin
│   ├── email_templates.py      # Branded HTML email templates
│   ├── requirements.txt
│   └── .env                    # MONGO_URL, JWT_SECRET, ADMIN_*, EMAIL_PROVIDER, FRONTEND_URL
├── frontend/
│   ├── public/                 # index.html, manifest.json, robots.txt, sitemap.xml
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
├── .env.example
├── vercel.json
└── README.md
```

## Local development

```bash
# Backend
cd backend
pip install -r requirements.txt
# .env required (see .env.example) — admin user seeds automatically on startup
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
1. Connect the repo, set the project root to `/`.
2. Vercel will pick up `vercel.json` (rewrites all `/api/*` and `/uploads/*` to the API origin).
3. Set env: `REACT_APP_BACKEND_URL=https://api.brandkrt.com`.

### Backend → any Python host (Render, Fly, Railway, AWS)
1. Provide MongoDB connection string (Mongo Atlas recommended).
2. Set env per `.env.example` (`JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `FRONTEND_URL`, `CORS_ORIGINS`).
3. Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`.
4. Point `api.brandkrt.com` DNS at the backend.
5. (Optional) Set `EMAIL_PROVIDER=resend` and add `RESEND_API_KEY` once the brandkrt.com domain is verified.

### Security checklist before launch
- [ ] `JWT_SECRET` rotated and ≥64 chars
- [ ] `ADMIN_PASSWORD` rotated
- [ ] `CORS_ORIGINS` set to exact production origins (no `*`)
- [ ] `APP_ENV=production` (enables `Secure` cookies)
- [ ] MongoDB IP allowlist + auth
- [ ] Run `vercel.json` security headers (X-Frame-Options, Permissions-Policy)
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
| Health | `/api/health` |

## Default credentials

See `memory/test_credentials.md`. **Rotate before production.**

## Roadmap

- Part 2 — Influencer Dashboard (profile builder, deals inbox, earnings) ✅
- Part 3 — Brand Dashboard (campaign creator, discovery, billing) ✅
- Part 4 — Collaborations · Chat · Agreements · Performance · Reviews ✅
- **Part 5 — Production hardening ✅**
  - Resend email provider (env-driven, falls back to console in dev)
  - Google OAuth sign-in via Google Identity Services + ID-token verification
  - Cloudinary file storage with local fallback (`POST /api/uploads/{folder}` and `POST /api/chat/upload` unchanged)
  - Pluggable payment provider — `stub` (default) or `stripe` via `PAYMENT_PROVIDER`
  - Security middleware: HSTS in prod, X-Frame-Options DENY, Permissions-Policy, Origin-based CSRF check
  - In-memory rate limiter on register / forgot-password / contact / OAuth
  - Production-safe logging with secret redaction
  - Cross-site cookie config (`COOKIE_SAMESITE=none` when Vercel↔Render are on different origins)
  - Expanded SEO: canonical, JSON-LD Organization + WebSite + Product, richer OG/Twitter, image sitemap
  - Vercel security headers + static asset immutable cache
  - `.env.example` for backend and frontend
  - Detailed `DEPLOYMENT.md` covering Resend, Google OAuth, Cloudinary, Stripe activation
