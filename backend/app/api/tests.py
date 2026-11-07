"""Конструктор тестов (преподаватель) и прохождение теста (студент)."""

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import (
    DbSession,
    StudentUser,
    TeacherUser,
    conflict,
    forbidden,
    not_found,
)
from app.models import Answer, Attempt, Lab, LabTest, Question, QueueEntry
from app.schemas.testing import (
    AnswersIn,
    AttemptFull,
    AttemptOut,
    QuestionIn,
    QuestionOut,
    TestCreate,
    TestDetail,
    TestOut,
    TestUpdate,
)
from app.services import queue_service as qs
from app.services import testing_service as ts

router = APIRouter(tags=["tests"])


async def _get_test(db: DbSession, test_id: int) -> LabTest:
    test = await db.scalar(
        select(LabTest)
        .where(LabTest.id == test_id)
        .options(selectinload(LabTest.questions))
        .execution_options(populate_existing=True)
    )
    if test is None:
        raise not_found("Тест не найден")
    return test


def _test_out(test: LabTest) -> TestOut:
    return TestOut(
        id=test.id,
        lab_id=test.lab_id,
        title=test.title,
        time_limit_min=test.time_limit_min,
        question_count=len(test.questions),
    )


def _test_detail(test: LabTest) -> TestDetail:
    return TestDetail(
        **_test_out(test).model_dump(),
        questions=[QuestionOut.model_validate(q) for q in test.questions],
    )


# --- Тесты ---


@router.get("/tests", response_model=list[TestOut])
async def list_tests(_: TeacherUser, db: DbSession, lab_id: int | None = None) -> list[TestOut]:
    query = select(LabTest).options(selectinload(LabTest.questions)).order_by(LabTest.id)
    if lab_id is not None:
        query = query.where(LabTest.lab_id == lab_id)
    return [_test_out(t) for t in await db.scalars(query)]


@router.get("/tests/{test_id}", response_model=TestDetail)
async def get_test(test_id: int, _: TeacherUser, db: DbSession) -> TestDetail:
    return _test_detail(await _get_test(db, test_id))


@router.post("/tests", response_model=TestDetail, status_code=status.HTTP_201_CREATED)
async def create_test(data: TestCreate, _: TeacherUser, db: DbSession) -> TestDetail:
    if await db.get(Lab, data.lab_id) is None:
        raise not_found("Лаба не найдена")
    test = LabTest(**data.model_dump())
    db.add(test)
    await db.commit()
    return _test_detail(await _get_test(db, test.id))


@router.patch("/tests/{test_id}", response_model=TestDetail)
async def update_test(test_id: int, data: TestUpdate, _: TeacherUser, db: DbSession) -> TestDetail:
    test = await _get_test(db, test_id)
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(test, field, value)
    await db.commit()
    return _test_detail(await _get_test(db, test_id))


