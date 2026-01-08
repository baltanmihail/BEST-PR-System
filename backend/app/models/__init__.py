"""
SQLAlchemy модели
"""
from app.models.user import User
from app.models.task import Task, TaskStage, TaskAssignment
from app.models.equipment import Equipment, EquipmentRequest
from app.models.event import Event
from app.models.gamification import PointsLog, Achievement
from app.models.file import File
from app.models.telegram import TelegramChat
from app.models.moderation import ModerationQueue
from app.models.activity import ActivityLog
from app.models.notification import Notification
from app.models.task_suggestion import TaskSuggestion
from app.models.onboarding import OnboardingResponse, OnboardingReminder

__all__ = [
    "User",
    "Task",
    "TaskStage",
    "TaskAssignment",
    "Equipment",
    "EquipmentRequest",
    "Event",
    "PointsLog",
    "Achievement",
    "File",
    "TelegramChat",
    "ModerationQueue",
    "ActivityLog",
    "Notification",
    "TaskSuggestion",
    "OnboardingResponse",
    "OnboardingReminder",
]
