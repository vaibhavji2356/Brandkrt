from backend_status import backend_status
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import logging
import secrets
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

import bcrypt
import jwt
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from starlette.middleware.cors import CORSMiddleware

# Part 5 production modules
import security as _security  # noqa: E402
import oauth as _oauth  # noqa: E402
_security.configure_logging()

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 7
LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15

mongo_url = os.environ.get('MONGO_URL', 'mongodb://127.0.0.1:27017')
db_name = os.environ.get('DB_NAME', 'brandkrt_db')
client = AsyncIOMotorClient(
    mongo_url,
    serverSelectionTimeoutMS=int(os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")),
    connectTimeoutMS=int(os.environ.get("MONGO_CONNECT_TIMEOUT_MS", "5000")),
    socketTimeoutMS=int(os.environ.get("MONGO_SOCKET_TIMEOUT_MS", "10000")),
    maxPoolSize=int(os.environ.get("MONGO_MAX_POOL_SIZE", "50")),
    minPoolSize=int(os.environ.get("MONGO_MIN_POOL_SIZE", "0")),
    maxIdleTimeMS=int(os.environ.get("MONGO_MAX_IDLE_TIME_MS", "60000")),
)
db = client[db_name]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Database migrations and admin bootstrap intentionally live in
    # database_setup.py, keeping the web process startup network-free.
    backend_status.mark_app_started()
    logger.info("[STARTUP] expensive initialization disabled; run `python database_setup.py` during deployment")
    try:
        yield
    finally:
        client.close()


app = FastAPI(title="BrandKrt API", lifespan=lifespan)
api_router = APIRouter(prefix="/api")
auth_router = APIRouter(prefix="/auth", tags=["auth"])

# -----------------------------------------------------------------------------
# Middlewares — attached BEFORE any router is included.
#
# Order matters. In Starlette the LAST middleware added is the OUTERMOST layer
# (first to see a request, last to touch a response). We therefore add custom
# security layers FIRST and CORSMiddleware LAST so that every response — even
# 403s emitted by the origin-CSRF guard — receives proper
# Access-Control-Allow-Origin headers and OPTIONS preflight is short-circuited
# by CORS before any other middleware sees it.
#
# Production origins are hard-coded as a safety net so a missing CORS_ORIGINS
# env var on Render can never break the public frontend.
# -----------------------------------------------------------------------------
_DEFAULT_CORS_ORIGINS = [
    "https://brandkrt.com",
    "https://www.brandkrt.com",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
]
_env_cors = [o.strip().rstrip("/") for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
_seen = set()
cors_origins = []
for _o in _env_cors + _DEFAULT_CORS_ORIGINS:
    if _o and _o not in _seen:
        _seen.add(_o)
        cors_origins.append(_o)
_is_prod = os.environ.get("APP_ENV", "development").lower() != "development"
# 1) innermost — defence-in-depth headers
app.add_middleware(_security.SecurityHeadersMiddleware, prod=_is_prod)
# 2) origin-based CSRF guard for state-changing requests
app.add_middleware(_security.OriginCSRFMiddleware, allow_origins=cors_origins)
# CORS is attached at the end of this module so it remains outermost.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("brandkrt")
_readiness_lock = asyncio.Lock()
_readiness_cache: Optional[dict] = None
_readiness_checked_at = 0.0
_readiness_cache_seconds = float(os.environ.get("READINESS_CACHE_SECONDS", "5"))

# -----------------------------------------------------------------------------
# Security helpers
# -----------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id, "email": email, "role": role, "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id, "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def _is_production_like_environment() -> bool:
    env = os.environ.get("APP_ENV", "").strip().lower()
    if env in {"production", "prod", "true", "1", "staging"}:
        return True

    frontend_url = os.environ.get("FRONTEND_URL", "").strip().lower()
    if frontend_url:
        if frontend_url.startswith("https://") and "localhost" not in frontend_url and "127.0.0.1" not in frontend_url:
            return True

    return False


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    secure = _is_production_like_environment()
    # cross-site cookies (Vercel <-> Render are different origins) require SameSite=None; only valid with Secure
    configured = os.environ.get("COOKIE_SAMESITE", "").strip().lower()
    samesite = configured or ("none" if secure else "lax")
    if samesite == "none" and not secure:
        secure = True
    response.set_cookie("access_token", access, httponly=True, secure=secure, samesite=samesite,
                        max_age=ACCESS_TOKEN_MINUTES * 60, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=secure, samesite=samesite,
                        max_age=REFRESH_TOKEN_DAYS * 24 * 60 * 60, path="/")


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


def serialize_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "name": user.get("name", ""),
        "role": user.get("role", "influencer"),
        "phone": user.get("phone"),
        "avatar_url": user.get("avatar_url"),
        "cover_url": user.get("cover_url"),
        "email_verified": user.get("email_verified", False),
        "created_at": user.get("created_at").isoformat() if isinstance(user.get("created_at"), datetime) else user.get("created_at"),
    }


# -----------------------------------------------------------------------------
# Email service
# -----------------------------------------------------------------------------
class EmailService:
    def __init__(self) -> None:
        self.provider = os.environ.get("EMAIL_PROVIDER", "").strip().lower() or "auto"
        self.from_addr = os.environ.get("EMAIL_FROM") or os.environ.get("SMTP_FROM") or "support@brandkrt.com"
        self.frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")

    async def send_verification(self, to: str, token: str) -> None:
        from email_templates import verify_email as tpl  # lazy import
        link = f"{self.frontend_url}/verify-email?token={token}"
        msg = tpl(link)
        await self._send(to, msg["subject"], msg["text"], msg.get("html"))

    async def send_signup_otp(self, to: str, code: str) -> None:
        from email_templates import verify_email as tpl  # lazy import
        link = f"{self.frontend_url}/verify-email"
        msg = tpl(link, code)
        await self._send(to, msg["subject"], msg["text"], msg.get("html"))

    async def send_password_reset(self, to: str, token: str) -> None:
        from email_templates import reset_password as tpl
        link = f"{self.frontend_url}/reset-password?token={token}"
        msg = tpl(link)
        await self._send(to, msg["subject"], msg["text"], msg.get("html"))

    def _smtp_config(self) -> dict:
        return {
            "host": os.environ.get("SMTP_HOST") or os.environ.get("EMAIL_HOST") or "smtp.hostinger.com",
            "port": int(os.environ.get("SMTP_PORT") or os.environ.get("EMAIL_PORT") or "465"),
            "user": os.environ.get("SMTP_USER") or self.from_addr,
            "password": os.environ.get("SMTP_PASS") or os.environ.get("EMAIL_PASSWORD"),
            "use_tls": os.environ.get("SMTP_USE_TLS", "false").strip().lower() in {"1", "true", "yes", "on"},
            "use_ssl": os.environ.get("SMTP_USE_SSL", "true").strip().lower() in {"1", "true", "yes", "on"},
        }

    def _allow_console_fallback(self) -> bool:
        configured = os.environ.get("EMAIL_CONSOLE_FALLBACK", "").strip().lower()
        if configured in {"0", "false", "no", "off"}:
            return False
        if configured in {"1", "true", "yes", "on"}:
            return True
        return not _is_production_like_environment()

    async def _send(self, to: str, subject: str, body: str, html: str = None) -> None:
        smtp_config = self._smtp_config()
        smtp_provider = (
            self.provider == "smtp"
            or (self.provider in {"auto", "console"} and bool(smtp_config["password"]))
        )
        if self.provider == "resend":
            try:
                import resend  # type: ignore
                api_key = os.environ.get("RESEND_API_KEY")
                if not api_key:
                    raise RuntimeError("EMAIL_PROVIDER=resend but RESEND_API_KEY is not configured")
                else:
                    resend.api_key = api_key
                    params = {
                        "from": self.from_addr,
                        "to": [to],
                        "subject": subject,
                        "text": body,
                    }
                    if html:
                        params["html"] = html
                    resend.Emails.send(params)
                    logger.info("[EMAIL:resend] sent to=%s subject=%s", to, subject)
                    return
            except Exception as e:
                if not self._allow_console_fallback():
                    raise RuntimeError(f"Resend email delivery failed: {e}") from e
                logger.warning("[EMAIL:resend] failed (%s); console fallback enabled", e)

        if self.provider == "smtp" and not smtp_config["password"]:
            raise RuntimeError("EMAIL_PROVIDER=smtp but SMTP_PASS is not configured")

        if smtp_provider:
            try:
                import smtplib
                from email.message import EmailMessage

                message = EmailMessage()
                message["From"] = self.from_addr
                message["To"] = to
                message["Subject"] = subject
                message.set_content(body)
                if html:
                    message.add_alternative(html, subtype="html")

                if smtp_config["use_ssl"]:
                    with smtplib.SMTP_SSL(smtp_config["host"], smtp_config["port"], timeout=30) as smtp:
                        smtp.login(smtp_config["user"], smtp_config["password"])
                        smtp.send_message(message)
                else:
                    with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=30) as smtp:
                        if smtp_config["use_tls"]:
                            smtp.starttls()
                        smtp.login(smtp_config["user"], smtp_config["password"])
                        smtp.send_message(message)

                logger.info("[EMAIL:smtp] sent to=%s subject=%s host=%s port=%s", to, subject, smtp_config["host"], smtp_config["port"])
                return
            except Exception as e:
                logger.error(
                    "[EMAIL:smtp] failed to send to=%s subject=%s host=%s port=%s error=%s",
                    to, subject, smtp_config["host"], smtp_config["port"], e,
                    exc_info=True,
                )
                if not self._allow_console_fallback():
                    raise RuntimeError(f"SMTP email delivery failed: {e}") from e

        if not self._allow_console_fallback():
            raise RuntimeError("No transactional email provider is configured")

        logger.info("[EMAIL:%s] to=%s subject=%s (console fallback; email body suppressed)", self.provider or "console", to, subject)


