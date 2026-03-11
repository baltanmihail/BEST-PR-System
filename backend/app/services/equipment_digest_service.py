"""
Одно обновляемое сообщение-дайджест для VP4PR и Channel.
Приоритет ВСЕГДА важность/срочность. Группировка по типу: задача, пользователь.
Оборудование — зона Channel и VP4PR, не PR-FR.
"""
import logging
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, String

from app.models.equipment import EquipmentRequest, EquipmentRequestStatus, Equipment
from app.models.user import User, UserRole
from app.models.equipment_admin_digest import EquipmentAdminDigest

logger = logging.getLogger(__name__)

DIGEST_HEADER = """📋 <b>Оборудование — уведомления</b>
<i>По важности и срочности • Группировка по задаче/пользователю</i>

"""

EMPTY_DIGEST = DIGEST_HEADER.strip() + "\n\n✅ Нет новых уведомлений."


def _full_fio(user) -> str:
    """Полное ФИО (не сокращать)."""
    if not user:
        return "—"
    fn = (user.full_name or "").strip()
    if fn and len(fn) >= 3:
        return fn
    return fn or "—"


class EquipmentDigestService:
    """Одно сообщение в TG на координатора — редактируется при новых заявках/напоминаниях"""

    @staticmethod
    async def _build_digest_content(db: AsyncSession) -> str:
        """
        Собрать контент дайджеста.
        Приоритет ВСЕГДА важность/срочность.
        Группировка по типу: по пользователю, по задаче и т.д.
        """
        lines: List[str] = []
        today = date.today()

        # === Приоритет 1: СРОЧНО — напоминания на завтра (выдача/возврат) ===
        approved_result = await db.execute(
            select(EquipmentRequest).where(
                cast(EquipmentRequest.status, String).in_([
                    EquipmentRequestStatus.APPROVED.value,
                    EquipmentRequestStatus.ACTIVE.value
                ])
            )
        )
        approved = approved_result.scalars().all()

        issue_by_user: dict = {}  # user_fio -> [eq_names]
        return_by_user: dict = {}
        for req in approved:
            eq_res = await db.execute(select(Equipment).where(Equipment.id == req.equipment_id))
            eq = eq_res.scalar_one_or_none()
            usr_res = await db.execute(select(User).where(User.id == req.user_id))
            usr = usr_res.scalar_one_or_none()
            fio = _full_fio(usr) if usr else "—"
            eq_name = eq.name if eq else "?"
            if (req.start_date - today).days == 1:
                issue_by_user.setdefault(fio, []).append(eq_name)
            if (req.end_date - today).days == 1:
                return_by_user.setdefault(fio, []).append(eq_name)

        if issue_by_user or return_by_user:
            lines.append("⏰ <b>СРОЧНО — Завтра:</b>")
            for fio, eqs in sorted(issue_by_user.items()):
                eq_str = ", ".join(eqs[:4])
                if len(eqs) > 4:
                    eq_str += f" (+{len(eqs)-4})"
                lines.append(f"  📥 Выдача — {fio}: {eq_str}")
            for fio, eqs in sorted(return_by_user.items()):
                eq_str = ", ".join(eqs[:4])
                if len(eqs) > 4:
                    eq_str += f" (+{len(eqs)-4})"
                lines.append(f"  📤 Возврат — {fio}: {eq_str}")
            lines.append("")

        # === Приоритет 2: Новые заявки — группировка по задаче, затем по пользователю ===
        pending_result = await db.execute(
            select(EquipmentRequest).where(
                cast(EquipmentRequest.status, String) == EquipmentRequestStatus.PENDING.value
            ).order_by(EquipmentRequest.created_at.desc()).limit(20)
        )
        pending = pending_result.scalars().all()

        by_task: dict = {}   # task_title -> {user_fio: [eq_name]}
        no_task: dict = {}   # user_fio -> [(eq_name, dates)]
        for req in pending:
            usr_res = await db.execute(select(User).where(User.id == req.user_id))
            usr = usr_res.scalar_one_or_none()
            eq_res = await db.execute(select(Equipment).where(Equipment.id == req.equipment_id))
            eq = eq_res.scalar_one_or_none()
            fio = _full_fio(usr) if usr else "—"
            eq_name = eq.name if eq else "?"
            dates = f"{req.start_date.strftime('%d.%m')}–{req.end_date.strftime('%d.%m')}"
            if req.task_id:
                from app.models.task import Task
                t_res = await db.execute(select(Task).where(Task.id == req.task_id))
                task = t_res.scalar_one_or_none()
                ttl = (task.title or "Съёмка")[:25] if task else "Съёмка"
                by_task.setdefault(ttl, {}).setdefault(fio, []).append(f"{eq_name} ({dates})")
            else:
                no_task.setdefault(fio, []).append((eq_name, dates))

        if by_task:
            lines.append("🔔 <b>Новые заявки (по задачам):</b>")
            for ttl, users in sorted(by_task.items()):
                u_parts = [f"{u}: {', '.join(items[:2])}" + (f" +{len(items)-2}" if len(items) > 2 else "") for u, items in sorted(users.items())]
                lines.append(f"  • {ttl}: {'; '.join(u_parts[:3])}")
            lines.append("")
        if no_task:
            lines.append("🔔 <b>Новые заявки (без задачи):</b>")
            for fio, items in sorted(no_task.items()):
                parts = [f"{eq} ({d})" for eq, d in items[:4]]
                if len(items) > 4:
                    parts.append(f"+{len(items)-4}")
                lines.append(f"  • {fio}: {', '.join(parts)}")
            lines.append("")

        if not lines:
            return EMPTY_DIGEST
        return DIGEST_HEADER + "\n".join(lines).strip()

    @staticmethod
    async def update_digest_for_coordinators(db: AsyncSession, bot=None) -> int:
        """
        Обновить дайджест для VP4PR и Channel.
        Отправить новое сообщение или отредактировать существующее.
        """
        if not bot:
            from app.utils.telegram_sender import get_bot
            bot = await get_bot()
        if not bot:
            return 0

        # VP4PR и Channel — зона оборудования
        coordinators_result = await db.execute(
            select(User).where(
                User.role.in_([UserRole.VP4PR, UserRole.COORDINATOR_CHANNEL]),
                User.telegram_id.isnot(None)
            )
        )
        coords = list(coordinators_result.scalars().all())
        # TELEGRAM_ADMIN_IDS (если не дублируют VP4PR/Channel)
        from app.config import settings
        seen_ids = {int(c.telegram_id) for c in coords if c.telegram_id}
        for admin_id in getattr(settings, "TELEGRAM_ADMIN_IDS", []) or []:
            if admin_id and int(admin_id) not in seen_ids:
                # Добавляем фиктивного User с telegram_id
                class FakeCoord:
                    telegram_id = int(admin_id)
                coords.append(FakeCoord())
                seen_ids.add(int(admin_id))
        content = await EquipmentDigestService._build_digest_content(db)
        updated = 0

        for coord in coords:
            tid = int(coord.telegram_id)
            chat_id = tid

            digest_result = await db.execute(
                select(EquipmentAdminDigest).where(EquipmentAdminDigest.telegram_id == tid)
            )
            digest = digest_result.scalar_one_or_none()

            try:
                if digest and digest.message_id:
                    # Редактируем существующее
                    from app.utils.telegram_sender import edit_telegram_message
                    ok = await edit_telegram_message(
                        chat_id=chat_id,
                        message_id=digest.message_id,
                        text=content,
                        silent_fail=True
                    )
                    if ok:
                        updated += 1
                    else:
                        # Сообщение могло быть удалено — отправляем новое
                        msg = await bot.send_message(chat_id=chat_id, text=content, parse_mode="HTML")
                        digest.message_id = msg.message_id
                        digest.chat_id = chat_id
                        await db.commit()
                        updated += 1
                else:
                    # Отправляем новое
                    msg = await bot.send_message(chat_id=chat_id, text=content, parse_mode="HTML")
                    if digest:
                        digest.message_id = msg.message_id
                        digest.chat_id = chat_id
                    else:
                        db.add(EquipmentAdminDigest(
                            telegram_id=tid,
                            chat_id=chat_id,
                            message_id=msg.message_id
                        ))
                    await db.commit()
                    updated += 1
            except Exception as e:
                logger.warning(f"Ошибка обновления дайджеста для {tid}: {e}")

        return updated

    @staticmethod
    async def delete_digest_message_for_request(db: AsyncSession, request_id: UUID) -> int:
        """
        Не удаляем дайджест — обновляем его (убираем заявку из списка).
        Вызываем update_digest_for_coordinators.
        """
        return await EquipmentDigestService.update_digest_for_coordinators(db, None)
