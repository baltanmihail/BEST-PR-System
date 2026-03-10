"""
Запуск API и Telegram бота одновременно
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
from bot.main import main as bot_main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_api():
    """Запуск FastAPI сервера"""
    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")
    
    config = uvicorn.Config(
        "app.main:app",
        host=host,
        port=port,
        reload=False,  # Отключаем reload на Railway для стабильности
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        access_log=True,
        timeout_keep_alive=30
    )
    server = uvicorn.Server(config)
    
    logger.info(f"🚀 Starting API server on {host}:{port}")
    logger.info(f"🔗 API будет доступен на http://{host}:{port}")
    logger.info(f"📚 Документация: http://{host}:{port}/docs")
    logger.info(f"💚 Health check: http://{host}:{port}/health")
    
    try:
        await server.serve()
    except Exception as e:
        logger.error(f"❌ API server error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


async def wait_for_api(max_attempts=60, delay=2):
    """Ждём, пока API станет доступен"""
    import httpx
    port = int(os.getenv("PORT", 8080))
    url = f"http://127.0.0.1:{port}/health"
    
    logger.info(f"⏳ Waiting for API at {url}...")
    
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    logger.info("✅ API готов к работе")
                    return True
        except Exception as e:
            # logger.debug(f"API check failed: {e}")
            pass
        
        if attempt < max_attempts - 1:
            if attempt % 5 == 0:
                logger.info(f"⏳ Ожидание запуска API... (попытка {attempt + 1}/{max_attempts})")
            await asyncio.sleep(delay)
    
    logger.warning("⚠️ API не ответил, но продолжаем запуск бота...")
    return False


async def run_reminders_scheduler():
    """Фоновая задача для периодической отправки напоминаний о регистрации"""
    # Запускаем планировщик только в production
    environment = os.getenv("ENVIRONMENT", "development")
    if environment != "production":
        logger.info(f"⚠️ Reminders scheduler не запускается в окружении '{environment}'")
        return
    
    # Ждём, пока API запустится
    await wait_for_api()
    
    # Небольшая задержка для полной инициализации API
    await asyncio.sleep(10)
    
    logger.info("⏰ Starting reminders scheduler (checking every 2 minutes)...")
    
    while True:
        try:
            import httpx
            from app.config import settings
            
            port = int(os.getenv("PORT", 8080))
            # Используем 127.0.0.1 вместо localhost для надежности
            url = f"http://127.0.0.1:{port}{settings.API_V1_PREFIX}/onboarding/reminders/process"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url)
                if response.status_code == 200:
                    data = response.json()
                    sent_count = data.get("sent_count", 0)
                    if sent_count > 0:
                        logger.info(f"📨 Sent {sent_count} reminder(s)")
                    # Логируем каждую проверку для отладки (можно убрать позже)
                    logger.debug(f"⏰ Reminders check completed: {sent_count} sent")
                else:
                    logger.warning(f"⚠️ Failed to process reminders: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"❌ Error in reminders scheduler: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Проверяем каждые 2 минуты
        await asyncio.sleep(120)


# Интервалы синхронизации оборудования (из BEST Channel Bot config.py)
SYNC_EQUIPMENT_INTERVAL_ACTIVE = 120   # 2 мин при активности
SYNC_EQUIPMENT_INTERVAL_IDLE = 300     # 5 мин без активности
SYNC_EQUIPMENT_INTERVAL_INITIAL = 60   # 1 мин первый запуск

# Интервалы двусторонней синхронизации (Sheets <-> БД)
BIDIRECTIONAL_SYNC_INTERVAL = 180      # 3 мин — основной интервал
BIDIRECTIONAL_SYNC_INITIAL_DELAY = 30  # 30с — задержка после старта
BIDIRECTIONAL_SYNC_QUOTA_ERROR = 600   # 10 мин при превышении квоты


async def run_equipment_sync_scheduler():
    """
    Периодическая синхронизация оборудования Sheets → PostgreSQL.
    Если в Sheets добавляется новое оборудование — оно подгружается на сайт.
    Работает и в production, и в development (в dev — реже).
    """
    await wait_for_api()
    await asyncio.sleep(15)  # После reminders
    
    environment = os.getenv("ENVIRONMENT", "development")
    interval = SYNC_EQUIPMENT_INTERVAL_INITIAL if environment == "production" else 120  # dev: 2 мин
    logger.info(f"📦 Equipment sync scheduler: interval={interval}s")
    
    while True:
        try:
            import httpx
            from app.config import settings
            
            port = int(os.getenv("PORT", 8080))
            url = f"http://127.0.0.1:{port}{settings.API_V1_PREFIX}/equipment/sync/cron"
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url)
                if response.status_code == 200:
                    data = response.json()
                    synced = data.get("synced", 0)
                    if synced > 0:
                        logger.info(f"📦 Equipment sync: {synced} items synced")
                else:
                    logger.warning(f"⚠️ Equipment sync failed: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Equipment sync error: {e}")
        
        await asyncio.sleep(interval)


async def run_bidirectional_sync_scheduler():
    """
    Периодическая двусторонняя синхронизация заявок Sheets <-> PostgreSQL.
    Аналог periodic_sync() из BEST Channel Bot:
    1. Читает статусы заявок из Google Sheets
    2. Сравнивает с БД и обновляет при расхождении
    3. Отправляет уведомления пользователям об изменении статуса
    4. Обновляет календарь занятости и статусы оборудования
    """
    environment = os.getenv("ENVIRONMENT", "development")
    if environment != "production":
        logger.info("Bidirectional sync scheduler не запускается вне production")
        return

    await wait_for_api()
    await asyncio.sleep(BIDIRECTIONAL_SYNC_INITIAL_DELAY)

    interval = BIDIRECTIONAL_SYNC_INTERVAL
    logger.info(f"Bidirectional sync scheduler: interval={interval}s")

    while True:
        try:
            from app.database import AsyncSessionLocal
            from app.services.google_service import GoogleService
            from app.services.equipment_sync_bidirectional import EquipmentBidirectionalSync
            from app.services.equipment_notifications import EquipmentNotifications

            async with AsyncSessionLocal() as db:
                google_service = GoogleService()
                sync_service = EquipmentBidirectionalSync(google_service)

                result = await sync_service.sync_from_sheets(db)

                status_changes = result.get("status_changes", [])
                if status_changes:
                    logger.info(
                        f"Bidirectional sync: {len(status_changes)} status change(s), sending notifications"
                    )
                    notifications = EquipmentNotifications()
                    await notifications.send_status_change_notifications(
                        db=db, status_changes=status_changes
                    )
                    try:
                        from app.services.notification_service import NotificationService
                        from app.models.notification import NotificationType
                        status_labels = {
                            "approved": "одобрена", "rejected": "отклонена",
                            "active": "выдано", "completed": "возвращено",
                        }
                        for change in status_changes:
                            user_id = change.get("user_id")
                            new_status = change.get("new_status", "")
                            eq_name = change.get("equipment_name", "оборудование")
                            if user_id:
                                ntype = NotificationType.EQUIPMENT_APPROVED if new_status == "approved" else NotificationType.SYSTEM
                                label = status_labels.get(new_status, new_status)
                                await NotificationService.create_notification(
                                    db=db,
                                    user_id=user_id,
                                    notification_type=ntype,
                                    title=f"Статус заявки изменён",
                                    message=f"Заявка на \"{eq_name}\" — {label}",
                                    data={"request_id": str(change.get("request_id", ""))},
                                )
                    except Exception as e:
                        logger.warning(f"In-app notification for bidirectional sync failed: {e}")

                updated = result.get("updated", 0)
                if updated > 0:
                    try:
                        from app.services.equipment_calendar_sync import EquipmentCalendarSync
                        calendar_sync = EquipmentCalendarSync(google_service)
                        await calendar_sync.create_or_update_calendar_sheet(db)
                        logger.info("Bidirectional sync: calendar updated")
                    except Exception as e:
                        logger.warning(f"Calendar update failed: {e}")

                    try:
                        from app.services.equipment_status_sync import EquipmentStatusSync
                        status_sync = EquipmentStatusSync(google_service)
                        await status_sync.update_equipment_statuses_by_date(db)
                        logger.info("Bidirectional sync: equipment statuses updated")
                    except Exception as e:
                        logger.warning(f"Equipment status update failed: {e}")

                if result.get("status") == "error" and "429" in str(result.get("error", "")):
                    interval = BIDIRECTIONAL_SYNC_QUOTA_ERROR
                    logger.warning(f"Quota exceeded, next sync in {interval}s")
                else:
                    interval = BIDIRECTIONAL_SYNC_INTERVAL

        except Exception as e:
            logger.error(f"Bidirectional sync error: {e}")

        await asyncio.sleep(interval)


async def run_bot():
    """Запуск Telegram бота"""
    # Запускаем бота только в production, чтобы избежать конфликтов
    environment = os.getenv("ENVIRONMENT", "development")
    if environment != "production":
        logger.info(f"⚠️ Бот не запускается в окружении '{environment}'. Запустите только в production.")
        return
    
    # Ждём, пока API запустится
    await wait_for_api()
    
    logger.info("🤖 Starting Telegram bot...")
    try:
        # Используем прямое создание бота и диспетчера
        from aiogram import Bot, Dispatcher
        from aiogram.enums import ParseMode
        from aiogram.fsm.storage.memory import MemoryStorage
        from app.config import settings
        from bot.handlers import router
        
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN не установлен, бот не запустится")
            return
        
        # Используем простой способ создания бота без DefaultBotProperties
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
        
        # Закрываем все предыдущие соединения, чтобы избежать конфликтов
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Удалены все предыдущие webhook'и и pending updates")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить webhook: {e}")
        
        # Устанавливаем команды бота для меню
        try:
            from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeAllGroupChats
            
            # Команды для личного чата (по умолчанию)
            private_commands = [
                BotCommand(command="start", description="Авторизация и главное меню"),
                BotCommand(command="register", description="Регистрация в системе"),
                BotCommand(command="tasks", description="Список моих задач"),
                BotCommand(command="stats", description="Моя статистика"),
                BotCommand(command="leaderboard", description="Рейтинг участников"),
                BotCommand(command="equipment", description="Мои заявки на оборудование"),
                BotCommand(command="notifications", description="Уведомления"),
                BotCommand(command="help", description="Справка"),
            ]
            
            # Команды для групп (только /help)
            group_commands = [
                BotCommand(command="help", description="Справка по чату"),
            ]
            
            # Устанавливаем команды для личного чата
            await bot.set_my_commands(private_commands, scope=BotCommandScopeDefault())
            logger.info("✅ Команды для личного чата установлены")
            
            # Устанавливаем команды для групп
            await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
            logger.info("✅ Команды для групп установлены")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось установить команды бота: {e}")
        
        # Используем MemoryStorage для FSM
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        dp.include_router(router)
        
        logger.info("✅ FSM Storage инициализирован (MemoryStorage)")
        
        # Запускаем polling с очисткой обновлений
        await dp.start_polling(bot, skip_updates=True, allowed_updates=["message", "callback_query"])
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def main():
    """Запуск API и бота параллельно"""
    # Выполняем миграции перед запуском
    try:
        import subprocess
        logger.info("🔄 Running database migrations...")
        result = subprocess.run(
            ["python", "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parent
        )
        if result.returncode == 0:
            logger.info("✅ Database migrations completed")
        else:
            logger.warning(f"⚠️ Migration warning: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ Migration error: {e}")
        # Продолжаем запуск даже если миграции не выполнились
    
    # Сначала запускаем API, затем с задержкой - бота и планировщик напоминаний
    api_task = asyncio.create_task(run_api())
    
    # Даём API время на запуск
    await asyncio.sleep(3)
    
    # Запускаем бота
    bot_task = asyncio.create_task(run_bot())
    
    # Запускаем планировщик напоминаний
    reminders_task = asyncio.create_task(run_reminders_scheduler())
    
    # Запускаем периодическую синхронизацию оборудования Sheets → PostgreSQL
    equipment_sync_task = asyncio.create_task(run_equipment_sync_scheduler())
    
    # Запускаем двустороннюю синхронизацию заявок Sheets <-> БД (как periodic_sync в BEST Channel Bot)
    bidirectional_sync_task = asyncio.create_task(run_bidirectional_sync_scheduler())
    
    # Ждём завершения всех задач
    await asyncio.gather(
        api_task,
        bot_task,
        reminders_task,
        equipment_sync_task,
        bidirectional_sync_task,
        return_exceptions=True
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
