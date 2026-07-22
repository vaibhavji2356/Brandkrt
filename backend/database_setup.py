"""Explicit MongoDB initialization for BrandKrt deployments.

Run this once during deployment, before starting the web service:

    python database_setup.py

Keeping index creation and admin bootstrap outside application startup makes
every web worker fast to boot and prevents repeated bcrypt work.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from operations.mongo import mongo_client_options


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger("brandkrt.database_setup")


async def create_indexes(database) -> None:
    from admin_lead_intelligence.repository import create_admin_lead_indexes
    from commercial_intelligence.repository import setup_indexes as setup_commercial_indexes
    from operations.index_verification import create_operational_indexes
    import domain
    import part4b
    import part4c

    await database.users.create_index("email", unique=True)
    await database.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await database.verification_tokens.create_index("expires_at", expireAfterSeconds=0)
    await database.registration_otps.create_index("expires_at", expireAfterSeconds=0)
    await database.registration_otps.create_index([("email", 1), ("created_at", -1)])
    await database.login_attempts.create_index("identifier")
    await domain.setup_indexes(database)
    await part4b.setup_part4b_indexes(database)
    await part4c.setup_part4c_indexes(database)
    await setup_commercial_indexes(database)
    await create_admin_lead_indexes(database)
    await create_operational_indexes(database)


async def bootstrap_admin(database) -> None:
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        logger.info("Admin bootstrap skipped; ADMIN_EMAIL or ADMIN_PASSWORD is not configured")
        return
    if await database.users.find_one({"email": email}):
        logger.info("Admin account already exists; password was not changed")
        return

    now = datetime.now(timezone.utc)
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    await database.users.insert_one({
        "email": email,
        "name": "BrandKrt Admin",
        "role": "admin",
        "password_hash": password_hash,
        "email_verified": True,
        "avatar_url": None,
        "cover_url": None,
        "created_at": now,
        "updated_at": now,
    })
    logger.info("Created configured admin account")


async def run() -> None:
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise RuntimeError("MONGO_URL and DB_NAME are required")

    client = AsyncIOMotorClient(
        mongo_url,
        **mongo_client_options(),
    )
    try:
        await client.admin.command("ping")
        await create_indexes(client[db_name])
        await bootstrap_admin(client[db_name])
        logger.info("Database initialization complete")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(run())
