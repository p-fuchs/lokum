from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Sequence
from uuid import UUID

from src.offer.models import OfferSourceType
from src.scraping.interface import (
    EnrichmentEngine,
    EnrichmentResult,
    ScrapingEngine,
    ScrapingRequest,
    ScrapingResult,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineItem:
    """Represents an OfferSource that needs processing through the pipeline."""

    url: str
    source_type: OfferSourceType
    offer_source_id: UUID
    scraping_result: ScrapingResult | None = None
    enrichment_result: EnrichmentResult | None = None


async def run_pipeline(
    items: Sequence[PipelineItem],
    scraper: ScrapingEngine,
    enricher: EnrichmentEngine,
) -> list[PipelineItem]:
    """
    Run the scraping + enrichment pipeline for each item.

    Pipeline stages:
    1. Scrape (ScrapingEngine) → ScrapingResult
    2. Enrich (EnrichmentEngine) → EnrichmentResult (only if description exists)

    Per-item failure isolation: if an item fails, log the error and continue.
    """
    results: list[PipelineItem] = []

    for item in items:
        try:
            # Stage 1: Scrape
            scraping_result = await scraper.scrape(
                ScrapingRequest(url=item.url, source_type=item.source_type)
            )
            item = replace(item, scraping_result=scraping_result)

            # Stage 2: Enrich (only if we have a description)
            if scraping_result.description:
                enrichment_result = await enricher.enrich(scraping_result)
                item = replace(item, enrichment_result=enrichment_result)
            else:
                logger.warning("Skipping enrichment for %s (no description)", item.url)

        except Exception:
            logger.exception("Pipeline failed for %s", item.url)

        results.append(item)

    return results
