"""
Service for checking task deadlines and sending reminders via Telegram.
Runs as a periodic background task.
"""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.task import Task, TaskStatus, TaskAssignment
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

THRESHOLDS_HOURS = [24, 3, 1]


class TaskDeadlineService:
    _sent_cache: set = set()

    @staticmethod
    async def check_and_send_reminders(db: AsyncSession):
        """Check all active tasks and send deadline reminders."""
        now = datetime.now(timezone.utc)
        window_start = now
        window_end = now + timedelta(hours=25)

        query = (
            select(Task)
            .where(
                Task.due_date.isnot(None),
                Task.status.notin_([TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value, 'completed', 'cancelled']),
                Task.due_date <= window_end,
            )
            .options(
                selectinload(Task.assignments),
            )
        )
        result = await db.execute(query)
        tasks = result.scalars().all()

        overdue_tasks = []

        for task in tasks:
            diff = task.due_date.replace(tzinfo=timezone.utc) - now if task.due_date.tzinfo is None else task.due_date - now
            hours_left = diff.total_seconds() / 3600

            if hours_left < 0:
                overdue_tasks.append(task)

            for threshold in THRESHOLDS_HOURS:
                cache_key = f"{task.id}:{threshold}"
                if cache_key in TaskDeadlineService._sent_cache:
                    continue
                if 0 <= hours_left <= threshold:
                    await TaskDeadlineService._send_reminder(db, task, hours_left)
                    TaskDeadlineService._sent_cache.add(cache_key)
                    break

        if overdue_tasks:
            await TaskDeadlineService._send_overdue_summary(db, overdue_tasks)

    @staticmethod
    async def _send_reminder(db: AsyncSession, task: Task, hours_left: float):
        """Send reminder to assigned users."""
        from app.utils.telegram_sender import send_telegram_message

        if hours_left < 1:
            time_str = f"{int(hours_left * 60)} мин"
            urgency = "🔴"
        elif hours_left < 3:
            time_str = f"{int(hours_left)}ч {int((hours_left % 1) * 60)}мин"
            urgency = "🟡"
        else:
            time_str = f"{int(hours_left)}ч"
            urgency = "🟢"

        msg = (
            f"{urgency} <b>Дедлайн приближается!</b>\n\n"
            f"📋 <b>{task.title}</b>\n"
            f"⏰ До дедлайна: <b>{time_str}</b>\n"
            f"📅 {task.due_date.strftime('%d.%m.%Y %H:%M') if task.due_date else 'N/A'}"
        )

        user_ids = [a.user_id for a in (task.assignments or []) if hasattr(a, 'status') and str(a.status) not in ('cancelled', 'completed')]
        if not user_ids:
            return

        users = await db.execute(select(User).where(User.id.in_(user_ids)))
        for user in users.scalars().all():
            if user.telegram_id and user.telegram_id > 0:
                try:
                    await send_telegram_message(chat_id=user.telegram_id, message=msg, parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"Failed to send deadline reminder to {user.telegram_id}: {e}")

    @staticmethod
    async def _send_overdue_summary(db: AsyncSession, tasks: list):
        """Send overdue tasks summary to VP4PR."""
        from app.utils.telegram_sender import send_telegram_message

        vp4pr_query = select(User).where(User.role == UserRole.VP4PR.value, User.is_active == True)
        result = await db.execute(vp4pr_query)
        vp4pr_users = result.scalars().all()

        if not vp4pr_users:
            return

        lines = []
        for t in tasks[:15]:
            overdue_hours = abs((datetime.now(timezone.utc) - (t.due_date.replace(tzinfo=timezone.utc) if t.due_date.tzinfo is None else t.due_date)).total_seconds() / 3600)
            if overdue_hours < 1:
                ov_str = f"{int(overdue_hours * 60)}мин"
            elif overdue_hours < 24:
                ov_str = f"{int(overdue_hours)}ч"
            else:
                ov_str = f"{int(overdue_hours / 24)}д"
            lines.append(f"• <b>{t.title}</b> — просрочено на {ov_str}")

        msg = f"🚨 <b>Просроченные задачи ({len(tasks)})</b>\n\n" + "\n".join(lines)

        for vp in vp4pr_users:
            if vp.telegram_id and vp.telegram_id > 0:
                try:
                    await send_telegram_message(chat_id=vp.telegram_id, message=msg, parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"Failed to send overdue summary to VP4PR {vp.telegram_id}: {e}")
