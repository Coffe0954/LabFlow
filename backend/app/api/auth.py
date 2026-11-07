from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import AdminUser, CurrentUser, DbSession, conflict, not_found
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User, UserRole
from app.schemas.user import LoginIn, RegisterIn, TokenOut, UserAdminUpdate, UserOut

router = APIRouter(tags=["auth"])


def _token(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.role),
        user=UserOut.model_validate(user),
    )


@router.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, db: DbSession) -> TokenOut:
    """Регистрация. Все новые пользователи — студенты; роль меняет администратор."""
    email = data.email.lower()
    if await db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise conflict("Пользователь с таким email уже есть")
    user = User(
        email=email,
        password_hash=hash_password(data.password),
        full_name=data.full_name.strip(),
        group=data.group.strip() if data.group else None,
        role=UserRole.student,
    )
    db.add(user)
    await db.commit()
    return _token(user)


@router.post("/auth/login", response_model=TokenOut)
async def login(data: LoginIn, db: DbSession) -> TokenOut:
    user = await db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    return _token(user)


@router.get("/auth/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user


# --- Управление пользователями (admin) ---


@router.get("/users", response_model=list[UserOut], tags=["admin"])
async def list_users(_: AdminUser, db: DbSession) -> list[User]:
    return list(await db.scalars(select(User).order_by(User.full_name)))


@router.patch("/users/{user_id}", response_model=UserOut, tags=["admin"])
async def update_user(user_id: int, data: UserAdminUpdate, admin: AdminUser, db: DbSession) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("Пользователь не найден")
    if user.id == admin.id and data.role is not None and data.role != UserRole.admin:
        raise conflict("Нельзя снять роль администратора с самого себя")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    return user
