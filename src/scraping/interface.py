from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Self, Sequence

import httpx

from src.offer.models import OfferSourceType


class SearchEngineType(enum.Enum):
    OLX = "olx"


@dataclass
class SearchResult:
    url: str
    title: str
    source_type: OfferSourceType
    price: str | None = None
    location: str | None = None
    date: str | None = None


@dataclass
class SearchParams:
    query: str
    location: str
    search_engine: SearchEngineType
    max_pages: int = 1


class SearchEngine(ABC):
    @classmethod
    @abstractmethod
    def create(cls, client: httpx.AsyncClient) -> Self: ...

    @abstractmethod
    async def search(self, params: SearchParams) -> Sequence[SearchResult]: ...
