"""
main.py — JARVIS Backend. Запуск: uvicorn main:app --reload --port 8000
"""
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import cfg
from database import Base, engine
import models  # noqa

from routers.auth      import router as auth_router
from routers.users     import router as users_router
from routers.vip       import router as vip_router
from routers.contact   import router as contact_router
from routers.admin     import router as admin_router
from routers.updates   import router as updates_router
from routers.analytics import router as analytics_router

# Создаём таблицы
try:
    Base.metadata.create_all(bind=engine)
    print("[DB] Таблицы OK")
except Exception as e:
    print(f"[DB] ОШИБКА: {e}")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=cfg.app_title,
    version=cfg.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS — добавляем ПОСЛЕДНИМ чтобы выполнялся ПЕРВЫМ (Starlette LIFO) ──────
ALLOWED_ORIGINS = [o.strip() for o in cfg.cors_origins.split(",") if o.strip()]
print(f"[CORS] Origins: {ALLOWED_ORIGINS}")

# ── Роутеры ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(vip_router)
app.include_router(contact_router)
app.include_router(admin_router)
app.include_router(updates_router)
app.include_router(analytics_router)


# ── Exception handler — FastAPI добавляет CORS к ответам exception_handler ───
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) if cfg.debug else "Внутренняя ошибка сервера"},
    )


# ── CORS middleware — регистрируем ПОСЛЕ роутеров и exception_handler
#    В Starlette middleware исполняется в порядке LIFO (последний = внешний)
#    Поэтому CORS должен быть добавлен последним — тогда он обернёт всё снаружи
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    print("\n" + "="*52)
    print(f"  JARVIS Backend v{cfg.app_version}  debug={cfg.debug}")
    print(f"  DB: {cfg.db_user}@{cfg.db_host}:{cfg.db_port}/{cfg.db_name}")
    print(f"  CORS: {ALLOWED_ORIGINS}")
    try:
        from sqlalchemy import text
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        print("  [OK] MySQL подключена")
    except Exception as e:
        print(f"\n  [!!] MySQL ОШИБКА: {e}\n")
    print("="*52 + "\n")


@app.get("/api/health", tags=["system"])
def health():
    try:
        from sqlalchemy import text
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        db = "ok"
    except Exception as e:
        db = str(e)
    return {"status": "ok", "version": cfg.app_version, "db": db}


@app.post("/api/test-cors")
def test_cors():
    """Тестовый эндпоинт — проверяет что CORS работает без БД."""
    return {"cors": "ok"}