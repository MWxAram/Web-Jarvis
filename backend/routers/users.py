"""
routers/users.py — профиль, смена пароля, управление устройствами.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from security import get_current_user, hash_password, verify_password
from database import get_db
from models import Device, User
from schemas import (
    ChangePasswordRequest, DeviceOut,
    MsgResponse, RegisterDeviceRequest,
    UpdateProfileRequest, UserProfile,
)
from vip_utils import get_active_user_key

router = APIRouter(prefix="/api/users", tags=["users"])


# ── GET /api/users/profile ────────────────────────────────────────────────────
@router.get("/profile", response_model=UserProfile)
def get_profile(
    user: User = Depends(get_current_user),
    db: Session  = Depends(get_db),
):
    db.refresh(user)  # перечитываем с relationship
    devices_count = db.query(Device).filter_by(user_id=user.id).count()

    from schemas import SubscriptionOut
    vip_data = None
    if user.subscription:
        active_key = get_active_user_key(db, user.id) if user.subscription.is_vip else None
        vip_data = SubscriptionOut(
            plan=user.subscription.plan,
            is_vip=user.subscription.is_vip,
            starts_at=user.subscription.starts_at,
            expires_at=user.subscription.expires_at,
            key_value=active_key.key_value if active_key else None,
        )

    return UserProfile(
        id=user.id,
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
        created_at=user.created_at,
        vip=vip_data,
        devices_count=devices_count,
    )


# ── PUT /api/users/profile ────────────────────────────────────────────────────
@router.put("/profile", response_model=MsgResponse)
def update_profile(
    body: UpdateProfileRequest,
    user: User  = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.username and body.username != user.username:
        if db.query(User).filter(User.username == body.username).first():
            raise HTTPException(400, detail="Имя пользователя уже занято")
        user.username = body.username
    db.commit()
    return MsgResponse(success=True, message="Профиль обновлён")


# ── POST /api/users/change-password ──────────────────────────────────────────
@router.post("/change-password", response_model=MsgResponse)
def change_password(
    body: ChangePasswordRequest,
    user: User  = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, detail="Неверный текущий пароль")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return MsgResponse(success=True, message="Пароль изменён")


# ── GET /api/users/devices ────────────────────────────────────────────────────
@router.get("/devices", response_model=list[DeviceOut])
def list_devices(
    user: User  = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Device).filter_by(user_id=user.id).all()


# ── POST /api/users/devices ───────────────────────────────────────────────────
@router.post("/devices", response_model=DeviceOut, status_code=201)
def register_device(
    body: RegisterDeviceRequest,
    user: User  = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # VIP-ограничение: максимум 3 ПК
    if user.subscription and user.subscription.is_vip:
        max_devices = 3
    else:
        max_devices = 1

    # Upsert: если устройство уже зарегистрировано — обновляем last_seen
    existing = db.query(Device).filter_by(user_id=user.id, hwid=body.hwid).first()
    if existing:
        existing.device_name = body.device_name
        db.commit()
        db.refresh(existing)
        return existing

    count = db.query(Device).filter_by(user_id=user.id).count()
    if count >= max_devices:
        raise HTTPException(
            403,
            detail=f"Достигнут лимит подключённых устройств ({max_devices}). "
                   f"Обновитесь до VIP чтобы добавить больше."
        )

    device = Device(user_id=user.id, device_name=body.device_name, hwid=body.hwid)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


# ── DELETE /api/users/devices/{device_id} ────────────────────────────────────
@router.delete("/devices/{device_id}", response_model=MsgResponse)
def remove_device(
    device_id: int,
    user: User  = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter_by(id=device_id, user_id=user.id).first()
    if device is None:
        raise HTTPException(404, detail="Устройство не найдено")
    db.delete(device)
    db.commit()
    return MsgResponse(success=True, message="Устройство удалено")