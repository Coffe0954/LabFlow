"""Все модели импортируются здесь, чтобы Alembic видел полную схему."""

from app.models.ad import AdBanner
from app.models.discipline import Discipline, Lab
from app.models.queue import (
    ACTIVE_STATUSES,
    FINAL_STATUSES,
    IN_PROGRESS_STATUSES,
    EntryStatus,
    Queue,
    QueueEntry,
    QueueStatus,
    entry_labs,
)
from app.models.testing import Answer, Attempt, LabTest, Question, QuestionKind
from app.models.user import User, UserRole

__all__ = [
    "ACTIVE_STATUSES",
    "FINAL_STATUSES",
    "IN_PROGRESS_STATUSES",
    "AdBanner",
    "Answer",
    "Attempt",
    "Discipline",
    "EntryStatus",
    "Lab",
    "LabTest",
    "Question",
    "QuestionKind",
    "Queue",
    "QueueEntry",
    "QueueStatus",
    "User",
    "UserRole",
    "entry_labs",
]
