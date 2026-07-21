# Deploying BrandKrt — Vercel + Render

This project is a monorepo:
```
/                ← repo root
├── frontend/    ← React (CRA) — deploy on VERCEL
├── backend/     ← FastAPI       — deploy on RENDER (or Fly.io)
├── frontend/vercel.json
└── ...
```

---

## ✅ Frontend (Vercel)

In the Vercel project **Settings → General**:

| Field | Value |
|---|---|
| **Root Directory** | `frontend` |
| **Framework Preset** | Create React App |
| **Install Command** | `yarn install --frozen-lockfile` |
| **Build Command** | `yarn build` |
| **Output Directory** | `build` |
| **Node.js Version** | 20.x |

The checked-in `frontend/vercel.json` targets the current Render service at
`https://brandkrt.onrender.com`. `REACT_APP_BACKEND_URL` remains the canonical
frontend API origin and can point at a custom API domain.

### Vercel Environment Variables
| Key | Required | Example |
|---|---|---|
| `REACT_APP_BACKEND_URL` | optional | `https://api.brandkrt.com` |
| `REACT_APP_GOOGLE_CLIENT_ID` | optional | `1234567-abc.apps.googleusercontent.com` |

The Google client ID must match `GOOGLE_CLIENT_ID` on the backend and be added to the OAuth client's **Authorised JavaScript origins** in Google Cloud.

For the standard Vercel deployment, leave `REACT_APP_BACKEND_URL` unset. The
frontend then uses the checked-in same-origin `/api` rewrite, allowing
HTTP-only authentication cookies to work even when third-party cookies are
blocked. Set this variable only when using a deliberate custom API origin.

---

## ✅ Backend (Render)

