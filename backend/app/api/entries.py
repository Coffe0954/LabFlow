"""Записи в очереди: запись, выход, перетаскивание, статусы, запуск теста."""

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import (
    CurrentUser,
    DbSession,
    StudentUser,
    TeacherUser,
    conflict,
    forbidden,
    not_found,
)
from app.api.queues import ensure_owner
from app.db.base import utcnow
from app.models import (
    ACTIVE_STATUSES,
    FINAL_STATUSES,
    Attempt,
    EntryStatus,
    Lab,
    LabTest,
    QueueEntry,
    QueueStatus,
    UserRole,
)
from app.schemas.queue import EntryCreate, EntryPublic, MyActiveEntry, PositionIn, StatusIn
from app.schemas.testing import AttemptOut, EntryDetail, StartTestIn, TestShort
from app.services import queue_service as qs
from app.services import testing_service as ts

router = APIRouter(tags=["entries"])

# Какие переходы статусов разрешены преподавателю через PATCH /entries/{id}/status.
# В testing запись переводится только через POST /entries/{id}/test/start.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    EntryStatus.waiting: {EntryStatus.called, EntryStatus.left},
    EntryStatus.called: {
        EntryStatus.waiting,  # студента нет на месте — вернуть в очередь
        EntryStatus.reviewing,
        EntryStatus.passed,
        EntryStatus.failed,
        EntryStatus.left,
    },
    EntryStatus.testing: {
        EntryStatus.reviewing,
        EntryStatus.passed,
        EntryStatus.failed,
        EntryStatus.left,
    },
    EntryStatus.reviewing: {EntryStatus.passed, EntryStatus.failed, EntryStatus.left},
}


async def _finish_open_attempts(db: DbSession, entry_id: int) -> None:
    open_ids = await db.scalars(
        select(Attempt.id).where(Attempt.entry_id == entry_id, Attempt.finished_at.is_(None))
    )
    for attempt_id in list(open_ids):
        await ts.finish_attempt(db, await ts.get_attempt(db, attempt_id))


async def _apply_status(db: DbSession, entry: QueueEntry, new_status: str) -> None:
    queue = await qs.get_queue(db, entry.queue_id)
    now = utcnow()
    if entry.status == EntryStatus.waiting and new_status != EntryStatus.waiting:
        await qs.shift_pins_before_removal(db, queue, entry.id)
    if entry.status == EntryStatus.testing:
        await _finish_open_attempts(db, entry.id)
    if new_status == EntryStatus.called:
        entry.called_at = now
        entry.pinned_position = None
    elif new_status == EntryStatus.waiting:
        # Возврат в очередь: накопленное ожидание (created_at) сохраняется.
        entry.called_at = None
    if new_status in FINAL_STATUSES:
        entry.finished_at = now
    entry.status = new_status


@router.post(
    "/queues/{queue_id}/entries", response_model=EntryPublic, status_code=status.HTTP_201_CREATED
)
async def join_queue(
    queue_id: int, data: EntryCreate, student: StudentUser, db: DbSession
) -> EntryPublic:
    """Записаться в очередь с выбранными лабами."""
    queue = await qs.get_queue(db, queue_id)
    if queue.status != QueueStatus.open:
        raise conflict("Очередь закрыта")
    lab_ids = set(data.lab_ids)
    labs = list(
        await db.scalars(
            select(Lab).where(Lab.id.in_(lab_ids), Lab.discipline_id == queue.discipline_id)
        )
    )
    if len(labs) != len(lab_ids):
        raise not_found("Лаба не найдена в дисциплине этой очереди")
    existing = await db.scalar(
        select(QueueEntry.id).where(
            QueueEntry.queue_id == queue_id,
            QueueEntry.student_id == student.id,
            QueueEntry.status.in_([s.value for s in ACTIVE_STATUSES]),
        )
    )
    if existing is not None:
        raise conflict("Вы уже записаны в эту очередь")

    entry = QueueEntry(queue_id=queue_id, student_id=student.id, labs=labs)
    db.add(entry)
    try:
        await db.commit()
    except IntegrityError as exc:  # одновременная двойная запись
        await db.rollback()
        raise conflict("Вы уже записаны в эту очередь") from exc
    await qs.publish(db, queue_id)
    state = await qs.build_state(db, queue)
    mine = next((e for e in state.waiting if e.id == entry.id), None)
    return mine or qs.entry_public(await qs.get_entry(db, entry.id))


