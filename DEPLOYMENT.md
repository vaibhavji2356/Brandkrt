# Deploying BrandKrt — Vercel + Render

This project is a monorepo:
```
/                ← repo root
├── frontend/    ← React (CRA) — deploy on VERCEL
├── backend/     ← FastAPI       — deploy on RENDER (or Fly.io)
├── vercel.json
└── ...
```

---

## ✅ Frontend (Vercel)

In the Vercel project **Settings → General**:

| Field | Value |
|---|---|
| **Root Directory** | `frontend` |
| **Framework Preset** | Create React App |
| **Install Command** | *(leave default — yarn auto-detected from `yarn.lock`)* |
| **Build Command** | *(leave default — `yarn build`)* |
| **Output Directory** | *(leave default — `build`)* |
| **Node.js Version** | 20.x |

After your Render backend URL is known, edit `frontend/vercel.json` rewrite destinations (`YOUR-RENDER-BACKEND.onrender.com`) and commit + push.

### Vercel Environment Variables
| Key | Required | Example |
|---|---|---|
| `REACT_APP_BACKEND_URL` | ✅ | `https://api.brandkrt.com` |
| `REACT_APP_GOOGLE_CLIENT_ID` | optional | `1234567-abc.apps.googleusercontent.com` |

The Google client ID must match `GOOGLE_CLIENT_ID` on the backend and be added to the OAuth client's **Authorised JavaScript origins** in Google Cloud.

---

## ✅ Backend (Render)

| Field | Value |
|---|---|
| **Root Directory** | `backend` |
| **Runtime** | Python 3.11 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn server:app --host 0.0.0.0 --port $PORT --workers 2` |
| **Health Check Path** | `/api/health` |

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
COOKIE_SAMESITE=none           # cross-site cookies for Vercel↔Render
```

### Optional — Email (Resend)
```
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxx
EMAIL_FROM=BrandKrt <no-reply@brandkrt.com>
```
1. Create an account at https://resend.com and add a domain (`brandkrt.com`).
2. Add the DNS records Resend shows you (SPF, DKIM, Return-Path).
3. Verify the domain, then create an API key with `Sending access`.
4. Paste the key as `RESEND_API_KEY` in Render.
Leaving `EMAIL_PROVIDER=console` (default) keeps the dev behaviour — verification + reset tokens just appear in Render logs.

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
```
1. Sign up at https://cloudinary.com — copy the `CLOUDINARY_URL` from the dashboard.
2. Paste it as a single env var on Render.
3. Existing upload endpoints (`POST /api/uploads/{folder}`, `POST /api/chat/upload`) start returning Cloudinary `secure_url` automatically. No frontend change needed — the React app already handles both relative and absolute URLs.

If `CLOUDINARY_URL` is not set, uploads continue to land on Render's local disk (ephemeral — files vanish on redeploy). Use this for dev only.

### Optional — Payments (Stripe)
```
PAYMENT_PROVIDER=stripe
STRIPE_SECRET_KEY=sk_live_xxx
```
- Default `PAYMENT_PROVIDER=stub` keeps the original DB-only escrow.
- When set to `stripe`, `POST /api/payments/escrow` creates a Stripe `PaymentIntent` with `capture_method=manual` and returns `client_secret` so the frontend can confirm via Stripe.js (already supported by the response shape).
- `POST /api/payments/{id}/release` calls `PaymentIntent.capture` on Stripe and flips the DB record to `released`.

---

## 🔐 Security checklist before launch
- [ ] `JWT_SECRET` rotated and ≥ 64 chars
- [ ] `ADMIN_PASSWORD` rotated, MFA-only afterwards
- [ ] `CORS_ORIGINS` exact production origins, no `*`
- [ ] `APP_ENV=production` (enables `Secure` cookies + HSTS)
- [ ] `COOKIE_SAMESITE=none` if frontend and backend live on different domains
- [ ] MongoDB Atlas IP allow-list configured, auth enabled
- [ ] Resend domain DKIM verified before sending bulk
- [ ] Google OAuth origins limited to production domain
- [ ] Cloudinary unsigned upload presets disabled — all uploads happen via our backend

---

## 🚀 First deploy order
1. Push the repo to GitHub.
2. Render → New Web Service → connect repo, Root = `backend`, paste env vars above.
3. Once the Render URL is up, set `CORS_ORIGINS` to include both Vercel domain and your custom domain.
4. Vercel → New Project → connect same repo, Root = `frontend`, set `REACT_APP_BACKEND_URL`.
5. Update `frontend/vercel.json` rewrite destinations to the real Render URL, commit, push.
6. Smoke-test: `/api/health` returns `{status: "ok"}`, `/register`, `/login`, `/influencer` (after login).

---

## 🩺 Troubleshooting
| Symptom | Likely cause |
|---|---|
| `Forbidden origin` 403 on POST | `CORS_ORIGINS` missing or includes a trailing slash |
| Cookies not persisted on Safari | Need `APP_ENV=production` + `COOKIE_SAMESITE=none` so cookies become `Secure; SameSite=None` |
| Google button greyed out | `REACT_APP_GOOGLE_CLIENT_ID` empty or `GOOGLE_CLIENT_ID` not set on backend |
| Uploads return relative `/uploads/...` but 404 in prod | Cloudinary not configured — local disk is ephemeral on Render. Set `CLOUDINARY_URL` |
| Emails not arriving | `EMAIL_PROVIDER` still `console`, or Resend domain not verified — check Render logs for `[EMAIL:resend]` line |
