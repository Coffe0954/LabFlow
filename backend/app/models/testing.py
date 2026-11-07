"""Тесты по лабам, вопросы, попытки и ответы.

Классы названы LabTest/Attempt, а не Test*, чтобы pytest не принимал их за тесты.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, UTCDateTime, utcnow
from app.models.discipline import Lab


class QuestionKind(StrEnum):
    single = "single"
    multi = "multi"
    text = "text"


class LabTest(Base):
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    time_limit_min: Mapped[int]

    lab: Mapped[Lab] = relationship()
    questions: Mapped[list["Question"]] = relationship(
        back_populates="test", order_by="Question.id", cascade="all, delete-orphan"
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text())
    kind: Mapped[str] = mapped_column(String(20))
    # Варианты ответа (для single/multi) — список строк.
    options: Mapped[list[str]] = mapped_column(JSONType, default=list)
    # single: индекс варианта; multi: список индексов; text: список допустимых ответов.
    correct: Mapped[Any] = mapped_column(JSONType)

    test: Mapped[LabTest] = relationship(back_populates="questions")


class Attempt(Base):
    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("queue_entries.id", ondelete="CASCADE"))
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    score: Mapped[float | None]  # процент правильных ответов, 0..100

    test: Mapped[LabTest] = relationship()
    answers: Mapped[list["Answer"]] = relationship(cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("test_attempts.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    value: Mapped[Any] = mapped_column(JSONType)
