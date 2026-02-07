from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Dialect, TypeDecorator, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return value

        if not value.tzinfo or value.tzinfo.utcoffset(value) is None:
            raise TypeError("UTCDateTime must be a timezone-aware datetime")

        value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return value

        return value.replace(tzinfo=timezone.utc)


class BaseDbModel(DeclarativeBase):
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        server_default=func.now(),
        default=lambda _: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), onupdate=lambda _: datetime.now(timezone.utc)
    )