| Field | Value |
|---|---|
| **Root Directory** | `backend` |
| **Runtime** | Python 3.11 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn server:app --host 0.0.0.0 --port $PORT --workers 1` |
| **Health Check Path** | `/api/health/ready` |

One async worker is the recommended baseline for small Render instances. It
avoids importing the application and opening a MongoDB pool twice. Increase
workers only after measuring CPU and memory on the selected instance size.

### Database initialization

Index creation and initial admin creation no longer run in every web worker.
Run the following explicitly once for a new database, and again when a release
adds indexes:

```bash
cd backend
python database_setup.py
```

The command is idempotent for indexes. It creates the configured admin only
when that email does not exist and never resets an existing admin password.
Use a Render pre-deploy command when the plan supports one; otherwise run it as
a one-off shell command before switching traffic to the new release.

### Required env vars (Render → Environment)
```
MONGO_URL=mongodb+srv://USER:PASS@cluster.mongodb.net/?retryWrites=true&w=majority
DB_NAME=brandkrt_db
JWT_SECRET=<64+ char random — rotate before launch>
ADMIN_EMAIL=admin@brandkrt.com
ADMIN_PASSWORD=<rotate before launch>
FRONTEND_URL=https://<your-vercel-app>.vercel.app
CORS_ORIGINS=https://<your-vercel-app>.vercel.app,https://brandkrt.com
APP_ENV=production
APP_VERSION=<release identifier>
COOKIE_SAMESITE=none           # cross-site cookies for Vercel↔Render
PUBLIC_BACKEND_URL=https://api.brandkrt.com
MONGO_SERVER_SELECTION_TIMEOUT_MS=5000
MONGO_CONNECT_TIMEOUT_MS=5000
MONGO_SOCKET_TIMEOUT_MS=10000
MONGO_MAX_POOL_SIZE=50
MONGO_MIN_POOL_SIZE=0
MONGO_MAX_IDLE_TIME_MS=60000
READINESS_CACHE_SECONDS=5
```

Every entry in `CORS_ORIGINS` must be an exact trusted origin. Vercel preview
domains are not accepted by wildcard; add a specific preview origin only for
the duration of an intentional review deployment.

### Email (SMTP from support@brandkrt.com)
```
EMAIL_PROVIDER=smtp
EMAIL_FROM=BrandKrt <support@brandkrt.com>
SMTP_HOST=<your-smtp-host>
SMTP_PORT=465
SMTP_USER=support@brandkrt.com
SMTP_PASS=<your-smtp-password>
SMTP_USE_SSL=true
SMTP_USE_TLS=false
```
Use the mailbox credentials for `support@brandkrt.com`. In production-like environments, the backend no longer logs verification/reset links as a fallback; missing or failing SMTP now surfaces a delivery error instead of silently printing the token.

### Optional — Google OAuth
```
GOOGLE_CLIENT_ID=<your-web-client-id>.apps.googleusercontent.com
```
1. Go to https://console.cloud.google.com/apis/credentials.
2. **Create credentials → OAuth client ID → Web application**.
3. **Authorised JavaScript origins** = your Vercel frontend URL (and any custom domain).
4. **Authorised redirect URIs** can be left empty (we use Google Identity Services with no redirect).
5. Copy the Client ID into `GOOGLE_CLIENT_ID` on Render **and** `REACT_APP_GOOGLE_CLIENT_ID` on Vercel.
6. Re-deploy both. The "Continue with Google" button on /login auto-activates.

### Optional — File storage (Cloudinary)
```
CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
MAX_UPLOAD_MB=10
MONGO_UPLOAD_MAX_MB=8
UPLOAD_ROOT=./uploads
```
1. Sign up at https://cloudinary.com — copy the `CLOUDINARY_URL` from the dashboard.
2. Paste it as a single env var on Render.
3. Existing upload endpoints (`POST /api/uploads/{folder}`, `POST /api/chat/upload`) start returning Cloudinary `secure_url` automatically. No frontend change needed — the React app already handles both relative and absolute URLs.

If `CLOUDINARY_URL` is not set, uploads continue to land on Render's local disk (ephemeral — files vanish on redeploy). Use this for dev only.

Instead of `CLOUDINARY_URL`, the backend also accepts the complete set of
`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET`.

Uploads are content-sniffed server-side. SVG, executable content, generic ZIP
archives, active PDFs, embedded executables, mismatched MIME types, and files
outside each folder's allow-list are rejected. Verification documents are
private and are served only to their owner or an admin through
`/api/uploads/{id}`; the legacy static mount does not expose the verification
folder.

### Optional — Payments (Razorpay)
```
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=rzp_test_xxx
RAZORPAY_KEY_SECRET=<your Razorpay key secret>
RAZORPAYX_ACCOUNT_NUMBER=<your RazorpayX account number>
RAZORPAYX_BANK_PAYOUT_MODE=IMPS
```
- `POST /api/payments/escrow` creates a Razorpay Order and returns Checkout details to the React app.
- The React app opens Razorpay Checkout from the existing `Fund escrow` button.
- After payment, `POST /api/payments/razorpay/verify` verifies the Razorpay signature on the backend before marking escrow as funded.
- Use test keys first. Switch to live keys only after Razorpay account activation and a successful test payment.

### Optional — Payments (Stripe)
```
PAYMENT_PROVIDER=stripe
STRIPE_SECRET_KEY=sk_live_xxx
```
- Default `PAYMENT_PROVIDER=stub` keeps the original DB-only escrow.
- When set to `stripe`, `POST /api/payments/escrow` creates a Stripe `PaymentIntent` with `capture_method=manual` and returns `client_secret` so the frontend can confirm via Stripe.js (already supported by the response shape).
- `POST /api/payments/{id}/release` calls `PaymentIntent.capture` on Stripe and flips the DB record to `released`.

### Environment source of truth

`backend/.env.example` and `frontend/.env.example` list every canonical runtime
variable used by the two applications. The backend still recognizes the legacy
aliases `BACKEND_URL`/`API_BASE_URL`, `SMTP_FROM`, `EMAIL_HOST`, `EMAIL_PORT`, and
`EMAIL_PASSWORD`, but new deployments should use the canonical names shown in
the example files.

---

## 🔐 Security checklist before launch
- [ ] `JWT_SECRET` rotated and ≥ 64 chars
- [ ] `ADMIN_PASSWORD` rotated, MFA-only afterwards
- [ ] `CORS_ORIGINS` exact production origins, no `*`
- [ ] `APP_ENV=production` (enables `Secure` cookies + HSTS)
- [ ] `COOKIE_SAMESITE=none` if frontend and backend live on different domains
- [ ] MongoDB Atlas IP allow-list configured, auth enabled
- [ ] `support@brandkrt.com` SMTP credentials configured and tested
- [ ] Google OAuth origins limited to production domain
- [ ] Cloudinary unsigned upload presets disabled — all uploads happen via our backend

---

## 🚀 First deploy order
1. Push the repo to GitHub.
2. Render → New Web Service → connect repo, Root = `backend`, paste env vars above.
3. Once the Render URL is up, set `CORS_ORIGINS` to include both Vercel domain and your custom domain.
4. Vercel → New Project → connect same repo, Root = `frontend`, set `REACT_APP_BACKEND_URL`.
5. Confirm `frontend/vercel.json` still targets the intended Render service.
6. Run `python database_setup.py` once for a new database or index release.
7. Smoke-test: `/api/health/live` returns `status: "live"`, `/api/health/ready` returns `isReady: true`, then test `/register`, `/login`, and `/influencer`.

---

## 🩺 Troubleshooting
| Symptom | Likely cause |
|---|---|
| `Forbidden origin` 403 on POST | `CORS_ORIGINS` missing or includes a trailing slash |
| Cookies not persisted on Safari | Need `APP_ENV=production` + `COOKIE_SAMESITE=none` so cookies become `Secure; SameSite=None` |
| Google button greyed out | `REACT_APP_GOOGLE_CLIENT_ID` empty or `GOOGLE_CLIENT_ID` not set on backend |
| Uploads return relative `/uploads/...` but 404 in prod | Cloudinary not configured — local disk is ephemeral on Render. Set `CLOUDINARY_URL` |
| Emails not arriving | Missing/incorrect SMTP env vars, or `support@brandkrt.com` mailbox authentication failed — check Render logs for `[EMAIL:smtp]` |
