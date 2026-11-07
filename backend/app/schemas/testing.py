from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.queue import EntryPublic

Kind = Literal["single", "multi", "text"]


class TestCreate(BaseModel):
    lab_id: int
    title: str = Field(min_length=1, max_length=200)
    time_limit_min: int = Field(default=10, ge=1, le=180)


class TestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    time_limit_min: int | None = Field(default=None, ge=1, le=180)


class TestOut(BaseModel):
    id: int
    lab_id: int
    title: str
    time_limit_min: int
    question_count: int


class QuestionIn(BaseModel):
    """correct: single — индекс варианта, multi — список индексов, text — список ответов."""

    text: str = Field(min_length=1, max_length=5000)
    kind: Kind
    options: list[str] = Field(default_factory=list, max_length=20)
    correct: Any

    @model_validator(mode="after")
    def _check(self) -> "QuestionIn":
        n = len(self.options)
        if self.kind == "single":
            if n < 2:
                raise ValueError("Нужно хотя бы 2 варианта ответа")
            if not isinstance(self.correct, int) or not 0 <= self.correct < n:
                raise ValueError("correct — номер правильного варианта (с нуля)")
        elif self.kind == "multi":
            if n < 2:
                raise ValueError("Нужно хотя бы 2 варианта ответа")
            if (
                not isinstance(self.correct, list)
                or not self.correct
                or not all(isinstance(c, int) and 0 <= c < n for c in self.correct)
            ):
                raise ValueError("correct — непустой список номеров правильных вариантов")
            self.correct = sorted(set(self.correct))
        else:
            if isinstance(self.correct, str):
                self.correct = [self.correct]
            if not isinstance(self.correct, list) or not all(
                isinstance(c, str) and c.strip() for c in self.correct
            ):
                raise ValueError("correct — список допустимых текстовых ответов")
            self.options = []
        return self


class QuestionOut(BaseModel):
    """Вопрос для преподавателя — с правильным ответом."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    test_id: int
    text: str
    kind: Kind
    options: list[str]
    correct: Any


class QuestionPublic(BaseModel):
    """Вопрос для студента — без правильного ответа."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    kind: Kind
    options: list[str]


class TestDetail(TestOut):
    questions: list[QuestionOut]


class StartTestIn(BaseModel):
    test_id: int | None = Field(default=None, description="null — первый тест по лабам записи")


class AttemptOut(BaseModel):
    id: int
    entry_id: int
    test_id: int
    test_title: str
    time_limit_min: int
    started_at: datetime
    deadline: datetime
    finished_at: datetime | None
    score: float | None


class AttemptFull(AttemptOut):
    questions: list[QuestionPublic]
    answers: dict[int, Any]


class AnswerIn(BaseModel):
    question_id: int
    value: Any


class AnswersIn(BaseModel):
    answers: list[AnswerIn] = Field(max_length=200)


class AnswerReview(BaseModel):
    question_id: int
    text: str
    kind: Kind
    options: list[str]
    correct: Any
    value: Any
    is_correct: bool


class AttemptReview(AttemptOut):
    """Результат попытки для преподавателя."""

    review: list[AnswerReview]


class TestShort(BaseModel):
    id: int
    lab_id: int
    title: str


class EntryDetail(EntryPublic):
    queue_id: int
    finished_at: datetime | None
    attempts: list[AttemptReview]
    available_tests: list[TestShort]


class LabTiming(BaseModel):
    """Сколько на самом деле длится сдача лабы — помогает точнее задать expected_minutes."""

    lab_id: int
    number: int
    title: str
    expected_minutes: int
    actual_avg_min: float | None
    samples: int


class QueueResultRow(BaseModel):
    """Строка итоговой ведомости очереди (для выгрузки в CSV)."""

    entry_id: int
    student_name: str
    group: str | None
    labs: list[str]
    status: str
    created_at: datetime
    wait_min: float | None
    service_min: float | None
    score: float | None


class QueueStats(BaseModel):
    total: int
    waiting: int
    in_progress: int
    passed: int
    failed: int
    left: int
    avg_wait_min: float | None
    avg_service_min: float | None
    avg_score: float | None
    labs: list[LabTiming]
    results: list[QueueResultRow]


class MyEntryResult(BaseModel):
    entry_id: int
    queue_id: int
    discipline_title: str
    date: str
    labs: list[str]
    status: str
    wait_min: float | None
    score: float | None


class MyStats(BaseModel):
    entries: list[MyEntryResult]
    passed_count: int
    attempts_count: int
    avg_score: float | None
    avg_wait_min: float | None
