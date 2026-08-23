from datetime import datetime
from typing import Optional
from tasks.email_tasks import task_send_status_change_email
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Query, status
from sqlalchemy.orm import Session
import hashlib
from database.database import get_db
from dependency.auth import require_admin, require_resident, require_any
from models.user_model import User, UserRole
from models.complaint_model import (
    Complaint,
    ComplaintStatusHistory,
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
)
from schemas.complaint_schema import (
    ComplaintCreate,
    ComplaintStatusUpdate,
    ComplaintPriorityUpdate,
    ComplaintResponse,
    ComplaintDetailResponse,
    ComplaintListResponse,
    ComplaintStatusHistoryResponse,
)
from storage.photo_storage import upload_complaint_photo
from utils.overdue import get_overdue_threshold, days_open
from caching.complaint_cache import complaint_cache
from caching.simple_cache import invalidate as invalidate_simple
from sse.connection_manager import connection_manager
router = APIRouter(prefix="/complaints", tags=["complaints"])

DASHBOARD_CACHE_KEY = "dashboard:summary"


def _to_response(complaint: Complaint, threshold_days: int) -> ComplaintResponse:
    open_days = days_open(complaint.created_at)
    overdue = complaint.status != ComplaintStatus.resolved and open_days > threshold_days
    data = ComplaintResponse.model_validate(complaint)
    data.is_overdue = overdue
    data.days_open = open_days
    return data


# --- Photo upload ------------------------------------------------------------

@router.post("/upload-photo")
async def upload_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(require_resident),
):
    """Uploads to Supabase Storage, returns the public URL. Call this first,
    then pass the returned photo_url into POST /complaints."""
    url = await upload_complaint_photo(file)
    return {"photo_url": url}


# --- Create + resident views --------------------------------------------------

@router.post("", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
def create_complaint(
    payload: ComplaintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_resident),
):
    complaint = Complaint(
        resident_id=current_user.id,
        category=payload.category,
        description=payload.description,
        photo_url=payload.photo_url,
        status=ComplaintStatus.open,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    db.add(ComplaintStatusHistory(
        complaint_id=complaint.id,
        actor_id=current_user.id,
        from_status=None,
        to_status=ComplaintStatus.open,
        note="Complaint submitted",
    ))
    db.commit()

    complaint_cache.bump_version()
    invalidate_simple(DASHBOARD_CACHE_KEY)
    admin_ids = [u.id for u in db.query(User.id).filter(User.role == UserRole.admin).all()]
    connection_manager.broadcast(admin_ids, {"type": "complaint_created", "complaint_id": complaint.id})

    threshold = get_overdue_threshold(db)
    return _to_response(complaint, threshold)


@router.get("/me", response_model=ComplaintListResponse)
def list_my_complaints(
    request: Request,
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_resident),
):
    all_complaints = (
        db.query(Complaint)
        .filter(Complaint.resident_id == current_user.id)
        .order_by(Complaint.created_at.desc())
        .all()
    )
    total = len(all_complaints)
    start = (page - 1) * page_size
    page_complaints = all_complaints[start:start + page_size]

    etag_source = "|".join(f"{c.id}:{c.status}" for c in page_complaints)
    etag = hashlib.md5(
        f"{current_user.id}:{page}:{page_size}:{total}:{etag_source}".encode()
    ).hexdigest()

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    threshold = get_overdue_threshold(db)
    items = [_to_response(c, threshold) for c in page_complaints]

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=30"

    return ComplaintListResponse(total=total, items=items)


# --- Detail (resident-owner or admin) -----------------------------------------

