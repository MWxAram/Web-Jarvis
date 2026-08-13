"""
models.py — SQLAlchemy ORM-модели (таблицы MySQL).
"""
import hashlib
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey,
    Integer, JSON, SmallInteger, String, Text,
)
from sqlalchemy.orm import relationship
from database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── Users ────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id            = Column(Integer,     primary_key=True, autoincrement=True)
    username      = Column(String(50),  nullable=False, unique=True, index=True)
    email         = Column(String(120), nullable=False, unique=True, index=True)
    password_hash = Column(String(128), nullable=False)
    is_active     = Column(Boolean,     nullable=False, default=True)
    is_admin      = Column(Boolean,     nullable=False, default=False)
    created_at    = Column(DateTime,    nullable=False, default=_now)
    updated_at    = Column(DateTime,    nullable=False, default=_now, onupdate=_now)
    last_seen_at  = Column(DateTime,    nullable=True)  # обновляется на каждом авторизованном запросе — для статуса «онлайн»

    # relationships
    subscription   = relationship("Subscription",  back_populates="user", uselist=False)
    devices        = relationship("Device",         back_populates="user")
    refresh_tokens = relationship("RefreshToken",   back_populates="user")
    license_keys   = relationship("LicenseKey",     back_populates="user")


# ─── Refresh tokens ──────────────────────────────────────────────────────────
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(Integer,  primary_key=True, autoincrement=True)
    user_id    = Column(Integer,  ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)  # SHA-256
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now)

    user = relationship("User", back_populates="refresh_tokens")

    @staticmethod
    def hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()


# ─── Subscriptions ────────────────────────────────────────────────────────────
class Subscription(Base):
    __tablename__ = "subscriptions"

    id         = Column(Integer,                      primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan       = Column(Enum("free", "vip", name="plan_type"), nullable=False, default="free")
    starts_at  = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    user = relationship("User", back_populates="subscription")

    @property
    def is_vip(self) -> bool:
        if self.plan != "vip":
            return False
        if self.expires_at is None:
            return True  # бессрочно
        return self.expires_at > _now()


# ─── License keys ─────────────────────────────────────────────────────────────
class LicenseKey(Base):
    __tablename__ = "license_keys"

    id            = Column(Integer,      primary_key=True, autoincrement=True)
    key_value     = Column(String(24),   nullable=False, unique=True)
    user_id       = Column(Integer,      ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    plan          = Column(Enum("vip",   name="key_plan"), nullable=False, default="vip")
    duration_days = Column(SmallInteger, nullable=False, default=30)
    activated_at  = Column(DateTime,     nullable=True)
    expires_at    = Column(DateTime,     nullable=True)
    created_at    = Column(DateTime,     nullable=False, default=_now)

    # relationships
    user = relationship("User", back_populates="license_keys")

    @property
    def is_used(self) -> bool:
        return self.user_id is not None


# ─── Devices ─────────────────────────────────────────────────────────────────
class Device(Base):
    __tablename__ = "devices"

    id          = Column(Integer,     primary_key=True, autoincrement=True)
    user_id     = Column(Integer,     ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_name = Column(String(80),  nullable=False)
    hwid        = Column(String(128), nullable=False)
    last_seen   = Column(DateTime,    nullable=False, default=_now, onupdate=_now)
    created_at  = Column(DateTime,    nullable=False, default=_now)

    user = relationship("User", back_populates="devices")


# ─── Contact messages ─────────────────────────────────────────────────────────
class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id         = Column(Integer,     primary_key=True, autoincrement=True)
    email      = Column(String(120), nullable=False)
    message    = Column(Text,        nullable=False)
    is_read    = Column(Boolean,     nullable=False, default=False)
    created_at = Column(DateTime,    nullable=False, default=_now)


# ─── Updates (журнал обновлений) ──────────────────────────────────────────────
class Update(Base):
    __tablename__ = "updates"

    id             = Column(Integer,     primary_key=True, autoincrement=True)
    version        = Column(String(30),  nullable=False)
    release_date   = Column(Date,        nullable=False)
    title          = Column(String(200), nullable=False)
    changelog      = Column(JSON,        nullable=False, default=list)  # [{tag, text}, ...]
    featured       = Column(Boolean,     nullable=False, default=False)
    featured_color = Column(String(20),  nullable=True)
    created_at     = Column(DateTime,    nullable=False, default=_now)
    updated_at     = Column(DateTime,    nullable=False, default=_now, onupdate=_now)


# ─── Analytics events (анонимная статистика использования JARVIS) ────────────
# ВАЖНО: намеренно НЕТ user_id / device_id / hwid / IP / текста запроса —
# см. jarvis_analytics.py на стороне приложения и routers/analytics.py здесь.
# Хранится только тип действия и момент события.
class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id          = Column(Integer,     primary_key=True, autoincrement=True)
    event_type  = Column(String(60),  nullable=False, index=True)
    event_ts    = Column(DateTime,    nullable=False, index=True)  # время на стороне JARVIS (UTC, naive)
    received_at = Column(DateTime,    nullable=False, default=_now)