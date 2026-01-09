"""
Скрипт для создания готовых шаблонов задач для каждого типа координатора
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


# Готовые шаблоны для каждого типа координатора
TEMPLATES = {
    TemplateCategory.COORDINATOR_SMM: [
        {
            "name": "Пост для соцсетей",
            "description": "Шаблон для создания поста в социальных сетях",
            "task_type": TaskType.SMM,
            "priority": TaskPriority.MEDIUM,
            "default_description": "Создать пост для социальных сетей",
            "equipment_available": False,
            "role_specific_requirements": {
                "smm": "Написать текст поста, подобрать хештеги, подготовить к публикации"
            },
            "questions": ["Какой формат поста? (текст, фото, видео)", "Какая целевая аудитория?"],
            "stages_template": [
                {"stage_name": "Написание текста", "stage_order": 1, "due_date_offset": 5, "status_color": "green"},
                {"stage_name": "Подбор визуала", "stage_order": 2, "due_date_offset": 3, "status_color": "yellow"},
                {"stage_name": "Согласование", "stage_order": 3, "due_date_offset": 1, "status_color": "blue"},
                {"stage_name": "Публикация", "stage_order": 4, "due_date_offset": 0, "status_color": "purple"}
            ]
        },
        {
            "name": "SMM-кампания",
            "description": "Шаблон для комплексной SMM-кампании",
            "task_type": TaskType.SMM,
            "priority": TaskPriority.HIGH,
            "default_description": "Провести SMM-кампанию",
            "equipment_available": False,
            "role_specific_requirements": {
                "smm": "Разработать стратегию кампании, создать контент-план, подготовить материалы"
            },
            "stages_template": [
                {"stage_name": "Разработка стратегии", "stage_order": 1, "due_date_offset": 14, "status_color": "green"},
                {"stage_name": "Создание контент-плана", "stage_order": 2, "due_date_offset": 10, "status_color": "yellow"},
                {"stage_name": "Подготовка материалов", "stage_order": 3, "due_date_offset": 5, "status_color": "blue"},
                {"stage_name": "Запуск кампании", "stage_order": 4, "due_date_offset": 0, "status_color": "purple"}
            ]
        }
    ],
    TemplateCategory.COORDINATOR_DESIGN: [
        {
            "name": "Дизайн поста",
            "description": "Шаблон для создания дизайна поста",
            "task_type": TaskType.DESIGN,
            "priority": TaskPriority.MEDIUM,
            "default_description": "Создать дизайн для поста",
            "equipment_available": False,
            "role_specific_requirements": {
                "design": "Создать визуал для поста в соответствии с брендбуком"
            },
            "stages_template": [
                {"stage_name": "Концепция", "stage_order": 1, "due_date_offset": 5, "status_color": "green"},
                {"stage_name": "Эскиз", "stage_order": 2, "due_date_offset": 3, "status_color": "yellow"},
                {"stage_name": "Финальный дизайн", "stage_order": 3, "due_date_offset": 1, "status_color": "blue"},
                {"stage_name": "Экспорт", "stage_order": 4, "due_date_offset": 0, "status_color": "purple"}
            ]
        },
        {
            "name": "Баннер для мероприятия",
            "description": "Шаблон для создания баннера",
            "task_type": TaskType.DESIGN,
            "priority": TaskPriority.HIGH,
            "default_description": "Создать баннер для мероприятия",
            "equipment_available": False,
            "role_specific_requirements": {
                "design": "Создать баннер с указанием даты, места и темы мероприятия"
            },
            "stages_template": [
                {"stage_name": "Бриф", "stage_order": 1, "due_date_offset": 7, "status_color": "green"},
                {"stage_name": "Концепция", "stage_order": 2, "due_date_offset": 5, "status_color": "yellow"},
                {"stage_name": "Дизайн", "stage_order": 3, "due_date_offset": 2, "status_color": "blue"},
                {"stage_name": "Согласование", "stage_order": 4, "due_date_offset": 1, "status_color": "purple"}
            ]
        }
    ],
    TemplateCategory.COORDINATOR_CHANNEL: [
        {
            "name": "Видеоролик",
            "description": "Шаблон для создания видеоролика",
            "task_type": TaskType.CHANNEL,
            "priority": TaskPriority.HIGH,
            "default_description": "Создать видеоролик",
            "equipment_available": True,
            "role_specific_requirements": {
                "channel": "Снять и смонтировать видеоролик"
            },
            "stages_template": [
                {"stage_name": "Сценарий", "stage_order": 1, "due_date_offset": 10, "status_color": "green"},
                {"stage_name": "Съёмка", "stage_order": 2, "due_date_offset": 5, "status_color": "yellow"},
                {"stage_name": "Монтаж", "stage_order": 3, "due_date_offset": 2, "status_color": "blue"},
                {"stage_name": "Цветокоррекция", "stage_order": 4, "due_date_offset": 1, "status_color": "purple"},
                {"stage_name": "Финальная версия", "stage_order": 5, "due_date_offset": 0, "status_color": "green"}
            ]
        },
        {
            "name": "Фотосессия",
            "description": "Шаблон для проведения фотосессии",
            "task_type": TaskType.CHANNEL,
            "priority": TaskPriority.MEDIUM,
            "default_description": "Провести фотосессию",
            "equipment_available": True,
            "role_specific_requirements": {
                "channel": "Провести фотосессию и обработать фотографии"
            },
            "stages_template": [
                {"stage_name": "Концепция", "stage_order": 1, "due_date_offset": 7, "status_color": "green"},
                {"stage_name": "Подготовка", "stage_order": 2, "due_date_offset": 3, "status_color": "yellow"},
                {"stage_name": "Съёмка", "stage_order": 3, "due_date_offset": 1, "status_color": "blue"},
                {"stage_name": "Обработка", "stage_order": 4, "due_date_offset": 0, "status_color": "purple"}
            ]
        }
    ],
    TemplateCategory.COORDINATOR_PRFR: [
        {
            "name": "PR-активность",
            "description": "Шаблон для PR-активности",
            "task_type": TaskType.PRFR,
            "priority": TaskPriority.HIGH,
            "default_description": "Организовать PR-активность",
            "equipment_available": False,
            "role_specific_requirements": {
                "prfr": "Организовать PR-активность, подготовить материалы"
            },
            "stages_template": [
                {"stage_name": "Планирование", "stage_order": 1, "due_date_offset": 14, "status_color": "green"},
                {"stage_name": "Подготовка", "stage_order": 2, "due_date_offset": 7, "status_color": "yellow"},
                {"stage_name": "Проведение", "stage_order": 3, "due_date_offset": 0, "status_color": "blue"},
                {"stage_name": "Отчёт", "stage_order": 4, "due_date_offset": -2, "status_color": "purple"}
            ]
        }
    ]
}


async def create_default_templates():
    """Создать готовые шаблоны задач"""
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Находим первого VP4PR для создания системных шаблонов
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.role == UserRole.VP4PR).limit(1)
        )
        vp4pr = result.scalar_one_or_none()
        
        if not vp4pr:
            print("❌ Не найден пользователь с ролью VP4PR. Создайте его сначала.")
            return
        
        print(f"✅ Используется пользователь {vp4pr.id} (VP4PR) для создания шаблонов")
        
        created_count = 0
        
        for category, templates in TEMPLATES.items():
            print(f"\n📁 Создание шаблонов для категории: {category.value}")
            
            for template_data in templates:
                # Проверяем, существует ли уже такой шаблон
                from sqlalchemy import select
                existing = await db.execute(
                    select(TaskTemplate).where(
                        TaskTemplate.name == template_data["name"],
                        TaskTemplate.category == category,
                        TaskTemplate.is_system == True
                    )
                )
                if existing.scalar_one_or_none():
                    print(f"  ⏭️  Шаблон '{template_data['name']}' уже существует, пропускаем")
                    continue
                
                template = TaskTemplate(
                    id=uuid4(),
                    created_by=vp4pr.id,
                    category=category,
                    is_system=True,
                    is_active=True,
                    **template_data
                )
                
                db.add(template)
                created_count += 1
                print(f"  ✅ Создан шаблон: {template_data['name']}")
        
        await db.commit()
        print(f"\n✅ Создано {created_count} шаблонов")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_default_templates())