@router.get("/{complaint_id}", response_model=ComplaintDetailResponse)
def get_complaint_detail(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if current_user.role == UserRole.resident and complaint.resident_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this complaint")

    threshold = get_overdue_threshold(db)
    base = _to_response(complaint, threshold)

    history_items = [
        ComplaintStatusHistoryResponse(
            id=h.id,
            from_status=h.from_status,
            to_status=h.to_status,
            note=h.note,
            actor_id=h.actor_id,
            actor_name=h.actor.name if h.actor else None,
            created_at=h.created_at,
        )
        for h in complaint.history
    ]

    return ComplaintDetailResponse(**base.model_dump(), history=history_items)


# --- Admin: list/filter (Redis-cached, paginated) -------------------------------

@router.get("", response_model=ComplaintListResponse)
def list_complaints(
    category: Optional[ComplaintCategory] = Query(None),
    status_filter: Optional[ComplaintStatus] = Query(None, alias="status"),
    priority: Optional[ComplaintPriority] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    overdue_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    filters = {
        "category": category.value if category else None,
        "status": status_filter.value if status_filter else None,
        "priority": priority.value if priority else None,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "overdue_only": overdue_only,
    }

    threshold = get_overdue_threshold(db)
    cached = complaint_cache.get_page(filters, page, page_size)

    if cached is not None:
        page_ids, total = cached
    else:
        query = db.query(Complaint.id, Complaint.created_at, Complaint.status)
        if category:
            query = query.filter(Complaint.category == category)
        if status_filter:
            query = query.filter(Complaint.status == status_filter)
        if priority:
            query = query.filter(Complaint.priority == priority)
        if date_from:
            query = query.filter(Complaint.created_at >= date_from)
        if date_to:
            query = query.filter(Complaint.created_at <= date_to)

        rows = query.all()
        enriched = [
            (cid, created_at, status_val != ComplaintStatus.resolved and days_open(created_at) > threshold)
            for cid, created_at, status_val in rows
        ]
        if overdue_only:
            enriched = [r for r in enriched if r[2]]

        enriched.sort(key=lambda r: r[1], reverse=True)
        enriched.sort(key=lambda r: r[2], reverse=True)

        ordered_ids = [r[0] for r in enriched]
        total = len(ordered_ids)
        complaint_cache.cache_pages(filters, ordered_ids, page_size)

        start = (page - 1) * page_size
        page_ids = ordered_ids[start:start + page_size]

    if not page_ids:
        return ComplaintListResponse(total=total, items=[])

    cached_entities = complaint_cache.get_entities(page_ids)
    missing_ids = [cid for cid in page_ids if cid not in cached_entities]

    if missing_ids:
        db_rows = db.query(Complaint).filter(Complaint.id.in_(missing_ids)).all()
        fresh = {c.id: _to_response(c, threshold).model_dump(mode="json") for c in db_rows}
        complaint_cache.cache_entities(fresh)
        cached_entities.update(fresh)

    items = [
        ComplaintResponse.model_validate(cached_entities[cid])
        for cid in page_ids
        if cid in cached_entities
    ]

    return ComplaintListResponse(total=total, items=items)


# --- Admin: status + priority updates -------------------------------------------

@router.patch("/{complaint_id}/status", response_model=ComplaintResponse)
def update_status(
    complaint_id: int,
    payload: ComplaintStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if complaint.status == ComplaintStatus.resolved:
        raise HTTPException(status_code=400, detail="This complaint is already resolved and closed")

    old_status = complaint.status
    complaint.status = payload.to_status
    if payload.to_status == ComplaintStatus.resolved:
        complaint.resolved_at = datetime.utcnow()

    db.add(ComplaintStatusHistory(
        complaint_id=complaint.id,
        actor_id=current_user.id,
        from_status=old_status,
        to_status=payload.to_status,
        note=payload.note,
    ))
    db.commit()
    db.refresh(complaint)

    complaint_cache.invalidate_entity(complaint.id)
    complaint_cache.bump_version()
    invalidate_simple(DASHBOARD_CACHE_KEY)

  
    complaint_cache.invalidate_entity(complaint.id)
    complaint_cache.bump_version()
    invalidate_simple(DASHBOARD_CACHE_KEY)
    
    connection_manager.send_to_user(
        complaint.resident_id,
        {"type": "complaint_updated", "complaint_id": complaint.id},
    )


    resident = db.query(User).filter(User.id == complaint.resident_id).first()
    if resident and resident.email:
        task_send_status_change_email.delay(
            to=resident.email,
            name=resident.name,
            complaint_id=complaint.id,
            category=complaint.category.value,
            old_status=old_status.value,
            new_status=payload.to_status.value,
            note=payload.note,
        )

    

    threshold = get_overdue_threshold(db)
    return _to_response(complaint, threshold)


@router.patch("/{complaint_id}/priority", response_model=ComplaintResponse)
def update_priority(
    complaint_id: int,
    payload: ComplaintPriorityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    complaint.priority = payload.priority
    db.commit()
    db.refresh(complaint)

    complaint_cache.invalidate_entity(complaint.id)
    complaint_cache.bump_version()

    threshold = get_overdue_threshold(db)
    return _to_response(complaint, threshold)
@router.delete("/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_resident),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if complaint.resident_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this complaint")

    if complaint.status != ComplaintStatus.open:
        raise HTTPException(status_code=400, detail="Only complaints still in 'open' status can be deleted")

    db.query(ComplaintStatusHistory).filter(
        ComplaintStatusHistory.complaint_id == complaint_id
    ).delete()
    db.delete(complaint)
    db.commit()

    complaint_cache.invalidate_entity(complaint_id)
    complaint_cache.bump_version()
    invalidate_simple(DASHBOARD_CACHE_KEY)