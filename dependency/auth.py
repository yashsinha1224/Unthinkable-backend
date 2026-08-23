from fastapi import Header, HTTPException, Depends, Query
from jose import JWTError
from sqlalchemy.orm import Session

from auth.jwt_handler import verify_token
from database.database import get_db
from models.user_model import User, UserRole


async def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.replace("Bearer ", "")
    return _resolve_user(token, db)


async def get_current_user_from_query_token(
    token: str = Query(...),
    db: Session = Depends(get_db)
) -> User:
    return _resolve_user(token, db)


def _resolve_user(token: str, db: Session) -> User:
    try:
        payload = verify_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    return user


def require_role(*roles: UserRole):    
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker


require_admin = require_role(UserRole.admin)
require_resident = require_role(UserRole.resident)
require_any = require_role(UserRole.resident, UserRole.admin)