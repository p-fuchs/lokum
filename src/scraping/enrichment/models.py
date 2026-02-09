from __future__ import annotations

from pydantic import BaseModel, Field

from src.offer.price import Currency


class _CostBreakdownSchema(BaseModel):
    """Internal Pydantic schema for LLM output — cost breakdown."""

    rent: float | None = None
    rent_currency: Currency | None = None
    admin_rent: float | None = None
    admin_rent_currency: Currency | None = None
    total_monthly: float | None = None
    total_monthly_currency: Currency | None = None


class _LLMOutputSchema(BaseModel):
    """Internal Pydantic schema for structured LLM output."""

    summary: str = Field(..., description="Compact 2-3 sentence summary of the offer")
    address: str | None = Field(
        None,
        description="Best street-level address for geocoding (extracted from description)",
    )
    costs: _CostBreakdownSchema = Field(
        default_factory=lambda: _CostBreakdownSchema(),
        description="Price decomposition and total monthly estimate",
    )
    notes: str | None = Field(
        None,
        description="Any observations or comments about the extraction (red flags, missing data, etc.)",
    )
