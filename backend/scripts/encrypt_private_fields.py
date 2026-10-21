"""Non-destructive, resumable financial-field migration. Dry-run by default.

Back up MongoDB and the encryption key separately before --apply. Existing
records remain readable. No collection, row or field is deleted.
"""
import argparse
import asyncio
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from motor.motor_asyncio import AsyncIOMotorClient
from private_fields import FIELDS, MARKER, protect_fields, _key


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if _key() is None:
        raise RuntimeError("Set PRIVATE_DATA_ENCRYPTION_KEY before migration")
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        db = client[os.environ["DB_NAME"]]
        for collection in ("brands", "influencers", "withdrawal_requests"):
            count = 0
            async for document in db[collection].find({}):
                fields = {key: document[key] for key in FIELDS if key in document
                          and document[key] not in (None, "")
                          and not (isinstance(document[key], dict) and MARKER in document[key])}
                if not fields:
                    continue
                if args.apply:
                    # Compare old values so concurrent profile edits are never overwritten.
                    await db[collection].update_one({"_id": document["_id"], **fields}, {"$set": protect_fields(fields)})
                count += 1
            print(f"{collection}: {count} records {'processed' if args.apply else 'would be encrypted'}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
