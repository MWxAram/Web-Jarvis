"""
vip_utils.py — общая логика выдачи и продления VIP-доступа + лицензионных
ключей. Используется и в routers/vip.py (юзер сам активирует код),
и в routers/admin.py (админ жмёт кнопку «Выдать VIP» вручную) —
в обоих случаях у пользователя должен в итоге появиться привязанный
к нему LicenseKey.key_value, который видно в профиле и который
приложение JARVIS может проверить через /api/vip/verify-code.
"""
import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import LicenseKey, Subscription, User


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_key_value(db: Session) -> str:
    """Генерирует уникальный ключ формата JRVS-XXXX-XXXX-XXXX."""
    chars = string.ascii_uppercase + string.digits
    for _ in range(20):
        parts = ["JRVS"] + ["".join(random.choices(chars, k=4)) for _ in range(3)]
        candidate = "-".join(parts)
        if not db.query(LicenseKey).filter_by(key_value=candidate).first():
            return candidate
    raise RuntimeError("Не удалось сгенерировать уникальный ключ — попробуйте ещё раз")


def get_active_user_key(db: Session, user_id: int) -> LicenseKey | None:
    """
    Возвращает «текущий» лицензионный ключ пользователя — тот, что привязан
    к его аккаунту и имеет самый поздний expires_at. Это тот код, который
    показывается в профиле и который пользователь вводит в JARVIS.
    """
    return (
        db.query(LicenseKey)
        .filter(LicenseKey.user_id == user_id)
        .order_by(LicenseKey.expires_at.desc(), LicenseKey.id.desc())
        .first()
    )


def grant_or_extend_vip(
    db: Session,
    user: User,
    duration_days: int,
    existing_key: LicenseKey | None = None,
) -> tuple[Subscription, LicenseKey]:
    """
    Единая точка выдачи/продления VIP. Гарантирует, что после вызова:
      - у user.subscription стоит plan='vip' с корректным expires_at
      - у пользователя есть привязанный LicenseKey с тем же expires_at,
        который можно показать в профиле и проверить через verify-code

    existing_key — если выдача идёт через активацию конкретного ключа
    (когда юзер сам вводит код), сюда передаётся этот LicenseKey, чтобы
    не плодить новый, а использовать/продлить его. Если None (например,
    админ нажал кнопку «Выдать VIP» без кода) — будет переиспользован
    текущий активный код пользователя или сгенерирован новый.
    """
    now = now_utc()

    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    if sub is None:
        sub = Subscription(user_id=user.id)
        db.add(sub)
        db.flush()

    # Если у юзера уже активен VIP — продлеваем от текущей даты истечения,
    # иначе — отсчитываем от сегодняшнего дня
    if sub.is_vip and sub.expires_at:
        new_expires = sub.expires_at + timedelta(days=duration_days)
    else:
        sub.starts_at = now
        new_expires = now + timedelta(days=duration_days)

    sub.plan = "vip"
    sub.expires_at = new_expires

    # ── Определяем, какой LicenseKey привязать/обновить ────────────────────
    key = existing_key or get_active_user_key(db, user.id)

    if key is None:
        # У пользователя ещё нет ни одного кода — генерируем новый
        key = LicenseKey(
            key_value=generate_key_value(db),
            plan="vip",
            duration_days=duration_days,
        )
        db.add(key)
        db.flush()

    key.user_id = user.id
    if key.activated_at is None:
        key.activated_at = now
    key.expires_at = new_expires

    db.commit()
    db.refresh(sub)
    db.refresh(key)
    return sub, key


def revoke_vip(db: Session, user: User) -> Subscription:
    """
    Забирает VIP у пользователя (кнопка «Забрать VIP» в админке):
      - переводит подписку на plan='free'
      - «протухает» привязанный код прямо сейчас (expires_at = текущий момент),
        НЕ отвязывая и НЕ удаляя его — так JARVIS при следующей проверке
        через /api/vip/verify-code сразу увидит, что код больше не действует,
        а в админке/истории ключ остаётся виден как «использованный».
    """
    now = now_utc()

    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    if sub is None:
        sub = Subscription(user_id=user.id)
        db.add(sub)

    sub.plan = "free"
    sub.expires_at = now
    sub.starts_at = None

    key = get_active_user_key(db, user.id)
    if key is not None:
        key.expires_at = now

    db.commit()
    db.refresh(sub)
    return sub
