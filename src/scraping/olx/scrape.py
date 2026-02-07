from __future__ import annotations

import json
import re
from typing import Any, Self

import httpx

from src.offer.models import OfferSourceType
from src.offer.price import Currency, _CURRENCY_PATTERN, _CURRENCY_MAP
from src.scraping.interface import ScrapingEngine, ScrapingRequest, ScrapingResult

_ROOMS_MAP: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
}


class OlxOfferScraper(ScrapingEngine):
    _PRERENDERED_STATE_PATTERN = re.compile(
        r'window\.__PRERENDERED_STATE__\s*=\s*"(.*?)"\s*;'
    )
    _HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
    _PHOTO_SIZE_PATTERN = re.compile(r";s=\d+x\d+$")

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @classmethod
    def create(cls, client: httpx.AsyncClient) -> Self:
        return cls(client)

    async def scrape(self, request: ScrapingRequest) -> ScrapingResult:
        response = await self._client.get(request.url)
        response.raise_for_status()
        ad_data = self._extract_ad_data(response.text)
        return self._parse_ad(ad_data, request.url)

    def _extract_ad_data(self, html: str) -> dict[str, Any]:
        match = self._PRERENDERED_STATE_PATTERN.search(html)
        if match is None:
            raise ValueError("Could not find __PRERENDERED_STATE__ in HTML")

        raw = match.group(1)
        json_str = raw.replace('\\"', '"').replace("\\\\", "\\")
        state: dict[str, Any] = json.loads(json_str)

        ad: dict[str, Any] = state.get("ad", {}).get("ad", {})
        if not ad:
            raise ValueError("Could not find ad data in __PRERENDERED_STATE__")
        return ad

    def _parse_ad(self, ad: dict[str, Any], url: str) -> ScrapingResult:
        params = self._parse_params(ad.get("params", []))
        location = ad.get("location", {})
        price_data = ad.get("price", {})
        regular_price = price_data.get("regularPrice", {})

        price_currency = self._parse_currency_code(regular_price.get("currencyCode"))

        admin_rent_value = _parse_float(params.get("rent_normalized"))
        admin_rent_currency = self._parse_currency_from_string(
            params.get("rent_raw", "")
        )

        district = location.get("districtName", "")
        city = location.get("cityName", "")
        region = location.get("regionName", "")
        address_parts = [p for p in (district, city, region) if p]
        address = ", ".join(address_parts) if address_parts else None

        photo_urls = tuple(
            self._PHOTO_SIZE_PATTERN.sub("", photo) for photo in ad.get("photos", [])
        )

        return ScrapingResult(
            url=url,
            title=ad.get("title", ""),
            description=self._clean_description(ad.get("description", "")),
            source_type=OfferSourceType.OLX,
            price=regular_price.get("value"),
            price_currency=price_currency,
            admin_rent=admin_rent_value,
            admin_rent_currency=admin_rent_currency,
            area=_parse_float(params.get("area")),
            rooms=_ROOMS_MAP.get(params.get("rooms", ""), None),
            address=address,
            photo_urls=photo_urls,
            external_id=str(ad["id"]) if "id" in ad else None,
        )

    @staticmethod
    def _parse_params(params: list[dict[str, Any]]) -> dict[str, str]:
        result: dict[str, str] = {}
        for param in params:
            key = param.get("key", "")
            value = param.get("value", "")
            normalized = param.get("normalizedValue", "")

            if key == "m":
                result["area"] = normalized
            elif key == "rent":
                result["rent_normalized"] = normalized
                result["rent_raw"] = value
            elif key == "rooms":
                result["rooms"] = normalized

        return result

    @staticmethod
    def _parse_currency_code(code: str | None) -> Currency | None:
        if code is None:
            return None
        try:
            return Currency(code)
        except ValueError:
            return None

    @staticmethod
    def _parse_currency_from_string(value: str) -> Currency | None:
        match = _CURRENCY_PATTERN.search(value)
        if match is None:
            return None
        return _CURRENCY_MAP[match.group(0).lower()]

    def _clean_description(self, desc: str) -> str:
        return self._HTML_TAG_PATTERN.sub("", desc).strip()


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
