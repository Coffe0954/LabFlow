"""Попытки прохождения тестов: сроки, завершение, сборка ответов API."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import not_found
from app.db.base import utcnow
from app.models import Attempt, EntryStatus, LabTest, QueueEntry
from app.schemas.testing import (
    AnswerReview,
    AttemptFull,
    AttemptOut,
    AttemptReview,
    QuestionPublic,
)
from app.services.grading import grade, is_correct

# Небольшой запас на сетевые задержки при отправке ответов после таймера.
GRACE = timedelta(seconds=30)


async def get_attempt(db: AsyncSession, attempt_id: int) -> Attempt:
    attempt = await db.scalar(
        select(Attempt)
        .where(Attempt.id == attempt_id)
        .options(
            selectinload(Attempt.test).selectinload(LabTest.questions),
            selectinload(Attempt.answers),
        )
        .execution_options(populate_existing=True)
    )
    if attempt is None:
        raise not_found("Попытка не найдена")
    return attempt


def deadline(attempt: Attempt) -> datetime:
    return attempt.started_at + timedelta(minutes=attempt.test.time_limit_min)


def is_expired(attempt: Attempt, now: datetime | None = None) -> bool:
    return (now or utcnow()) > deadline(attempt) + GRACE


def answers_map(attempt: Attempt) -> dict[int, object]:
    return {a.question_id: a.value for a in attempt.answers}


async def finish_attempt(db: AsyncSession, attempt: Attempt) -> None:
    """Подсчитывает балл, закрывает попытку и переводит запись в «проверку кода»."""
    if attempt.finished_at is not None:
        return
    attempt.finished_at = utcnow()
    attempt.score = grade(attempt.test.questions, answers_map(attempt))
    entry = await db.get(QueueEntry, attempt.entry_id)
    if entry is not None and entry.status == EntryStatus.testing:
        entry.status = EntryStatus.reviewing


def attempt_out(attempt: Attempt) -> AttemptOut:
    return AttemptOut(
        id=attempt.id,
        entry_id=attempt.entry_id,
        test_id=attempt.test_id,
        test_title=attempt.test.title,
        time_limit_min=attempt.test.time_limit_min,
        started_at=attempt.started_at,
        deadline=deadline(attempt),
        finished_at=attempt.finished_at,
        score=attempt.score,
    )


def attempt_full(attempt: Attempt) -> AttemptFull:
    return AttemptFull(
        **attempt_out(attempt).model_dump(),
        questions=[QuestionPublic.model_validate(q) for q in attempt.test.questions],
        answers=answers_map(attempt),
    )


def attempt_review(attempt: Attempt) -> AttemptReview:
    given = answers_map(attempt)
    return AttemptReview(
        **attempt_out(attempt).model_dump(),
        review=[
            AnswerReview(
                question_id=q.id,
                text=q.text,
                kind=q.kind,
                options=q.options,
                correct=q.correct,
                value=given.get(q.id),
                is_correct=is_correct(q.kind, q.correct, given.get(q.id)),
            )
            for q in attempt.test.questions
        ],
    )


async def expire_open_attempts(db: AsyncSession, entry_id: int) -> bool:
    """Закрывает попытки записи, у которых вышло время. True — если что-то закрыли.

    Нужно, чтобы преподаватель увидел результат, даже если студент так и не открыл тест.
    """
    open_ids = list(
        await db.scalars(
            select(Attempt.id).where(Attempt.entry_id == entry_id, Attempt.finished_at.is_(None))
        )
    )
    expired = False
    for attempt_id in open_ids:
        attempt = await get_attempt(db, attempt_id)
        if is_expired(attempt):
            await finish_attempt(db, attempt)
            expired = True
    return expired
