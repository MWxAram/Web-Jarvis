"""
schemas.py — Pydantic-схемы для валидации запросов и формирования ответов.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
import re


# ══════════════════════════════ AUTH ══════════════════════════════════════════

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Имя пользователя: от 3 до 50 символов")
        if not re.match(r"^[A-Za-zА-Яа-яЁё0-9_\-]+$", v):
            raise ValueError("Имя пользователя: только буквы, цифры, _ и -")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Пароль: минимум 8 символов")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int   # секунды


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ══════════════════════════════ USERS ═════════════════════════════════════════

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfile(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime
    # VIP info (вложено)
    vip: "SubscriptionOut | None" = None
    devices_count: int = 0

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Имя пользователя: от 3 до 50 символов")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Новый пароль: минимум 8 символов")
        return v


# ══════════════════════════════ SUBSCRIPTIONS ═════════════════════════════════

class SubscriptionOut(BaseModel):
    plan: str
    is_vip: bool
    starts_at: Optional[datetime]
    expires_at: Optional[datetime]
    key_value: Optional[str] = None  # текущий привязанный VIP-код (для копирования в профиле / ввода в JARVIS)

    model_config = {"from_attributes": True}


# ══════════════════════════════ VIP / LICENSE ═════════════════════════════════

class ActivateKeyRequest(BaseModel):
    key: str

    @field_validator("key")
    @classmethod
    def key_format(cls, v: str) -> str:
        v = v.strip().upper()
        # формат: JRVS-XXXX-XXXX-XXXX
        if not re.match(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$", v):
            raise ValueError("Неверный формат ключа. Ожидается: XXXX-XXXX-XXXX-XXXX")
        return v


class ActivateKeyResponse(BaseModel):
    success: bool
    message: str
    expires_at: Optional[datetime] = None


class VerifyCodeRequest(BaseModel):
    """Запрос от приложения JARVIS — проверка кода без авторизации."""
    key: str

    @field_validator("key")
    @classmethod
    def key_format(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.match(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$", v):
            raise ValueError("Неверный формат ключа. Ожидается: XXXX-XXXX-XXXX-XXXX")
        return v


class VerifyCodeResponse(BaseModel):
    valid: bool
    message: str
    expires_at: Optional[datetime] = None  # None = бессрочно (если valid=True) либо неприменимо
    plan: Optional[str] = None


# ══════════════════════════════ ПОКУПКА VIP (демо, без реальной оплаты) ═══════
# ВАЖНО: пока на сайте не подключена настоящая платёжная система (Stripe /
# ЮКасса / крипто-эквайринг), этот эндпоинт просто сразу выдаёт VIP — это
# демо-режим для проверки UX покупки. Перед реальным запуском в прод
# routers/vip.py::purchase_vip нужно заменить на создание счёта у платёжного
# провайдера и выдачу VIP только из его вебхука об успешной оплате.

class PurchaseVipRequest(BaseModel):
    plan: str  # "month" | "year"

    @field_validator("plan")
    @classmethod
    def plan_valid(cls, v: str) -> str:
        if v not in ("month", "year"):
            raise ValueError("plan должен быть 'month' или 'year'")
        return v


class PurchaseVipResponse(BaseModel):
    success: bool
    message: str
    key_value: str
    expires_at: Optional[datetime] = None


class LicenseKeyOut(BaseModel):
    key_value: str
    plan: str
    duration_days: int
    activated_at: Optional[datetime]
    expires_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ══════════════════════════════ DEVICES ═══════════════════════════════════════

class DeviceOut(BaseModel):
    id: int
    device_name: str
    hwid: str
    last_seen: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class RegisterDeviceRequest(BaseModel):
    device_name: str
    hwid: str


# ══════════════════════════════ CONTACT ═══════════════════════════════════════

class ContactRequest(BaseModel):
    email: EmailStr
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if len(v.strip()) < 5:
            raise ValueError("Сообщение слишком короткое")
        if len(v) > 4000:
            raise ValueError("Сообщение слишком длинное (максимум 4000 символов)")
        return v.strip()


class ContactResponse(BaseModel):
    success: bool
    message: str


# ══════════════════════════════ GENERIC ═══════════════════════════════════════

class MsgResponse(BaseModel):
    success: bool
    message: str


# ══════════════════════════════ UPDATES (журнал обновлений) ═══════════════════

class ChangelogItem(BaseModel):
    tag: str = "new"   # new | improved | fixed
    text: str

    @field_validator("tag")
    @classmethod
    def tag_valid(cls, v: str) -> str:
        if v not in ("new", "improved", "fixed"):
            raise ValueError("tag должен быть: new, improved или fixed")
        return v

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Текст пункта изменений не может быть пустым")
        return v


class UpdateCreateRequest(BaseModel):
    version: str
    release_date: datetime
    title: str
    changelog: list[ChangelogItem]
    featured: bool = False
    featured_color: Optional[str] = None

    @field_validator("version")
    @classmethod
    def version_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Версия обязательна")
        return v

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Заголовок обязателен")
        return v

    @field_validator("changelog")
    @classmethod
    def changelog_not_empty(cls, v: list[ChangelogItem]) -> list[ChangelogItem]:
        if not v:
            raise ValueError("Добавьте хотя бы один пункт изменений")
        return v


class UpdateOut(BaseModel):
    id: int
    version: str
    release_date: datetime
    title: str
    changelog: list[ChangelogItem]
    featured: bool
    featured_color: Optional[str] = None

    model_config = {"from_attributes": True}


# ══════════════════════════════ ANALYTICS (приватная статистика JARVIS) ═══════
# Приложение JARVIS присылает сюда ТОЛЬКО тип действия + время события.
# Никакого текста запроса, имён программ/сайтов/заметок, ID пользователя
# или устройства — см. jarvis_analytics.py на стороне приложения.

class AnalyticsEventIn(BaseModel):
    type: str
    ts: datetime

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 60:
            raise ValueError("type: от 1 до 60 символов")
        if not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError("type: разрешены только буквы, цифры, _ и -")
        return v


class AnalyticsEventsRequest(BaseModel):
    events: list[AnalyticsEventIn]

    @field_validator("events")
    @classmethod
    def events_bounds(cls, v: list[AnalyticsEventIn]) -> list[AnalyticsEventIn]:
        if not v:
            raise ValueError("events не может быть пустым")
        if len(v) > 5000:
            raise ValueError("Слишком много событий за один запрос (максимум 5000)")
        return v


class AnalyticsIngestResponse(BaseModel):
    success: bool
    accepted: int