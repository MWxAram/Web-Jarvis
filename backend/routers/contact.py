"""
routers/contact.py — обращения через форму обратной связи.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import ContactMessage
from schemas import ContactRequest, ContactResponse

router = APIRouter(prefix="/api/contact", tags=["contact"])


@router.post("", response_model=ContactResponse, status_code=201)
def send_message(body: ContactRequest, db: Session = Depends(get_db)):
    msg = ContactMessage(email=body.email, message=body.message)
    db.add(msg)
    db.commit()
    return ContactResponse(
        success=True,
        message="Сообщение получено. Мы свяжемся с вами в ближайшее время.",
    )
