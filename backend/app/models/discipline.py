from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Discipline(Base):
    __tablename__ = "disciplines"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))

    labs: Mapped[list["Lab"]] = relationship(
        back_populates="discipline", order_by="Lab.number", cascade="all, delete-orphan"
    )


class Lab(Base):
    __tablename__ = "labs"
    __table_args__ = (UniqueConstraint("discipline_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id", ondelete="CASCADE"))
    number: Mapped[int]
    title: Mapped[str] = mapped_column(String(200))
    # Сколько минут обычно занимает сдача — это D в алгоритме очереди.
    expected_minutes: Mapped[int]

    discipline: Mapped[Discipline] = relationship(back_populates="labs")
