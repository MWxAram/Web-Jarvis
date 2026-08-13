"""
database.py — подключение к MySQL через SQLAlchemy.
Экспортирует: engine, SessionLocal, Base, get_db (dependency).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import cfg

engine = create_engine(
    cfg.db_url,
    pool_pre_ping=True,      # переподключение при обрыве
    pool_recycle=3600,       # обновлять соединения раз в час
    pool_size=10,
    max_overflow=20,
    echo=cfg.debug,          # SQL-лог только в debug-режиме
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


# FastAPI dependency — в каждый роутер через Depends(get_db)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
