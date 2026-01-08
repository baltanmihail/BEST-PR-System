"""
FSM состояния для Telegram бота
"""
from aiogram.fsm.state import State, StatesGroup


class TaskCreationStates(StatesGroup):
    """Состояния для создания задачи"""
    waiting_for_title = State()  # Ожидание названия задачи
    waiting_for_type = State()  # Ожидание выбора типа задачи
    waiting_for_description = State()  # Ожидание описания задачи
    waiting_for_priority = State()  # Ожидание приоритета
    waiting_for_due_date = State()  # Ожидание дедлайна
    waiting_for_stages = State()  # Ожидание этапов (для Channel задач)
    waiting_for_files = State()  # Ожидание файлов (материалы задачи)
    confirming = State()  # Подтверждение создания задачи


class EquipmentRequestStates(StatesGroup):
    """Состояния для подачи заявки на оборудование"""
    waiting_for_shooting_name = State()  # Ожидание названия съёмки
    waiting_for_shooting_date = State()  # Ожидание даты съёмки
    waiting_for_rental_start = State()  # Ожидание даты получения оборудования
    waiting_for_rental_end = State()  # Ожидание даты возврата оборудования
    waiting_for_equipment_selection = State()  # Ожидание выбора оборудования
    waiting_for_comment = State()  # Ожидание комментария (опционально)
    confirming = State()  # Подтверждение заявки
