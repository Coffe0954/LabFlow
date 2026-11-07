from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.catalog import LabOut

EntryStatusName = Literal["waiting", "called", "testing", "reviewing", "passed", "failed", "left"]
QueueStatusName = Literal["open", "closed"]


class QueueCreate(BaseModel):
    discipline_id: int
    date: date
    starts_at: time
    ends_at: time
    aging_k: float = Field(default=0.5, gt=0, le=10)

    @model_validator(mode="after")
    def _check_times(self) -> "QueueCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("Время окончания должно быть позже начала")
        return self


class QueueUpdate(BaseModel):
    status: QueueStatusName | None = None
    aging_k: float | None = Field(default=None, gt=0, le=10)


class QueueOut(BaseModel):
    id: int
    discipline_id: int
    discipline_title: str
    teacher_id: int
    teacher_name: str
    date: date
    starts_at: time
    ends_at: time
    status: QueueStatusName
    aging_k: float
    waiting_count: int


class EntryPublic(BaseModel):
    """Запись в очереди — только то, что можно показывать всем участникам."""

    id: int
    student_id: int
    student_name: str
    group: str | None
    status: EntryStatusName
    labs: list[LabOut]
    duration_min: int
    position: int | None = None  # только для waiting
    wait_minutes: int | None = None  # только для waiting
    pinned_position: int | None
    created_at: datetime
    called_at: datetime | None


class QueueState(BaseModel):
    queue: QueueOut
    waiting: list[EntryPublic]
    in_progress: list[EntryPublic]
    current_remaining_min: int
    finished_count: int
    updated_at: datetime


class EntryCreate(BaseModel):
    lab_ids: list[int] = Field(min_length=1, max_length=20)


class PositionIn(BaseModel):
    position: int | None = Field(default=None, ge=1, description="null — снять закрепление")


class StatusIn(BaseModel):
    status: Literal["waiting", "called", "reviewing", "passed", "failed", "left"]


class MyActiveEntry(BaseModel):
    """Активная запись студента вместе с очередью — для главной страницы студента."""

    entry: EntryPublic
    queue: QueueOut
