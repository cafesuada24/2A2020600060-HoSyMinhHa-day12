"""JWT Authentication Module."""

import os
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import (
    HTTPBearer,
    OAuth2PasswordBearer,
)

from app.config import settings

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
SECRET_KEY = settings.jwt_secret
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Demo users (trong thực tế lưu trong database)
DEMO_USERS = {
    'student': {'password': 'demo123', 'role': 'user', 'daily_limit': 50},
    'teacher': {'password': 'teach456', 'role': 'admin', 'daily_limit': 1000},
}

security = HTTPBearer(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def create_token(username: str, role: str) -> str:
    """Tạo JWT token với expiry."""
    payload = {
        'sub': username,  # subject (user identifier)
        'role': role,
        'iat': datetime.now(UTC),  # issued at
        'exp': datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)



def verify_token(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    """Dependency: verify JWT token từ Authorization header.
    Raise HTTPException nếu token invalid hoặc expired.
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        return {
            'username': payload['sub'],
            'role': payload['role'],
        }
    except jwt.ExpiredSignatureError as jwt_expried_sig_err:
        raise HTTPException(
            status_code=401,
            detail='Token expired. Please login again.',
        ) from jwt_expried_sig_err
    except jwt.InvalidTokenError as jwt_invalid_token_err:
        raise HTTPException(
            status_code=403,
            detail='Invalid token.',
        ) from jwt_invalid_token_err


def authenticate_user(username: str, password: str) -> dict:
    """Kiểm tra username/password, trả về user info nếu hợp lệ."""
    user = DEMO_USERS.get(username)
    if not user or user['password'] != password:
        raise HTTPException(status_code=401, detail='Invalid credentials')
    return {'username': username, 'role': user['role']}
