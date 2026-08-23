# caching/user_cache.py
from caching.paginated_cache import PaginatedCache

user_cache = PaginatedCache("users", index_ttl=180, entity_ttl=300)