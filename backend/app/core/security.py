"""Хэширование паролей (bcrypt) и JWT-токены."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def _pw_bytes(password: str) -> bytes:
    # bcrypt учитывает только первые 72 байта пароля.
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Возвращает id пользователя или None, если токен неверный или истёк."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
