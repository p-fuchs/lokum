import httpx
import pytest

from src.offer.models import OfferSourceType
from src.scraping.olx.search import OlxSearchEngine, OlxSearchResult
from src.scraping.interface import SearchParams, SearchEngineType


@pytest.fixture
def engine() -> OlxSearchEngine:
    return OlxSearchEngine(httpx.AsyncClient())


class TestParseResults:
    @pytest.fixture
    def results(self, engine: OlxSearchEngine, olx_search_html: str):
        return engine._parse_results(olx_search_html)

    def test_parses_all_results(self, results: list[OlxSearchResult]) -> None:
        assert len(results) == 24

    def test_first_result_title(self, results: list[OlxSearchResult]) -> None:
        assert results[0].title == "Studio | Od zaraz | Pets Friendly | Woronicza"

    def test_first_result_price(self, results: list[OlxSearchResult]) -> None:
        assert "2 750" in results[0].price
        assert "zł" in results[0].price

    def test_first_result_location(self, results: list[OlxSearchResult]) -> None:
        assert "Warszawa" in results[0].location

    def test_first_result_area(self, results: list[OlxSearchResult]) -> None:
        assert results[0].area is not None
        assert "33" in results[0].area

    def test_urls_are_absolute(self, results: list[OlxSearchResult]) -> None:
        for r in results:
            assert r.url.startswith("https://www.olx.pl/d/oferta/")

    def test_urls_have_no_query_params(self, results: list[OlxSearchResult]) -> None:
        for r in results:
            assert "?" not in r.url

    def test_promoted_results_detected(self, results: list[OlxSearchResult]) -> None:
        promoted = [r for r in results if r.is_promoted]
        regular = [r for r in results if not r.is_promoted]
        assert len(promoted) == 11
        assert len(regular) == 13

    def test_all_results_have_required_fields(
        self, results: list[OlxSearchResult]
    ) -> None:
        for r in results:
            assert r.title
            assert r.price
            assert r.url
            assert r.location


class TestToSearchResult:
    def test_converts_correctly(self) -> None:
        olx_result = OlxSearchResult(
            title="Test",
            price="2 000 zł",
            url="https://www.olx.pl/d/oferta/test.html",
            location="Warszawa, Mokotów",
            date="Dzisiaj o 15:00",
            area="25 m²",
            is_promoted=False,
        )
        result = OlxSearchEngine._to_search_result(olx_result)

        assert result.url == olx_result.url
        assert result.title == olx_result.title
        assert result.source_type == OfferSourceType.OLX
        assert result.price == olx_result.price
        assert result.location == olx_result.location
        assert result.date == olx_result.date


class TestPrepareUrl:
    def test_basic_url(self, engine: OlxSearchEngine) -> None:
        params = SearchParams(
            query="kawalerka",
            location="warszawa",
            search_engine=SearchEngineType.OLX,
        )
        url = engine._prepare_url(params)
        assert "warszawa" in url
        assert "kawalerka" in url
        assert "page" not in url

    def test_url_with_page(self, engine: OlxSearchEngine) -> None:
        params = SearchParams(
            query="kawalerka",
            location="warszawa",
            search_engine=SearchEngineType.OLX,
        )
        url = engine._prepare_url(params, page=3)
        assert "page=3" in url

    def test_url_has_sort_order(self, engine: OlxSearchEngine) -> None:
        params = SearchParams(
            query="kawalerka",
            location="warszawa",
            search_engine=SearchEngineType.OLX,
        )
        url = engine._prepare_url(params)
        assert "created_at" in url


class TestHasNextPage:
    def test_detects_next_page(self, olx_search_html: str) -> None:
        assert OlxSearchEngine._HAS_NEXT_PAGE.search(olx_search_html) is not None

    def test_no_pagination_in_empty_html(self) -> None:
        assert OlxSearchEngine._HAS_NEXT_PAGE.search("<html></html>") is None
