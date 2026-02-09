from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from src.offer.models import Offer, OfferRawInfo


def consolidate_offer(offer: Offer, raw_infos: Sequence[OfferRawInfo]) -> None:
    """
    Update Offer from its OfferRawInfo records. Mutates in place.

    Strategy: Use the most recently scraped OfferRawInfo as the primary source.
    Enriched data takes precedence over raw scraped data.
    """
    if not raw_infos:
        return

    # Find the most recent raw info (by scraped_at)
    best = max(
        raw_infos,
        key=lambda r: r.scraped_at or datetime.min.replace(tzinfo=timezone.utc),
    )

    # Update Offer fields from best raw info
    # Summary comes from LLM enrichment
    offer.summary = best.summary

    # Address: enriched > raw
    offer.street_address = best.enriched_address or best.address

    # Area: use raw info if available (keep existing if not better)
    if best.area is not None:
        offer.area = best.area

    # Rent: enriched > raw
    offer.rent = best.enriched_rent or best.price or offer.rent

    # Admin fee: enriched > raw
    offer.admin_fee = best.enriched_admin_rent or best.admin_rent or offer.admin_fee

    # Total monthly cost (new field)
    offer.total_monthly_cost = best.total_monthly_cost
    offer.total_monthly_cost_currency = best.total_monthly_cost_currency

    # Geocoding (future)
    offer.latitude = best.latitude
    offer.longitude = best.longitude
