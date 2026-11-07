"""Общие зависимости: сессия БД, текущий пользователь, проверка ролей."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User, UserRole

DbSession = Annotated[AsyncSession, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется вход")
    user_id = decode_access_token(creds.credentials)
    user = await db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия истекла, войдите снова")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостаточно прав")
        return user

    return checker


StudentUser = Annotated[User, Depends(require_roles(UserRole.student))]
TeacherUser = Annotated[User, Depends(require_roles(UserRole.teacher))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.admin))]


def not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, message)


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def forbidden(message: str = "Недостаточно прав") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, message)