@router.delete("/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test(test_id: int, _: TeacherUser, db: DbSession) -> Response:
    await db.delete(await _get_test(db, test_id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Вопросы ---


@router.get("/tests/{test_id}/questions", response_model=list[QuestionOut])
async def list_questions(test_id: int, _: TeacherUser, db: DbSession) -> list[Question]:
    return list((await _get_test(db, test_id)).questions)


@router.post(
    "/tests/{test_id}/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED
)
async def create_question(
    test_id: int, data: QuestionIn, _: TeacherUser, db: DbSession
) -> Question:
    await _get_test(db, test_id)
    question = Question(test_id=test_id, **data.model_dump())
    db.add(question)
    await db.commit()
    return question


async def _get_question(db: DbSession, test_id: int, question_id: int) -> Question:
    question = await db.get(Question, question_id)
    if question is None or question.test_id != test_id:
        raise not_found("Вопрос не найден")
    return question


@router.put("/tests/{test_id}/questions/{question_id}", response_model=QuestionOut)
async def update_question(
    test_id: int, question_id: int, data: QuestionIn, _: TeacherUser, db: DbSession
) -> Question:
    question = await _get_question(db, test_id, question_id)
    for field, value in data.model_dump().items():
        setattr(question, field, value)
    await db.commit()
    return question


@router.delete("/tests/{test_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    test_id: int, question_id: int, _: TeacherUser, db: DbSession
) -> Response:
    await db.delete(await _get_question(db, test_id, question_id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Прохождение теста студентом ---


async def _own_attempt(db: DbSession, attempt_id: int, student_id: int) -> Attempt:
    attempt = await ts.get_attempt(db, attempt_id)
    entry = await db.get(QueueEntry, attempt.entry_id)
    if entry is None or entry.student_id != student_id:
        raise forbidden("Это не ваша попытка")
    return attempt


async def _expire_if_needed(db: DbSession, attempt: Attempt) -> bool:
    """Если время вышло — завершает попытку. Возвращает True, если завершили сейчас."""
    if attempt.finished_at is None and ts.is_expired(attempt):
        await ts.finish_attempt(db, attempt)
        await db.commit()
        entry = await db.get(QueueEntry, attempt.entry_id)
        if entry is not None:
            await qs.publish(db, entry.queue_id)
        return True
    return False


@router.get("/attempts/current", response_model=AttemptFull | None)
async def current_attempt(student: StudentUser, db: DbSession) -> AttemptFull | None:
    """Незавершённый тест текущего студента или null."""
    attempt_id = await db.scalar(
        select(Attempt.id)
        .join(QueueEntry, QueueEntry.id == Attempt.entry_id)
        .where(QueueEntry.student_id == student.id, Attempt.finished_at.is_(None))
        .order_by(Attempt.id.desc())
        .limit(1)
    )
    if attempt_id is None:
        return None
    attempt = await ts.get_attempt(db, attempt_id)
    if await _expire_if_needed(db, attempt):
        return None
    return ts.attempt_full(attempt)


@router.get("/attempts/{attempt_id}", response_model=AttemptFull)
async def get_attempt(attempt_id: int, student: StudentUser, db: DbSession) -> AttemptFull:
    attempt = await _own_attempt(db, attempt_id, student.id)
    await _expire_if_needed(db, attempt)
    return ts.attempt_full(await ts.get_attempt(db, attempt_id))


@router.post("/attempts/{attempt_id}/answers", response_model=AttemptFull)
async def save_answers(
    attempt_id: int, data: AnswersIn, student: StudentUser, db: DbSession
) -> AttemptFull:
    """Сохранить ответы (можно отправлять много раз — ответ на вопрос перезаписывается)."""
    attempt = await _own_attempt(db, attempt_id, student.id)
    if attempt.finished_at is not None:
        raise conflict("Тест уже завершён")
    if await _expire_if_needed(db, attempt):
        raise conflict("Время теста истекло")
    question_ids = {q.id for q in attempt.test.questions}
    existing: dict[int, Answer] = {a.question_id: a for a in attempt.answers}
    for item in data.answers:
        if item.question_id not in question_ids:
            raise not_found("Вопрос не из этого теста")
        value: Any = item.value
        if item.question_id in existing:
            existing[item.question_id].value = value
        else:
            answer = Answer(attempt_id=attempt.id, question_id=item.question_id, value=value)
            attempt.answers.append(answer)
            existing[item.question_id] = answer
    await db.commit()
    return ts.attempt_full(await ts.get_attempt(db, attempt_id))


@router.post("/attempts/{attempt_id}/finish", response_model=AttemptOut)
async def finish(attempt_id: int, student: StudentUser, db: DbSession) -> AttemptOut:
    """Завершить тест: подсчитать балл и передать запись преподавателю на проверку кода."""
    attempt = await _own_attempt(db, attempt_id, student.id)
    if attempt.finished_at is None:
        await ts.finish_attempt(db, attempt)
        await db.commit()
        entry = await db.get(QueueEntry, attempt.entry_id)
        if entry is not None:
            await qs.publish(db, entry.queue_id)
    return ts.attempt_out(await ts.get_attempt(db, attempt_id))
