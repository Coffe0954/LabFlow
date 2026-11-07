"""Статистика очереди (преподаватель) и личная статистика студента."""

from datetime import datetime
from statistics import mean

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, StudentUser, TeacherUser
from app.api.queues import ensure_owner
from app.models import (
    IN_PROGRESS_STATUSES,
    Attempt,
    EntryStatus,
    Lab,
    Queue,
    QueueEntry,
)
from app.schemas.testing import LabTiming, MyEntryResult, MyStats, QueueResultRow, QueueStats
from app.services import queue_service as qs

router = APIRouter(tags=["stats"])


def _minutes(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (end - start).total_seconds() / 60


def _avg(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return round(mean(clean), 1) if clean else None


def _lab_timings(entries: list[QueueEntry], labs: list[Lab]) -> list[LabTiming]:
    """Фактическая длительность сдачи каждой лабы.

    Если в записи несколько лаб, время сдачи делится между ними пропорционально
    их ожидаемой длительности.
    """
    shares: dict[int, list[float]] = {lab.id: [] for lab in labs}
    for e in entries:
        service = _minutes(e.called_at, e.finished_at)
        if e.status not in (EntryStatus.passed, EntryStatus.failed) or service is None:
            continue
        if e.duration_min <= 0:
            continue
        for lab in e.labs:
            if lab.id in shares:
                shares[lab.id].append(service * lab.expected_minutes / e.duration_min)
    return [
        LabTiming(
            lab_id=lab.id,
            number=lab.number,
            title=lab.title,
            expected_minutes=lab.expected_minutes,
            actual_avg_min=_avg(list(shares[lab.id])),
            samples=len(shares[lab.id]),
        )
        for lab in labs
    ]


@router.get("/queues/{queue_id}/stats", response_model=QueueStats)
async def queue_stats(queue_id: int, teacher: TeacherUser, db: DbSession) -> QueueStats:
    queue = await qs.get_queue(db, queue_id)
    ensure_owner(queue, teacher)
    entries = list(
        await db.scalars(
            select(QueueEntry)
            .where(QueueEntry.queue_id == queue_id)
            .options(selectinload(QueueEntry.labs), selectinload(QueueEntry.student))
            .order_by(QueueEntry.created_at)
        )
    )
    attempts = list(
        await db.scalars(
            select(Attempt)
            .where(Attempt.entry_id.in_([e.id for e in entries]), Attempt.score.is_not(None))
            .order_by(Attempt.id)
        )
    )
    last_score = {a.entry_id: a.score for a in attempts}
    labs = list(
        await db.scalars(
            select(Lab).where(Lab.discipline_id == queue.discipline_id).order_by(Lab.number)
        )
    )

    def count(*statuses: str) -> int:
        return sum(1 for e in entries if e.status in statuses)

    def service(e: QueueEntry) -> float | None:
        if e.status not in (EntryStatus.passed, EntryStatus.failed):
            return None
        return _minutes(e.called_at, e.finished_at)

    return QueueStats(
        total=len(entries),
        waiting=count(EntryStatus.waiting),
        in_progress=count(*IN_PROGRESS_STATUSES),
        passed=count(EntryStatus.passed),
        failed=count(EntryStatus.failed),
        left=count(EntryStatus.left),
        # Время ожидания — от записи до вызова.
        avg_wait_min=_avg([_minutes(e.created_at, e.called_at) for e in entries]),
        # Время сдачи — от вызова до результата.
        avg_service_min=_avg([service(e) for e in entries]),
        avg_score=_avg([a.score for a in attempts]),
        labs=_lab_timings(entries, labs),
        results=[
            QueueResultRow(
                entry_id=e.id,
                student_name=e.student.full_name,
                group=e.student.group,
                labs=[f"ЛР {lab.number}" for lab in e.labs],
                status=e.status,
                created_at=e.created_at,
                wait_min=_avg([_minutes(e.created_at, e.called_at)]),
                service_min=_avg([service(e)]),
                score=last_score.get(e.id),
            )
            for e in entries
        ],
    )


@router.get("/stats/me", response_model=MyStats)
async def my_stats(student: StudentUser, db: DbSession) -> MyStats:
    entries = list(
        await db.scalars(
            select(QueueEntry)
            .where(QueueEntry.student_id == student.id)
            .options(selectinload(QueueEntry.labs))
            .order_by(QueueEntry.created_at.desc())
        )
    )
    queues = {
        q.id: q
        for q in await db.scalars(
            select(Queue)
            .where(Queue.id.in_({e.queue_id for e in entries}))
            .options(selectinload(Queue.discipline))
        )
    }
    attempts = list(
        await db.scalars(
            select(Attempt)
            .where(Attempt.entry_id.in_([e.id for e in entries]))
            .order_by(Attempt.id)
        )
    )
    last_score: dict[int, float | None] = {}
    for a in attempts:
        if a.score is not None:
            last_score[a.entry_id] = a.score

    results = [
        MyEntryResult(
            entry_id=e.id,
            queue_id=e.queue_id,
            discipline_title=queues[e.queue_id].discipline.title,
            date=queues[e.queue_id].date.isoformat(),
            labs=[f"ЛР {lab.number}. {lab.title}" for lab in e.labs],
            status=e.status,
            wait_min=_avg([_minutes(e.created_at, e.called_at)]),
            score=last_score.get(e.id),
        )
        for e in entries
    ]
    return MyStats(
        entries=results,
        passed_count=sum(1 for e in entries if e.status == EntryStatus.passed),
        attempts_count=sum(1 for a in attempts if a.finished_at is not None),
        avg_score=_avg([a.score for a in attempts]),
        avg_wait_min=_avg([r.wait_min for r in results]),
    )
