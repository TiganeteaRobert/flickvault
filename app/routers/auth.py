from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import SECURE_COOKIES
from app.database import get_db
from app.schemas import UserRegister, UserLogin, UserOut
from app.auth import create_user, authenticate_user, create_token
from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_SETTINGS = dict(
    httponly=True,
    samesite="lax",
    secure=SECURE_COOKIES,
    max_age=30 * 24 * 3600,
)


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: UserRegister, db: Session = Depends(get_db)):
    if not data.username or len(data.username.strip()) < 1:
        raise HTTPException(status_code=400, detail="Username is required")
    if not data.password or len(data.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    try:
        user = create_user(db, data.username.strip(), data.password)
    except Exception:
        raise HTTPException(status_code=400, detail="Username already taken")
    token = create_token(user.id)
    response = JSONResponse(
        content={"token": token, "user": {"id": user.id, "username": user.username, "created_at": user.created_at.isoformat()}},
        status_code=201,
    )
    response.set_cookie(key="token", value=token, **COOKIE_SETTINGS)
    return response


@router.post("/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(user.id)
    response = JSONResponse(
        content={"token": token, "user": {"id": user.id, "username": user.username, "created_at": user.created_at.isoformat()}},
    )
    response.set_cookie(key="token", value=token, **COOKIE_SETTINGS)
    return response


@router.post("/logout")
def logout():
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(key="token")
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
