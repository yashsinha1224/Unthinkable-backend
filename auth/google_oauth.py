import os
import httpx
from fastapi import APIRouter, HTTPException, Depends
from urllib.parse import urlencode
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from auth.jwt_handler import create_access_token, create_refresh_token
from database.database import get_db    
from models.user_model import User, UserRole

load_dotenv()

router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("google_client_id")
GOOGLE_CLIENT_SECRET = os.getenv("google_client_secret")
REDIRECT_URI = os.getenv("google_redirect_uri", "http://localhost:8000/auth/google/callback")
FRONTEND_URL = os.getenv("frontend_auth_url", "http://localhost:3000/oauth/callback")

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise RuntimeError("Google OAuth credentials not set in .env")


@router.get("/auth/google")
async def login_with_google():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
    }
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@router.get("/auth/google/callback")
async def google_callback(code: str, db: Session = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        tokens = token_response.json()

        if "error" in tokens:
            raise HTTPException(
                status_code=400,
                detail=f"Google OAuth error: {tokens.get('error_description', tokens['error'])}",
            )

        user_info_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        user_info = user_info_response.json()

    user = db.query(User).filter(User.email == user_info["email"]).first()

    is_new_user = False
    if not user:
        is_new_user = True
        user = User(
            name=user_info["name"],
            email=user_info["email"],
            google_id=user_info["id"],
            role=UserRole.resident,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.google_id:
        user.google_id = user_info["id"]
        db.commit()
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    access_token = create_access_token(data={"user_id": str(user.id), "role": user.role.value})
    refresh_token = create_refresh_token(data={"user_id": str(user.id)})
    redirect_url = f"{FRONTEND_URL}?{urlencode({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user_id': user.id,
        'role': user.role.value,
        'is_new_user': str(is_new_user).lower(),
    })}"

    print("REDIRECTING TO:", redirect_url)

    return RedirectResponse(url=redirect_url)