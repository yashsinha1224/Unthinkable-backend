from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models.config_model import AppConfig


def get_overdue_threshold(db: Session) -> int:
    config = db.query(AppConfig).filter(AppConfig.id == 1).first()
    return config.overdue_threshold_days if config else 7


def days_open(created_at: datetime) -> int:
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return (now - created_at).days


def is_overdue(status_value: str, created_at: datetime, threshold_days: int) -> bool:
    return status_value != "resolved" and days_open(created_at) > threshold_days