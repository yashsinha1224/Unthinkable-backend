from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database.database import get_db
from dependency.auth import get_current_user, require_admin
from models.user_model import User, UserRole
from schemas.user_schema import UserResponse, UserProfileUpdate, UserListResponse, RoleChangeRequestCreate
from caching.user_cache import user_cache
from caching.simple_cache import get_cached, set_cached, invalidate as invalidate_simple
from sse.connection_manager import connection_manager

router = APIRouter(prefix="/users", tags=["users"])

NO_FILTERS: dict = {}
ROLE_REQUESTS_CACHE_KEY = "users:role_requests"
ROLE_REQUESTS_CACHE_TTL = 60


@router.patch("/me", response_model=UserResponse)
def update_my_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.name is not None:
        current_user.name = payload.name
    if payload.flat_number is not None:
        current_user.flat_number = payload.flat_number
    if payload.phone is not None:
        current_user.phone = payload.phone

    db.commit()
    db.refresh(current_user)

    user_cache.invalidate_entity(current_user.id)

    return current_user


# --- Role change requests (resident-initiated, admin-approved) -----------------

@router.post("/me/role-request", response_model=UserResponse)
def request_role_change(
    payload: RoleChangeRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.requested_role == current_user.role:
        raise HTTPException(status_code=400, detail="You already have this role")

    if current_user.requested_role is not None:
        raise HTTPException(status_code=400, detail="You already have a pending role change request")

    current_user.requested_role = payload.requested_role
    db.commit()
    db.refresh(current_user)

    user_cache.invalidate_entity(current_user.id)
    invalidate_simple(ROLE_REQUESTS_CACHE_KEY)

    admin_ids = [u.id for u in db.query(User.id).filter(User.role == UserRole.admin).all()]
    connection_manager.broadcast(admin_ids, {
        "type": "role_request_created",
        "user_id": current_user.id,
        "requested_role": current_user.requested_role.value,
    })

    return current_user


@router.delete("/me/role-request", response_model=UserResponse)
def cancel_my_role_request(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.requested_role is None:
        raise HTTPException(status_code=400, detail="You have no pending role change request")

    current_user.requested_role = None
    db.commit()
    db.refresh(current_user)

    user_cache.invalidate_entity(current_user.id)
    invalidate_simple(ROLE_REQUESTS_CACHE_KEY)

    return current_user


@router.get("/role-requests", response_model=UserListResponse)
def list_role_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cached = get_cached(ROLE_REQUESTS_CACHE_KEY)

    if cached is not None:
        all_items = cached
    else:
        rows = (
            db.query(User)
            .filter(User.requested_role.isnot(None))
            .order_by(User.created_at.desc())
            .all()
        )
        all_items = [UserResponse.model_validate(u).model_dump(mode="json") for u in rows]
        set_cached(ROLE_REQUESTS_CACHE_KEY, all_items, ROLE_REQUESTS_CACHE_TTL)

    total = len(all_items)
    start = (page - 1) * page_size
    page_items = all_items[start:start + page_size]

    return UserListResponse(
        total=total,
        items=[UserResponse.model_validate(item) for item in page_items],
    )


@router.patch("/{user_id}/role-request/approve", response_model=UserResponse)
def approve_role_request(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.requested_role is None:
        raise HTTPException(status_code=400, detail="This user has no pending role change request")

    target.role = target.requested_role
    target.requested_role = None
    db.commit()
    db.refresh(target)

    user_cache.invalidate_entity(target.id)
    invalidate_simple(ROLE_REQUESTS_CACHE_KEY)

    connection_manager.send_to_user(target.id, {
        "type": "role_request_approved",
        "role": target.role.value,
    })

    return target


@router.patch("/{user_id}/role-request/reject", response_model=UserResponse)
def reject_role_request(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.requested_role is None:
        raise HTTPException(status_code=400, detail="This user has no pending role change request")

    target.requested_role = None
    db.commit()
    db.refresh(target)

    user_cache.invalidate_entity(target.id)
    invalidate_simple(ROLE_REQUESTS_CACHE_KEY)

    connection_manager.send_to_user(target.id, {
        "type": "role_request_rejected",
    })

    return target


# --- Admin: list/deactivate/reactivate ------------------------------------------

@router.get("", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cached = user_cache.get_page(NO_FILTERS, page, page_size)

    if cached is not None:
        page_ids, total = cached
    else:
        rows = db.query(User.id).order_by(User.created_at.desc()).all()
        ordered_ids = [r[0] for r in rows]
        total = len(ordered_ids)
        user_cache.cache_pages(NO_FILTERS, ordered_ids, page_size)

        start = (page - 1) * page_size
        page_ids = ordered_ids[start:start + page_size]

    if not page_ids:
        return UserListResponse(total=total, items=[])

    cached_entities = user_cache.get_entities(page_ids)
    missing_ids = [uid for uid in page_ids if uid not in cached_entities]

    if missing_ids:
        db_rows = db.query(User).filter(User.id.in_(missing_ids)).all()
        fresh = {u.id: UserResponse.model_validate(u).model_dump(mode="json") for u in db_rows}
        user_cache.cache_entities(fresh)
        cached_entities.update(fresh)

    items = [
        UserResponse.model_validate(cached_entities[uid])
        for uid in page_ids
        if uid in cached_entities
    ]

    return UserListResponse(total=total, items=items)


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")

    if target.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="Cannot deactivate another admin account")

    target.is_active = False
    db.commit()
    db.refresh(target)

    user_cache.invalidate_entity(target.id)

    return target


@router.patch("/{user_id}/reactivate", response_model=UserResponse)
def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.is_active = True
    db.commit()
    db.refresh(target)

    user_cache.invalidate_entity(target.id)

    return target