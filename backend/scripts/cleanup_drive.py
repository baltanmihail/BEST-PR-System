"""
Очистка старых папок/файлов в Google Drive.

Запуск:
    GOOGLE_CREDENTIALS_1_JSON=... GOOGLE_DRIVE_OWNER_EMAIL=... \
    python backend/scripts/cleanup_drive.py
"""
import logging

from app.services.google_service import GoogleService

# ID старых папок, созданных до смены корневой директории
OLD_FILE_IDS = [
    "11A1lVlBkHKLjGtrEmndS__5MOqNDqEJn",  # старая корневая
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
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    service = GoogleService()

    for file_id in OLD_FILE_IDS:
        ok = service.delete_file(file_id, background=False)
        if ok:
            logger.info(f"Удалено: {file_id}")
        else:
            logger.info(f"Пропущено (возможно уже нет доступа): {file_id}")


if __name__ == "__main__":
    main()
