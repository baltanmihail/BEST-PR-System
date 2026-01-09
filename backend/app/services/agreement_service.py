"""
Сервис для работы с пользовательским соглашением
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AgreementService:
    """Сервис для получения текста пользовательского соглашения"""
    
    AGREEMENT_FILE = "BEST_PR_System_Agreement.md"
    AGREEMENT_VERSION = "2.0"
    
    @staticmethod
    def get_agreement_path() -> Path:
        """Получить путь к файлу соглашения"""
        # Ищем файл в папке docs относительно корня проекта
        base_path = Path(__file__).resolve().parent.parent.parent.parent
        agreement_path = base_path / "docs" / AgreementService.AGREEMENT_FILE
        
        # Если не найден, пробуем альтернативные пути
        if not agreement_path.exists():
            # Пробуем относительно текущего файла
            current_file = Path(__file__).resolve()
            alternative_path = current_file.parent.parent.parent / "docs" / AgreementService.AGREEMENT_FILE
            if alternative_path.exists():
                return alternative_path
        
        return agreement_path
    
    @staticmethod
    def get_agreement_content() -> dict:
        """
        Получить содержимое пользовательского соглашения
        
        Returns:
            Словарь с версией, заголовком и содержимым соглашения
        """
        try:
            agreement_path = AgreementService.get_agreement_path()
            
            if not agreement_path.exists():
                logger.warning(f"Файл соглашения не найден: {agreement_path}")
                # Возвращаем базовую версию из кода
                return AgreementService._get_default_agreement()
            
            with open(agreement_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "version": AgreementService.AGREEMENT_VERSION,
                "title": "Пользовательское соглашение BEST PR System",
                "content": content
            }
            
        except Exception as e:
            logger.error(f"Ошибка чтения соглашения: {e}", exc_info=True)
            return AgreementService._get_default_agreement()
    
    @staticmethod
    def _get_default_agreement() -> dict:
        """Получить соглашение по умолчанию (заглушка)"""
        return {
            "version": AgreementService.AGREEMENT_VERSION,
            "title": "Пользовательское соглашение BEST PR System",
            "content": """
ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ 
ДЛЯ ИСПОЛЬЗОВАНИЯ СИСТЕМЫ УПРАВЛЕНИЯ PR-ОТДЕЛОМ ОРГАНИЗАЦИЕЙ "BEST МОСКВА" 

Настоящее соглашение определяет правила использования системы управления PR-отделом BEST Москва.

Для получения полного текста соглашения обратитесь к администрации.
            """.strip()
        }
