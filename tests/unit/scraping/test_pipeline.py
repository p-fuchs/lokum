from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.offer.models import OfferSourceType
from src.scraping.interface import (
    EnrichmentEngine,
    EnrichmentResult,
    ScrapingEngine,
    ScrapingResult,
)
from src.scraping.pipeline import PipelineItem, run_pipeline


@pytest.fixture
def mock_scraper() -> AsyncMock:
    """Mock scraping engine that returns a fixed result."""
    scraper = AsyncMock(spec=ScrapingEngine)
    scraper.scrape = AsyncMock(
        return_value=ScrapingResult(
            url="https://example.com/offer",
            title="Test Offer",
            description="A test description",
            source_type=OfferSourceType.OLX,
        )
    )
    return scraper


@pytest.fixture
def mock_enricher() -> AsyncMock:
    """Mock enrichment engine that returns a fixed result."""
    enricher = AsyncMock(spec=EnrichmentEngine)
    enricher.enrich = AsyncMock(
        return_value=EnrichmentResult(
            summary="Test summary",
            address="Test Address 1",
        )
    )
    return enricher


class TestRunPipeline:
    async def test_scrapes_and_enriches(
        self, mock_scraper: AsyncMock, mock_enricher: AsyncMock
    ) -> None:
        """Test that pipeline calls scraper and enricher for each item."""
        items = [
            PipelineItem(
                url="https://example.com/offer1",
                source_type=OfferSourceType.OLX,
                offer_source_id=uuid4(),
            ),
            PipelineItem(
                url="https://example.com/offer2",
                source_type=OfferSourceType.OLX,
                offer_source_id=uuid4(),
            ),
        ]

        results = await run_pipeline(items, mock_scraper, mock_enricher)

        assert len(results) == 2
        assert all(r.scraping_result is not None for r in results)
        assert all(r.enrichment_result is not None for r in results)
        assert mock_scraper.scrape.call_count == 2
        assert mock_enricher.enrich.call_count == 2

    async def test_skips_enrichment_without_description(
        self, mock_enricher: AsyncMock
    ) -> None:
        """Test that enrichment is skipped when scraping result has no description."""
        scraper = AsyncMock(spec=ScrapingEngine)
        scraper.scrape = AsyncMock(
            return_value=ScrapingResult(
                url="https://example.com/offer",
                title="Test Offer",
                description="",  # Empty description
                source_type=OfferSourceType.OLX,
            )
        )

        items = [
            PipelineItem(
                url="https://example.com/offer",
                source_type=OfferSourceType.OLX,
                offer_source_id=uuid4(),
            )
        ]

        results = await run_pipeline(items, scraper, mock_enricher)

        assert len(results) == 1
        assert results[0].scraping_result is not None
        assert results[0].enrichment_result is None
        assert mock_enricher.enrich.call_count == 0

    async def test_per_item_failure_isolation(
        self, mock_scraper: AsyncMock, mock_enricher: AsyncMock
    ) -> None:
        """Test that if one item fails, others continue processing."""
        # Make scraper fail for the first call, succeed for the second
        scraper = AsyncMock(spec=ScrapingEngine)
        scraper.scrape = AsyncMock(
            side_effect=[
                Exception("Scraping failed"),
                ScrapingResult(
                    url="https://example.com/offer2",
                    title="Test Offer 2",
                    description="Description 2",
                    source_type=OfferSourceType.OLX,
                ),
            ]
        )

        items = [
            PipelineItem(
                url="https://example.com/offer1",
                source_type=OfferSourceType.OLX,
                offer_source_id=uuid4(),
            ),
            PipelineItem(
                url="https://example.com/offer2",
                source_type=OfferSourceType.OLX,
                offer_source_id=uuid4(),
            ),
        ]

        results = await run_pipeline(items, scraper, mock_enricher)

        # Both items should be in results, but first one has no scraping_result
        assert len(results) == 2
        assert results[0].scraping_result is None
        assert results[1].scraping_result is not None
        assert results[1].enrichment_result is not None

    async def test_empty_items_list(
        self, mock_scraper: AsyncMock, mock_enricher: AsyncMock
    ) -> None:
        """Test that pipeline handles empty items list."""
        results = await run_pipeline([], mock_scraper, mock_enricher)

        assert len(results) == 0
        assert mock_scraper.scrape.call_count == 0
        assert mock_enricher.enrich.call_count == 0
