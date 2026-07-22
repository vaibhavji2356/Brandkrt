"""Bounded shared MongoDB client options used by web and setup processes."""

from __future__ import annotations

import os


def mongo_client_options(environment=None) -> dict:
    values = environment if environment is not None else os.environ
    return {
        "serverSelectionTimeoutMS": _bounded(values, "MONGO_SERVER_SELECTION_TIMEOUT_MS", 5000, 500, 30_000),
        "connectTimeoutMS": _bounded(values, "MONGO_CONNECT_TIMEOUT_MS", 5000, 500, 30_000),
        "socketTimeoutMS": _bounded(values, "MONGO_SOCKET_TIMEOUT_MS", 10_000, 1000, 120_000),
        "maxPoolSize": _bounded(values, "MONGO_MAX_POOL_SIZE", 50, 1, 500),
        "minPoolSize": _bounded(values, "MONGO_MIN_POOL_SIZE", 0, 0, 100),
        "maxIdleTimeMS": _bounded(values, "MONGO_MAX_IDLE_TIME_MS", 60_000, 1000, 600_000),
        "waitQueueTimeoutMS": _bounded(values, "MONGO_WAIT_QUEUE_TIMEOUT_MS", 5000, 500, 60_000),
        "retryReads": True,
        "retryWrites": True,
        "tz_aware": True,
    }


def _bounded(values, name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(values.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))
