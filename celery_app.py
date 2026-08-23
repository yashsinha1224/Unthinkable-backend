from celery import Celery
from dotenv import load_dotenv
import os

load_dotenv()

REDIS_CONNECTION     = os.getenv("REDIS_CONNECTION")
REDIS_PORT     = os.getenv("redis_port", "6379")
REDIS_TLS      = os.getenv("redis_tls", "false").lower() == "true"


scheme = "rediss" if REDIS_TLS else "redis"
broker_url = f"{scheme}://:{REDIS_CONNECTION}/0"

celery_app = Celery(
    "society_tracker",
    broker=broker_url,
    backend=broker_url,
    include=["tasks.email_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_default_retry_delay=30,
    task_max_retries=3,
)