import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.base.models import BaseDbModel, UTCDateTime
from src.base.schemas import PydanticJSONB
from src.offer.price import ParsedPrice


class OfferSourceType(enum.Enum):
    OLX = "olx"


class Offer(BaseDbModel):
    __tablename__ = "offers"

    title: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    rent: Mapped[float | None] = mapped_column(Float, nullable=True)
    admin_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    utilities: Mapped[float | None] = mapped_column(Float, nullable=True)

    sources: Mapped[list["OfferSource"]] = relationship(back_populates="offer")


class OfferSource(BaseDbModel):
    __tablename__ = "offer_sources"

    offer_id: Mapped[UUID] = mapped_column(ForeignKey("offers.id"), nullable=False)
    source_type: Mapped[OfferSourceType] = mapped_column(
        Enum(OfferSourceType), nullable=False
    )
    url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    raw_price: Mapped[ParsedPrice | None] = mapped_column(
        PydanticJSONB(ParsedPrice), nullable=True
    )
    scraped_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    offer: Mapped[Offer] = relationship(back_populates="sources")
