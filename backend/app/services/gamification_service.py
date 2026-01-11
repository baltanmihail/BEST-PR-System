"""
Сервис геймификации: начисление баллов, уровни, ачивки
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timedelta, date, timezone

from app.models.user import User, UserRole
from app.models.task import Task, TaskStatus, TaskPriority, TaskType
from app.models.gamification import PointsLog, Achievement
from app.models.task import TaskAssignment, AssignmentStatus


class GamificationService:
    """Сервис для работы с геймификацией"""
    
    # Константы для начисления баллов
    POINTS_TAKE_TASK_NORMAL = 50
    POINTS_TAKE_TASK_PRIORITY = 100
    POINTS_TAKE_TASK_URGENT = 80  # <48 часов до дедлайна
    POINTS_COMPLETE_ON_TIME = 200
    POINTS_EARLY_COMPLETION_PER_DAY = 30
    POINTS_QUALITY_5 = 150
    POINTS_QUALITY_4 = 100
    POINTS_QUALITY_3 = 50
    POINTS_COMPLEXITY_MULTIPLIER = 20
    POINTS_EQUIPMENT_GOOD = 50
    POINTS_EQUIPMENT_DAMAGE = -100
    POINTS_HELP_OTHERS = 25
    POINTS_CHAT_ACTIVITY_MAX = 20  # максимум в день
    
    # Уровни пользователей
    LEVEL_THRESHOLDS = {
        1: (0, 100),      # Новичок
        2: (101, 500),    # Активный
        3: (501, 1500),   # Опытный
        4: (1501, 3000),  # Эксперт
        5: (3001, None),  # Мастер
    }
    
    @staticmethod
    async def calculate_user_level(points: int) -> int:
        """Вычислить уровень пользователя на основе баллов"""
        for level, (min_points, max_points) in GamificationService.LEVEL_THRESHOLDS.items():
            if max_points is None:
                if points >= min_points:
                    return level
            else:
                if min_points <= points <= max_points:
                    return level
        return 1
    
    @staticmethod
    async def calculate_user_role(points: int) -> UserRole:
        """Вычислить роль пользователя на основе баллов"""
        if points < 101:
            return UserRole.NOVICE
        elif points < 501:
            return UserRole.PARTICIPANT
        else:
            return UserRole.ACTIVE_PARTICIPANT
    
    @staticmethod
    async def award_points(
        db: AsyncSession,
        user_id: UUID,
        points: int,
        reason: str,
        task_id: Optional[UUID] = None
    ) -> PointsLog:
        """Начислить баллы пользователю"""
        # Создаём запись в логе
        points_log = PointsLog(
            user_id=user_id,
            task_id=task_id,
            points=points,
            reason=reason
        )
        db.add(points_log)
        
        # Обновляем баллы пользователя
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one()
        
        user.points += points
        
        # Пересчитываем уровень и роль
        user.level = await GamificationService.calculate_user_level(user.points)
        if user.role in [UserRole.NOVICE, UserRole.PARTICIPANT, UserRole.ACTIVE_PARTICIPANT]:
            user.role = await GamificationService.calculate_user_role(user.points)
        
        await db.commit()
        await db.refresh(points_log)
        
        return points_log
    
    @staticmethod
    async def award_task_taken_points(
        db: AsyncSession,
        user_id: UUID,
        task: Task
    ) -> PointsLog:
        """Начислить баллы за взятие задачи"""
        points = GamificationService.POINTS_TAKE_TASK_NORMAL
        
        # Проверяем приоритет
        if task.priority == TaskPriority.CRITICAL:
            points = GamificationService.POINTS_TAKE_TASK_PRIORITY
        elif task.priority == TaskPriority.HIGH:
            points = GamificationService.POINTS_TAKE_TASK_PRIORITY
        
        # Проверяем, горящая ли задача (<48 часов до дедлайна)
        if task.due_date:
            now = datetime.now(task.due_date.tzinfo) if task.due_date.tzinfo else datetime.now(timezone.utc)
            time_until_deadline = task.due_date - now
            if time_until_deadline < timedelta(hours=48):
                points = GamificationService.POINTS_TAKE_TASK_URGENT
        
        return await GamificationService.award_points(
            db=db,
            user_id=user_id,
            points=points,
            reason="task_taken",
            task_id=task.id
        )
    
    @staticmethod
    async def award_task_completed_points(
        db: AsyncSession,
        user_id: UUID,
        task: Task,
        assignment: TaskAssignment,
        completed_at: datetime
    ) -> List[PointsLog]:
        """Начислить баллы за выполнение задачи"""
        logs = []
        
        # Базовые баллы за выполнение в срок
        if task.due_date and completed_at <= task.due_date:
            log = await GamificationService.award_points(
                db=db,
                user_id=user_id,
                points=GamificationService.POINTS_COMPLETE_ON_TIME,
                reason="task_completed_on_time",
                task_id=task.id
            )
            logs.append(log)
            
            # Бонус за досрочное выполнение
            if completed_at < task.due_date:
                days_early = (task.due_date - completed_at).days
                early_bonus = days_early * GamificationService.POINTS_EARLY_COMPLETION_PER_DAY
                if early_bonus > 0:
                    log = await GamificationService.award_points(
                        db=db,
                        user_id=user_id,
                        points=early_bonus,
                        reason="early_completion",
                        task_id=task.id
                    )
                    logs.append(log)
        
        # Баллы за качество (если координатор поставил оценку)
        if assignment.rating:
            quality_points = 0
            if assignment.rating == 5:
                quality_points = GamificationService.POINTS_QUALITY_5
            elif assignment.rating == 4:
                quality_points = GamificationService.POINTS_QUALITY_4
            elif assignment.rating == 3:
                quality_points = GamificationService.POINTS_QUALITY_3
            
            if quality_points > 0:
                log = await GamificationService.award_points(
                    db=db,
                    user_id=user_id,
                    points=quality_points,
                    reason="quality_bonus",
                    task_id=task.id
                )
                logs.append(log)
        
        # Баллы за сложность (если есть поле сложности в задаче)
        # TODO: добавить поле complexity в модель Task
        
        return logs
    
    @staticmethod
    async def check_and_award_achievements(
        db: AsyncSession,
        user_id: UUID,
        task: Optional[Task] = None
    ) -> List[Achievement]:
        """Проверить и начислить ачивки"""
        new_achievements = []
        
        # Получаем пользователя
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one()
        
        # Получаем уже полученные ачивки
        achievements_query = select(Achievement).where(Achievement.user_id == user_id)
        achievements_result = await db.execute(achievements_query)
        existing_achievements = {a.achievement_type for a in achievements_result.scalars().all()}
        
        # 1. Первая кровь - первая взятая задача
        if "first_task" not in existing_achievements:
            tasks_query = select(TaskAssignment).where(
                and_(
                    TaskAssignment.user_id == user_id,
                    TaskAssignment.status == AssignmentStatus.COMPLETED.value
                )
            )
            tasks_result = await db.execute(tasks_query)
            completed_tasks = tasks_result.scalars().all()
            
            if len(completed_tasks) >= 1:
                achievement = Achievement(
                    user_id=user_id,
                    achievement_type="first_task"
                )
                db.add(achievement)
                new_achievements.append(achievement)
        
        # 2. Скорострел - 3 задачи за неделю
        if "speedster" not in existing_achievements:
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            tasks_query = select(TaskAssignment).where(
                and_(
                    TaskAssignment.user_id == user_id,
                    TaskAssignment.status == AssignmentStatus.COMPLETED.value,
                    TaskAssignment.completed_at >= week_ago
                )
            )
            tasks_result = await db.execute(tasks_query)
            recent_tasks = tasks_result.scalars().all()
            
            if len(recent_tasks) >= 3:
                achievement = Achievement(
                    user_id=user_id,
                    achievement_type="speedster"
                )
                db.add(achievement)
                new_achievements.append(achievement)
        
        # 3. Надёжный - все задачи в срок за месяц
        if "reliable" not in existing_achievements:
            month_ago = datetime.now(timezone.utc) - timedelta(days=30)
            tasks_query = select(TaskAssignment).join(Task).where(
                and_(
                    TaskAssignment.user_id == user_id,
                    TaskAssignment.status == AssignmentStatus.COMPLETED.value,
                    TaskAssignment.completed_at >= month_ago,
                    Task.due_date.isnot(None),
                    TaskAssignment.completed_at <= Task.due_date
                )
            )
            tasks_result = await db.execute(tasks_query)
            on_time_tasks = tasks_result.scalars().all()
            
            # Проверяем, что все задачи за месяц выполнены в срок
            all_tasks_query = select(TaskAssignment).join(Task).where(
                and_(
                    TaskAssignment.user_id == user_id,
                    TaskAssignment.status == AssignmentStatus.COMPLETED.value,
                    TaskAssignment.completed_at >= month_ago,
                    Task.due_date.isnot(None)
                )
            )
            all_tasks_result = await db.execute(all_tasks_query)
            all_tasks = all_tasks_result.scalars().all()
            
            if len(all_tasks) > 0 and len(on_time_tasks) == len(all_tasks):
                achievement = Achievement(
                    user_id=user_id,
                    achievement_type="reliable"
                )
                db.add(achievement)
                new_achievements.append(achievement)
        
        # 4. Режиссёр - 5 выполненных задач Channel
        if "director" not in existing_achievements:
            tasks_query = select(TaskAssignment).join(Task).where(
                and_(
                    TaskAssignment.user_id == user_id,
                    TaskAssignment.status == AssignmentStatus.COMPLETED.value,
                    Task.type == TaskType.CHANNEL
                )
            )
            tasks_result = await db.execute(tasks_query)
            channel_tasks = tasks_result.scalars().all()
            
            if len(channel_tasks) >= 5:
                achievement = Achievement(
                    user_id=user_id,
                    achievement_type="director"
                )
                db.add(achievement)
                new_achievements.append(achievement)
        
        # 5. Дизайнер - 5 выполненных задач Design
        if "designer" not in existing_achievements:
            tasks_query = select(TaskAssignment).join(Task).where(
                and_(
                    TaskAssignment.user_id == user_id,
                    TaskAssignment.status == AssignmentStatus.COMPLETED.value,
                    Task.type == TaskType.DESIGN
                )
            )
            tasks_result = await db.execute(tasks_query)
            design_tasks = tasks_result.scalars().all()
            
            if len(design_tasks) >= 5:
                achievement = Achievement(
                    user_id=user_id,
                    achievement_type="designer"
                )
                db.add(achievement)
                new_achievements.append(achievement)
        
        # 6. SMM-гур - 5 выполненных задач SMM
        if "smm_guru" not in existing_achievements:
            tasks_query = select(TaskAssignment).join(Task).where(
                and_(
                    TaskAssignment.user_id == user_id,
                    TaskAssignment.status == AssignmentStatus.COMPLETED.value,
                    Task.type == TaskType.SMM
                )
            )
            tasks_result = await db.execute(tasks_query)
            smm_tasks = tasks_result.scalars().all()
            
            if len(smm_tasks) >= 5:
                achievement = Achievement(
                    user_id=user_id,
                    achievement_type="smm_guru"
                )
                db.add(achievement)
                new_achievements.append(achievement)
        
        # 7. Неудержимый - 30-дневный стрик активности
        if "unstoppable" not in existing_achievements:
            # Проверяем последние 30 дней активности
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            
            # Проверяем, что пользователь был активен каждый день
            activity_query = select(func.date(TaskAssignment.completed_at)).where(
                and_(
                    TaskAssignment.user_id == user_id,
                    TaskAssignment.completed_at >= thirty_days_ago
                )
            ).distinct()
            activity_result = await db.execute(activity_query)
            active_days = len(activity_result.scalars().all())
            
            if active_days >= 30:
                achievement = Achievement(
                    user_id=user_id,
                    achievement_type="unstoppable"
                )
                db.add(achievement)
                new_achievements.append(achievement)
        
        if new_achievements:
            await db.commit()
            for achievement in new_achievements:
                await db.refresh(achievement)
        
        return new_achievements
    
    @staticmethod
    async def get_user_stats(
        db: AsyncSession,
        user_id: UUID
    ) -> Dict:
        """Получить статистику пользователя"""
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        
        # Количество выполненных задач
        # Используем .value для корректного сравнения с PostgreSQL ENUM (lowercase)
        completed_query = select(func.count(TaskAssignment.id)).where(
            and_(
                TaskAssignment.user_id == user_id,
                TaskAssignment.status == AssignmentStatus.COMPLETED.value
            )
        )
        completed_result = await db.execute(completed_query)
        completed_tasks = completed_result.scalar_one() or 0
        
        # Количество активных задач
        active_query = select(func.count(TaskAssignment.id)).where(
            and_(
                TaskAssignment.user_id == user_id,
                TaskAssignment.status.in_([
                    AssignmentStatus.ASSIGNED.value,
                    AssignmentStatus.IN_PROGRESS.value
                ])
            )
        )
        active_result = await db.execute(active_query)
        active_tasks = active_result.scalar_one() or 0
        
        # Количество ачивок
        achievements_query = select(func.count(Achievement.id)).where(
            Achievement.user_id == user_id
        )
        achievements_result = await db.execute(achievements_query)
        achievements_count = achievements_result.scalar_one() or 0
        
        # История баллов (последние 10)
        points_log_query = select(PointsLog).where(
            PointsLog.user_id == user_id
        ).order_by(PointsLog.awarded_at.desc()).limit(10)
        points_log_result = await db.execute(points_log_query)
        recent_points = points_log_result.scalars().all()
        
        # Вычисляем очки для следующего уровня
        current_level = user.level
        current_points = user.points
        
        # Находим порог следующего уровня
        next_level_threshold = None
        current_level_min = 0
        for level, (min_points, max_points) in GamificationService.LEVEL_THRESHOLDS.items():
            if level == current_level:
                current_level_min = min_points
                if max_points is not None:
                    next_level_threshold = max_points + 1
                else:
                    # Максимальный уровень
                    next_level_threshold = None
                break
        
        # Очки от начала текущего уровня
        current_level_points = current_points - current_level_min
        
        # Очки до следующего уровня
        if next_level_threshold is not None:
            points_to_next = next_level_threshold - current_points
        else:
            points_to_next = 0
        
        return {
            "user_id": str(user_id),
            "points": user.points,
            "level": user.level,
            "role": user.role.value,
            "completed_tasks": completed_tasks,
            "active_tasks": active_tasks,
            "achievements_count": achievements_count,
            "next_level_points": next_level_threshold or 0,
            "current_level_points": current_level_points,
            "points_to_next": points_to_next,
            "recent_points": [
                {
                    "points": log.points,
                    "reason": log.reason,
                    "awarded_at": log.awarded_at.isoformat()
                }
                for log in recent_points
            ]
        }
    
    @staticmethod
    async def get_leaderboard(
        db: AsyncSession,
        limit: int = 10,
        exclude_roles: Optional[List[UserRole]] = None
    ) -> List[Dict]:
        """Получить рейтинг пользователей"""
        if exclude_roles is None:
            exclude_roles = [
                UserRole.COORDINATOR_SMM,
                UserRole.COORDINATOR_DESIGN,
                UserRole.COORDINATOR_CHANNEL,
                UserRole.COORDINATOR_PRFR,
                UserRole.VP4PR
            ]
        
        query = select(
            User.id,
            User.telegram_id,
            User.full_name,
            User.points,
            User.level,
            func.count(TaskAssignment.id).filter(
                TaskAssignment.status == AssignmentStatus.COMPLETED.value
            ).label("completed_tasks")
        ).outerjoin(
            TaskAssignment, User.id == TaskAssignment.user_id
        ).where(
            ~User.role.in_(exclude_roles)
        ).group_by(
            User.id
        ).order_by(
            User.points.desc()
        ).limit(limit)
        
        result = await db.execute(query)
        rows = result.all()
        
        leaderboard = []
        for rank, row in enumerate(rows, start=1):
            # Используем username из User, если есть, иначе из telegram_id
            username = None
            try:
                # Пытаемся получить username из User объекта (если он был загружен)
                user_query = select(User).where(User.id == row.id)
                user_result = await db.execute(user_query)
                user_obj = user_result.scalar_one_or_none()
                if user_obj and user_obj.username:
                    username = user_obj.username
            except:
                pass
            
            leaderboard.append({
                "rank": rank,
                "user_id": str(row.id),
                "name": row.full_name,  # Для совместимости с фронтендом
                "username": username,
                "telegram_id": row.telegram_id,
                "full_name": row.full_name,
                "points": row.points,
                "level": row.level,
                "completed_tasks": row.completed_tasks or 0
            })
        
        return leaderboard
