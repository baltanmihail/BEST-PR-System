"""
Alembic environment configuration
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Import models and config
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.database import Base
from app.models import *  # Import all models

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set SQLAlchemy URL from settings
# Convert to async URL if needed
db_url = settings.DATABASE_URL

# Валидация DATABASE_URL
if not db_url or db_url.strip() == "":
    raise ValueError("❌ DATABASE_URL не установлен! Проверьте переменные окружения в Railway.")

if db_url.startswith("sqlite"):
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
elif db_url.startswith("postgresql://") or db_url.startswith("postgresql+asyncpg://"):
    # Convert postgresql:// to postgresql+asyncpg://
    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    
    # Проверяем формат URL
    try:
        if "@" not in db_url:
            raise ValueError("DATABASE_URL должен содержать @ (user:password@host)")
        
        host_part = db_url.split("@")[1]
        if ":" not in host_part.split("/")[0]:
            raise ValueError("DATABASE_URL должен содержать порт (host:port)")
        
        host_port = host_part.split("/")[0]
        host, port = host_port.rsplit(":", 1)
        
        # Проверяем, что порт - число
        try:
            port_num = int(port)
        except ValueError:
            if port == "port":
                raise ValueError(
                    "❌ ОШИБКА: В DATABASE_URL указан порт 'port' вместо числа!\n"
                    "   Вы скопировали пример URL, а не реальный из Railway.\n"
                    "   Действия:\n"
                    "   1. Railway Dashboard → PostgreSQL база данных → Variables\n"
                    "   2. Скопируйте РЕАЛЬНЫЙ DATABASE_URL (там будет число, например 5432)\n"
                    "   3. Замените postgresql:// на postgresql+asyncpg://\n"
                    "   4. Обновите переменную DATABASE_URL в вашем сервисе"
                )
            raise ValueError(f"Порт должен быть числом, получено: '{port}'")
    except ValueError as e:
        print(f"\n❌ ОШИБКА ВАЛИДАЦИИ DATABASE_URL:\n{e}\n")
        raise

config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Get db_url from config (already converted)
    db_url = config.get_main_option("sqlalchemy.url")
    
    try:
        # Create async engine directly
        connectable = create_async_engine(
            db_url,
            poolclass=pool.NullPool,
        )

        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

        await connectable.dispose()
    except Exception as e:
        error_msg = str(e)
        if "port" in error_msg.lower() or "invalid literal" in error_msg.lower():
            print("\n" + "="*60)
            print("❌ ОШИБКА ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ")
            print("="*60)
            print("\nПроблема: DATABASE_URL содержит неправильный формат порта.")
            print("\nЧто делать:")
            print("1. Откройте Railway Dashboard")
            print("2. Перейдите в вашу PostgreSQL базу данных")
            print("3. Откройте вкладку 'Variables'")
            print("4. Скопируйте РЕАЛЬНЫЙ DATABASE_URL")
            print("   (он должен содержать число после :, например :5432)")
            print("5. Замените postgresql:// на postgresql+asyncpg://")
            print("6. Обновите переменную DATABASE_URL в вашем сервисе (Backend)")
            print("\nПример правильного URL:")
            print("postgresql+asyncpg://postgres:password@host.railway.app:5432/railway")
            print("                                                      ^^^^")
            print("                                                      Это число!")
            print("="*60 + "\n")
        raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
