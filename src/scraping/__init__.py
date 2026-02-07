import httpx
from fake_useragent import UserAgent

from src.scraping.interface import SearchEngine, SearchEngineType
from src.scraping.olx.search import OlxSearchEngine

_FACTORIES: dict[SearchEngineType, type[SearchEngine]] = {
    SearchEngineType.OLX: OlxSearchEngine,
}


def create_engine(engine_type: SearchEngineType) -> SearchEngine:
    """Create a search engine instance with a fresh HTTP client."""
    ua = UserAgent()
    client = httpx.AsyncClient(
        headers={"User-Agent": ua.firefox},
        follow_redirects=True,
    )
    cls = _FACTORIES[engine_type]
    return cls.create(client)
