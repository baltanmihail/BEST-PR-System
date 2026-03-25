"""
Daily and weekly task digest sent via Telegram.
"""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.task import Task, TaskStatus, TaskAssignment
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


class TaskDigestService:

    @staticmethod
    async def send_daily_digest(db: AsyncSession):
        """Send daily digest to each user with their active tasks."""
        from app.utils.telegram_sender import send_telegram_message

        now = datetime.now(timezone.utc)
        today_end = now + timedelta(hours=24)

        users_result = await db.execute(
            select(User).where(User.is_active == True, User.telegram_id > 0)
        )
        users = users_result.scalars().all()

        for user in users:
            assignments_result = await db.execute(
                select(TaskAssignment)
                .where(
                    TaskAssignment.user_id == user.id,
                    TaskAssignment.status.notin_(['cancelled', 'completed']),
                )
                .options(selectinload(TaskAssignment.task))
            )
            assignments = assignments_result.scalars().all()

            if not assignments:
                continue

            lines = []
            urgent = 0
            for a in assignments:
                task = a.task
                if not task or task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, 'completed', 'cancelled'):
                    continue
                status_emoji = "🔵"
                if task.due_date:
                    dl = task.due_date if task.due_date.tzinfo else task.due_date.replace(tzinfo=timezone.utc)
                    if dl < now:
                        status_emoji = "🔴"
                        urgent += 1
                    elif dl < today_end:
                        status_emoji = "🟡"
                        urgent += 1
                    due_str = task.due_date.strftime('%d.%m %H:%M')
                    lines.append(f"{status_emoji} <b>{task.title}</b> — до {due_str}")
                else:
                    lines.append(f"{status_emoji} <b>{task.title}</b>")

            if not lines:
                continue

            header = f"📋 <b>Твои задачи на сегодня ({len(lines)})</b>"
            if urgent:
                header += f"\n⚠️ Срочных: {urgent}"
            msg = header + "\n\n" + "\n".join(lines[:20])

            try:
                await send_telegram_message(chat_id=user.telegram_id, message=msg, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Daily digest failed for {user.telegram_id}: {e}")

    @staticmethod
    async def send_weekly_digest(db: AsyncSession):
        """Send weekly digest to VP4PR with full picture."""
        from app.utils.telegram_sender import send_telegram_message

        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        vp_result = await db.execute(
            select(User).where(User.role.in_([UserRole.VP4PR.value, UserRole.ADMIN.value]), User.is_active == True)
        )
        vp_users = vp_result.scalars().all()
        if not vp_users:
            return

        completed_result = await db.execute(
            select(Task).where(
                Task.status.in_([TaskStatus.COMPLETED.value, 'completed']),
                Task.updated_at >= week_ago
            )
        )
        completed = completed_result.scalars().all()

        overdue_result = await db.execute(
            select(Task).where(
                Task.due_date.isnot(None),
                Task.due_date < now,
                Task.status.notin_([TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value, 'completed', 'cancelled']),
            )
        )
        overdue = overdue_result.scalars().all()

        active_result = await db.execute(
            select(Task).where(
                Task.status.notin_([TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value, TaskStatus.DRAFT.value, 'completed', 'cancelled', 'draft']),
            )
        )
        active = active_result.scalars().all()

        msg = (
            f"📊 <b>Еженедельная сводка BEST PR</b>\n\n"
            f"✅ Завершено за неделю: <b>{len(completed)}</b>\n"
            f"🔴 Просрочено: <b>{len(overdue)}</b>\n"
            f"🔵 Активных: <b>{len(active)}</b>\n"
        )

        if overdue:
            msg += "\n<b>Просроченные:</b>\n"
            for t in overdue[:10]:
                msg += f"• {t.title}\n"

        for vp in vp_users:
            if vp.telegram_id and vp.telegram_id > 0:
                try:
                    await send_telegram_message(chat_id=vp.telegram_id, message=msg, parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"Weekly digest failed for VP4PR {vp.telegram_id}: {e}")
