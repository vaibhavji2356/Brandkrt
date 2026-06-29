from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

import bcrypt
import jwt
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from starlette.middleware.cors import CORSMiddleware

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 7
LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

app = FastAPI(title="BrandKrt API")
api_router = APIRouter(prefix="/api")
auth_router = APIRouter(prefix="/auth", tags=["auth"])

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("brandkrt")

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


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    secure = os.environ.get("APP_ENV", "development") != "development"
    response.set_cookie("access_token", access, httponly=True, secure=secure, samesite="lax",
                        max_age=ACCESS_TOKEN_MINUTES * 60, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=secure, samesite="lax",
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
        "avatar_url": user.get("avatar_url"),
        "cover_url": user.get("cover_url"),
        "email_verified": user.get("email_verified", False),
        "created_at": user.get("created_at").isoformat() if isinstance(user.get("created_at"), datetime) else user.get("created_at"),
    }


# -----------------------------------------------------------------------------
# Email service (modular abstraction - console only for Part 1A)
# -----------------------------------------------------------------------------
class EmailService:
    def __init__(self) -> None:
        self.provider = os.environ.get("EMAIL_PROVIDER", "console")
        self.from_addr = os.environ.get("EMAIL_FROM", "support@brandkrt.com")
        self.frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")

    async def send_verification(self, to: str, token: str) -> None:
        link = f"{self.frontend_url}/verify-email?token={token}"
        await self._send(to, "Verify your BrandKrt email", f"Welcome to BrandKrt! Verify your email: {link}")

    async def send_password_reset(self, to: str, token: str) -> None:
        link = f"{self.frontend_url}/reset-password?token={token}"
        await self._send(to, "Reset your BrandKrt password", f"Reset link (expires in 1 hour): {link}")

    async def _send(self, to: str, subject: str, body: str) -> None:
        if self.provider == "console":
            logger.info("[EMAIL:%s] to=%s subject=%s\n%s", self.provider, to, subject, body)
        # NOTE: Resend / SendGrid providers can be plugged in here in Part 1B.


email_service = EmailService()


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
    accept_terms: bool = True


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
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# -----------------------------------------------------------------------------
# Brute-force helpers
# -----------------------------------------------------------------------------
async def _is_locked(identifier: str) -> bool:
    rec = await db.login_attempts.find_one({"identifier": identifier})
    if not rec:
        return False
    if rec.get("count", 0) >= LOCKOUT_THRESHOLD:
        locked_until = rec.get("locked_until")
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
@auth_router.post("/register")
async def register(payload: RegisterIn, response: Response):
    if not payload.accept_terms:
        raise HTTPException(status_code=400, detail="You must accept the terms to continue")
    if payload.role == "admin":
        raise HTTPException(status_code=400, detail="Admin accounts cannot be self-registered")
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    now = datetime.now(timezone.utc)
    doc = {
        "email": email,
        "name": payload.name.strip(),
        "role": payload.role,
        "password_hash": hash_password(payload.password),
        "email_verified": False,
        "avatar_url": None,
        "cover_url": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.users.insert_one(doc)
    user_id = str(result.inserted_id)

    # email verification token
    verify_token = secrets.token_urlsafe(32)
    await db.verification_tokens.insert_one({
        "token": verify_token, "user_id": user_id, "email": email,
        "expires_at": now + timedelta(hours=24), "used": False, "created_at": now,
    })
    await email_service.send_verification(email, verify_token)

    access = create_access_token(user_id, email, payload.role)
    refresh = create_refresh_token(user_id)
    set_auth_cookies(response, access, refresh)
    doc["_id"] = result.inserted_id
    return {"user": serialize_user(doc), "access_token": access}


@auth_router.post("/login")
async def login(payload: LoginIn, request: Request, response: Response):
    email = payload.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
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
    return {"user": serialize_user(user), "access_token": access}


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
async def forgot_password(payload: ForgotPasswordIn):
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
    if rec["expires_at"] < datetime.now(timezone.utc):
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
    if rec["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification token has expired")
    await db.users.update_one({"_id": ObjectId(rec["user_id"])}, {"$set": {"email_verified": True}})
    await db.verification_tokens.update_one({"_id": rec["_id"]}, {"$set": {"used": True}})
    return {"success": True, "message": "Email verified successfully"}


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
async def contact(payload: ContactIn):
    now = datetime.now(timezone.utc)
    await db.contact_messages.insert_one({**payload.model_dump(), "created_at": now})
    logger.info("[CONTACT] %s <%s> - %s", payload.name, payload.email, payload.subject)
    return {"success": True, "message": "Thanks! We'll be in touch within 24 hours."}


@api_router.get("/health")
async def health():
    return {"status": "ok", "service": "brandkrt-api"}


# -----------------------------------------------------------------------------
# Startup
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.verification_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier")

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@brandkrt.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    now = datetime.now(timezone.utc)
    if not existing:
        await db.users.insert_one({
            "email": admin_email, "name": "BrandKrt Admin", "role": "admin",
            "password_hash": hash_password(admin_password), "email_verified": True,
            "avatar_url": None, "cover_url": None, "created_at": now, "updated_at": now,
        })
        logger.info("Seeded admin user %s", admin_email)
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
        logger.info("Updated admin password for %s", admin_email)


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# -----------------------------------------------------------------------------
# Register routers + CORS
# -----------------------------------------------------------------------------
api_router.include_router(auth_router)
app.include_router(api_router)

cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
