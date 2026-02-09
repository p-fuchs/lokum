from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.base.models import BaseDbModel, UTCDateTime
from src.offer.models import OfferSource
from src.scraping.interface import SearchEngineType
from src.user.models import User


class Query(BaseDbModel):
    __tablename__ = "queries"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    search_query: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    search_engine: Mapped[SearchEngineType] = mapped_column(
        Enum(SearchEngineType), nullable=False
    )
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    run_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship(back_populates="queries")
    results: Mapped[list[QueryResult]] = relationship(back_populates="query")


class QueryResult(BaseDbModel):
    __tablename__ = "query_results"
    __table_args__ = (
        UniqueConstraint("query_id", "offer_source_id", name="uq_query_source"),
    )

    query_id: Mapped[UUID] = mapped_column(ForeignKey("queries.id"), nullable=False)
    offer_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("offer_sources.id"), nullable=False
    )
    found_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    query: Mapped[Query] = relationship(back_populates="results")
    offer_source: Mapped[OfferSource] = relationship()
