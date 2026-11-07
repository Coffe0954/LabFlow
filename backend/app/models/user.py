from datetime import datetime
from enum import StrEnum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, utcnow


class UserRole(StrEnum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    group: Mapped[str | None] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20), default=UserRole.student)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
