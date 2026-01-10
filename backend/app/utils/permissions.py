"""
Утилиты для проверки прав доступа
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.utils.auth import verify_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    require_active: bool = False
) -> User:
    """
    Получить текущего пользователя из JWT токена
    
    Args:
        require_active: Если True, требует активного пользователя. 
                       Если False, разрешает неактивных (для /auth/me и просмотра профиля)
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    # Проверяем, не удалён ли пользователь
    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deleted",
        )
    
    # Проверяем активность только если требуется
    if require_active and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive. Please wait for moderation approval.",
        )
    
    return user


def require_role(*allowed_roles: UserRole, require_active: bool = True):
    """Декоратор для проверки роли пользователя"""
    async def role_checker(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        current_user = await get_current_user(credentials, db, require_active=require_active)
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join([r.value for r in allowed_roles])}"
            )
        return current_user
    return role_checker


def require_coordinator():
    """Проверка, что пользователь - координатор"""
    return require_role(
        UserRole.COORDINATOR_SMM,
        UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL,
        UserRole.COORDINATOR_PRFR,
        UserRole.VP4PR
    )


def require_vp4pr():
    """Проверка, что пользователь - VP4PR"""
    return require_role(UserRole.VP4PR)


def get_current_user_allow_inactive():
    """Зависимость для получения текущего пользователя без требования активности"""
    async def _get_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        return await get_current_user(credentials, db, require_active=False)
    return _get_user


async def OptionalUser(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Опциональная авторизация - возвращает пользователя если токен есть, иначе None
    
    Используется для endpoints, которые работают и без авторизации
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        if payload is None:
            return None
        
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            return None
        
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if user is None or not user.is_active:
            return None
        
        return user
    except Exception:
        return None
