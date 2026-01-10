"""
Скрипт для удаления старых папок Google Drive, созданных в неправильной директории
Запускать вручную при необходимости очистки
"""
import sys
import os
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.google_service import GoogleService
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Список ID старых папок для удаления (из логов при создании в неправильной директории)
OLD_FOLDER_IDS = [
    "11A1lVlBkHKLjGtrEmndS__5MOqNDqEJn",  # Старая главная папка
    "1sH7RHpyj3Fl_1ZidZUsEbe3IS5z3v_DE",  # Tasks
    "12j962MkazQioS9IOqkwBDjWqrkZZt1Kv",  # Gallery
    "18blLlv8O4ovypGch0dycuxMKDmlWaF_K",  # Equipment
    "1NQCYe7C8jcLLGNrfJnOovgHfqrz25tES",  # Support
    "1cZKdzPWwUEIP2aNwktgvwXRk97bV5zQm",  # Users
    "1JKZIjRf2ZMFUw0rQXlPC2a-YS2xrlQDs",  # Admin
    "1tZVq_V3N60ftkJgJjp0JkddPU6LVpFQm",  # Coordinators
    "1OJvqDZMD6qFId3QD3eT9TTl7aO1WPCIo",  # SMM
    "1GiSzSjARN7KCFGk7SqFXjDXQ0Le1rtoG",  # Design
    "190G8QXEturS3J5UvPdDoI5PGySL3WO9I",  # Channel
    "1dA0g8tS-Nm2-gRHhjNS8djygcvdrljUs",  # PR-FR
    "1YphbIc3ymL8NL77t1dS4zhCHD5yDVxpi",  # VP4PR
]


def main():
    """Удалить старые папки Google Drive"""
    if not settings.GOOGLE_CREDENTIALS_1_JSON:
        logger.error("❌ Google credentials не настроены. Установите GOOGLE_CREDENTIALS_1_JSON")
        return
    
    google_service = GoogleService()
    
    logger.info(f"🗑️ Начинаем удаление {len(OLD_FOLDER_IDS)} старых папок...")
    
    deleted_count = 0
    failed_count = 0
    
    for folder_id in OLD_FOLDER_IDS:
        try:
            # Проверяем, существует ли папка перед удалением
            try:
                drive_service = google_service._get_drive_service(background=False)
                file_info = drive_service.files().get(
                    fileId=folder_id,
                    fields='id, name, trashed'
                ).execute()
                
                if file_info.get('trashed'):
                    logger.info(f"⏭️ Папка {folder_id} уже в корзине, пропускаем")
                    continue
                
                folder_name = file_info.get('name', folder_id)
                
            except Exception as e:
                logger.warning(f"⚠️ Папка {folder_id} не найдена или недоступна: {e}")
                continue
            
            # Удаляем папку
            if google_service.delete_file(folder_id, background=False):
                logger.info(f"✅ Удалена папка '{folder_name}' (ID: {folder_id})")
                deleted_count += 1
            else:
                logger.error(f"❌ Не удалось удалить папку '{folder_name}' (ID: {folder_id})")
                failed_count += 1
                
        except Exception as e:
            logger.error(f"❌ Ошибка при удалении папки {folder_id}: {e}")
            failed_count += 1
    
    logger.info(f"\n📊 Итого: удалено {deleted_count}, ошибок {failed_count}, всего {len(OLD_FOLDER_IDS)}")
    
    if deleted_count > 0:
        logger.info("💡 Папки перемещены в корзину Google Drive. Можно окончательно удалить через веб-интерфейс.")


if __name__ == "__main__":
    main()
