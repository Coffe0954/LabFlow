"""Дисциплины и лабы."""

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, TeacherUser, conflict, not_found
from app.models import Discipline, Lab
from app.schemas.catalog import DisciplineIn, DisciplineOut, LabCreate, LabOut, LabUpdate

router = APIRouter(tags=["labs"])


@router.get("/disciplines", response_model=list[DisciplineOut])
async def list_disciplines(_: CurrentUser, db: DbSession) -> list[Discipline]:
    return list(await db.scalars(select(Discipline).order_by(Discipline.title)))


@router.post("/disciplines", response_model=DisciplineOut, status_code=status.HTTP_201_CREATED)
async def create_discipline(data: DisciplineIn, _: TeacherUser, db: DbSession) -> Discipline:
    discipline = Discipline(title=data.title.strip())
    db.add(discipline)
    await db.commit()
    return discipline


@router.patch("/disciplines/{discipline_id}", response_model=DisciplineOut)
async def update_discipline(
    discipline_id: int, data: DisciplineIn, _: TeacherUser, db: DbSession
) -> Discipline:
    discipline = await db.get(Discipline, discipline_id)
    if discipline is None:
        raise not_found("Дисциплина не найдена")
    discipline.title = data.title.strip()
    await db.commit()
    return discipline


@router.get("/labs", response_model=list[LabOut])
async def list_labs(_: CurrentUser, db: DbSession, discipline_id: int | None = None) -> list[Lab]:
    query = select(Lab).order_by(Lab.discipline_id, Lab.number)
    if discipline_id is not None:
        query = query.where(Lab.discipline_id == discipline_id)
    return list(await db.scalars(query))


@router.get("/labs/{lab_id}", response_model=LabOut)
async def get_lab(lab_id: int, _: CurrentUser, db: DbSession) -> Lab:
    lab = await db.get(Lab, lab_id)
    if lab is None:
        raise not_found("Лаба не найдена")
    return lab


async def _commit_lab(db: DbSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise conflict("Лаба с таким номером уже есть в дисциплине") from exc


@router.post("/labs", response_model=LabOut, status_code=status.HTTP_201_CREATED)
async def create_lab(data: LabCreate, _: TeacherUser, db: DbSession) -> Lab:
    if await db.get(Discipline, data.discipline_id) is None:
        raise not_found("Дисциплина не найдена")
    lab = Lab(**data.model_dump())
    db.add(lab)
    await _commit_lab(db)
    return lab


@router.patch("/labs/{lab_id}", response_model=LabOut)
async def update_lab(lab_id: int, data: LabUpdate, _: TeacherUser, db: DbSession) -> Lab:
    lab = await db.get(Lab, lab_id)
    if lab is None:
        raise not_found("Лаба не найдена")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(lab, field, value)
    await _commit_lab(db)
    return lab


@router.delete("/labs/{lab_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lab(lab_id: int, _: TeacherUser, db: DbSession) -> Response:
    lab = await db.get(Lab, lab_id)
    if lab is None:
        raise not_found("Лаба не найдена")
    await db.delete(lab)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
