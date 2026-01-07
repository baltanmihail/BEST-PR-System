"""
FastAPI приложение
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.api import auth, tasks, stages, events, equipment, calendar, gamification, moderation, notifications

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BEST PR System API",
    description="API для системы управления PR-отделом BEST Москва",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(tasks.router, prefix=settings.API_V1_PREFIX)
app.include_router(stages.router, prefix=settings.API_V1_PREFIX)
app.include_router(events.router, prefix=settings.API_V1_PREFIX)
app.include_router(equipment.router, prefix=settings.API_V1_PREFIX)
app.include_router(calendar.router, prefix=settings.API_V1_PREFIX)
app.include_router(gamification.router, prefix=settings.API_V1_PREFIX)
app.include_router(moderation.router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications.router, prefix=settings.API_V1_PREFIX)

@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "message": "BEST PR System API",
        "version": "0.1.0",
        "docs": "/docs",
        "api_prefix": settings.API_V1_PREFIX
    }

@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok"}


@app.get("/test")
async def test():
    """Тестовый endpoint для проверки работы API"""
    return {
        "status": "ok",
        "message": "API работает!",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "api_prefix": settings.API_V1_PREFIX
        }
    }


@app.get("/docs-redirect")
async def docs_redirect():
    """Редирект на документацию"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")


@app.on_event("startup")
async def startup_event():
    """Выполняется при запуске приложения"""
    logger.info("BEST PR System API starting up...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database URL: {settings.DATABASE_URL[:20]}..." if len(settings.DATABASE_URL) > 20 else f"Database URL: {settings.DATABASE_URL}")


@app.on_event("shutdown")
async def shutdown_event():
    """Выполняется при остановке приложения"""
    logger.info("BEST PR System API shutting down...")
