from __future__ import annotations

import time
from typing import cast

from langchain_core.language_models import BaseChatModel

from src.base.maintenance import MaintenanceData
from src.scraping.enrichment.models import _LLMOutputSchema
from src.scraping.enrichment.prompts import SYSTEM_PROMPT, build_user_prompt
from src.scraping.interface import (
    CostBreakdown,
    EnrichmentEngine,
    EnrichmentResult,
    ScrapingResult,
)


class LangChainEnrichmentEngine(EnrichmentEngine):
    """LLM-based enrichment using LangChain with Google Gemini."""

    _MODEL = "gemini-2.5-flash-lite"

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def enrich(self, scraping_result: ScrapingResult) -> EnrichmentResult:
        """Enrich scraped data with LLM-extracted information."""
        # Build the prompt
        user_prompt = build_user_prompt(
            title=scraping_result.title,
            location=scraping_result.address,
            description=scraping_result.description,
        )

        # Get structured output from LLM
        structured_llm = self._llm.with_structured_output(_LLMOutputSchema)
        messages = [
            ("system", SYSTEM_PROMPT),
            ("user", user_prompt),
        ]

        start = time.monotonic()
        response = cast(_LLMOutputSchema, await structured_llm.ainvoke(messages))
        duration = time.monotonic() - start

        # Convert to EnrichmentResult
        return _to_enrichment_result(response, duration, self._MODEL)


def _to_enrichment_result(
    schema: _LLMOutputSchema,
    duration: float,
    model_name: str,
) -> EnrichmentResult:
    """Convert LLM output schema to EnrichmentResult."""
    # Convert cost breakdown
    costs = CostBreakdown(
        rent=schema.costs.rent,
        rent_currency=schema.costs.rent_currency,
        admin_rent=schema.costs.admin_rent,
        admin_rent_currency=schema.costs.admin_rent_currency,
        total_monthly=schema.costs.total_monthly,
        total_monthly_currency=schema.costs.total_monthly_currency,
    )

    # Build maintenance data for traceability
    maintenance = MaintenanceData(
        model_name=model_name,
        notes=schema.notes,
        duration_seconds=duration,
    )

    # Notes go into EnrichmentResult.notes (which will be stored in OfferRawInfo.maintenance_data)
    return EnrichmentResult(
        summary=schema.summary,
        address=schema.address,
        costs=costs,
        notes=maintenance.model_dump_json(),  # Serialize for storage
    )
