"""
API endpoints для системы поддержки
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr
import logging

from app.database import get_db
from app.models.user import User, UserRole
from app.models.notification import NotificationType
from app.services.notification_service import NotificationService
from app.services.google_service import GoogleService
from app.services.drive_structure import drive_structure
from app.utils.permissions import get_current_user, OptionalUser

router = APIRouter(prefix="/support", tags=["support"])
logger = logging.getLogger(__name__)


class SupportRequest(BaseModel):
    """Запрос в поддержку"""
    message: str
    contact: Optional[str] = None  # Telegram username или email для неавторизованных
    category: Optional[str] = None  # Тип вопроса (опционально)
    link: Optional[str] = None  # Ссылка (для предложений)


@router.post("/request", response_model=dict)
async def create_support_request(
    message: str = Form(...),
    category: Optional[str] = Form(None),
    contact: Optional[str] = Form(None),
    link: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(OptionalUser)
):
    """
    Создать запрос в поддержку с возможностью прикрепления файла
    
    Доступно всем (авторизованным и неавторизованным)
    """
    # Определяем контакт
    contact_info = None
    user_name = "Неизвестный пользователь"
    
    if current_user:
        user_name = current_user.full_name
        contact_info = f"Telegram: @{current_user.username or current_user.telegram_id}"
    elif contact:
        contact_info = contact
    else:
        contact_info = "Контакт не указан"
    
    # Формируем полное сообщение
    full_message = message
    if link:
        full_message += f"\n\n🔗 Ссылка: {link}"
    
    uploaded_file_id = None
    if file:
        try:
            # Читаем файл
            file_content = await file.read()
            file_size_mb = len(file_content) / (1024 * 1024)
            
            if file_size_mb > 10:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Файл слишком большой. Максимальный размер: 10MB"
                )
            
            # Определяем MIME тип
            mime_type = file.content_type or "application/octet-stream"
            
            # Загружаем в Google Drive
            support_folder_id = drive_structure.get_support_folder_id()
            google_service = GoogleService()
            
            # Формируем имя файла с информацией о пользователе
            filename = f"{user_name}_{file.filename}".replace(" ", "_")
            uploaded_file_id = google_service.upload_file(
                file_content=file_content,
                filename=filename,
                mime_type=mime_type,
                folder_id=support_folder_id
            )
            
            # Делаем файл доступным по ссылке
            file_url = google_service.get_shareable_link(uploaded_file_id)
            full_message += f"\n\n📎 Прикреплён файл: {file.filename}\n🔗 {file_url}"
            
            logger.info(f"✅ Файл загружен в Google Drive: {uploaded_file_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки файла: {e}")
            # Не прерываем отправку запроса, если файл не загрузился
    
    # Находим всех координаторов и VP4PR для уведомления
    from app.models.user import UserRole
    admins_query = select(User).where(
        User.role.in_([
            UserRole.COORDINATOR_SMM,
            UserRole.COORDINATOR_DESIGN,
            UserRole.COORDINATOR_CHANNEL,
            UserRole.COORDINATOR_PRFR,
            UserRole.VP4PR
        ])
    )
    admins_result = await db.execute(admins_query)
    admins = admins_result.scalars().all()
    
    # Отправляем уведомление всем админам
    for admin in admins:
        await NotificationService.create_notification(
            db=db,
            user_id=admin.id,
            notification_type=NotificationType.SUPPORT_REQUEST,
            title="Новый запрос в поддержку",
            message=f"От: {user_name}\nКонтакт: {contact_info}\nКатегория: {category or 'не указана'}\n\n{full_message}",
            data={
                "user_id": str(current_user.id) if current_user else None,
                "user_name": user_name,
                "contact": contact_info,
                "category": category,
                "message": message,
                "link": link,
                "file_id": uploaded_file_id,
            }
        )
    
    # Если пользователь авторизован, отправляем ему подтверждение
    if current_user:
        await NotificationService.create_notification(
            db=db,
            user_id=current_user.id,
            notification_type=NotificationType.SUPPORT_REQUEST,
            title="Запрос отправлен",
            message="Ваш запрос в поддержку получен. Мы ответим вам в ближайшее время.",
            data={"status": "sent"}
        )
    
    return {
        "status": "success",
        "message": "Ваш запрос отправлен. Мы свяжемся с вами в ближайшее время.",
        "file_id": uploaded_file_id
    }
