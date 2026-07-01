import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server

async def main():
    email = 'demo@brandkrt.com'
    password = 'Password123!'
    user = await server.db.users.find_one({'email': email})
    print('user_exists', bool(user))
    if not user:
        result = await server.db.users.insert_one({
            'email': email,
            'name': 'Demo User',
            'role': 'influencer',
            'password_hash': server.hash_password(password),
            'email_verified': True,
            'avatar_url': None,
            'cover_url': None,
            'created_at': server.datetime.now(server.timezone.utc),
            'updated_at': server.datetime.now(server.timezone.utc),
        })
        print('inserted', str(result.inserted_id))

asyncio.run(main())
