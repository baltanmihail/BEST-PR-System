"""
Подключение к базе данных
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import logging
import re

logger = logging.getLogger(__name__)

# Создаём async engine
db_url = settings.DATABASE_URL

# Валидация и преобразование URL
if not db_url or db_url.strip() == "":
    raise ValueError("DATABASE_URL не установлен! Проверьте переменные окружения в Railway.")

# Преобразуем URL для async драйверов
if db_url.startswith("sqlite"):
    # SQLite для разработки
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
elif db_url.startswith("postgresql://") or db_url.startswith("postgresql+asyncpg://"):
    # PostgreSQL - добавляем asyncpg драйвер если его нет
    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    
    # Проверяем, что URL правильно сформирован
    # Формат: postgresql+asyncpg://user:password@host:port/database
    if "@" not in db_url or ":" not in db_url.split("@")[1]:
        raise ValueError(
            f"Неправильный формат DATABASE_URL! "
            f"Ожидается: postgresql+asyncpg://user:password@host:port/database\n"
            f"Получено: {db_url[:50]}...\n"
            f"Проверьте переменную DATABASE_URL в Railway Variables."
        )
else:
    logger.warning(f"Неизвестный формат DATABASE_URL: {db_url[:30]}...")

try:
    engine = create_async_engine(
        db_url,
        echo=settings.ENVIRONMENT == "development",
        future=True
    )
    logger.info(f"Database engine создан успешно (URL: {db_url.split('@')[0]}@***)")
except Exception as e:
    logger.error(f"Ошибка создания database engine: {e}")
    logger.error(f"Проверьте DATABASE_URL в Railway Variables")
    raise

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base для моделей
Base = declarative_base()

async def get_db():
    """Dependency для получения сессии БД"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
