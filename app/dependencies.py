"""FastAPI dependencies for per-user API key extraction and authentication."""

from dataclasses import dataclass

from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import ANTHROPIC_API_KEY, TMDB_API_KEY
from app.database import get_db
from app.auth import decode_token, get_user_by_id
from app.models import User


@dataclass
class APIKeys:
    anthropic_key: str
    tmdb_key: str


def get_api_keys(request: Request) -> APIKeys:
    """Extract API keys from request headers, falling back to server env vars."""
    return APIKeys(
        anthropic_key=request.headers.get("X-Anthropic-Key", "") or ANTHROPIC_API_KEY,
        tmdb_key=request.headers.get("X-TMDB-Key", "") or TMDB_API_KEY,
    )


def _extract_token(request: Request) -> str | None:
    """Read JWT from cookie or Authorization: Bearer header."""
    token = request.cookies.get("token")
    if token:
        return token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Return the authenticated user or raise 401."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Return the authenticated user or None (for redirect-to-login pages)."""
    token = _extract_token(request)
    if not token:
        return None
    user_id = decode_token(token)
    if user_id is None:
        return None
    return get_user_by_id(db, user_id)
