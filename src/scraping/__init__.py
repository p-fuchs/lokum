from typing import TYPE_CHECKING

import httpx
from fake_useragent import UserAgent

from src.offer.models import OfferSourceType
from src.scraping.interface import ScrapingEngine, SearchEngine, SearchEngineType
from src.scraping.olx.scrape import OlxOfferScraper
from src.scraping.olx.search import OlxSearchEngine
from langchain_google_genai import ChatGoogleGenerativeAI

from src.scraping.enrichment import LangChainEnrichmentEngine
from src.scraping.interface import EnrichmentEngine


if TYPE_CHECKING:
    from src.scraping.interface import EnrichmentEngine

_SEARCH_FACTORIES: dict[SearchEngineType, type[SearchEngine]] = {
    SearchEngineType.OLX: OlxSearchEngine,
}

_SCRAPING_FACTORIES: dict[OfferSourceType, type[ScrapingEngine]] = {
    OfferSourceType.OLX: OlxOfferScraper,
}


def _make_client() -> httpx.AsyncClient:
    ua = UserAgent()
    return httpx.AsyncClient(
        headers={"User-Agent": ua.firefox},
        follow_redirects=True,
    )


def create_engine(engine_type: SearchEngineType) -> SearchEngine:
    """Create a search engine instance with a fresh HTTP client."""
    cls = _SEARCH_FACTORIES[engine_type]
    return cls.create(_make_client())


def create_scraper(source_type: OfferSourceType) -> ScrapingEngine:
    """Create a scraping engine instance with a fresh HTTP client."""
    cls = _SCRAPING_FACTORIES[source_type]
    return cls.create(_make_client())


def create_enricher() -> "EnrichmentEngine":
    """Create an enrichment engine instance using Google Gemini."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0,
    )
    return LangChainEnrichmentEngine(llm)
