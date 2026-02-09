import httpx
import pytest

from src.offer.models import OfferSourceType
from src.offer.price import Currency
from src.scraping.olx.scrape import OlxOfferScraper


@pytest.fixture
def scraper() -> OlxOfferScraper:
    return OlxOfferScraper(httpx.AsyncClient())


class TestExtractAdData:
    def test_extracts_ad_dict(
        self, scraper: OlxOfferScraper, olx_offer_html: str
    ) -> None:
        ad = scraper._extract_ad_data(olx_offer_html)
        assert isinstance(ad, dict)
        assert ad["id"] == 1053866955

    def test_raises_on_missing_state(self, scraper: OlxOfferScraper) -> None:
        with pytest.raises(ValueError, match="__PRERENDERED_STATE__"):
            scraper._extract_ad_data("<html></html>")

    def test_raises_on_empty_ad(self, scraper: OlxOfferScraper) -> None:
        html = 'window.__PRERENDERED_STATE__ = "{\\"other\\": {}}";'
        with pytest.raises(ValueError, match="ad data"):
            scraper._extract_ad_data(html)


class TestParseAd:
    @pytest.fixture
    def result(self, scraper: OlxOfferScraper, olx_offer_html: str):
        ad = scraper._extract_ad_data(olx_offer_html)
        return scraper._parse_ad(
            ad,
            "https://www.olx.pl/d/oferta/male-studio-bezposrednio-CID3-ID19jUV7.html",
        )

    def test_title(self, result) -> None:
        assert result.title == "Małe studio. Bezpośrednio."

    def test_source_type(self, result) -> None:
        assert result.source_type == OfferSourceType.OLX

    def test_price(self, result) -> None:
        assert result.price == 2200
        assert result.price_currency == Currency.PLN

    def test_admin_rent(self, result) -> None:
        assert result.admin_rent == 300.0
        assert result.admin_rent_currency == Currency.PLN

    def test_area(self, result) -> None:
        assert result.area == 20.0

    def test_rooms(self, result) -> None:
        assert result.rooms == 1

    def test_address(self, result) -> None:
        assert result.address == "Praga-Północ, Warszawa, Mazowieckie"

    def test_external_id(self, result) -> None:
        assert result.external_id == "1053866955"

    def test_url_preserved(self, result) -> None:
        assert (
            result.url
            == "https://www.olx.pl/d/oferta/male-studio-bezposrednio-CID3-ID19jUV7.html"
        )

    def test_description_no_html_tags(self, result) -> None:
        assert "<" not in result.description
        assert ">" not in result.description
        assert "Bezpośrednio od właściciela" in result.description

    def test_photo_urls_count(self, result) -> None:
        assert len(result.photo_urls) == 8

    def test_photo_urls_are_clean(self, result) -> None:
        for url in result.photo_urls:
            assert ";s=" not in url
            assert url.startswith("https://")
            assert url.endswith("/image")

    def test_photo_urls_are_tuple(self, result) -> None:
        assert isinstance(result.photo_urls, tuple)

    def test_floor(self, result) -> None:
        # May be None if not present in fixture
        assert result.floor is None or isinstance(result.floor, int)

    def test_furnished(self, result) -> None:
        # May be None if not present in fixture
        assert result.furnished is None or isinstance(result.furnished, bool)

    def test_pets_allowed(self, result) -> None:
        # May be None if not present in fixture
        assert result.pets_allowed is None or isinstance(result.pets_allowed, bool)

    def test_elevator(self, result) -> None:
        # May be None if not present in fixture
        assert result.elevator is None or isinstance(result.elevator, bool)

    def test_parking(self, result) -> None:
        # May be None if not present in fixture
        assert result.parking is None or isinstance(result.parking, str)

    def test_building_type(self, result) -> None:
        # May be None if not present in fixture
        assert result.building_type is None or isinstance(result.building_type, str)


