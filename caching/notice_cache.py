# caching/notice_cache.py
from caching.paginated_cache import PaginatedCache

# notices change less often than complaints -> longer TTL, tune as you like
notice_cache = PaginatedCache("notices", index_ttl=300, entity_ttl=600)