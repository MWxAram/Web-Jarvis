"""
routers/admin.py — административная панель JARVIS.
Все эндпоинты требуют is_admin=True (через get_current_admin).

Маршруты:
  GET  /api/admin/stats              — дашборд: счётчики + графики
  GET  /api/admin/users              — список пользователей (поиск, пагинация)
  GET  /api/admin/users/{id}         — детали пользователя
  POST /api/admin/users/{id}/block   — заблокировать / разблокировать
  POST /api/admin/users/{id}/vip     — выдать VIP вручную (+ код)
  POST /api/admin/users/{id}/revoke-vip — забрать VIP вручную (код деактивируется)
  DELETE /api/admin/users/{id}       — удалить пользователя
  GET  /api/admin/keys               — список лицензионных ключей
  POST /api/admin/keys/generate      — сгенерировать ключи (N штук)
  DELETE /api/admin/keys/{id}        — удалить свободный ключ
  GET  /api/admin/messages           — обращения через форму
  POST /api/admin/messages/{id}/read — пометить прочитанным
  GET  /api/admin/updates            — список записей журнала обновлений
  POST /api/admin/updates            — создать запись в журнале
  PUT  /api/admin/updates/{id}       — изменить запись
  DELETE /api/admin/updates/{id}     — удалить запись
  GET  /api/admin/analytics/summary  — статистика использования JARVIS (по типам функций + по дням)
  GET  /api/admin/analytics/functions-all — все функции сразу со счётчиками (сегодня/вчера/неделя/месяц/всё время)
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import AnalyticsEvent, ContactMessage, Device, LicenseKey, Subscription, RefreshToken, Update, User
from schemas import ChangelogItem, UpdateCreateRequest, UpdateOut
from security import get_current_admin
from vip_utils import generate_key_value, get_active_user_key, grant_or_extend_vip, revoke_vip

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ══════════════════════════ Schemas (локальные) ═══════════════════════════════

class UserAdminOut(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    plan: str
    vip_expires_at: Optional[datetime]
    vip_code: Optional[str] = None
    devices_count: int
    is_online: bool = False
    last_seen_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StatsOut(BaseModel):
    total_users: int
    active_users: int
    vip_users: int
    free_users: int
    online_users: int
    offline_users: int
    total_keys: int
    used_keys: int
    free_keys: int
    total_messages: int
    unread_messages: int
    total_devices: int
    # Для графиков: регистрации за последние 7 дней
    registrations_7d: list[dict]


class GenerateKeysRequest(BaseModel):
    count: int = 5          # сколько ключей создать (1–50)
    duration_days: int = 30  # на сколько дней


class VipGrantRequest(BaseModel):
    duration_days: int = 30


class BlockResponse(BaseModel):
    success: bool
    is_active: bool
    message: str


class KeyAdminOut(BaseModel):
    id: int
    key_value: str
    plan: str
    duration_days: int
    is_used: bool
    user_id: Optional[int]
    activated_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageAdminOut(BaseModel):
    id: int
    email: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MsgResponse(BaseModel):
    success: bool
    message: str


class AnalyticsTypeCount(BaseModel):
    type: str
    count: int


class AnalyticsDayCount(BaseModel):
    date: str
    count: int


class AnalyticsSummaryOut(BaseModel):
    period_days: int
    total_events: int
    by_type: list[AnalyticsTypeCount]      # какие функции используют чаще всего (за period_days)
    daily_totals_14d: list[AnalyticsDayCount]  # активность по дням (последние 14 дней, независимо от period_days)


class AnalyticsFunctionAllPeriods(BaseModel):
    type: str
    today: int
    yesterday: int
    week: int
    month: int
    all_time: int


class AnalyticsFunctionsAllOut(BaseModel):
    functions: list[AnalyticsFunctionAllPeriods]  # каждая функция + счётчики за все 5 периодов сразу


# ══════════════════════════ Helpers ══════════════════════════════════════════

def _build_user_out(user: User, db: Session) -> UserAdminOut:
    sub = user.subscription
    devices_count = db.query(Device).filter_by(user_id=user.id).count()
    is_vip = bool(sub and sub.is_vip)
    active_key = get_active_user_key(db, user.id) if is_vip else None

    is_online = bool(
        user.last_seen_at and (_now() - user.last_seen_at) <= timedelta(minutes=5)
    )

    return UserAdminOut(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        plan=sub.plan if sub else "free",
        vip_expires_at=sub.expires_at if sub else None,
        vip_code=active_key.key_value if active_key else None,
        devices_count=devices_count,
        is_online=is_online,
        last_seen_at=user.last_seen_at,
    )


# ══════════════════════════ Endpoints ════════════════════════════════════════

# ── Статистика дашборда ───────────────────────────────────────────────────────
@router.get("/stats", response_model=StatsOut)
def get_stats(
    _admin: User = Depends(get_current_admin),
    db: Session  = Depends(get_db),
):
    total_users  = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()
    vip_users    = (db.query(func.count(Subscription.id))
                      .filter(Subscription.plan == "vip").scalar())
    free_users   = total_users - vip_users

    # «Онлайн» = был активен (обновлял токен / делал запросы) за последние 5 минут
    online_cutoff  = _now() - timedelta(minutes=5)
    online_users   = (db.query(func.count(User.id))
                         .filter(User.last_seen_at.isnot(None), User.last_seen_at >= online_cutoff)
                         .scalar())
    offline_users  = total_users - online_users

    total_keys = db.query(func.count(LicenseKey.id)).scalar()
    used_keys  = db.query(func.count(LicenseKey.id)).filter(LicenseKey.user_id.isnot(None)).scalar()
    free_keys  = total_keys - used_keys

    total_messages  = db.query(func.count(ContactMessage.id)).scalar()
    unread_messages = db.query(func.count(ContactMessage.id)).filter(ContactMessage.is_read == False).scalar()
    total_devices   = db.query(func.count(Device.id)).scalar()

    # Регистрации за последние 7 дней
    registrations_7d = []
    for i in range(6, -1, -1):
        day_start = (_now() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        count = (db.query(func.count(User.id))
                   .filter(User.created_at >= day_start, User.created_at < day_end)
                   .scalar())
        registrations_7d.append({
            "date":  day_start.strftime("%d.%m"),
            "count": count,
        })

    return StatsOut(
        total_users=total_users,
        active_users=active_users,
        vip_users=vip_users,
        free_users=free_users,
        online_users=online_users,
        offline_users=offline_users,
        total_keys=total_keys,
        used_keys=used_keys,
        free_keys=free_keys,
        total_messages=total_messages,
        unread_messages=unread_messages,
        total_devices=total_devices,
        registrations_7d=registrations_7d,
    )


# ── Список пользователей ──────────────────────────────────────────────────────
@router.get("/users", response_model=list[UserAdminOut])
def list_users(
    search: Optional[str] = Query(None, description="Поиск по username/email"),
    plan:   Optional[str] = Query(None, description="Фильтр: free | vip"),
    skip:   int = Query(0,  ge=0),
    limit:  int = Query(50, ge=1, le=200),
    _admin: User    = Depends(get_current_admin),
    db:     Session = Depends(get_db),
):
    q = db.query(User).outerjoin(Subscription)
    if search:
        like = f"%{search}%"
        q = q.filter((User.username.like(like)) | (User.email.like(like)))
    if plan:
        if plan == "vip":
            q = q.filter(Subscription.plan == "vip")
        else:
            q = q.filter((Subscription.plan == "free") | (Subscription.id.is_(None)))
    users = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return [_build_user_out(u, db) for u in users]


# ── Детали пользователя ───────────────────────────────────────────────────────
@router.get("/users/{user_id}", response_model=UserAdminOut)
def get_user(
    user_id: int,
    _admin:  User    = Depends(get_current_admin),
    db:      Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="Пользователь не найден")
    return _build_user_out(user, db)


# ── Блокировка / разблокировка ────────────────────────────────────────────────
@router.post("/users/{user_id}/block", response_model=BlockResponse)
def toggle_block(
    user_id: int,
    admin:   User    = Depends(get_current_admin),
    db:      Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="Пользователь не найден")
    if user.id == admin.id:
        raise HTTPException(400, detail="Нельзя заблокировать самого себя")

    user.is_active = not user.is_active
    if not user.is_active:
        # При блокировке — отзываем все токены
        db.query(RefreshToken).filter_by(user_id=user.id).delete()
    db.commit()

    action = "заблокирован" if not user.is_active else "разблокирован"
    return BlockResponse(
        success=True,
        is_active=user.is_active,
        message=f"Пользователь {user.username} {action}",
    )


# ── Выдать VIP вручную ────────────────────────────────────────────────────────
@router.post("/users/{user_id}/vip", response_model=MsgResponse)
def grant_vip(
    user_id: int,
    body:    VipGrantRequest,
    _admin:  User    = Depends(get_current_admin),
    db:      Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="Пользователь не найден")

    sub, key = grant_or_extend_vip(db, user, body.duration_days)

    return MsgResponse(
        success=True,
        message=f"VIP выдан пользователю {user.username} на {body.duration_days} дней. "
                f"Код: {key.key_value} · истекает {sub.expires_at.strftime('%d.%m.%Y')}",
    )


# ── Забрать VIP вручную ───────────────────────────────────────────────────────
@router.post("/users/{user_id}/revoke-vip", response_model=MsgResponse)
def revoke_vip_endpoint(
    user_id: int,
    _admin:  User    = Depends(get_current_admin),
    db:      Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="Пользователь не найден")

    sub = user.subscription
    if not sub or sub.plan != "vip" or not sub.is_vip:
        raise HTTPException(400, detail=f"У пользователя {user.username} нет активного VIP")

    revoke_vip(db, user)

    return MsgResponse(
        success=True,
        message=f"VIP у пользователя {user.username} отозван. Его код деактивирован.",
    )


# ── Удалить пользователя ──────────────────────────────────────────────────────
@router.delete("/users/{user_id}", response_model=MsgResponse)
def delete_user(
    user_id: int,
    admin:   User    = Depends(get_current_admin),
    db:      Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="Пользователь не найден")
    if user.id == admin.id:
        raise HTTPException(400, detail="Нельзя удалить самого себя")

    username = user.username
    db.delete(user)
    db.commit()
    return MsgResponse(success=True, message=f"Пользователь {username} удалён")


# ══════════════════════════ Лицензионные ключи ═══════════════════════════════

@router.get("/keys", response_model=list[KeyAdminOut])
def list_keys(
    used:   Optional[bool] = Query(None, description="true=использованные, false=свободные"),
    skip:   int = Query(0, ge=0),
    limit:  int = Query(100, ge=1, le=500),
    _admin: User    = Depends(get_current_admin),
    db:     Session = Depends(get_db),
):
    q = db.query(LicenseKey)
    if used is True:
        q = q.filter(LicenseKey.user_id.isnot(None))
    elif used is False:
        q = q.filter(LicenseKey.user_id.is_(None))
    keys = q.order_by(LicenseKey.created_at.desc()).offset(skip).limit(limit).all()
    return [
        KeyAdminOut(
            id=k.id,
            key_value=k.key_value,
            plan=k.plan,
            duration_days=k.duration_days,
            is_used=k.is_used,
            user_id=k.user_id,
            activated_at=k.activated_at,
            expires_at=k.expires_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.post("/keys/generate", response_model=list[KeyAdminOut])
def generate_keys(
    body:   GenerateKeysRequest,
    _admin: User    = Depends(get_current_admin),
    db:     Session = Depends(get_db),
):
    if not (1 <= body.count <= 50):
        raise HTTPException(400, detail="count должен быть от 1 до 50")

    # Используем единый генератор ключей из vip_utils (тот же, что и при
    # активации/выдаче VIP) — раньше здесь была отдельная копия этой логики
    # с собственной, менее надёжной проверкой коллизий.
    created = []
    for _ in range(body.count):
        k = LicenseKey(key_value=generate_key_value(db), duration_days=body.duration_days)
        db.add(k)
        db.flush()
        created.append(k)

    db.commit()
    for k in created:
        db.refresh(k)

    return [
        KeyAdminOut(
            id=k.id, key_value=k.key_value, plan=k.plan,
            duration_days=k.duration_days, is_used=k.is_used,
            user_id=k.user_id, activated_at=k.activated_at,
            expires_at=k.expires_at, created_at=k.created_at,
        )
        for k in created
    ]


@router.delete("/keys/{key_id}", response_model=MsgResponse)
def delete_key(
    key_id: int,
    _admin: User    = Depends(get_current_admin),
    db:     Session = Depends(get_db),
):
    key = db.get(LicenseKey, key_id)
    if not key:
        raise HTTPException(404, detail="Ключ не найден")
    if key.is_used:
        raise HTTPException(400, detail="Нельзя удалить активированный ключ")
    db.delete(key)
    db.commit()
    return MsgResponse(success=True, message=f"Ключ {key.key_value} удалён")


# ══════════════════════════ Обращения ════════════════════════════════════════

@router.get("/messages", response_model=list[MessageAdminOut])
def list_messages(
    unread_only: bool = Query(False),
    skip:  int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _admin: User    = Depends(get_current_admin),
    db:     Session = Depends(get_db),
):
    q = db.query(ContactMessage)
    if unread_only:
        q = q.filter(ContactMessage.is_read == False)
    return q.order_by(ContactMessage.created_at.desc()).offset(skip).limit(limit).all()


@router.post("/messages/{msg_id}/read", response_model=MsgResponse)
def mark_read(
    msg_id: int,
    _admin: User    = Depends(get_current_admin),
    db:     Session = Depends(get_db),
):
    msg = db.get(ContactMessage, msg_id)
    if not msg:
        raise HTTPException(404, detail="Сообщение не найдено")
    msg.is_read = True
    db.commit()
    return MsgResponse(success=True, message="Помечено как прочитанное")


# ══════════════════════════ Журнал обновлений ═════════════════════════════════
# Эти эндпоинты пишут в общую таблицу `updates` — изменения сразу видны
# всем посетителям на updates.html и index.html (через /api/updates).

@router.get("/updates", response_model=list[UpdateOut])
def admin_list_updates(
    _admin: User    = Depends(get_current_admin),
    db:     Session = Depends(get_db),
):
    return db.query(Update).order_by(Update.release_date.desc(), Update.id.desc()).all()


@router.post("/updates", response_model=UpdateOut, status_code=201)
def admin_create_update(
    body:   UpdateCreateRequest,
    _admin: User    = Depends(get_current_admin),
    db:     Session = Depends(get_db),
):
    # Не больше 3 featured-карточек одновременно (главная показывает только 3 слота)
    if body.featured:
        featured_count = db.query(func.count(Update.id)).filter(Update.featured.is_(True)).scalar()
        if featured_count >= 3:
            raise HTTPException(
                400,
                detail="На главной уже выбрано 3 обновления. "
                       "Снимите отметку «featured» с одного из них, прежде чем добавлять новое.",
            )

    upd = Update(
        version=body.version,
        release_date=body.release_date,
        title=body.title,
        changelog=[item.model_dump() for item in body.changelog],
        featured=body.featured,
        featured_color=body.featured_color,
    )
    db.add(upd)
    db.commit()
    db.refresh(upd)
    return upd


@router.put("/updates/{update_id}", response_model=UpdateOut)
def admin_update_update(
    update_id: int,
    body:      UpdateCreateRequest,
    _admin:    User    = Depends(get_current_admin),
    db:        Session = Depends(get_db),
):
    upd = db.get(Update, update_id)
    if not upd:
        raise HTTPException(404, detail="Запись не найдена")

    if body.featured and not upd.featured:
        featured_count = db.query(func.count(Update.id)).filter(Update.featured.is_(True)).scalar()
        if featured_count >= 3:
            raise HTTPException(
                400,
                detail="На главной уже выбрано 3 обновления. "
                       "Снимите отметку «featured» с одного из них, прежде чем добавлять новое.",
            )

    upd.version        = body.version
    upd.release_date   = body.release_date
    upd.title          = body.title
    upd.changelog      = [item.model_dump() for item in body.changelog]
    upd.featured       = body.featured
    upd.featured_color = body.featured_color
    db.commit()
    db.refresh(upd)
    return upd


@router.delete("/updates/{update_id}", response_model=MsgResponse)
def admin_delete_update(
    update_id: int,
    _admin:    User    = Depends(get_current_admin),
    db:        Session = Depends(get_db),
):
    upd = db.get(Update, update_id)
    if not upd:
        raise HTTPException(404, detail="Запись не найдена")
    db.delete(upd)
    db.commit()
    return MsgResponse(success=True, message=f"Обновление {upd.version} удалено из журнала")


# ══════════════════════════ Статистика использования JARVIS ═══════════════════
# Данные приходят из приложения JARVIS через POST /api/analytics/events
# (см. routers/analytics.py) — только тип действия + время, без привязки
# к конкретному пользователю/устройству, поэтому здесь нет разбивки «кто
# использовал», только общие агрегаты «что и сколько раз использовали».

@router.get("/analytics/summary", response_model=AnalyticsSummaryOut)
def analytics_summary(
    days:   int = Query(30, ge=1, le=3650, description="За сколько последних дней считать разбивку по функциям"),
    _admin: User    = Depends(get_current_admin),
    db:     Session = Depends(get_db),
):
    cutoff = _now() - timedelta(days=days)

    total_events = (
        db.query(func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.event_ts >= cutoff)
        .scalar()
    )

    by_type_rows = (
        db.query(AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.event_ts >= cutoff)
        .group_by(AnalyticsEvent.event_type)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .all()
    )
    by_type = [AnalyticsTypeCount(type=t, count=c) for t, c in by_type_rows]

    # Активность по дням — фиксированное окно 14 дней (для графика),
    # независимое от параметра days (который управляет только разбивкой по типам)
    daily_totals_14d = []
    for i in range(13, -1, -1):
        day_start = (_now() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        count = (
            db.query(func.count(AnalyticsEvent.id))
            .filter(AnalyticsEvent.event_ts >= day_start, AnalyticsEvent.event_ts < day_end)
            .scalar()
        )
        daily_totals_14d.append(AnalyticsDayCount(date=day_start.strftime("%d.%m"), count=count))

    return AnalyticsSummaryOut(
        period_days=days,
        total_events=total_events,
        by_type=by_type,
        daily_totals_14d=daily_totals_14d,
    )


@router.get("/analytics/functions-all", response_model=AnalyticsFunctionsAllOut)
def analytics_functions_all(
    _admin: User    = Depends(get_current_admin),
    db:     Session = Depends(get_db),
):
    """
    Полный список всех функций (типов событий), которые когда-либо
    встречались в аналитике, с их количеством применений сразу за
    пять периодов: сегодня / вчера / неделя / месяц / всё время.
    """
    now = _now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    def _counts_since(cutoff: Optional[datetime]) -> dict[str, int]:
        q = db.query(AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
        if cutoff is not None:
            q = q.filter(AnalyticsEvent.event_ts >= cutoff)
        return {t: c for t, c in q.group_by(AnalyticsEvent.event_type).all()}

    def _counts_between(start: datetime, end: datetime) -> dict[str, int]:
        q = (
            db.query(AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
            .filter(AnalyticsEvent.event_ts >= start, AnalyticsEvent.event_ts < end)
        )
        return {t: c for t, c in q.group_by(AnalyticsEvent.event_type).all()}

    today_counts = _counts_since(today_start)
    yesterday_counts = _counts_between(yesterday_start, today_start)
    week_counts = _counts_since(week_start)
    month_counts = _counts_since(month_start)
    all_time_counts = _counts_since(None)

    # Полный список типов — берём объединение всех, что вообще встречались
    all_types = sorted(
        all_time_counts.keys(),
        key=lambda t: all_time_counts.get(t, 0),
        reverse=True,
    )

    functions = [
        AnalyticsFunctionAllPeriods(
            type=t,
            today=today_counts.get(t, 0),
            yesterday=yesterday_counts.get(t, 0),
            week=week_counts.get(t, 0),
            month=month_counts.get(t, 0),
            all_time=all_time_counts.get(t, 0),
        )
        for t in all_types
    ]

    return AnalyticsFunctionsAllOut(functions=functions)