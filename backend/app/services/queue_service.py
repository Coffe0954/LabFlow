"""Связка БД и алгоритма очереди: загрузка записей, пересчёт, рассылка по WebSocket."""

import math
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import not_found
from app.db.base import utcnow
from app.models import (
    ACTIVE_STATUSES,
    IN_PROGRESS_STATUSES,
    EntryStatus,
    Queue,
    QueueEntry,
)
from app.schemas.catalog import LabOut
from app.schemas.queue import EntryPublic, QueueOut, QueueState
from app.services.queue_engine import QueueItem, RankedItem, rank_queue, remaining_minutes
from app.ws.hub import hub


async def get_queue(db: AsyncSession, queue_id: int) -> Queue:
    queue = await db.scalar(
        select(Queue)
        .where(Queue.id == queue_id)
        .options(selectinload(Queue.discipline), selectinload(Queue.teacher))
    )
    if queue is None:
        raise not_found("Очередь не найдена")
    return queue


async def get_entry(db: AsyncSession, entry_id: int) -> QueueEntry:
    entry = await db.scalar(
        select(QueueEntry)
        .where(QueueEntry.id == entry_id)
        .options(selectinload(QueueEntry.labs), selectinload(QueueEntry.student))
    )
    if entry is None:
        raise not_found("Запись не найдена")
    return entry


async def load_active_entries(db: AsyncSession, queue_id: int) -> list[QueueEntry]:
    rows = await db.scalars(
        select(QueueEntry)
        .where(
            QueueEntry.queue_id == queue_id,
            QueueEntry.status.in_([s.value for s in ACTIVE_STATUSES]),
        )
        .options(selectinload(QueueEntry.labs), selectinload(QueueEntry.student))
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def waiting_counts(db: AsyncSession, queue_ids: list[int]) -> dict[int, int]:
    if not queue_ids:
        return {}
    rows = await db.execute(
        select(QueueEntry.queue_id, func.count())
        .where(QueueEntry.queue_id.in_(queue_ids), QueueEntry.status == EntryStatus.waiting)
        .group_by(QueueEntry.queue_id)
    )
    return {qid: cnt for qid, cnt in rows.all()}


def queue_out(queue: Queue, waiting_count: int) -> QueueOut:
    return QueueOut(
        id=queue.id,
        discipline_id=queue.discipline_id,
        discipline_title=queue.discipline.title,
        teacher_id=queue.teacher_id,
        teacher_name=queue.teacher.full_name,
        date=queue.date,
        starts_at=queue.starts_at,
        ends_at=queue.ends_at,
        status=queue.status,
        aging_k=queue.aging_k,
        waiting_count=waiting_count,
    )


def entry_public(
    entry: QueueEntry, position: int | None = None, wait_minutes: float | None = None
) -> EntryPublic:
    return EntryPublic(
        id=entry.id,
        student_id=entry.student_id,
        student_name=entry.student.full_name,
        group=entry.student.group,
        status=entry.status,
        labs=[LabOut.model_validate(lab) for lab in entry.labs],
        duration_min=entry.duration_min,
        position=position,
        wait_minutes=math.ceil(wait_minutes) if wait_minutes is not None else None,
        pinned_position=entry.pinned_position,
        created_at=entry.created_at,
        called_at=entry.called_at,
    )


def current_remaining(entries: list[QueueEntry], now: datetime) -> float:
    """Остаток времени у текущего сдающего. Если сдают несколько — берём наибольший."""
    in_progress = [e for e in entries if e.status in IN_PROGRESS_STATUSES]
    return max(
        (remaining_minutes(e.duration_min, e.called_at, now) for e in in_progress), default=0.0
    )


def rank_entries(
    queue: Queue, entries: list[QueueEntry], now: datetime
) -> list[tuple[QueueEntry, RankedItem]]:
    """Запускает алгоритм для записей в статусе waiting."""
    waiting = {e.id: e for e in entries if e.status == EntryStatus.waiting}
    items = [
        QueueItem(e.id, e.created_at, e.duration_min, e.pinned_position) for e in waiting.values()
    ]
    ranked = rank_queue(items, now, queue.aging_k, current_remaining(entries, now))
    return [(waiting[r.item.id], r) for r in ranked]


async def build_state(db: AsyncSession, queue: Queue, now: datetime | None = None) -> QueueState:
    now = now or utcnow()
    entries = await load_active_entries(db, queue.id)
    ranked = rank_entries(queue, entries, now)
    finished = await db.scalar(
        select(func.count()).where(
            QueueEntry.queue_id == queue.id,
            QueueEntry.status.in_([EntryStatus.passed, EntryStatus.failed]),
        )
    )
    in_progress = sorted(
        (e for e in entries if e.status in IN_PROGRESS_STATUSES),
        key=lambda e: e.called_at or e.created_at,
    )
    return QueueState(
        queue=queue_out(queue, len(ranked)),
        waiting=[entry_public(e, r.position, r.wait_minutes) for e, r in ranked],
        in_progress=[entry_public(e) for e in in_progress],
        current_remaining_min=math.ceil(current_remaining(entries, now)),
        finished_count=finished or 0,
        updated_at=now,
    )


async def shift_pins_before_removal(db: AsyncSession, queue: Queue, removed_id: int) -> None:
    """Запись уходит из ожидания — закреплённые ниже неё поднимаются на одно место.

    Так закреплённый студент продвигается вместе с очередью и не застревает навсегда.
    Вызывать ДО смены статуса уходящей записи.
    """
    ranked = rank_entries(queue, await load_active_entries(db, queue.id), utcnow())
    removed_pos = next((r.position for e, r in ranked if e.id == removed_id), None)
    if removed_pos is None:
        return
    for entry, r in ranked:
        if entry.pinned_position is not None and r.position > removed_pos:
            entry.pinned_position = r.position - 1


async def publish(db: AsyncSession, queue_id: int) -> None:
    """Пересчитывает очередь и рассылает новое состояние подписчикам."""
    if hub.subscribers(queue_id) == 0:
        return
    queue = await get_queue(db, queue_id)
    state = await build_state(db, queue)
    await hub.broadcast(queue_id, {"type": "queue_state", "data": state.model_dump(mode="json")})
