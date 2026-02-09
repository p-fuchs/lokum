from __future__ import annotations

from pydantic import BaseModel


class MaintenanceData(BaseModel):
    """Stored as JSONB on OfferRawInfo. Contains LLM notes and traceability info."""

    model_name: str
    notes: str | None = None
    duration_seconds: float | None = None
