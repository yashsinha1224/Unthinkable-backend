# caching/redis_client.py
import os
import redis

REDIS_CONNET= os.environ["REDIS_CONNECTION"]
REDIS_TLS      = os.getenv("redis_tls", "false").lower() == "true"

scheme = "rediss" if REDIS_TLS else "redis"
REDIS_CONNECTION =f"{scheme}://:{REDIS_CONNET}/0"
redis_client = redis.from_url(
    REDIS_CONNECTION,
    decode_responses=True,
    socket_timeout=2,
    socket_connect_timeout=2,
    retry_on_timeout=True,
)