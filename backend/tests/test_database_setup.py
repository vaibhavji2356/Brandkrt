import asyncio

from mongomock_motor import AsyncMongoMockClient

from database_setup import create_indexes


def test_explicit_database_setup_creates_auth_and_domain_indexes():
    async def scenario():
        client = AsyncMongoMockClient()
        database = client.brandkrt_database_setup

        await create_indexes(database)

        users = await database.users.index_information()
        deals = await database.deals.index_information()
        conversations = await database.conversations.index_information()
        reviews = await database.reviews.index_information()
        withdrawals = await database.withdrawal_requests.index_information()

        assert any(spec.get("unique") for spec in users.values())
        assert len(deals) >= 3
        assert len(conversations) >= 3
        assert len(reviews) >= 4
        assert any(
            spec.get("unique") and spec.get("key") == [("active_key", 1)]
            for spec in withdrawals.values()
        )

        client.close()

    asyncio.run(scenario())