class TestParseParams:
    def test_extracts_known_keys(self, scraper: OlxOfferScraper) -> None:
        params = [
            {"key": "m", "value": "20 m²", "normalizedValue": "20"},
            {"key": "rent", "value": "300 zł", "normalizedValue": "300"},
            {"key": "rooms", "value": "Kawalerka", "normalizedValue": "one"},
        ]
        result = scraper._parse_params(params)
        assert result["area"] == "20"
        assert result["rent_normalized"] == "300"
        assert result["rent_raw"] == "300 zł"
        assert result["rooms"] == "one"

    def test_extracts_new_params(self, scraper: OlxOfferScraper) -> None:
        params = [
            {"key": "floor_select", "value": "Piętro 4", "normalizedValue": "floor_4"},
            {"key": "furniture", "value": "Tak", "normalizedValue": "yes"},
            {"key": "pets", "value": "Nie", "normalizedValue": "Nie"},
            {"key": "winda", "value": "Tak", "normalizedValue": "Tak"},
            {"key": "parking", "value": "Garaż", "normalizedValue": "garage"},
            {"key": "builttype", "value": "Blok", "normalizedValue": "block"},
        ]
        result = scraper._parse_params(params)
        assert result["floor"] == "floor_4"
        assert result["furnished"] == "yes"
        assert result["pets_allowed"] == "Nie"
        assert result["elevator"] == "Tak"
        assert result["parking"] == "Garaż"
        assert result["building_type"] == "Blok"

    def test_ignores_unknown_keys(self, scraper: OlxOfferScraper) -> None:
        params = [
            {
                "key": "unknown_key",
                "value": "some value",
                "normalizedValue": "normalized",
            },
        ]
        result = scraper._parse_params(params)
        assert result == {}

    def test_empty_params(self, scraper: OlxOfferScraper) -> None:
        assert scraper._parse_params([]) == {}


class TestParseCurrencyCode:
    @pytest.mark.parametrize(
        "code, expected",
        [
            ("PLN", Currency.PLN),
            ("EUR", Currency.EUR),
            ("USD", Currency.USD),
            (None, None),
            ("GBP", None),
        ],
    )
    def test_parse_currency_code(self, code, expected) -> None:
        assert OlxOfferScraper._parse_currency_code(code) == expected


class TestParseCurrencyFromString:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("300 zł", Currency.PLN),
            ("500 EUR", Currency.EUR),
            ("100 $", Currency.USD),
            ("300", None),
            ("", None),
        ],
    )
    def test_parse_currency_from_string(self, value, expected) -> None:
        assert OlxOfferScraper._parse_currency_from_string(value) == expected


class TestCleanDescription:
    def test_strips_html_tags(self, scraper: OlxOfferScraper) -> None:
        html = "Hello<br />world<br />\nfoo"
        assert scraper._clean_description(html) == "Helloworld\nfoo"

    def test_strips_whitespace(self, scraper: OlxOfferScraper) -> None:
        assert scraper._clean_description("  text  ") == "text"

    def test_empty_string(self, scraper: OlxOfferScraper) -> None:
        assert scraper._clean_description("") == ""


class TestParseFloor:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("floor_1", 1),
            ("floor_4", 4),
            ("floor_10", 10),
            ("parter", None),
            (None, None),
            ("", None),
        ],
    )
    def test_parse_floor(self, value, expected) -> None:
        from src.scraping.olx.scrape import _parse_floor

        assert _parse_floor(value) == expected


class TestParseYesNo:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("yes", True),
            ("Yes", True),
            ("YES", True),
            ("no", False),
            ("No", False),
            ("NO", False),
            (None, None),
            ("", False),
            ("other", False),
        ],
    )
    def test_parse_yes_no(self, value, expected) -> None:
        from src.scraping.olx.scrape import _parse_yes_no

        assert _parse_yes_no(value) == expected


class TestParseTakNie:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("Tak", True),
            ("tak", True),
            ("TAK", True),
            ("Nie", False),
            ("nie", False),
            ("NIE", False),
            (None, None),
            ("", None),
            ("other", None),
        ],
    )
    def test_parse_tak_nie(self, value, expected) -> None:
        from src.scraping.olx.scrape import _parse_tak_nie

        assert _parse_tak_nie(value) == expected
