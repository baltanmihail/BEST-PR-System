"""
FastAPI приложение
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.api import auth, tasks, stages, events, equipment, calendar, gamification, moderation, notifications, public, support, task_suggestions, registration, ai_assistant, activity, gallery, qr_auth, onboarding, tour, telegram_chats, drive, users, task_templates, file_uploads

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
app.include_router(onboarding.router, prefix=settings.API_V1_PREFIX)
app.include_router(tour.router, prefix=settings.API_V1_PREFIX)
app.include_router(telegram_chats.router, prefix=settings.API_V1_PREFIX)
app.include_router(drive.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(task_templates.router, prefix=settings.API_V1_PREFIX)
app.include_router(file_uploads.router, prefix=settings.API_V1_PREFIX)

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
    logger.info(f"🌐 CORS allowed origins: {settings.CORS_ORIGINS}")
    
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
    
    # Инициализация структуры Google Drive (в production, если credentials доступны)
    # ВНИМАНИЕ: Если нет доступа к Shared Drive, система автоматически создаст папку в корне Google Drive сервисного аккаунта
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
                    
                    # Инициализируем Google таблицу таймлайна задач
                    try:
                        from app.services.sheets_sync import SheetsSyncService
                        from app.services.google_service import GoogleService
                        from googleapiclient.errors import HttpError
                        
                        logger.info("📊 Инициализация таблицы таймлайна задач...")
                        google_service = GoogleService()
                        sheets_sync = SheetsSyncService(google_service)
                        # Создаём таблицу таймлайна при первом запуске
                        timeline_sheets = sheets_sync._get_or_create_timeline_sheets()
                        if timeline_sheets and timeline_sheets.get('id'):
                            logger.info(f"✅ Google таблица таймлайна задач готова: {timeline_sheets.get('id')}")
                            logger.info(f"🔗 URL таблицы: {timeline_sheets.get('url', 'N/A')}")
                            
                            # Автоматическая синхронизация при старте (ВСЕГДА создаём полную сетку календаря)
                            try:
                                from app.database import AsyncSessionLocal
                                from datetime import datetime
                                
                                async def auto_sync_calendar():
                                    """Автоматическая синхронизация календаря при старте - создаёт полную сетку календаря"""
                                    try:
                                        async with AsyncSessionLocal() as db:
                                            logger.info(f"📊 Автоматическая синхронизация календаря (создание полной сетки календаря)...")
                                            now = datetime.now()
                                            result = await sheets_sync.sync_calendar_to_sheets_async(
                                                month=now.month,
                                                year=now.year,
                                                roles=["all"],
                                                db=db,
                                                statuses=None,
                                                scale="days",
                                                pull_from_sheets=False  # При старте не читаем из Sheets
                                            )
                                            logger.info(f"✅ Автоматическая синхронизация завершена: {result.get('status', 'unknown')}")
                                    except Exception as e:
                                        logger.error(f"❌ Ошибка автоматической синхронизации календаря: {e}", exc_info=True)
                                
                                # Запускаем автоматическую синхронизацию в фоне через 10 секунд (после полного старта)
                                import asyncio
                                async def delayed_sync():
                                    await asyncio.sleep(10)
                                    await auto_sync_calendar()
                                asyncio.create_task(delayed_sync())
                                logger.info(f"💡 Автоматическая синхронизация календаря будет выполнена через 10 секунд (создание полной сетки)")
                            except Exception as e:
                                logger.warning(f"⚠️ Не удалось запустить автоматическую синхронизацию: {e}")
                                logger.info(f"💡 Для заполнения данными вызовите: POST /api/v1/calendar/sync/sheets")
                        else:
                            logger.warning(f"⚠️ Таблица таймлайна не была создана или не вернула ID: {timeline_sheets}")
                    except HttpError as e:
                        error_str = str(e)
                        logger.error(f"❌ HttpError при создании таблицы таймлайна: {error_str}")
                        if 'storageQuotaExceeded' in error_str:
                            logger.warning(f"⚠️ Квота Google Drive превышена. Таблица таймлайна не будет создана.")
                            logger.warning(f"💡 Освободите место в Google Drive или используйте другой аккаунт.")
                            logger.warning(f"💡 Таблицу можно создать вручную через API: POST /api/v1/calendar/sync/sheets")
                        elif 'permissionDenied' in error_str or 'forbidden' in error_str.lower():
                            logger.error(f"❌ Нет доступа к Google Drive для создания таблицы таймлайна")
                            logger.error(f"💡 Проверьте, что сервисный аккаунт имеет права на создание файлов в папке {structure.get('bot_folder_id', 'N/A')}")
                        else:
                            logger.error(f"⚠️ Ошибка инициализации таблицы таймлайна: {e}", exc_info=True)
                    except Exception as e:
                        logger.error(f"❌ Неожиданная ошибка при создании таблицы таймлайна: {e}", exc_info=True)
                        logger.error(f"Тип ошибки: {type(e).__name__}")
                else:
                    logger.warning("⚠️ Google Drive структура не была создана (credentials не найдены или ошибка)")
            else:
                logger.info("ℹ️ Google credentials не найдены, Google Drive функции будут недоступны")
                logger.info("💡 Для использования Google Drive добавьте GOOGLE_CREDENTIALS_*_JSON в переменные окружения")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка инициализации Google Drive: {e}", exc_info=True)
            logger.error(f"Тип ошибки: {type(e).__name__}")
            logger.error("💡 Проверьте переменные окружения GOOGLE_CREDENTIALS_*_JSON и GOOGLE_DRIVE_FOLDER_ID")
    
    # Инициализация системных шаблонов задач (в фоне)
    try:
        import asyncio
        from app.database import AsyncSessionLocal
        from app.models.task_template import TaskTemplate
        from sqlalchemy import select, func
        
        async def init_system_templates():
            try:
                async with AsyncSessionLocal() as db:
                    try:
                        # Проверяем, есть ли уже системные шаблоны
                        count_query = select(func.count(TaskTemplate.id)).where(TaskTemplate.is_system == True)
                        result = await db.execute(count_query)
                        count = result.scalar()
                        
                        if count == 0:
                            logger.info("📋 Создание системных шаблонов задач...")
                            from scripts.create_system_templates import create_system_templates
                            await create_system_templates(db)
                            logger.info("✅ Системные шаблоны созданы")
                        else:
                            logger.info(f"ℹ️ Системные шаблоны уже существуют ({count} шт.)")
                    except Exception as e:
                        logger.error(f"❌ Ошибка создания системных шаблонов: {e}", exc_info=True)
                        logger.error(f"Тип ошибки: {type(e).__name__}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации системных шаблонов: {e}")
        
        # Запускаем инициализацию шаблонов в фоне (не блокируем старт приложения)
        asyncio.create_task(init_system_templates())
    except Exception as e:
        logger.warning(f"⚠️ Не удалось запустить инициализацию системных шаблонов: {e}")
    
    # Запускаем фоновые задачи для оборудования
    try:
        import asyncio
        from app.database import AsyncSessionLocal
        
        async def periodic_equipment_tasks():
            """Периодические задачи для оборудования"""
            # Ждём 1 час перед первым запуском (чтобы дать время системе запуститься)
            await asyncio.sleep(60 * 60)
            
            while True:
                try:
                    async with AsyncSessionLocal() as db:
                        try:
                            # Обновление статусов оборудования
                            from app.services.google_service import GoogleService
                            from app.services.equipment_status_sync import EquipmentStatusSync
                            
                            google_service = GoogleService()
                            status_sync = EquipmentStatusSync(google_service)
                            result = await status_sync.update_equipment_statuses_by_date(db)
                            logger.info(f"✅ Периодическое обновление статусов оборудования: {result}")
                            
                            # Проверка напоминаний
                            from app.services.equipment_reminders import EquipmentReminders
                            
                            reminders = EquipmentReminders(google_service)
                            reminder_result = await reminders.check_and_send_reminders(db, bot=None)
                            logger.info(f"✅ Проверка напоминаний: {reminder_result}")
                            
                        except Exception as e:
                            logger.error(f"❌ Ошибка в периодических задачах оборудования: {e}", exc_info=True)
                    
                    # Ждём 6 часов до следующего запуска
                    await asyncio.sleep(6 * 60 * 60)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка в цикле периодических задач оборудования: {e}", exc_info=True)
                    await asyncio.sleep(60 * 60)  # Ждём час перед повтором при ошибке
        
        # Запускаем периодические задачи в фоне
        asyncio.create_task(periodic_equipment_tasks())
        logger.info("✅ Периодические задачи для оборудования запущены (каждые 6 часов)")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось запустить периодические задачи для оборудования: {e}")
    
    # Запускаем периодическую синхронизацию Drive и Sheets
    try:
        import asyncio
        from app.database import AsyncSessionLocal
        
        async def periodic_drive_sheets_sync():
            """Периодическая синхронизация Google Drive и Google Sheets с системой"""
            # Ждём 30 минут перед первым запуском (чтобы дать время системе запуститься)
            await asyncio.sleep(30 * 60)
            
            while True:
                try:
                    async with AsyncSessionLocal() as db:
                        try:
                            # Синхронизация изменений из Google Drive
                            from app.services.drive_sync_service import DriveSyncService
                            
                            drive_sync = DriveSyncService()
                            drive_stats = await drive_sync.sync_drive_changes(db)
                            logger.info(f"✅ Периодическая синхронизация Drive: создано={drive_stats.get('created', 0)}, обновлено={drive_stats.get('updated', 0)}, ошибок={drive_stats.get('errors', 0)}")
                            
                            # Синхронизация изменений из Google Sheets (таймлайн)
                            from app.services.google_service import GoogleService
                            from app.services.sheets_sync import SheetsSyncService
                            
                            google_service = GoogleService()
                            sheets_sync = SheetsSyncService(google_service)
                            
                            # Получаем или создаём таблицу таймлайна
                            timeline_sheets = sheets_sync._get_or_create_timeline_sheets()
                            if not timeline_sheets or 'id' not in timeline_sheets:
                                logger.warning("⚠️ Не удалось получить таблицу таймлайна, пропускаем синхронизацию Sheets")
                            else:
                                sheets_result = await sheets_sync.sync_sheets_changes_to_db(
                                    spreadsheet_id=timeline_sheets["id"],
                                    db=db,
                                    sheet_name="Общий"
                                )
                                
                                if sheets_result.get('status') == 'success':
                                    changes_count = sheets_result.get('changes_count', 0)
                                    logger.info(f"✅ Периодическая синхронизация Sheets: проверено задач={sheets_result.get('tasks_checked', 0)}, изменений={changes_count}")
                                else:
                                    logger.debug(f"ℹ️ Синхронизация Sheets: {sheets_result.get('status', 'skipped')} - {sheets_result.get('reason', 'N/A')}")
                            
                        except Exception as e:
                            logger.error(f"❌ Ошибка в периодической синхронизации Drive/Sheets: {e}", exc_info=True)
                    
                    # Ждём 2 часа до следующего запуска
                    await asyncio.sleep(2 * 60 * 60)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка в цикле синхронизации Drive/Sheets: {e}", exc_info=True)
                    await asyncio.sleep(60 * 60)  # Ждём час перед повтором при ошибке
        
        # Запускаем периодическую синхронизацию в фоне
        asyncio.create_task(periodic_drive_sheets_sync())
        logger.info("✅ Периодическая синхронизация Drive и Sheets запущена (каждые 2 часа)")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось запустить периодическую синхронизацию Drive/Sheets: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Выполняется при остановке приложения"""
    logger.info("BEST PR System API shutting down...")
