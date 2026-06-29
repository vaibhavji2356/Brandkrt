# Deploying BrandKrt — Vercel + Render

This project is a monorepo:
```
/                ← repo root (what "Save to GitHub" creates)
├── frontend/    ← React (CRA) — deploy on VERCEL
├── backend/     ← FastAPI       — deploy on RENDER (or Fly.io)
├── vercel.json  ← used ONLY if Vercel Root Directory = repo root
└── ...
```

## ✅ Recommended Vercel setup (works out of the box)

In the Vercel project **Settings → General**:

| Field | Value |
|---|---|
| **Root Directory** | `frontend` |
| **Framework Preset** | Create React App |
| **Install Command** | *(leave default — Vercel auto-detects yarn from `yarn.lock`)* |
| **Build Command** | *(leave default — `yarn build`)* |
| **Output Directory** | *(leave default — `build`)* |
| **Node.js Version** | 20.x |

Why this works:
- `frontend/yarn.lock` is committed → Vercel uses **yarn**, not npm.
- `frontend/vercel.json` overrides rewrites/headers automatically.
- No `cd frontend` is needed because Vercel runs everything inside `frontend/`.

### Vercel **Environment Variables**
| Key | Value |
|---|---|
| `REACT_APP_BACKEND_URL` | `https://YOUR-RENDER-BACKEND.onrender.com` |

After your Render backend URL is known, also edit the two `destination` URLs in `frontend/vercel.json` and replace `YOUR-RENDER-BACKEND.onrender.com` with the real host. Commit + push.

---

## Alternative — Root Directory = `/` (repo root)

If you really want to leave Vercel's Root Directory unchanged, the root-level `vercel.json` handles it (it does `cd frontend` itself). But that requires **manually** setting:
- Install Command: `cd frontend && yarn install --frozen-lockfile`
- Build Command: `cd frontend && yarn build`
- Output Directory: `frontend/build`

The recommended setup (Root Directory = `frontend`) is simpler and avoids the npm-vs-yarn confusion.

---

## Render setup (backend)

| Field | Value |
|---|---|
| **Root Directory** | `backend` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn server:app --host 0.0.0.0 --port $PORT` |

### Render **Environment Variables**
```
MONGO_URL=<mongodb+srv://… from Mongo Atlas>
DB_NAME=brandkrt_db
JWT_SECRET=<64-char random>
ADMIN_EMAIL=admin@brandkrt.com
ADMIN_PASSWORD=<rotate this!>
FRONTEND_URL=https://<your-vercel-app>.vercel.app
CORS_ORIGINS=https://<your-vercel-app>.vercel.app,https://brandkrt.com
APP_ENV=production
EMAIL_PROVIDER=console
EMAIL_FROM=support@brandkrt.com
```
