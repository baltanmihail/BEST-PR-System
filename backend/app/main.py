"""
FastAPI приложение
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.api import auth, tasks, stages, events, equipment, calendar, gamification, moderation, notifications, public, support, task_suggestions, registration, ai_assistant, activity, gallery, qr_auth

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
app.include_router(public.router, prefix=settings.API_V1_PREFIX)
app.include_router(support.router, prefix=settings.API_V1_PREFIX)
app.include_router(task_suggestions.router, prefix=settings.API_V1_PREFIX)
app.include_router(registration.router, prefix=settings.API_V1_PREFIX)
app.include_router(ai_assistant.router, prefix=settings.API_V1_PREFIX)
app.include_router(activity.router, prefix=settings.API_V1_PREFIX)
app.include_router(gallery.router, prefix=settings.API_V1_PREFIX)
app.include_router(qr_auth.router, prefix=settings.API_V1_PREFIX)

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
    
    # Проверка QR code модуля
    try:
        import qrcode
        from PIL import Image
        logger.info("✅ QR code module is available")
    except ImportError as e:
        logger.error(f"❌ QR code module is NOT available: {e}")
        logger.error("⚠️ QR code authentication will be disabled")
        logger.error("💡 To fix: Install system dependencies (libjpeg, zlib, etc.) and reinstall qrcode[pil]")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database URL: {settings.DATABASE_URL[:20]}..." if len(settings.DATABASE_URL) > 20 else f"Database URL: {settings.DATABASE_URL}")
    
    # Инициализация структуры Google Drive (только в production, если credentials доступны)
    if settings.ENVIRONMENT == "production":
        try:
            # Lazy import - не создаём GoogleService при импорте
            from app.services.drive_structure import DriveStructureService
            
            # Проверяем наличие хотя бы одного credentials
            if any([
                settings.GOOGLE_CREDENTIALS_1_JSON,
                settings.GOOGLE_CREDENTIALS_2_JSON,
                settings.GOOGLE_CREDENTIALS_3_JSON,
                settings.GOOGLE_CREDENTIALS_4_JSON,
                settings.GOOGLE_CREDENTIALS_5_JSON,
            ]):
                drive_structure = DriveStructureService()
                structure = drive_structure.initialize_structure()
                if structure and structure.get('bot_folder_id'):
                    logger.info(f"✅ Google Drive структура инициализирована: {structure.get('bot_folder_id')}")
                    
                    # Сохраняем ID главной папки, если не задан
                    if not settings.GOOGLE_DRIVE_FOLDER_ID:
                        logger.info(f"💡 Установите GOOGLE_DRIVE_FOLDER_ID={structure.get('bot_folder_id')} для использования этой папки")
                else:
                    logger.warning("⚠️ Google Drive структура не была создана (credentials не найдены или ошибка)")
            else:
                logger.info("ℹ️ Google credentials не найдены, Google Drive функции будут недоступны")
                logger.info("💡 Для использования Google Drive добавьте GOOGLE_CREDENTIALS_*_JSON в переменные окружения")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось инициализировать Google Drive структуру: {e}")
            logger.warning("Google Drive функции будут недоступны до добавления credentials")


@app.on_event("shutdown")
async def shutdown_event():
    """Выполняется при остановке приложения"""
    logger.info("BEST PR System API shutting down...")
