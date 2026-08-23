# caching/simple_cache.py — for single-object caches (dashboard), not lists
import json
from typing import Any, Optional

from caching.redis_client import redis_client


def get_cached(key: str) -> Optional[dict]:
    try:
        raw = redis_client.get(key)
    except Exception:
        return None
    return json.loads(raw) if raw is not None else None


def set_cached(key: str, value: Any, ttl: int) -> None:
    try:
        redis_client.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        pass


def invalidate(key: str) -> None:
    try:
        redis_client.delete(key)
    except Exception:
        pass