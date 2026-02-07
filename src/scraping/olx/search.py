import re
from dataclasses import dataclass
from typing import Self, Sequence
from urllib.parse import urlencode, quote

import httpx

from src.offer.models import OfferSourceType
from src.scraping.interface import SearchEngine, SearchParams, SearchResult


@dataclass
class OlxSearchResult:
    title: str
    price: str
    url: str
    location: str
    date: str
    area: str | None = None
    is_promoted: bool = False


class OlxSearchEngine(SearchEngine):
    OLX_URL_TEMPLATE = "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/{location}/q-{query}/?{query_params}"

    _CARD_PATTERN = re.compile(
        r'data-testid="l-card".*?(?=data-testid="l-card"|$)', re.DOTALL
    )
    _TITLE_PATTERN = re.compile(r'class="css-hzlye5">(.*?)</h4>')
    _PRICE_PATTERN = re.compile(r'data-testid="ad-price"[^>]*>(.*?)</p>', re.DOTALL)
    _URL_PATTERN = re.compile(r'href="(/d/oferta/[^"]+)"')
    _LOCATION_DATE_PATTERN = re.compile(
        r'data-testid="location-date"[^>]*>(.*?)</p>', re.DOTALL
    )
    _AREA_PATTERN = re.compile(r"(\d+)\s*m²")
    _HAS_NEXT_PAGE = re.compile(r'data-testid="pagination-forward"')

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @classmethod
    def create(cls, client: httpx.AsyncClient) -> Self:
        return cls(client)

    def _prepare_url(self, params: SearchParams, page: int | None = None) -> str:
        query = quote(params.query)
        location = quote(params.location)

        query_params_raw: dict[str, str] = {"search[order]": "created_at:desc"}

        if page is not None:
            query_params_raw["page"] = str(page)

        query_params = urlencode(query_params_raw)
        return self.OLX_URL_TEMPLATE.format(
            location=location, query=query, query_params=query_params
        )

    async def search(self, params: SearchParams) -> Sequence[SearchResult]:
        raw_results = await self._search_raw(params)
        return [self._to_search_result(r) for r in raw_results]

    async def _search_raw(self, params: SearchParams) -> list[OlxSearchResult]:
        results: list[OlxSearchResult] = []

        for page in range(1, params.max_pages + 1):
            query_url = self._prepare_url(params, page=page)
            search_response = await self._client.get(query_url)
            search_response.raise_for_status()

            html = search_response.text
            results.extend(self._parse_results(html))

            if not self._HAS_NEXT_PAGE.search(html):
                break

        return results

    def _parse_results(self, html: str) -> list[OlxSearchResult]:
        results: list[OlxSearchResult] = []

        for card_match in self._CARD_PATTERN.finditer(html):
            card = card_match.group(0)

            title_m = self._TITLE_PATTERN.search(card)
            price_m = self._PRICE_PATTERN.search(card)
            url_m = self._URL_PATTERN.search(card)
            loc_m = self._LOCATION_DATE_PATTERN.search(card)

            if not (title_m and price_m and url_m and loc_m):
                continue

            title = title_m.group(1).strip()
            price_html = re.sub(
                r"<style[^>]*>.*?</style>", "", price_m.group(1), flags=re.DOTALL
            )
            price = re.sub(r"<[^>]+>", "", price_html).strip()
            url = "https://www.olx.pl" + url_m.group(1).split("?")[0]

            loc_raw = re.sub(r"<[^>]+>", " - ", loc_m.group(1)).strip(" -")
            parts = [p.strip() for p in loc_raw.split(" - ") if p.strip()]
            location = parts[0] if parts else ""
            date = parts[-1] if len(parts) > 1 else ""

            area_m = self._AREA_PATTERN.search(card)
            area = f"{area_m.group(1)} m²" if area_m else None

            is_promoted = "search%7Cpromoted" in card

            results.append(
                OlxSearchResult(
                    title=title,
                    price=price,
                    url=url,
                    location=location,
                    date=date,
                    area=area,
                    is_promoted=is_promoted,
                )
            )

        return results

    @staticmethod
    def _to_search_result(r: OlxSearchResult) -> SearchResult:
        return SearchResult(
            url=r.url,
            title=r.title,
            source_type=OfferSourceType.OLX,
            price=r.price,
            location=r.location,
            date=r.date,
        )
