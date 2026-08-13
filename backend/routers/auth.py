"""
routers/auth.py — регистрация, вход, обновление токенов, выход.
"""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from security import (
    create_access_token, create_refresh_token,
    hash_password, verify_password,
    rotate_refresh_token, revoke_all_tokens,
    get_current_user,
)
from config import cfg
from database import get_db
from models import Subscription, User
from schemas import (
    AccessTokenResponse, LoginRequest, MsgResponse,
    RefreshRequest, RegisterRequest, TokenResponse, UserOut,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── POST /api/auth/register ───────────────────────────────────────────────────
@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    # Проверяем уникальность
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(400, detail="Email уже зарегистрирован")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, detail="Имя пользователя уже занято")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.flush()  # получаем user.id до commit

    # Создаём бесплатную подписку сразу при регистрации
    sub = Subscription(user_id=user.id, plan="free")
    db.add(sub)
    db.commit()
    db.refresh(user)

    access  = create_access_token(user.id)
    refresh = create_refresh_token(db, user.id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=cfg.jwt_access_expire_minutes * 60,
    )


# ── POST /api/auth/login ──────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    if not user.is_active:
        raise HTTPException(403, detail="Аккаунт заблокирован")

    access  = create_access_token(user.id)
    refresh = create_refresh_token(db, user.id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=cfg.jwt_access_expire_minutes * 60,
    )


# ── POST /api/auth/refresh ────────────────────────────────────────────────────
@router.post("/refresh", response_model=AccessTokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    result = rotate_refresh_token(db, body.refresh_token)
    if result is None:
        raise HTTPException(401, detail="Refresh token недействителен или истёк")
    new_refresh, user_id = result
    access = create_access_token(user_id)
    return AccessTokenResponse(
        access_token=access,
        expires_in=cfg.jwt_access_expire_minutes * 60,
    )


# ── POST /api/auth/logout ─────────────────────────────────────────────────────
@router.post("/logout", response_model=MsgResponse)
def logout(
    user: User = Depends(get_current_user),
    db: Session  = Depends(get_db),
):
    revoke_all_tokens(db, user.id)
    return MsgResponse(success=True, message="Вы успешно вышли из системы")


# ── GET /api/auth/me ──────────────────────────────────────────────────────────
@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
