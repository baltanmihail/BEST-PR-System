"""
Сервис дедлайнов задач — одно обновляемое сообщение-планёрка в день.

Логика:
- Работает с 8:00 до 24:00 МСК
- Каждый час проверяет задачи
- Для каждого пользователя: если нет сообщения за сегодня — отправляет новое,
  если есть — редактирует его (обновляет время, статусы)
- Для VP4PR: отдельная сводка по всем задачам команды
- Отдельные напоминания НЕ отправляются — всё в одном сообщении
- message_id хранятся в БД (таблица bot_message_tracking) для переживания рестартов
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.models.task import Task, TaskStatus, TaskAssignment
from app.models.user import User, UserRole
from app.models.daily_task import DailyTask

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))


class TaskDeadlineService:

    @staticmethod
    async def check_and_send_reminders(db: AsyncSession):
        """Проверить дедлайны и обновить планёрку."""
        now_msk = datetime.now(MSK)

        if now_msk.hour < 8:
            logger.debug("Дедлайн-чек: ещё рано (до 8:00 МСК), пропускаем")
            return

        now_utc = datetime.now(timezone.utc)
        today_str = now_msk.strftime("%Y-%m-%d")

        # Загрузить все активные задачи с назначениями
        query = (
            select(Task)
            .where(
                Task.status.notin_([TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value, 'completed', 'cancelled']),
                Task.due_date.isnot(None),
            )
            .options(
                selectinload(Task.assignments),
                selectinload(Task.stages),
            )
        )
        result = await db.execute(query)
        tasks = result.scalars().all()

        if not tasks:
            return

        # Собрать задачи по пользователям
        user_tasks: Dict[str, list] = {}  # user_id -> [tasks]
        all_overdue = []

        for task in tasks:
            dl = task.due_date
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            diff_hours = (dl - now_utc).total_seconds() / 3600

            is_overdue = diff_hours < 0
            is_soon = 0 <= diff_hours <= 48

            if not is_overdue and not is_soon:
                continue

            if is_overdue:
                all_overdue.append(task)

            assignees = [a for a in (task.assignments or []) if str(getattr(a, 'status', '')) not in ('cancelled', 'completed')]
            if assignees:
                for a in assignees:
                    uid = str(a.user_id)
                    if uid not in user_tasks:
                        user_tasks[uid] = []
                    user_tasks[uid].append(task)
            else:
                if '__unassigned__' not in user_tasks:
                    user_tasks['__unassigned__'] = []
                user_tasks['__unassigned__'].append(task)

        # Загрузить быстрые задачи на сегодня
        daily_query = (
            select(DailyTask)
            .where(DailyTask.date == now_msk.date())
            .options(
                selectinload(DailyTask.creator),
                selectinload(DailyTask.assignee),
            )
        )
        daily_result = await db.execute(daily_query)
        daily_tasks_all = daily_result.scalars().all()

        # Группируем быстрые задачи по assignee
        user_daily: Dict[str, list] = {}
        for dt in daily_tasks_all:
            uid = str(dt.assignee_id)
            if uid not in user_daily:
                user_daily[uid] = []
            user_daily[uid].append(dt)

        # Загрузить пользователей
        all_user_ids_set = set(uid for uid in user_tasks.keys() if uid != '__unassigned__')
        all_user_ids_set.update(user_daily.keys())
        users_map: Dict[str, User] = {}
        if all_user_ids_set:
            from uuid import UUID
            uuids = [UUID(uid) for uid in all_user_ids_set]
            users_result = await db.execute(select(User).where(User.id.in_(uuids)))
            for u in users_result.scalars().all():
                users_map[str(u.id)] = u

        # Отправить/обновить планёрку каждому
        all_uids = set(user_tasks.keys()) | set(user_daily.keys())
        all_uids.discard('__unassigned__')

        for uid in all_uids:
            user = users_map.get(uid)
            if not user or not user.telegram_id or user.telegram_id <= 0:
                continue

            task_list = user_tasks.get(uid, [])
            daily_list = user_daily.get(uid, [])

            if not task_list and not daily_list:
                continue

            msg = TaskDeadlineService._build_daily_message(
                task_list, daily_list, now_utc, now_msk, user.full_name
            )
            await TaskDeadlineService._send_or_update(db, user.telegram_id, today_str, msg)

        # VP4PR сводка
        vp_result = await db.execute(
            select(User).where(User.role.in_([UserRole.VP4PR.value, UserRole.ADMIN.value]), User.is_active == True)
        )
        for vp in vp_result.scalars().all():
            if not vp.telegram_id or vp.telegram_id <= 0:
                continue
            vp_msg = TaskDeadlineService._build_vp4pr_message(
                tasks, all_overdue, daily_tasks_all, now_utc, now_msk
            )
            await TaskDeadlineService._send_or_update(db, vp.telegram_id, f"vp_{today_str}", vp_msg)

    @staticmethod
    def _build_daily_message(
        task_list: list, daily_list: list, now_utc: datetime, now_msk: datetime, user_name: str
    ) -> str:
        """Построить сообщение-планёрку для пользователя."""
        lines_overdue = []
        lines_today = []
        lines_soon = []

        for task in task_list:
            dl = task.due_date
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            diff = dl - now_utc
            hours = diff.total_seconds() / 3600

            dl_msk = dl.astimezone(MSK)
            dl_str = dl_msk.strftime("%d.%m %H:%M")

            if hours < 0:
                overdue_h = abs(hours)
                if overdue_h < 1:
                    ov_str = f"{int(overdue_h * 60)}мин"
                elif overdue_h < 24:
                    ov_str = f"{int(overdue_h)}ч"
                else:
                    ov_str = f"{int(overdue_h / 24)}д {int(overdue_h % 24)}ч"
                lines_overdue.append(f"  🔴 <b>{task.title}</b> — просрочено на {ov_str}")
            elif hours <= 24:
                if hours < 1:
                    left = f"{int(hours * 60)}мин"
                else:
                    left = f"{int(hours)}ч {int((hours % 1) * 60)}мин"
                lines_today.append(f"  🟡 <b>{task.title}</b> — до {dl_str} (осталось {left})")
            else:
                lines_soon.append(f"  🟢 <b>{task.title}</b> — до {dl_str}")

        # Быстрые задачи на день
        lines_daily_pending = []
        lines_daily_done = []
        for dt in daily_list:
            if dt.is_done:
                lines_daily_done.append(f"  ✅ <s>{dt.title}</s>")
            else:
                lines_daily_pending.append(f"  ⬜ {dt.title}")

        time_str = now_msk.strftime("%H:%M")
        msg = f"📋 <b>Планёрка</b> — {now_msk.strftime('%d.%m.%Y')} ({time_str})\n"
        msg += f"Привет, {user_name}!\n\n"

        if lines_overdue:
            msg += f"<b>🚨 Просрочено ({len(lines_overdue)}):</b>\n" + "\n".join(lines_overdue) + "\n\n"
        if lines_today:
            msg += f"<b>⚡ Горящие задачи ({len(lines_today)}):</b>\n" + "\n".join(lines_today) + "\n\n"
        if lines_soon:
            msg += f"<b>📅 Ближайшие ({len(lines_soon)}):</b>\n" + "\n".join(lines_soon) + "\n\n"

        if lines_daily_pending or lines_daily_done:
            total_daily = len(lines_daily_pending) + len(lines_daily_done)
            done_daily = len(lines_daily_done)
            msg += f"<b>📝 Задачи на день ({done_daily}/{total_daily}):</b>\n"
            msg += "\n".join(lines_daily_pending + lines_daily_done) + "\n\n"

        if not lines_overdue and not lines_today and not lines_soon and not lines_daily_pending:
            msg += "✨ Всё чисто, горящих задач нет!\n"

        msg += f"\n<i>Обновлено в {time_str} МСК</i>"
        return msg

    @staticmethod
    def _build_vp4pr_message(
        all_tasks: list, overdue: list, daily_tasks_all: list,
        now_utc: datetime, now_msk: datetime
    ) -> str:
        """Сводка для VP4PR."""
        time_str = now_msk.strftime("%H:%M")
        active_count = len(all_tasks)
        overdue_count = len(overdue)

        type_labels = {"smm": "SMM", "design": "Дизайн", "channel": "Channel", "prfr": "PR-FR", "multitask": "Мульти"}

        msg = f"📊 <b>Сводка VP4PR</b> — {now_msk.strftime('%d.%m.%Y')} ({time_str})\n\n"
        msg += f"Активных задач: <b>{active_count}</b>\n"
        msg += f"Просрочено: <b>{overdue_count}</b>\n\n"

        if overdue:
            msg += "<b>🚨 Просроченные:</b>\n"
            for t in overdue[:15]:
                dl = t.due_date
                if dl.tzinfo is None:
                    dl = dl.replace(tzinfo=timezone.utc)
                ov_h = abs((now_utc - dl).total_seconds() / 3600)
                if ov_h < 1:
                    ov_str = f"{int(ov_h * 60)}мин"
                elif ov_h < 24:
                    ov_str = f"{int(ov_h)}ч {int(ov_h % 1 * 60)}мин"
                else:
                    ov_str = f"{int(ov_h / 24)}д {int(ov_h % 24)}ч"
                task_type = type_labels.get(str(getattr(t, 'type', '')), '')
                type_prefix = f"[{task_type}] " if task_type else ""
                dl_msk = dl.astimezone(MSK)
                msg += f"  🔴 {type_prefix}<b>{t.title}</b> — просрочено на {ov_str} (DL {dl_msk.strftime('%d.%m %H:%M')})\n"
            if len(overdue) > 15:
                msg += f"  ... и ещё {len(overdue) - 15}\n"

        upcoming = []
        for t in all_tasks:
            dl = t.due_date
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            diff_h = (dl - now_utc).total_seconds() / 3600
            if 0 <= diff_h <= 24:
                upcoming.append(t)

        if upcoming:
            msg += f"\n<b>⚡ Ближайшие 24ч ({len(upcoming)}):</b>\n"
            for t in upcoming[:10]:
                dl_msk = t.due_date
                if dl_msk.tzinfo is None:
                    dl_msk = dl_msk.replace(tzinfo=timezone.utc)
                dl_msk = dl_msk.astimezone(MSK)
                task_type = type_labels.get(str(getattr(t, 'type', '')), '')
                type_prefix = f"[{task_type}] " if task_type else ""
                msg += f"  🟡 {type_prefix}<b>{t.title}</b> — {dl_msk.strftime('%d.%m %H:%M')}\n"

        if daily_tasks_all:
            done_count = sum(1 for d in daily_tasks_all if d.is_done)
            total_count = len(daily_tasks_all)
            msg += f"\n<b>📝 Задачи на день команды ({done_count}/{total_count}):</b>\n"
            for dt in daily_tasks_all[:20]:
                assignee_name = dt.assignee.full_name if dt.assignee else "?"
                if dt.is_done:
                    msg += f"  ✅ <s>{dt.title}</s> — {assignee_name}\n"
                else:
                    msg += f"  ⬜ {dt.title} — {assignee_name}\n"
            if len(daily_tasks_all) > 20:
                msg += f"  ... и ещё {len(daily_tasks_all) - 20}\n"

        msg += f"\n<i>Обновлено в {time_str} МСК</i>"
        return msg

    @staticmethod
    async def cleanup_old_messages(db: AsyncSession, keep_days: int = 2):
        """Удалить старые сообщения бота и записи из bot_message_tracking."""
        from app.utils.telegram_sender import delete_telegram_message

        now_msk = datetime.now(MSK)
        cutoff_date = (now_msk - timedelta(days=keep_days)).strftime("%Y-%m-%d")

        try:
            result = await db.execute(text(
                "SELECT telegram_chat_id, message_key, message_id FROM bot_message_tracking"
            ))
            rows = result.fetchall()
        except Exception:
            return

        deleted_keys = []
        for chat_id, key, msg_id in rows:
            date_part = key.replace("vp_", "")
            try:
                datetime.strptime(date_part, "%Y-%m-%d")
            except ValueError:
                continue
            if date_part < cutoff_date:
                try:
                    await delete_telegram_message(chat_id=chat_id, message_id=msg_id, silent_fail=True)
                except Exception:
                    pass
                deleted_keys.append((chat_id, key))

        if deleted_keys:
            for cid, k in deleted_keys:
                try:
                    await db.execute(text(
                        "DELETE FROM bot_message_tracking WHERE telegram_chat_id = :cid AND message_key = :key"
                    ), {"cid": cid, "key": k})
                except Exception:
                    pass
            try:
                await db.commit()
                logger.info(f"Cleaned up {len(deleted_keys)} old bot messages")
            except Exception:
                await db.rollback()

    @staticmethod
    async def _send_or_update(db: AsyncSession, telegram_id: int, key: str, message: str):
        """Отправить новое или отредактировать существующее сообщение.
        
        message_id хранится в БД (bot_message_tracking) для устойчивости к рестартам.
        """
        from app.utils.telegram_sender import send_telegram_message, edit_telegram_message

        existing_msg_id = None
        try:
            result = await db.execute(text(
                "SELECT message_id FROM bot_message_tracking "
                "WHERE telegram_chat_id = :cid AND message_key = :key"
            ), {"cid": telegram_id, "key": key})
            row = result.fetchone()
            if row:
                existing_msg_id = row[0]
        except Exception:
            pass

        if existing_msg_id:
            ok = await edit_telegram_message(
                chat_id=telegram_id,
                message_id=existing_msg_id,
                text=message,
                parse_mode="HTML",
                silent_fail=True,
            )
            if ok:
                logger.debug(f"Edited message {existing_msg_id} for {telegram_id}/{key}")
                return

        result = await send_telegram_message(
            chat_id=telegram_id,
            message=message,
            parse_mode="HTML",
            return_message_id=True,
        )
        if isinstance(result, tuple):
            success, msg_id = result
        else:
            success, msg_id = result, None

        if success and msg_id:
            try:
                if existing_msg_id:
                    await db.execute(text(
                        "UPDATE bot_message_tracking SET message_id = :mid "
                        "WHERE telegram_chat_id = :cid AND message_key = :key"
                    ), {"mid": msg_id, "cid": telegram_id, "key": key})
                else:
                    await db.execute(text(
                        "INSERT INTO bot_message_tracking (telegram_chat_id, message_key, message_id) "
                        "VALUES (:cid, :key, :mid)"
                    ), {"cid": telegram_id, "key": key, "mid": msg_id})
                await db.commit()
            except Exception as e:
                logger.warning(f"Failed to persist message_id: {e}")
                await db.rollback()
