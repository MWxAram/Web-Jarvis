"""
routers/updates.py — публичный журнал обновлений (без авторизации).
Используется на updates.html (полный список) и index.html (featured-карточки).

Маршруты:
  GET /api/updates           — полный список (новые сверху)
  GET /api/updates/featured  — карточки, отмеченные featured=true (для главной)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Update
from schemas import UpdateOut

router = APIRouter(prefix="/api/updates", tags=["updates"])


# ── GET /api/updates ──────────────────────────────────────────────────────────
@router.get("", response_model=list[UpdateOut])
def list_updates(db: Session = Depends(get_db)):
    return (
        db.query(Update)
        .order_by(Update.release_date.desc(), Update.id.desc())
        .all()
    )


# ── GET /api/updates/featured ─────────────────────────────────────────────────
@router.get("/featured", response_model=list[UpdateOut])
def list_featured_updates(db: Session = Depends(get_db)):
    return (
        db.query(Update)
        .filter(Update.featured.is_(True))
        .order_by(Update.release_date.desc(), Update.id.desc())
        .limit(3)
        .all()
    )
