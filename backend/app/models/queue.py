from datetime import date, datetime, time
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, Index, String, Table, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, utcnow
from app.models.discipline import Discipline, Lab
from app.models.user import User


class QueueStatus(StrEnum):
    open = "open"
    closed = "closed"


class EntryStatus(StrEnum):
    waiting = "waiting"
    called = "called"
    testing = "testing"
    reviewing = "reviewing"
    passed = "passed"
    failed = "failed"
    left = "left"


# Запись «активна», пока студент не сдал, не провалил и не вышел.
ACTIVE_STATUSES = (
    EntryStatus.waiting,
    EntryStatus.called,
    EntryStatus.testing,
    EntryStatus.reviewing,
)
IN_PROGRESS_STATUSES = (EntryStatus.called, EntryStatus.testing, EntryStatus.reviewing)
FINAL_STATUSES = (EntryStatus.passed, EntryStatus.failed, EntryStatus.left)

DEFAULT_AGING_K = 0.5


class Queue(Base):
    __tablename__ = "queues"

    id: Mapped[int] = mapped_column(primary_key=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id", ondelete="CASCADE"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    date: Mapped[date]
    starts_at: Mapped[time] = mapped_column(Time())
    ends_at: Mapped[time] = mapped_column(Time())
    status: Mapped[str] = mapped_column(String(20), default=QueueStatus.open)
    # Коэффициент aging k из формулы key = D − k·W (настройка очереди).
    aging_k: Mapped[float] = mapped_column(default=DEFAULT_AGING_K)

    discipline: Mapped[Discipline] = relationship()
    teacher: Mapped[User] = relationship()


entry_labs = Table(
    "entry_labs",
    Base.metadata,
    Column("entry_id", ForeignKey("queue_entries.id", ondelete="CASCADE"), primary_key=True),
    Column("lab_id", ForeignKey("labs.id", ondelete="CASCADE"), primary_key=True),
)


class QueueEntry(Base):
    __tablename__ = "queue_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    queue_id: Mapped[int] = mapped_column(ForeignKey("queues.id", ondelete="CASCADE"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default=EntryStatus.waiting)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    called_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    pinned_position: Mapped[int | None]

    student: Mapped[User] = relationship()
    labs: Mapped[list[Lab]] = relationship(secondary=entry_labs, order_by=Lab.number)

    @property
    def duration_min(self) -> int:
        """D — суммарная ожидаемая длительность выбранных лаб."""
        return sum(lab.expected_minutes for lab in self.labs)


_active = QueueEntry.status.in_([s.value for s in ACTIVE_STATUSES])

# Быстрый пересчёт очереди.
Index("ix_queue_entries_queue_id_status", QueueEntry.queue_id, QueueEntry.status)
# Одна активная запись студента в одной очереди (частичный уникальный индекс).
Index(
    "uq_queue_entries_active_student",
    QueueEntry.queue_id,
    QueueEntry.student_id,
    unique=True,
    postgresql_where=_active,
    sqlite_where=_active,
)
