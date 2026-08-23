# caching/paginated_cache.py
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from caching.redis_client import redis_client


class PaginatedCache:
    """Two-tier list cache: {namespace}:idx:v{N}:{filter_hash}:p{page}:s{size}
    -> [ids], {namespace}:{id} -> entity. A per-namespace version counter
    invalidates every index key at once without SCAN/pattern-delete."""

    def __init__(self, namespace: str, index_ttl: int = 120, entity_ttl: int = 300):
        self.namespace = namespace
        self.index_ttl = index_ttl
        self.entity_ttl = entity_ttl
        self._version_key = f"{namespace}:list_version"

    def _get_version(self) -> int:
        v = redis_client.get(self._version_key)
        if v is None:
            redis_client.set(self._version_key, 1)
            return 1
        return int(v)

    def bump_version(self) -> None:
        try:
            redis_client.incr(self._version_key)
        except Exception:
            pass

    def _filter_hash(self, filters: Dict[str, Any]) -> str:
        canonical = json.dumps(filters, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def _index_key(self, filters, page, page_size, version) -> str:
        return f"{self.namespace}:idx:v{version}:{self._filter_hash(filters)}:p{page}:s{page_size}"

    def _total_key(self, filters, version) -> str:
        return f"{self.namespace}:idx:v{version}:{self._filter_hash(filters)}:total"

    def _entity_key(self, entity_id) -> str:
        return f"{self.namespace}:{entity_id}"

    def get_page(self, filters: Dict[str, Any], page: int, page_size: int) -> Optional[Tuple[List[int], int]]:
        version = self._get_version()
        key = self._index_key(filters, page, page_size, version)
        total_key = self._total_key(filters, version)
        try:
            raw_ids, raw_total = redis_client.mget([key, total_key])
        except Exception:
            return None
        if raw_ids is None or raw_total is None:
            return None
        return json.loads(raw_ids), int(raw_total)

    def cache_pages(self, filters: Dict[str, Any], ordered_ids: List[int], page_size: int) -> None:
        version = self._get_version()
        total = len(ordered_ids)
        try:
            pipe = redis_client.pipeline()
            pipe.set(self._total_key(filters, version), total, ex=self.index_ttl)
            total_pages = max(1, (total + page_size - 1) // page_size)
            for page in range(1, total_pages + 1):
                start = (page - 1) * page_size
                chunk = ordered_ids[start:start + page_size]
                pipe.set(self._index_key(filters, page, page_size, version), json.dumps(chunk), ex=self.index_ttl)
            pipe.execute()
        except Exception:
            pass

    def get_entities(self, ids: List[int]) -> Dict[int, dict]:
        if not ids:
            return {}
        keys = [self._entity_key(i) for i in ids]
        try:
            raw_values = redis_client.mget(keys)
        except Exception:
            return {}
        return {eid: json.loads(raw) for eid, raw in zip(ids, raw_values) if raw is not None}

    def cache_entities(self, entities: Dict[int, dict]) -> None:
        if not entities:
            return
        try:
            pipe = redis_client.pipeline()
            for eid, data in entities.items():
                pipe.set(self._entity_key(eid), json.dumps(data, default=str), ex=self.entity_ttl)
            pipe.execute()
        except Exception:
            pass

    def invalidate_entity(self, entity_id: int) -> None:
        try:
            redis_client.delete(self._entity_key(entity_id))
        except Exception:
            pass