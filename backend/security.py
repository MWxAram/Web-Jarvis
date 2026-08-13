"""
security.py — утилиты авторизации: хэшинг паролей, JWT, dependency текущего юзера.
Используем bcrypt напрямую (без passlib) — совместимо с bcrypt 4.x
"""
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import cfg
from database import get_db
from models import RefreshToken, User


# ── Пароли (bcrypt напрямую, без passlib) ────────────────────────────────────
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain[:72].encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain[:72].encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=cfg.jwt_access_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)

def decode_access_token(token: str) -> Optional[int]:
    try:
        data = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
        if data.get("type") != "access":
            return None
        return int(data["sub"])
    except JWTError:
        return None


# ── Refresh token ─────────────────────────────────────────────────────────────
def create_refresh_token(db: Session, user_id: int) -> str:
    raw = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(days=cfg.jwt_refresh_expire_days)
    rt = RefreshToken(
        user_id=user_id,
        token_hash=RefreshToken.hash_token(raw),
        expires_at=expires.replace(tzinfo=None),
    )
    db.add(rt)
    db.commit()
    return raw

def rotate_refresh_token(db: Session, old_raw: str) -> Optional[tuple[str, int]]:
    old_hash = RefreshToken.hash_token(old_raw)
    rt = db.query(RefreshToken).filter_by(token_hash=old_hash).first()
    if rt is None:
        return None
    if rt.expires_at < datetime.utcnow():
        db.delete(rt)
        db.commit()
        return None
    user_id = rt.user_id
    db.delete(rt)
    new_raw = create_refresh_token(db, user_id)
    return new_raw, user_id

def revoke_all_tokens(db: Session, user_id: int) -> None:
    db.query(RefreshToken).filter_by(user_id=user_id).delete()
    db.commit()


# ── Dependency: текущий пользователь ─────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Не обновляем last_seen_at на КАЖДОМ запросе (это лишний UPDATE на каждый
# вызов API) — обновляем, только если прошло больше этого порога с прошлого
# раза. Порог намного меньше окна «онлайн» (5 минут) в /admin/stats, так что
# статус всё равно остаётся точным.
_LAST_SEEN_UPDATE_THROTTLE = timedelta(seconds=60)


def _touch_last_seen(db: Session, user: User) -> None:
    now = _now()
    if user.last_seen_at is None or (now - user.last_seen_at) > _LAST_SEEN_UPDATE_THROTTLE:
        user.last_seen_at = now
        db.commit()


def _get_user_or_401(db: Session, user_id: Optional[int]) -> User:
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или истёкший токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или заблокирован",
        )
    _touch_last_seen(db, user)
    return user

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    user_id = decode_access_token(token)
    return _get_user_or_401(db, user_id)

def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет прав администратора")
    return user