"""
routers/analytics.py — приём анонимной статистики использования JARVIS.

  POST /api/analytics/events   — [публичный, БЕЗ авторизации] приложение
                                  JARVIS шлёт сюда накопленную очередь
                                  событий перед выключением и/или при
                                  следующем запуске, если прошлая отправка
                                  не удалась (см. jarvis_analytics.py).

Что принимаем и храним: ТОЛЬКО тип действия (event.type) и время события
(event.ts). Никакого текста запроса, никаких имён программ/сайтов/заметок,
никакого ID пользователя или устройства — на стороне JARVIS это в принципе
не собирается и не отправляется, поэтому здесь их и не может быть.

Без авторизации намеренно: приложение не заставляет пользователя логиниться
только чтобы отправить статистику, и события не привязываются к аккаунту.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import AnalyticsEvent
from schemas import AnalyticsEventsRequest, AnalyticsIngestResponse

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.post("/events", response_model=AnalyticsIngestResponse, status_code=201)
def ingest_events(body: AnalyticsEventsRequest, db: Session = Depends(get_db)):
    rows = [
        AnalyticsEvent(
            event_type=e.type,
            # ts приходит от клиента как UTC ISO с offset — SQLAlchemy/MySQL
            # DATETIME хранит naive-время, поэтому просто отбрасываем tzinfo
            # (значение уже в UTC, см. jarvis_analytics.py::_now_iso).
            event_ts=e.ts.replace(tzinfo=None),
        )
        for e in body.events
    ]
    db.bulk_save_objects(rows)
    db.commit()
    return AnalyticsIngestResponse(success=True, accepted=len(rows))
