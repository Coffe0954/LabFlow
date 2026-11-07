"""Очереди: список, состояние, создание, закрытие, вызов следующего."""

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, TeacherUser, conflict, forbidden, not_found
from app.db.base import utcnow
from app.models import Discipline, EntryStatus, Queue, User
from app.schemas.queue import (
    EntryPublic,
    QueueCreate,
    QueueOut,
    QueueState,
    QueueStatusName,
    QueueUpdate,
)
from app.services import queue_service as qs

router = APIRouter(tags=["queues"])


def ensure_owner(queue: Queue, user: User) -> None:
    if queue.teacher_id != user.id:
        raise forbidden("Это очередь другого преподавателя")


@router.get("/queues", response_model=list[QueueOut])
async def list_queues(
    user: CurrentUser,
    db: DbSession,
    status: QueueStatusName | None = "open",
    mine: bool = False,
) -> list[QueueOut]:
    """Список очередей. По умолчанию — открытые. mine=true — очереди текущего преподавателя."""
    query = (
        select(Queue)
        .options(selectinload(Queue.discipline), selectinload(Queue.teacher))
        .order_by(Queue.date.desc(), Queue.starts_at)
    )
    if status is not None:
        query = query.where(Queue.status == status)
    if mine:
        query = query.where(Queue.teacher_id == user.id)
    queues = list(await db.scalars(query.limit(200)))
    counts = await qs.waiting_counts(db, [q.id for q in queues])
    return [qs.queue_out(q, counts.get(q.id, 0)) for q in queues]


@router.get("/queues/{queue_id}", response_model=QueueState)
async def get_queue_state(queue_id: int, _: CurrentUser, db: DbSession) -> QueueState:
    """Очередь с порядком и примерным временем ожидания."""
    return await qs.build_state(db, await qs.get_queue(db, queue_id))


@router.post("/queues", response_model=QueueOut, status_code=status.HTTP_201_CREATED)
async def create_queue(data: QueueCreate, teacher: TeacherUser, db: DbSession) -> QueueOut:
    if await db.get(Discipline, data.discipline_id) is None:
        raise not_found("Дисциплина не найдена")
    queue = Queue(**data.model_dump(), teacher_id=teacher.id)
    db.add(queue)
    await db.commit()
    return qs.queue_out(await qs.get_queue(db, queue.id), 0)


@router.patch("/queues/{queue_id}", response_model=QueueOut)
async def update_queue(
    queue_id: int, data: QueueUpdate, teacher: TeacherUser, db: DbSession
) -> QueueOut:
    """Закрыть/открыть очередь или изменить коэффициент aging k."""
    queue = await qs.get_queue(db, queue_id)
    ensure_owner(queue, teacher)
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(queue, field, value)
    await db.commit()
    await qs.publish(db, queue_id)
    counts = await qs.waiting_counts(db, [queue_id])
    return qs.queue_out(queue, counts.get(queue_id, 0))


@router.post("/queues/{queue_id}/call-next", response_model=EntryPublic)
async def call_next(queue_id: int, teacher: TeacherUser, db: DbSession) -> EntryPublic:
    """Вызвать первого по алгоритму. Закрепление вызванного снимается."""
    queue = await qs.get_queue(db, queue_id)
    ensure_owner(queue, teacher)
    ranked = qs.rank_entries(queue, await qs.load_active_entries(db, queue_id), utcnow())
    if not ranked:
        raise conflict("В очереди никого нет")
    entry = ranked[0][0]
    await qs.shift_pins_before_removal(db, queue, entry.id)
    entry.status = EntryStatus.called
    entry.called_at = utcnow()
    entry.pinned_position = None
    await db.commit()
    await qs.publish(db, queue_id)
    return qs.entry_public(entry)
