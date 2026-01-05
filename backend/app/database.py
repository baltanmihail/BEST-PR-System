"""
Подключение к базе данных
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Создаём async engine
db_url = settings.DATABASE_URL

# Преобразуем URL для async драйверов
if db_url.startswith("sqlite"):
    # SQLite для разработки
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
elif db_url.startswith("postgresql://") and "asyncpg" not in db_url:
    # PostgreSQL - добавляем asyncpg драйвер если его нет
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    db_url,
    echo=settings.ENVIRONMENT == "development",
    future=True
)

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
