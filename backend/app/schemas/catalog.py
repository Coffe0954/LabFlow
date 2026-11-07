"""Дисциплины, лабы, рекламные баннеры."""

from pydantic import BaseModel, ConfigDict, Field


class DisciplineIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class DisciplineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


class LabCreate(BaseModel):
    discipline_id: int
    number: int = Field(ge=1, le=100)
    title: str = Field(min_length=1, max_length=200)
    expected_minutes: int = Field(ge=1, le=240)


class LabUpdate(BaseModel):
    number: int | None = Field(default=None, ge=1, le=100)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    expected_minutes: int | None = Field(default=None, ge=1, le=240)


class LabOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    discipline_id: int
    number: int
    title: str
    expected_minutes: int


class AdCreate(BaseModel):
    image_url: str = Field(min_length=1, max_length=500, pattern=r"^https?://")
    link: str = Field(min_length=1, max_length=500, pattern=r"^https?://")
    active: bool = True


class AdUpdate(BaseModel):
    image_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://")
    link: str | None = Field(default=None, max_length=500, pattern=r"^https?://")
    active: bool | None = None


class AdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    link: str
    active: bool
