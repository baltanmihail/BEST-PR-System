"""
Скрипт для создания системных шаблонов задач
Запускается при первом запуске системы или вручную
"""
import asyncio
import sys
import os
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.task_template import TaskTemplate, TemplateCategory
from app.models.task import TaskType, TaskPriority
from app.models.user import User, UserRole
from app.config import settings
from uuid import uuid4
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Системные шаблоны задач
SYSTEM_TEMPLATES = [
    {
        "name": "Пост в соцсети",
        "description": "Шаблон для создания поста в социальных сетях",
        "category": TemplateCategory.COORDINATOR_SMM,
        "task_type": TaskType.SMM,
        "priority": TaskPriority.MEDIUM,
        "default_description": "Создать пост для социальных сетей с текстом и дизайном",
        "equipment_available": False,
        "role_specific_requirements": {
            "smm": "Написать текст поста, подобрать хештеги, определить время публикации",
            "design": "Создать графику для поста в соответствии с брендбуком"
        },
        "questions": [
            "Какая цель поста?",
            "Какая целевая аудитория?",
            "Есть ли особые требования к дизайну?"
        ],
        "stages_template": [
            {
                "stage_name": "Концепт",
                "stage_order": 1,
                "due_date_offset": 7,
                "status_color": "green"
            },
            {
                "stage_name": "Текст",
                "stage_order": 2,
                "due_date_offset": 5,
                "status_color": "yellow"
            },
            {
                "stage_name": "Дизайн",
                "stage_order": 3,
                "due_date_offset": 3,
                "status_color": "blue"
            },
            {
                "stage_name": "Публикация",
                "stage_order": 4,
                "due_date_offset": 0,
                "status_color": "green"
            }
        ]
    },
    {
        "name": "Графика для поста",
        "description": "Шаблон для создания графики для поста",
        "category": TemplateCategory.COORDINATOR_DESIGN,
        "task_type": TaskType.DESIGN,
        "priority": TaskPriority.MEDIUM,
        "default_description": "Создать графику для поста в социальных сетях",
        "equipment_available": False,
        "role_specific_requirements": {
            "design": "Создать графику в соответствии с брендбуком и требованиями SMM"
        },
        "questions": [
            "Какие размеры нужны?",
            "Есть ли референсы?",
            "Какие цвета использовать?"
        ],
        "stages_template": [
            {
                "stage_name": "Бриф",
                "stage_order": 1,
                "due_date_offset": 7,
                "status_color": "green"
            },
            {
                "stage_name": "Концепт",
                "stage_order": 2,
                "due_date_offset": 5,
                "status_color": "yellow"
            },
            {
                "stage_name": "Эскиз",
                "stage_order": 3,
                "due_date_offset": 4,
                "status_color": "blue"
            },
            {
                "stage_name": "Финальная версия",
                "stage_order": 4,
                "due_date_offset": 2,
                "status_color": "purple"
            },
            {
                "stage_name": "Публикация",
                "stage_order": 5,
                "due_date_offset": 0,
                "status_color": "green"
            }
        ]
    },
    {
        "name": "Видеоролик",
        "description": "Шаблон для создания видеоролика",
        "category": TemplateCategory.COORDINATOR_CHANNEL,
        "task_type": TaskType.CHANNEL,
        "priority": TaskPriority.HIGH,
        "default_description": "Создать видеоролик для публикации",
        "equipment_available": True,
        "role_specific_requirements": {
            "channel": "Снять и смонтировать видеоролик, добавить музыку и эффекты"
        },
        "questions": [
            "Какой формат видео нужен?",
            "Какая длительность?",
            "Нужна ли озвучка?",
            "Есть ли сценарий?"
        ],
        "stages_template": [
            {
                "stage_name": "Сценарий",
                "stage_order": 1,
                "due_date_offset": 10,
                "status_color": "green"
            },
            {
                "stage_name": "Съёмка",
                "stage_order": 2,
                "due_date_offset": 7,
                "status_color": "yellow"
            },
            {
                "stage_name": "Монтаж",
                "stage_order": 3,
                "due_date_offset": 4,
                "status_color": "blue"
            },
            {
                "stage_name": "Озвучка",
                "stage_order": 4,
                "due_date_offset": 2,
                "status_color": "purple"
            },
            {
                "stage_name": "Публикация",
                "stage_order": 5,
                "due_date_offset": 0,
                "status_color": "green"
            }
        ]
    },
    {
        "name": "Организация мероприятия",
        "description": "Шаблон для организации мероприятия",
        "category": TemplateCategory.COORDINATOR_PRFR,
        "task_type": TaskType.PRFR,
        "priority": TaskPriority.HIGH,
        "default_description": "Организовать мероприятие",
        "equipment_available": False,
        "role_specific_requirements": {
            "prfr": "Организовать мероприятие: найти место, пригласить гостей, подготовить программу"
        },
        "questions": [
            "Какое мероприятие?",
            "Сколько участников ожидается?",
            "Какие требования к месту?"
        ],
        "stages_template": [
            {
                "stage_name": "Планирование",
                "stage_order": 1,
                "due_date_offset": 14,
                "status_color": "green"
            },
            {
                "stage_name": "Подготовка",
                "stage_order": 2,
                "due_date_offset": 7,
                "status_color": "yellow"
            },
            {
                "stage_name": "Проведение",
                "stage_order": 3,
                "due_date_offset": 0,
                "status_color": "blue"
            },
            {
                "stage_name": "Отчёт",
                "stage_order": 4,
                "due_date_offset": -2,
                "status_color": "green"
            }
        ]
    }
]


