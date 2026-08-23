from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.database import get_db
from dependency.auth import require_admin
from models.user_model import User
from models.complaint_model import Complaint, ComplaintStatus
from schemas.dashboard_schema import DashboardResponse
from utils.overdue import get_overdue_threshold, days_open
from caching.simple_cache import get_cached, set_cached

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DASHBOARD_CACHE_KEY = "dashboard:summary"
DASHBOARD_TTL_SECONDS = 30


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cached = get_cached(DASHBOARD_CACHE_KEY)
    if cached is not None:
        return DashboardResponse.model_validate(cached)

    total = db.query(Complaint).count()
    status_counts = dict(
        db.query(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status).all()
    )
    category_counts = dict(
        db.query(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all()
    )

    threshold = get_overdue_threshold(db)
    open_complaints = db.query(Complaint).filter(Complaint.status != ComplaintStatus.resolved).all()
    overdue_count = sum(1 for c in open_complaints if days_open(c.created_at) > threshold)

    result = DashboardResponse(
        total_complaints=total,
        by_status=status_counts,
        by_category=category_counts,
        overdue_count=overdue_count,
    )

    set_cached(DASHBOARD_CACHE_KEY, result.model_dump(mode="json"), DASHBOARD_TTL_SECONDS)
    return result