email_service = EmailService()


def normalize_phone(phone: str) -> str:
    raw = (phone or "").strip()
    if not raw:
        return ""
    prefix = "+" if raw.startswith("+") else ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return ""
    if prefix:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    return f"+{digits}"


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
Role = Literal["influencer", "brand", "admin"]


class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role
    phone: str = Field(min_length=8, max_length=24)
    otp_code: str = Field(min_length=4, max_length=12)
    accept_terms: bool = True


class RegisterOtpIn(BaseModel):
    email: EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailIn(BaseModel):
    token: str


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)


# -----------------------------------------------------------------------------
# Auth dependency
# -----------------------------------------------------------------------------
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if user.get("status") == "suspended":
            raise HTTPException(status_code=403, detail="Account is suspended")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# -----------------------------------------------------------------------------
# Brute-force helpers
# -----------------------------------------------------------------------------
def _aware(dt):
    if dt is None:
        return None
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _is_locked(identifier: str) -> bool:
    rec = await db.login_attempts.find_one({"identifier": identifier})
    if not rec:
        return False
    if rec.get("count", 0) >= LOCKOUT_THRESHOLD:
        locked_until = _aware(rec.get("locked_until"))
        if locked_until and locked_until > datetime.now(timezone.utc):
            return True
        await db.login_attempts.delete_one({"identifier": identifier})
    return False


