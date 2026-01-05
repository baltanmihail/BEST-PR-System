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
    try:
        # Парсим URL для проверки
        if "@" not in db_url:
            raise ValueError("DATABASE_URL должен содержать @ (user:password@host)")
        
        parts = db_url.split("@")
        if len(parts) != 2:
            raise ValueError("DATABASE_URL должен содержать ровно один @")
        
        host_part = parts[1]
        if ":" not in host_part:
            raise ValueError("DATABASE_URL должен содержать порт после хоста (host:port)")
        
        host_port = host_part.split("/")[0]  # host:port
        if ":" not in host_port:
            raise ValueError("DATABASE_URL должен содержать порт (host:port)")
        
        host, port = host_port.rsplit(":", 1)
        
        # Проверяем, что порт - это число, а не слово
        try:
            port_num = int(port)
            if port_num < 1 or port_num > 65535:
                raise ValueError(f"Порт должен быть от 1 до 65535, получено: {port_num}")
        except ValueError as e:
            if "invalid literal" in str(e) or port == "port":
                raise ValueError(
                    f"❌ ОШИБКА: В DATABASE_URL указан порт '{port}' вместо числа!\n"
                    f"   Это значит, что вы скопировали пример URL, а не реальный.\n"
                    f"   Действия:\n"
                    f"   1. Откройте Railway Dashboard\n"
                    f"   2. Перейдите в вашу PostgreSQL базу данных\n"
                    f"   3. Откройте вкладку 'Variables'\n"
                    f"   4. Скопируйте РЕАЛЬНЫЙ DATABASE_URL (там будет число, например 5432)\n"
                    f"   5. Замените postgresql:// на postgresql+asyncpg://\n"
                    f"   6. Обновите переменную DATABASE_URL в вашем сервисе\n"
                    f"   Текущий URL: {db_url[:80]}..."
                ) from e
            raise
        
        logger.info(f"✅ DATABASE_URL валиден: {db_url.split('@')[0]}@***:{port}/***")
        
    except ValueError as e:
        logger.error(f"❌ Ошибка валидации DATABASE_URL: {e}")
        raise
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
