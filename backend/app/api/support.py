"""
API endpoints для системы поддержки
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel
import json
import logging

from app.database import get_db
from app.models.user import User, UserRole
from app.models.notification import Notification, NotificationType
from app.services.notification_service import NotificationService
from app.utils.permissions import get_current_user, require_coordinator, OptionalUser

router = APIRouter(prefix="/support", tags=["support"])
logger = logging.getLogger(__name__)


class SupportRequest(BaseModel):
    """Запрос в поддержку"""
    message: str
    contact: Optional[str] = None
    category: Optional[str] = None
    link: Optional[str] = None


class SupportReply(BaseModel):
    """Ответ VP4PR на запрос в поддержку"""
    user_telegram_id: int
    user_name: str
    message: str


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
            
            # Пытаемся загрузить в Google Drive (если credentials доступны)
            try:
                # Импортируем только при необходимости (lazy import)
                from app.services.google_service import GoogleService
                from app.services.drive_structure import DriveStructureService
                drive_structure = DriveStructureService()
                
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
            except ValueError as e:
                # Google credentials не найдены
                logger.warning(f"⚠️ Google credentials не найдены, файл не загружен: {e}")
                full_message += f"\n\n📎 Прикреплён файл: {file.filename} (файл не загружен в Google Drive - credentials не найдены)"
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки файла в Google Drive: {e}")
                full_message += f"\n\n📎 Прикреплён файл: {file.filename} (ошибка загрузки в Google Drive)"
            
        except HTTPException:
            # Пере-поднимаем HTTPException (например, для размера файла)
            raise
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при работе с файлом: {e}")
            full_message += f"\n\n📎 Прикреплён файл: {file.filename} (ошибка обработки файла)"
    
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
    
    # Отправляем уведомление всем админам (в систему + Telegram)
    from app.utils.telegram_sender import send_telegram_message
    
    tg_text = (
        f"💬 <b>Новый запрос в поддержку</b>\n\n"
        f"👤 <b>От:</b> {user_name}\n"
        f"📞 <b>Контакт:</b> {contact_info}\n"
        f"📁 <b>Категория:</b> {category or 'не указана'}\n\n"
        f"💭 {message[:500]}"
    )
    if link:
        tg_text += f"\n\n🔗 {link}"
    
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
        # Отправляем в Telegram каждому админу, сохраняем message_id для ответов
        if admin.telegram_id and admin.telegram_id > 0:
            try:
                result = await send_telegram_message(
                    chat_id=admin.telegram_id,
                    message=tg_text,
                    parse_mode="HTML",
                    silent_fail=True,
                    return_message_id=True,
                )
                if isinstance(result, tuple):
                    ok, msg_id = result
                else:
                    ok, msg_id = result, None
                if ok and msg_id and current_user and current_user.telegram_id:
                    from app.api.support_reply_tracker import track_support_message
                    track_support_message(admin.telegram_id, msg_id, current_user.telegram_id, user_name)
            except Exception:
                pass
    
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


@router.get("/tickets")
async def get_support_tickets(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator()),
):
    """Получить запросы в поддержку (для VP4PR / координаторов)"""
    query = (
        select(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.type == NotificationType.SUPPORT_REQUEST,
            Notification.title == "Новый запрос в поддержку",
        )
        .order_by(desc(Notification.created_at))
        .limit(limit)
    )
    result = await db.execute(query)
    notifications = result.scalars().all()

    tickets = []
    for n in notifications:
        data = {}
        if n.data:
            try:
                data = json.loads(n.data) if isinstance(n.data, str) else n.data
            except Exception:
                pass
        tickets.append({
            "id": str(n.id),
            "user_name": data.get("user_name", "Неизвестный"),
            "user_telegram_id": data.get("user_telegram_id"),
            "contact": data.get("contact", ""),
            "category": data.get("category", ""),
            "message": data.get("message", n.message),
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        })
    return {"items": tickets}


@router.post("/reply")
async def reply_to_support(
    body: SupportReply,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator()),
):
    """VP4PR / координатор отвечает пользователю через Telegram"""
    from app.utils.telegram_sender import send_telegram_message

    if not body.user_telegram_id:
        raise HTTPException(status_code=400, detail="telegram_id пользователя не указан")

    text = (
        f"💬 <b>Ответ от поддержки</b>\n\n"
        f"👤 <b>От:</b> {current_user.full_name}\n\n"
        f"{body.message}"
    )

    ok = await send_telegram_message(
        chat_id=body.user_telegram_id,
        message=text,
        parse_mode="HTML",
        silent_fail=True,
    )

    if not ok:
        raise HTTPException(status_code=500, detail="Не удалось отправить сообщение в Telegram")

    # Сохраняем уведомление для пользователя (если он есть в базе)
    user_query = select(User).where(User.telegram_id == body.user_telegram_id)
    user_result = await db.execute(user_query)
    target_user = user_result.scalar_one_or_none()
    if target_user:
        await NotificationService.create_notification(
            db=db,
            user_id=target_user.id,
            notification_type=NotificationType.SUPPORT_REQUEST,
            title="Ответ от поддержки",
            message=f"От: {current_user.full_name}\n\n{body.message}",
            data=json.dumps({
                "from_admin": str(current_user.id),
                "admin_name": current_user.full_name,
            }),
        )

    return {"status": "success", "message": "Ответ отправлен"}