async def _record_failed(identifier: str) -> None:
    rec = await db.login_attempts.find_one({"identifier": identifier})
    count = (rec or {}).get("count", 0) + 1
    update = {"count": count, "updated_at": datetime.now(timezone.utc)}
    if count >= LOCKOUT_THRESHOLD:
        update["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
    await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)


async def _clear_failed(identifier: str) -> None:
    await db.login_attempts.delete_one({"identifier": identifier})


# -----------------------------------------------------------------------------
# Auth endpoints
# -----------------------------------------------------------------------------
@auth_router.post("/register/send-otp")
async def send_register_otp(payload: RegisterOtpIn, _rl: None = Depends(_security.limiter_dependency("register_otp", limit=5, window=600))):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    now = datetime.now(timezone.utc)
    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.registration_otps.update_many(
        {"email": email, "used": False},
        {"$set": {"used": True, "updated_at": now}},
    )
    await db.registration_otps.insert_one({
        "email": email,
        "code": code,
        "used": False,
        "expires_at": now + timedelta(minutes=10),
        "created_at": now,
        "updated_at": now,
    })
    await email_service.send_signup_otp(email, code)
    return {"success": True, "message": "OTP sent to your email inbox"}


@auth_router.post("/register")
async def register(payload: RegisterIn, response: Response):
    if not payload.accept_terms:
        raise HTTPException(status_code=400, detail="You must accept the terms to continue")
    if payload.role == "admin":
        raise HTTPException(status_code=400, detail="Admin accounts cannot be self-registered")
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    phone = normalize_phone(payload.phone)
    if not phone or len("".join(ch for ch in phone if ch.isdigit())) < 10:
        raise HTTPException(status_code=400, detail="Please enter a valid mobile number")
    if await db.users.find_one({"phone": phone}):
        raise HTTPException(status_code=409, detail="An account with this phone number already exists")
    now = datetime.now(timezone.utc)
    otp = await db.registration_otps.find_one({"email": email, "code": payload.otp_code.strip(), "used": False})
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid OTP code")
    if _aware(otp["expires_at"]) < now:
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new code.")

    doc = {
        "email": email,
        "name": payload.name.strip(),
        "role": payload.role,
        "password_hash": hash_password(payload.password),
        "phone": phone,
        "email_verified": True,
        "avatar_url": None,
        "cover_url": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.users.insert_one(doc)
    user_id = str(result.inserted_id)
    await db.registration_otps.update_one({"_id": otp["_id"]}, {"$set": {"used": True, "used_at": now}})

    access = create_access_token(user_id, email, payload.role)
    refresh = create_refresh_token(user_id)
    set_auth_cookies(response, access, refresh)
    doc["_id"] = result.inserted_id
    return {"user": serialize_user(doc), "email_verified": True}


@auth_router.post("/login")
async def login(payload: LoginIn, request: Request, response: Response):
    email = payload.email.lower().strip()
    ip = _client_ip(request)
    identifier = f"{ip}:{email}"

    if await _is_locked(identifier):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        await _record_failed(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await _clear_failed(identifier)
    access = create_access_token(str(user["_id"]), email, user.get("role", "influencer"))
    refresh = create_refresh_token(str(user["_id"]))
    set_auth_cookies(response, access, refresh)
    return {"user": serialize_user(user)}


@auth_router.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"success": True}


@auth_router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": serialize_user(user)}


@auth_router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access = create_access_token(str(user["_id"]), user["email"], user.get("role", "influencer"))
        new_refresh = create_refresh_token(str(user["_id"]))
        set_auth_cookies(response, access, new_refresh)
        return {"user": serialize_user(user)}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@auth_router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordIn, request: Request,
                          _rl: None = Depends(_security.limiter_dependency("forgot", limit=5, window=600))):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    # Always respond success to avoid email enumeration
    if user:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        await db.password_reset_tokens.insert_one({
            "token": token, "user_id": str(user["_id"]), "email": email,
            "expires_at": now + timedelta(hours=1), "used": False, "created_at": now,
        })
        await email_service.send_password_reset(email, token)
    return {"success": True, "message": "If an account exists, a reset link has been sent."}


