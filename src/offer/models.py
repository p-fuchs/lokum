import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.base.maintenance import MaintenanceData
from src.base.models import BaseDbModel, UTCDateTime
from src.base.schemas import PydanticJSONB
from src.offer.price import Currency, ParsedPrice


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
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    street_address: Mapped[str | None] = mapped_column(String, nullable=True)
    total_monthly_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_monthly_cost_currency: Mapped[Currency | None] = mapped_column(
        Enum(Currency), nullable=True
    )
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

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
    raw_info: Mapped["OfferRawInfo | None"] = relationship(
        back_populates="offer_source"
    )


class OfferRawInfo(BaseDbModel):
    """1:1 with OfferSource. Contains all scraped, enriched, and geocoded data."""

    __tablename__ = "offer_raw_infos"

    offer_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("offer_sources.id"), nullable=False, unique=True
    )

    # ── Scraped data (from ScrapingResult) ──
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_currency: Mapped[Currency | None] = mapped_column(
        Enum(Currency), nullable=True
    )
    admin_rent: Mapped[float | None] = mapped_column(Float, nullable=True)
    admin_rent_currency: Mapped[Currency | None] = mapped_column(
        Enum(Currency), nullable=True
    )
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    rooms: Mapped[int | None] = mapped_column(nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    floor: Mapped[int | None] = mapped_column(nullable=True)
    furnished: Mapped[bool | None] = mapped_column(nullable=True)
    pets_allowed: Mapped[bool | None] = mapped_column(nullable=True)
    elevator: Mapped[bool | None] = mapped_column(nullable=True)
    parking: Mapped[str | None] = mapped_column(String, nullable=True)
    building_type: Mapped[str | None] = mapped_column(String, nullable=True)
    photo_urls: Mapped[list[str] | None] = mapped_column(
        PydanticJSONB(list[str]), nullable=True
    )
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scraped_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    # ── LLM enrichment (structured data only) ──
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    enriched_address: Mapped[str | None] = mapped_column(String, nullable=True)
    enriched_rent: Mapped[float | None] = mapped_column(Float, nullable=True)
    enriched_rent_currency: Mapped[Currency | None] = mapped_column(
        Enum(Currency), nullable=True
    )
    enriched_admin_rent: Mapped[float | None] = mapped_column(Float, nullable=True)
    enriched_admin_rent_currency: Mapped[Currency | None] = mapped_column(
        Enum(Currency), nullable=True
    )
    total_monthly_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_monthly_cost_currency: Mapped[Currency | None] = mapped_column(
        Enum(Currency), nullable=True
    )
    enriched_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    # ── Geocoding (future) ──
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geocoded_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    # ── Maintenance (JSONB — notes, model info) ──
    maintenance_data: Mapped[MaintenanceData | None] = mapped_column(
        PydanticJSONB(MaintenanceData), nullable=True
    )

    # ── Relationships ──
    offer_source: Mapped[OfferSource] = relationship(back_populates="raw_info")
