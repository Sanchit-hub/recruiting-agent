"""MongoDB connection and collection accessors.

A single module-level client is created lazily on first use and reused for the
life of the process, per pymongo's recommended usage pattern.
"""
from __future__ import annotations

import logging
import os

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

_client: MongoClient | None = None
_db: Database | None = None

DB_NAME = "recruiting_agent"


def get_client() -> MongoClient:
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    return _client


def get_db() -> Database:
    global _db
    if _db is None:
        _db = get_client()[DB_NAME]
    return _db


def check_connection() -> bool:
    """Ping MongoDB to verify connectivity. Used by the health check route."""
    try:
        get_client().admin.command("ping")
        return True
    except PyMongoError as exc:
        logger.error("MongoDB connection check failed: %s", exc)
        return False


def jd_runs_collection() -> Collection:
    return get_db()["jd_runs"]


def candidates_collection() -> Collection:
    return get_db()["candidates"]


def feedback_collection() -> Collection:
    return get_db()["feedback_records"]


def learned_patterns_collection() -> Collection:
    return get_db()["learned_patterns"]


def ensure_indexes() -> None:
    """Create indexes used by the API's query patterns. Safe to call repeatedly."""
    jd_runs_collection().create_index("jd_run_id", unique=True)
    candidates_collection().create_index("candidate_id", unique=True)
    candidates_collection().create_index("jd_run_id")
    feedback_collection().create_index("jd_run_id")
    feedback_collection().create_index("candidate_id")
    learned_patterns_collection().create_index("active")
