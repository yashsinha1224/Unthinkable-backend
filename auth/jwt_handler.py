from datetime import datetime, timedelta
from jose import jwt, JWTError
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("super_secret")
ALGORITHM = "HS256"

if not SECRET_KEY:
    raise RuntimeError("super_secret not set in .env")  

def create_access_token(data: dict) -> str:
    to_crypt = data.copy()
    to_crypt.update({
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "type": "access"
    })
    return jwt.encode(to_crypt, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_crypt = data.copy()
    to_crypt.update({
        "exp": datetime.utcnow() + timedelta(days=12),
        "type": "refresh"
    })
    return jwt.encode(to_crypt, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    try:                                           
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise JWTError(str(e))  