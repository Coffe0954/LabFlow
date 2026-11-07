"""Рекламные баннеры."""

from fastapi import APIRouter, Response, status
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession, not_found
from app.models import AdBanner
from app.schemas.catalog import AdCreate, AdOut, AdUpdate

router = APIRouter(tags=["ads"])


@router.get("/ads/active", response_model=AdOut | None)
async def active_ad(db: DbSession) -> AdBanner | None:
    """Случайный активный баннер или null, если активных нет."""
    return await db.scalar(
        select(AdBanner).where(AdBanner.active.is_(True)).order_by(func.random()).limit(1)
    )


@router.get("/ads", response_model=list[AdOut])
async def list_ads(_: AdminUser, db: DbSession) -> list[AdBanner]:
    return list(await db.scalars(select(AdBanner).order_by(AdBanner.id)))


@router.post("/ads", response_model=AdOut, status_code=status.HTTP_201_CREATED)
async def create_ad(data: AdCreate, _: AdminUser, db: DbSession) -> AdBanner:
    ad = AdBanner(**data.model_dump())
    db.add(ad)
    await db.commit()
    return ad


@router.patch("/ads/{ad_id}", response_model=AdOut)
async def update_ad(ad_id: int, data: AdUpdate, _: AdminUser, db: DbSession) -> AdBanner:
    ad = await db.get(AdBanner, ad_id)
    if ad is None:
        raise not_found("Баннер не найден")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ad, field, value)
    await db.commit()
    return ad


@router.delete("/ads/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ad(ad_id: int, _: AdminUser, db: DbSession) -> Response:
    ad = await db.get(AdBanner, ad_id)
    if ad is None:
        raise not_found("Баннер не найден")
    await db.delete(ad)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