@auth_router.post("/reset-password")
async def reset_password(payload: ResetPasswordIn):
    rec = await db.password_reset_tokens.find_one({"token": payload.token})
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or used token")
    if _aware(rec["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token has expired")
    await db.users.update_one(
        {"_id": ObjectId(rec["user_id"])},
        {"$set": {"password_hash": hash_password(payload.new_password), "updated_at": datetime.now(timezone.utc)}},
    )
    await db.password_reset_tokens.update_one({"_id": rec["_id"]}, {"$set": {"used": True}})
    return {"success": True, "message": "Password updated. You can now log in."}


@auth_router.post("/verify-email")
async def verify_email(payload: VerifyEmailIn):
    rec = await db.verification_tokens.find_one({"token": payload.token})
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or used verification token")
    if _aware(rec["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification token has expired")
    await db.users.update_one({"_id": ObjectId(rec["user_id"])}, {"$set": {"email_verified": True}})
    await db.verification_tokens.update_one({"_id": rec["_id"]}, {"$set": {"used": True}})
    return {"success": True, "message": "Email verified successfully"}


# ----- Part 5: Google OAuth ID-token sign-in --------------------------------
class GoogleSignInIn(BaseModel):
    credential: str = Field(min_length=20)


@auth_router.get("/google/config")
async def google_config():
    """Frontend uses this to know whether to render the Google button."""
    return {"enabled": _oauth.is_configured(), "client_id": _oauth.get_client_id()}


@auth_router.post("/google")
async def google_signin(payload: GoogleSignInIn, request: Request, response: Response,
                        _rl: None = Depends(_security.limiter_dependency("oauth", limit=20, window=600))):
    # Google certificate retrieval is synchronous. Run it off the event loop so
    # a first Google login cannot stall health checks or unrelated requests.
    info = await asyncio.to_thread(_oauth.verify_google_id_token, payload.credential)
    email = info["email"]
    now = datetime.now(timezone.utc)
    user = await db.users.find_one({"email": email})
    if not user:
        doc = {
            "email": email,
            "name": info.get("name") or email.split("@")[0],
            "role": "influencer",
            "password_hash": hash_password(secrets.token_urlsafe(24)),
            "email_verified": bool(info.get("email_verified", True)),
            "avatar_url": info.get("picture"),
            "cover_url": None,
            "google_sub": info.get("sub"),
            "auth_provider": "google",
            "created_at": now,
            "updated_at": now,
        }
        res = await db.users.insert_one(doc)
        doc["_id"] = res.inserted_id
        user = doc
    else:
        if user.get("google_sub") and user.get("google_sub") != info.get("sub"):
            raise HTTPException(409, "This email is linked to a different Google account")
        # link google sub on next sign-in if missing
        if not user.get("google_sub"):
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"google_sub": info.get("sub"), "email_verified": True,
                          "avatar_url": user.get("avatar_url") or info.get("picture"),
                          "updated_at": now}},
            )
            user = await db.users.find_one({"_id": user["_id"]})

    access = create_access_token(str(user["_id"]), email, user.get("role", "influencer"))
    refresh = create_refresh_token(str(user["_id"]))
    set_auth_cookies(response, access, refresh)
    return {"user": serialize_user(user)}