async def create_system_templates(db: AsyncSession):
    """Создать системные шаблоны задач"""
    # Находим первого VP4PR для создания шаблонов
    from sqlalchemy import select
    vp4pr_query = select(User).where(User.role == UserRole.VP4PR, User.is_active == True)
    vp4pr_result = await db.execute(vp4pr_query)
    vp4pr = vp4pr_result.scalar_one_or_none()
    
    if not vp4pr:
        logger.warning("⚠️ VP4PR не найден, создаём шаблоны с системным пользователем")
        # Создаём системного пользователя для шаблонов
        system_user_id = uuid4()
    else:
        system_user_id = vp4pr.id
    
    created_count = 0
    skipped_count = 0
    
    for template_data in SYSTEM_TEMPLATES:
        # Проверяем, существует ли уже такой шаблон
        from sqlalchemy import select
        
        # Получаем значение enum (строку) для сравнения в запросе
        # Проблема: SQLAlchemy при сравнении enum в WHERE может передавать имя enum (COORDINATOR_SMM)
        # вместо значения (coordinator_smm), поэтому используем прямое сравнение со строковым значением
        category_enum = template_data["category"]
        category_value = category_enum.value if hasattr(category_enum, 'value') else str(category_enum)
        
        # Используем прямое сравнение со строковым значением через cast
        from sqlalchemy import cast, String
        existing_query = select(TaskTemplate).where(
            TaskTemplate.name == template_data["name"],
            cast(TaskTemplate.category, String) == category_value,
            TaskTemplate.is_system == True
        )
        existing_result = await db.execute(existing_query)
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            logger.info(f"⏭️ Шаблон '{template_data['name']}' уже существует, пропускаем")
            skipped_count += 1
            continue
        
        # Создаём шаблон
        template = TaskTemplate(
            name=template_data["name"],
            description=template_data["description"],
            category=template_data["category"],
            created_by=system_user_id,
            task_type=template_data["task_type"],
            priority=template_data["priority"],
            default_description=template_data["default_description"],
            equipment_available=template_data["equipment_available"],
            role_specific_requirements=template_data["role_specific_requirements"],
            questions=template_data["questions"],
            stages_template=template_data["stages_template"],
            is_system=True,
            is_active=True
        )
        
        db.add(template)
        created_count += 1
        logger.info(f"✅ Создан системный шаблон: {template_data['name']}")
    
    await db.commit()
    
    logger.info(f"✅ Создано шаблонов: {created_count}, пропущено: {skipped_count}")
    return created_count


async def main():
    """Главная функция"""
    # Создаём подключение к БД
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            count = await create_system_templates(db)
            logger.info(f"✅ Инициализация системных шаблонов завершена. Создано: {count}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания системных шаблонов: {e}", exc_info=True)
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
