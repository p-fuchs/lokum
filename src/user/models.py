from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.base.models import BaseDbModel

if TYPE_CHECKING:
    from src.query.models import Query


class User(BaseDbModel):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    queries: Mapped[list[Query]] = relationship(back_populates="user")
