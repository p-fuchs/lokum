from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Self, Sequence

import httpx

from src.offer.models import OfferSourceType
from src.offer.price import Currency


class SearchEngineType(enum.Enum):
    OLX = "olx"


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    source_type: OfferSourceType
    price: str | None = None
    location: str | None = None
    date: str | None = None


@dataclass(frozen=True)
class SearchParams:
    query: str
    location: str
    search_engine: SearchEngineType
    max_pages: int = 1


@dataclass(frozen=True)
class ScrapingRequest:
    url: str
    source_type: OfferSourceType


@dataclass(frozen=True)
class ScrapingResult:
    url: str
    title: str
    description: str
    source_type: OfferSourceType
    price: float | None = None
    price_currency: Currency | None = None
    admin_rent: float | None = None
    admin_rent_currency: Currency | None = None
    area: float | None = None
    rooms: int | None = None
    address: str | None = None
    photo_urls: tuple[str, ...] = ()
    external_id: str | None = None


class SearchEngine(ABC):
    @classmethod
    @abstractmethod
    def create(cls, client: httpx.AsyncClient) -> Self: ...

    @abstractmethod
    async def search(self, params: SearchParams) -> Sequence[SearchResult]: ...


class ScrapingEngine(ABC):
    @classmethod
    @abstractmethod
    def create(cls, client: httpx.AsyncClient) -> Self: ...

    @abstractmethod
    async def scrape(self, request: ScrapingRequest) -> ScrapingResult: ...
