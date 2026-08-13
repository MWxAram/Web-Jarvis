"""
routers/vip.py — статус VIP-подписки, активация лицензионного ключа,
а также публичная проверка кода для приложения JARVIS.

Маршруты:
  GET  /api/vip/status        — статус подписки текущего юзера (+ его код)
  POST /api/vip/activate      — активировать код на своём аккаунте
  POST /api/vip/purchase      — [ДЕМО] купить VIP — сразу выдаёт VIP без
                                 реальной оплаты, пока не подключена платёжная
                                 система. См. комментарий у функции purchase_vip.
  POST /api/vip/verify-code   — [публичный, без авторизации] проверка кода
                                 приложением JARVIS: существует ли, не истёк ли
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from security import get_current_user
from database import get_db
from models import LicenseKey, Subscription, User
from schemas import (
    ActivateKeyRequest, ActivateKeyResponse,
    PurchaseVipRequest, PurchaseVipResponse,
    SubscriptionOut, VerifyCodeRequest, VerifyCodeResponse,
)
from vip_utils import get_active_user_key, grant_or_extend_vip

router = APIRouter(prefix="/api/vip", tags=["vip"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


PLAN_DURATIONS = {"month": 30, "year": 365}


# ── GET /api/vip/status ───────────────────────────────────────────────────────
@router.get("/status", response_model=SubscriptionOut)
def vip_status(
    user: User  = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    if sub is None:
        # Создаём free-подписку если по какой-то причине её нет
        sub = Subscription(user_id=user.id, plan="free")
        db.add(sub); db.commit(); db.refresh(sub)

    active_key = get_active_user_key(db, user.id) if sub.is_vip else None
    return SubscriptionOut(
        plan=sub.plan,
        is_vip=sub.is_vip,
        starts_at=sub.starts_at,
        expires_at=sub.expires_at,
        key_value=active_key.key_value if active_key else None,
    )


# ── POST /api/vip/activate ────────────────────────────────────────────────────
# Пользователь сам вводит код на сайте (например, купленный или выданный
# вручную). Если код уже привязан к этому же юзеру (повторная активация
# того же кода) — отклоняем, чтобы не путать пользователя.
@router.post("/activate", response_model=ActivateKeyResponse)
def activate_key(
    body: ActivateKeyRequest,
    user: User  = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lk = db.query(LicenseKey).filter_by(key_value=body.key).first()

    if lk is None:
        raise HTTPException(400, detail="Лицензионный ключ не найден")
    if lk.is_used and lk.user_id != user.id:
        raise HTTPException(400, detail="Этот ключ уже использован")
    if lk.user_id == user.id:
        raise HTTPException(400, detail="Этот ключ уже активирован на вашем аккаунте")

    sub, key = grant_or_extend_vip(db, user, lk.duration_days, existing_key=lk)

    return ActivateKeyResponse(
        success=True,
        message=f"VIP активирован на {lk.duration_days} дней!",
        expires_at=sub.expires_at,
    )


# ── POST /api/vip/purchase ────────────────────────────────────────────────────
# [ДЕМО-РЕЖИМ] Пока на сайте не подключена настоящая платёжная система,
# этот эндпоинт имитирует успешную оплату и сразу выдаёт VIP. Фронтенд
# показывает короткую анимацию «Обработка платежа…», как будто идёт
# настоящее списание, но по факту никаких денег не берётся.
#
# Когда будет подключён реальный платёжный провайдер (Stripe/ЮКасса/крипто-
# эквайринг), этот хендлер нужно заменить на:
#   1) создание счёта/сессии оплаты у провайдера, возврат ссылки на оплату;
#   2) выдачу VIP (вызов grant_or_extend_vip) только из вебхука провайдера
#      об успешном платеже — а не прямо здесь.
@router.post("/purchase", response_model=PurchaseVipResponse)
def purchase_vip(
    body: PurchaseVipRequest,
    user: User  = Depends(get_current_user),
    db:   Session = Depends(get_db),
):
    duration_days = PLAN_DURATIONS[body.plan]

    sub, key = grant_or_extend_vip(db, user, duration_days)

    plan_label = "1 месяц" if body.plan == "month" else "1 год"
    return PurchaseVipResponse(
        success=True,
        message=f"VIP оформлен на {plan_label}!",
        key_value=key.key_value,
        expires_at=sub.expires_at,
    )


# ── POST /api/vip/verify-code ─────────────────────────────────────────────────
# Публичный эндпоинт БЕЗ авторизации — его дёргает приложение JARVIS:
#   1) один раз, когда пользователь вводит код в самой программе;
#   2) при каждом следующем запуске программы — чтобы проверить, не истёк
#      ли срок (или не был ли код вообще удалён/отвязан администратором).
# JARVIS хранит код локально и просто шлёт его сюда — никакого логина
# пользователя в самой программе не требуется.
@router.post("/verify-code", response_model=VerifyCodeResponse)
def verify_code(
    body: VerifyCodeRequest,
    db: Session = Depends(get_db),
):
    lk = db.query(LicenseKey).filter_by(key_value=body.key).first()

    if lk is None:
        return VerifyCodeResponse(valid=False, message="Код не найден")

    if lk.user_id is None:
        return VerifyCodeResponse(valid=False, message="Код ещё не активирован ни одним аккаунтом")

    if lk.expires_at is not None and lk.expires_at <= _now():
        return VerifyCodeResponse(
            valid=False,
            message="Срок действия кода истёк",
            expires_at=lk.expires_at,
            plan=lk.plan,
        )

    return VerifyCodeResponse(
        valid=True,
        message="Код активен",
        expires_at=lk.expires_at,   # None = бессрочно
        plan=lk.plan,
    )