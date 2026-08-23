# caching/complaint_cache.py
from caching.paginated_cache import PaginatedCache

complaint_cache = PaginatedCache("complaints", index_ttl=120, entity_ttl=300)