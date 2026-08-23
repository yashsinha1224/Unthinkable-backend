from fastapi import APIRouter, Depends, Query, status , HTTPException
from sqlalchemy.orm import Session
from models.user_model import User, UserRole
from tasks.email_tasks import task_send_important_notice_email
from database.database import get_db
from dependency.auth import require_admin, require_any
from models.user_model import User
from models.notice_model import Notice
from schemas.notice_schema import NoticeCreate, NoticeResponse, NoticeListResponse
from caching.notice_cache import notice_cache
from sse.connection_manager import connection_manager

router = APIRouter(prefix="/notices", tags=["notices"])

NO_FILTERS: dict = {}


def _to_response(notice: Notice) -> NoticeResponse:
    return NoticeResponse(
        id=notice.id,
        title=notice.title,
        body=notice.body,
        is_important=notice.is_important,
        posted_by_id=notice.posted_by_id,
        posted_by_name=notice.posted_by.name if notice.posted_by else None,
        created_at=notice.created_at,
    )


@router.post("", response_model=NoticeResponse, status_code=status.HTTP_201_CREATED)
def create_notice(
    payload: NoticeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    notice = Notice(
        title=payload.title,
        body=payload.body,
        is_important=payload.is_important,
        posted_by_id=current_user.id,
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)

    notice_cache.bump_version()

    residents = (
        db.query(User)
        .filter(User.role == UserRole.resident, User.is_active == True)
        .all()
    )
    resident_ids = [r.id for r in residents]
    connection_manager.broadcast(resident_ids, {"type": "notice_created", "notice_id": notice.id})

    if payload.is_important:
        for resident in residents:
            if resident.email:
                task_send_important_notice_email.delay(
                    to=resident.email,
                    name=resident.name,
                    notice_title=notice.title,
                    notice_body=notice.body,
                )

    return _to_response(notice)


@router.patch("/{notice_id}/unpin", response_model=NoticeResponse)
def unpin_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    notice.is_important = False
    db.commit()
    db.refresh(notice)

    notice_cache.bump_version()

    return _to_response(notice)


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    db.delete(notice)
    db.commit()

    notice_cache.bump_version()


@router.get("", response_model=NoticeListResponse)
def list_notices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any),
):
    cached = notice_cache.get_page(NO_FILTERS, page, page_size)

    if cached is not None:
        page_ids, total = cached
    else:
        rows = (
            db.query(Notice.id)
            .order_by(Notice.is_important.desc(), Notice.created_at.desc())
            .all()
        )
        ordered_ids = [r[0] for r in rows]
        total = len(ordered_ids)
        notice_cache.cache_pages(NO_FILTERS, ordered_ids, page_size)

        start = (page - 1) * page_size
        page_ids = ordered_ids[start:start + page_size]

    if not page_ids:
        return NoticeListResponse(total=total, items=[])

    cached_entities = notice_cache.get_entities(page_ids)
    missing_ids = [nid for nid in page_ids if nid not in cached_entities]

    if missing_ids:
        db_rows = db.query(Notice).filter(Notice.id.in_(missing_ids)).all()
        fresh = {n.id: _to_response(n).model_dump(mode="json") for n in db_rows}
        notice_cache.cache_entities(fresh)
        cached_entities.update(fresh)

    items = [
        NoticeResponse.model_validate(cached_entities[nid])
        for nid in page_ids
        if nid in cached_entities
    ]

    return NoticeListResponse(total=total, items=items)