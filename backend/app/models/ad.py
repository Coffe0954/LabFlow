from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdBanner(Base):
    __tablename__ = "ad_banners"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_url: Mapped[str] = mapped_column(String(500))
    link: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(default=True)