@router.get("/entries/me", response_model=list[MyActiveEntry])
async def my_active_entries(student: StudentUser, db: DbSession) -> list[MyActiveEntry]:
    """Очереди, в которых студент сейчас стоит, с его местом и временем ожидания."""
    queue_ids = set(
        await db.scalars(
            select(QueueEntry.queue_id).where(
                QueueEntry.student_id == student.id,
                QueueEntry.status.in_([s.value for s in ACTIVE_STATUSES]),
            )
        )
    )
    result: list[MyActiveEntry] = []
    for queue_id in sorted(queue_ids):
        state = await qs.build_state(db, await qs.get_queue(db, queue_id))
        mine = next(
            (e for e in [*state.waiting, *state.in_progress] if e.student_id == student.id), None
        )
        if mine is not None:
            result.append(MyActiveEntry(entry=mine, queue=state.queue))
    return result


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def leave_queue(entry_id: int, user: CurrentUser, db: DbSession) -> Response:
    """Выйти из очереди (студент — свою запись, преподаватель — в своей очереди)."""
    entry = await qs.get_entry(db, entry_id)
    if user.role == UserRole.student:
        if entry.student_id != user.id:
            raise forbidden("Это не ваша запись")
    elif user.role == UserRole.teacher:
        ensure_owner(await qs.get_queue(db, entry.queue_id), user)
    else:
        raise forbidden()
    if entry.status not in ACTIVE_STATUSES:
        raise conflict("Запись уже не активна")
    await _apply_status(db, entry, EntryStatus.left)
    await db.commit()
    await qs.publish(db, entry.queue_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/entries/{entry_id}", response_model=EntryDetail)
async def get_entry_detail(entry_id: int, user: CurrentUser, db: DbSession) -> EntryDetail:
    """Карточка студента: лабы, тесты, результаты."""
    entry = await qs.get_entry(db, entry_id)
    is_teacher = user.role == UserRole.teacher
    if is_teacher:
        ensure_owner(await qs.get_queue(db, entry.queue_id), user)
    elif entry.student_id != user.id:
        raise forbidden("Это не ваша запись")

    if await ts.expire_open_attempts(db, entry.id):
        await db.commit()
        await qs.publish(db, entry.queue_id)
        entry = await qs.get_entry(db, entry_id)

    attempt_ids = await db.scalars(
        select(Attempt.id).where(Attempt.entry_id == entry.id).order_by(Attempt.id)
    )
    attempts = []
    for attempt_id in list(attempt_ids):
        review = ts.attempt_review(await ts.get_attempt(db, attempt_id))
        if not is_teacher:
            review.review = []  # студенту не показываем правильные ответы
        attempts.append(review)

    tests: list[TestShort] = []
    if is_teacher:
        rows = await db.scalars(
            select(LabTest)
            .where(LabTest.lab_id.in_([lab.id for lab in entry.labs]))
            .order_by(LabTest.lab_id, LabTest.id)
        )
        tests = [TestShort(id=t.id, lab_id=t.lab_id, title=t.title) for t in rows]

    return EntryDetail(
        **qs.entry_public(entry).model_dump(),
        queue_id=entry.queue_id,
        finished_at=entry.finished_at,
        attempts=attempts,
        available_tests=tests,
    )


@router.patch("/entries/{entry_id}/position", response_model=EntryPublic)
async def pin_position(
    entry_id: int, data: PositionIn, teacher: TeacherUser, db: DbSession
) -> EntryPublic:
    """Закрепить запись на месте (drag-and-drop). position=null снимает закрепление."""
    entry = await qs.get_entry(db, entry_id)
    queue = await qs.get_queue(db, entry.queue_id)
    ensure_owner(queue, teacher)
    if entry.status != EntryStatus.waiting:
        raise conflict("Перемещать можно только ожидающих")
    entry.pinned_position = data.position
    await db.commit()
    await qs.publish(db, queue.id)
    return qs.entry_public(entry)


@router.patch("/entries/{entry_id}/status", response_model=EntryPublic)
async def change_status(
    entry_id: int, data: StatusIn, teacher: TeacherUser, db: DbSession
) -> EntryPublic:
    """Сменить статус записи и зафиксировать результат (passed / failed)."""
    entry = await qs.get_entry(db, entry_id)
    ensure_owner(await qs.get_queue(db, entry.queue_id), teacher)
    if data.status not in ALLOWED_TRANSITIONS.get(entry.status, set()):
        raise conflict(f"Нельзя перевести запись из «{entry.status}» в «{data.status}»")
    await _apply_status(db, entry, data.status)
    await db.commit()
    await qs.publish(db, entry.queue_id)
    return qs.entry_public(entry)


@router.post(
    "/entries/{entry_id}/test/start",
    response_model=AttemptOut,
    status_code=status.HTTP_201_CREATED,
)
async def start_test(
    entry_id: int, data: StartTestIn, teacher: TeacherUser, db: DbSession
) -> AttemptOut:
    """Запустить тест для вызванного студента."""
    entry = await qs.get_entry(db, entry_id)
    ensure_owner(await qs.get_queue(db, entry.queue_id), teacher)
    if entry.status not in (EntryStatus.called, EntryStatus.reviewing):
        raise conflict("Тест можно запустить только вызванному студенту")

    lab_ids = [lab.id for lab in entry.labs]
    query = (
        select(LabTest)
        .where(LabTest.lab_id.in_(lab_ids))
        .options(selectinload(LabTest.questions))
        .order_by(LabTest.lab_id, LabTest.id)
    )
    if data.test_id is not None:
        query = query.where(LabTest.id == data.test_id)
    test = await db.scalar(query.limit(1))
    if test is None:
        raise not_found("Для лаб этой записи нет теста")
    if not test.questions:
        raise conflict("В тесте нет вопросов")

    attempt = Attempt(entry_id=entry.id, test_id=test.id, started_at=utcnow())
    db.add(attempt)
    entry.status = EntryStatus.testing
    await db.commit()
    await qs.publish(db, entry.queue_id)
    return ts.attempt_out(await ts.get_attempt(db, attempt.id))