@auth_router.post("/resend-verification")
async def resend_verification(user: dict = Depends(get_current_user)):
    if user.get("email_verified"):
        return {"success": True, "message": "Email already verified"}
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    await db.verification_tokens.insert_one({
        "token": token, "user_id": str(user["_id"]), "email": user["email"],
        "expires_at": now + timedelta(hours=24), "used": False, "created_at": now,
    })
    await email_service.send_verification(user["email"], token)
    return {"success": True, "message": "Verification email sent"}


# -----------------------------------------------------------------------------
# Profile endpoints
# -----------------------------------------------------------------------------
class ProfileUpdateIn(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    cover_url: Optional[str] = None


@api_router.patch("/profile")
async def update_profile(payload: ProfileUpdateIn, user: dict = Depends(get_current_user)):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update:
        return {"user": serialize_user(user)}
    update["updated_at"] = datetime.now(timezone.utc)
    await db.users.update_one({"_id": user["_id"]}, {"$set": update})
    fresh = await db.users.find_one({"_id": user["_id"]})
    return {"user": serialize_user(fresh)}


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


@api_router.post("/profile/change-password")
async def change_password(payload: PasswordChangeIn, user: dict = Depends(get_current_user)):
    if not verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(payload.new_password), "updated_at": datetime.now(timezone.utc)}},
    )
    return {"success": True}


