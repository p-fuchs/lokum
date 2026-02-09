from datetime import datetime, timezone

from src.offer.consolidation import consolidate_offer
from src.offer.models import Offer, OfferRawInfo
from src.offer.price import Currency


class TestConsolidateOffer:
    def test_no_raw_infos_no_op(self) -> None:
        """Test that consolidate_offer with no raw infos is a no-op."""
        offer = Offer(
            title="Original",
            location="Original Location",
            rent=1000.0,
        )
        original_rent = offer.rent

        consolidate_offer(offer, [])

        assert offer.rent == original_rent

    def test_single_raw_info_updates_offer(self) -> None:
        """Test that consolidate_offer updates from a single OfferRawInfo."""
        offer = Offer(
            title="Old Title",
            location="Old Location",
            rent=1000.0,
        )

        raw_info = OfferRawInfo(
            scraped_at=datetime.now(timezone.utc),
            summary="Great apartment",
            enriched_address="ul. Marszałkowska 1, Warszawa",
            area=50.0,
            enriched_rent=2000.0,
            enriched_admin_rent=300.0,
            total_monthly_cost=2500.0,
            total_monthly_cost_currency=Currency.PLN,
            latitude=52.2297,
            longitude=21.0122,
        )

        consolidate_offer(offer, [raw_info])

        assert offer.summary == "Great apartment"
        assert offer.street_address == "ul. Marszałkowska 1, Warszawa"
        assert offer.area == 50.0
        assert offer.rent == 2000.0
        assert offer.admin_fee == 300.0
        assert offer.total_monthly_cost == 2500.0
        assert offer.total_monthly_cost_currency == Currency.PLN
        assert offer.latitude == 52.2297
        assert offer.longitude == 21.0122

    def test_enriched_data_takes_precedence(self) -> None:
        """Test that enriched data takes precedence over raw data."""
        offer = Offer(
            title="Title",
            location="Location",
        )

        raw_info = OfferRawInfo(
            scraped_at=datetime.now(timezone.utc),
            # Raw data
            address="Praga, Warszawa",
            price=1800.0,
            admin_rent=250.0,
            # Enriched data (should take precedence)
            enriched_address="ul. Targowa 5, Warszawa",
            enriched_rent=2000.0,
            enriched_admin_rent=300.0,
        )

        consolidate_offer(offer, [raw_info])

        assert offer.street_address == "ul. Targowa 5, Warszawa"
        assert offer.rent == 2000.0
        assert offer.admin_fee == 300.0

    def test_fallback_to_raw_when_enriched_missing(self) -> None:
        """Test that raw data is used when enriched data is missing."""
        offer = Offer(
            title="Title",
            location="Location",
        )

        raw_info = OfferRawInfo(
            scraped_at=datetime.now(timezone.utc),
            address="Praga, Warszawa",
            price=1800.0,
            admin_rent=250.0,
            # No enriched data
        )

        consolidate_offer(offer, [raw_info])

        assert offer.street_address == "Praga, Warszawa"
        assert offer.rent == 1800.0
        assert offer.admin_fee == 250.0

    def test_most_recent_raw_info_wins(self) -> None:
        """Test that the most recently scraped raw info is used."""
        offer = Offer(
            title="Title",
            location="Location",
        )

        older = OfferRawInfo(
            scraped_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            summary="Old summary",
            enriched_rent=1500.0,
        )

        newer = OfferRawInfo(
            scraped_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
            summary="New summary",
            enriched_rent=2000.0,
        )

        consolidate_offer(offer, [older, newer])

        assert offer.summary == "New summary"
        assert offer.rent == 2000.0

    def test_none_scraped_at_handled(self) -> None:
        """Test that OfferRawInfo with None scraped_at is handled."""
        offer = Offer(
            title="Title",
            location="Location",
        )

        # One with None scraped_at, one with actual timestamp
        no_date = OfferRawInfo(
            scraped_at=None,
            summary="No date",
        )

        with_date = OfferRawInfo(
            scraped_at=datetime.now(timezone.utc),
            summary="With date",
        )

        consolidate_offer(offer, [no_date, with_date])

        # Should pick the one with actual date
        assert offer.summary == "With date"
