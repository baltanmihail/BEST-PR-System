"""
Скрипт для создания координаторов в системе
Запуск: python scripts/create_coordinators.py
"""
import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.user import User, UserRole
from uuid import uuid4
from datetime import datetime, timezone


# Данные координаторов
COORDINATORS = [
    {
        "telegram_id": 5079636941,
        "username": "bfm5451",
        "full_name": "Балтян Михаил",
        "role": UserRole.VP4PR,
        "is_active": True,
    },
    {
        "telegram_id": 2118710401,
        "username": "yalkaugamer",
        "full_name": "Тамила Закирова",
        "role": UserRole.COORDINATOR_SMM,
        "is_active": True,
    },
    {
        "telegram_id": 1014621744,
        "username": "Art1fex",
        "full_name": "Олег Сычёв",
        "role": UserRole.COORDINATOR_CHANNEL,
        "is_active": True,
    },
    {
        "telegram_id": 796652169,
        "username": "KsuZay",
        "full_name": "Ксения Зайцева",
        "role": UserRole.COORDINATOR_DESIGN,
        "is_active": True,
    },
    {
        "telegram_id": 1281345523,
        "username": "timplooo",
        "full_name": "Тимофей Плошкин",
        "role": UserRole.COORDINATOR_PRFR,
        "is_active": True,
    },
]


async def create_coordinators():
    """Создать координаторов в базе данных"""
    database_url = settings.DATABASE_URL
    # Преобразуем для asyncpg если нужно
    if database_url.startswith("postgresql://") and "asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(database_url, echo=False)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as db:
        created_count = 0
        updated_count = 0
        
        for coord_data in COORDINATORS:
            telegram_id = coord_data["telegram_id"]
            
            # Проверяем, существует ли пользователь
            from sqlalchemy import select
            result = await db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Обновляем существующего пользователя
                user.username = coord_data["username"]
                user.full_name = coord_data["full_name"]
                user.role = coord_data["role"]
                user.is_active = coord_data["is_active"]
                user.personal_data_consent = True
                user.user_agreement_accepted = True
                print(f"✅ Обновлён: {coord_data['full_name']} ({coord_data['role'].value})")
                updated_count += 1
            else:
                # Создаём нового пользователя
                user = User(
                    telegram_id=telegram_id,
                    username=coord_data["username"],
                    full_name=coord_data["full_name"],
                    role=coord_data["role"],
                    is_active=coord_data["is_active"],
                    personal_data_consent=True,
                    user_agreement_accepted=True,
                    consent_date=datetime.now(timezone.utc),
                    agreement_version="1.0",
                    agreement_accepted_at=datetime.now(timezone.utc),
                )
                db.add(user)
                print(f"✅ Создан: {coord_data['full_name']} ({coord_data['role'].value})")
                created_count += 1
        
        await db.commit()
        
        print(f"\n📊 Итого:")
        print(f"   Создано: {created_count}")
        print(f"   Обновлено: {updated_count}")
        print(f"   Всего: {len(COORDINATORS)}")
    
    await engine.dispose()


if __name__ == "__main__":
    print("🚀 Создание координаторов...\n")
    asyncio.run(create_coordinators())
    print("\n✅ Готово!")