@api_router.delete("/profile")
async def delete_account(response: Response, user: dict = Depends(get_current_user)):
    if user.get("role") == "admin":
        raise HTTPException(status_code=400, detail="Admin account cannot be deleted via API")
    await db.users.delete_one({"_id": user["_id"]})
    clear_auth_cookies(response)
    return {"success": True}


# -----------------------------------------------------------------------------
# Contact form
# -----------------------------------------------------------------------------
@api_router.post("/contact")
async def contact(payload: ContactIn, request: Request,
                  _rl: None = Depends(_security.limiter_dependency("contact", limit=10, window=600))):
    now = datetime.now(timezone.utc)
    await db.contact_messages.insert_one({**payload.model_dump(), "created_at": now})
    logger.info("[CONTACT] %s <%s> - %s", payload.name, payload.email, payload.subject)
    return {"success": True, "message": "Thanks! We'll be in touch within 24 hours."}


@api_router.get("/health")
async def health():
    """Backwards-compatible liveness endpoint used by existing deployments."""
    return {"status": "ok", "service": "brandkrt-api", **backend_status.snapshot()}


@api_router.get("/health/live")
async def health_live():
    """Cheap process liveness check. It intentionally does not touch MongoDB."""
    return {"status": "live", "service": "brandkrt-api", **backend_status.snapshot()}


@api_router.get("/health/ready")
async def health_ready(response: Response):
    """Dependency-aware readiness check for Render and frontend wake handling."""
    global _readiness_cache, _readiness_checked_at
    now = asyncio.get_running_loop().time()
    if _readiness_cache is None or now - _readiness_checked_at >= _readiness_cache_seconds:
        async with _readiness_lock:
            now = asyncio.get_running_loop().time()
            if _readiness_cache is None or now - _readiness_checked_at >= _readiness_cache_seconds:
                _readiness_cache = await backend_status.check_readiness(lambda: client.admin.command("ping"))
                _readiness_checked_at = now
    status = _readiness_cache
    if not status["isReady"]:
        response.status_code = 503
    return {"status": "ready" if status["isReady"] else "not_ready", "service": "brandkrt-api", **status}


# -----------------------------------------------------------------------------
# Register routers + CORS
# -----------------------------------------------------------------------------
api_router.include_router(auth_router)

# Part 1B: domain routes
import domain  # noqa: E402

domain.init(db, get_current_user)
domain.register_handlers()
for r in domain.ALL_ROUTERS:
    api_router.include_router(r)

# Part 4B: collaborations, chat, agreements
import part4b  # noqa: E402

part4b.init(db, get_current_user)
part4b.register_handlers()
for r in part4b.ALL_ROUTERS:
    api_router.include_router(r)

# Part 4C: performance, reviews, completion reports
import part4c  # noqa: E402

part4c.init(db, get_current_user)
part4c.register_handlers()
for r in part4c.ALL_ROUTERS:
    api_router.include_router(r)

app.include_router(api_router)

# Static mount for uploaded files (Part 1B)
from fastapi.staticfiles import StaticFiles  # noqa: E402
import os as _os
_uploads_dir = _os.environ.get("UPLOAD_ROOT", "./uploads")
_os.makedirs(_uploads_dir, exist_ok=True)
# Verification documents are never exposed through the legacy static mount.
# New verification files use the authenticated /api/uploads/{id} route.
for _public_folder in ("profiles", "brand_logos", "products", "contracts", "invoices", "chat"):
    _folder_path = _os.path.join(_uploads_dir, _public_folder)
    _os.makedirs(_folder_path, exist_ok=True)
    app.mount(
        f"/uploads/{_public_folder}",
        StaticFiles(directory=_folder_path),
        name=f"uploads-{_public_folder}",
    )

@app.options("/{full_path:path}", include_in_schema=False)
async def cors_preflight(full_path: str):
    return Response(status_code=204)


# Final middleware layer: keep CORS outermost so preflight and error responses
# from auth/security routes always include Access-Control-Allow-Origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)
