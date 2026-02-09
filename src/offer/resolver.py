from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.base.maintenance import MaintenanceData
from src.offer.consolidation import consolidate_offer
from src.offer.models import Offer, OfferRawInfo, OfferSource
from src.offer.price import parse_price
from src.scraping import create_engine
from src.scraping.interface import SearchParams, SearchResult
from src.scraping.pipeline import PipelineItem


async def resolve_offers(
    session: AsyncSession,
    results: Sequence[SearchResult],
) -> list[Offer]:
    """Find existing offers by URL or create new Offer + OfferSource pairs.

    Uses a single query for all URLs. The caller is responsible
    for committing the session.
    """
    if not results:
        return []

    urls = [r.url for r in results]

    stmt = (
        select(OfferSource)
        .where(OfferSource.url.in_(urls))
        .options(selectinload(OfferSource.offer).selectinload(Offer.sources))
    )
    existing_sources = (await session.execute(stmt)).scalars().all()
    existing_by_url = {s.url: s for s in existing_sources}

    seen: dict[str, Offer] = {}
    offers: list[Offer] = []
    now = datetime.now(timezone.utc)

    for result in results:
        if result.url in seen:
            offers.append(seen[result.url])
            continue

        parsed = parse_price(result.price) if result.price else None
        existing_source = existing_by_url.get(result.url)

        if existing_source is not None:
            existing_source.raw_price = parsed
            existing_source.scraped_at = now
            offer = existing_source.offer
            offer.title = result.title
            offer.location = result.location
            offer.rent = parsed.amount if parsed else None
        else:
            offer = Offer(
                title=result.title,
                location=result.location,
                rent=parsed.amount if parsed else None,
            )
            source = OfferSource(
                source_type=result.source_type,
                url=result.url,
                raw_price=parsed,
                scraped_at=now,
            )
            offer.sources.append(source)
            session.add(offer)

        seen[result.url] = offer
        offers.append(offer)

    return offers


async def search_and_resolve(
    session: AsyncSession,
    params_list: Sequence[SearchParams],
) -> list[Offer]:
    """Search all params concurrently and resolve all results into offers."""
    engines = {p.search_engine: create_engine(p.search_engine) for p in params_list}
    search_results = await asyncio.gather(
        *(engines[p.search_engine].search(p) for p in params_list)
    )
    all_results = [r for results in search_results for r in results]
    return await resolve_offers(session, all_results)


async def persist_pipeline_results(
    session: AsyncSession,
    items: Sequence[PipelineItem],
) -> list[Offer]:
    """
    Persist pipeline results: create/update OfferRawInfo and consolidate Offer.

    For each PipelineItem (which references an existing OfferSource by ID):
    1. Load OfferSource + parent Offer
    2. Create or update OfferRawInfo from ScrapingResult + EnrichmentResult
    3. Run consolidation to update Offer from all its OfferRawInfo records
    """
    if not items:
        return []

    # Load all OfferSources with their Offers
    source_ids = [item.offer_source_id for item in items]
    stmt = (
        select(OfferSource)
        .where(OfferSource.id.in_(source_ids))
        .options(selectinload(OfferSource.offer))
    )
    sources = (await session.execute(stmt)).scalars().all()
    sources_by_id = {s.id: s for s in sources}

    now = datetime.now(timezone.utc)
    offers_to_consolidate: dict[UUID, Offer] = {}

    for item in items:
        source = sources_by_id.get(item.offer_source_id)
        if source is None:
            continue

        # Load or create OfferRawInfo
        raw_info = source.raw_info
        if raw_info is None:
            raw_info = OfferRawInfo(offer_source_id=source.id)
            session.add(raw_info)
            source.raw_info = raw_info

        # Update from ScrapingResult
        if item.scraping_result is not None:
            sr = item.scraping_result
            raw_info.title = sr.title
            raw_info.description = sr.description
            raw_info.price = sr.price
            raw_info.price_currency = sr.price_currency
            raw_info.admin_rent = sr.admin_rent
            raw_info.admin_rent_currency = sr.admin_rent_currency
            raw_info.area = sr.area
            raw_info.rooms = sr.rooms
            raw_info.address = sr.address
            raw_info.floor = sr.floor
            raw_info.furnished = sr.furnished
            raw_info.pets_allowed = sr.pets_allowed
            raw_info.elevator = sr.elevator
            raw_info.parking = sr.parking
            raw_info.building_type = sr.building_type
            raw_info.photo_urls = list(sr.photo_urls)
            raw_info.external_id = sr.external_id
            raw_info.scraped_at = now

        # Update from EnrichmentResult
        if item.enrichment_result is not None:
            er = item.enrichment_result
            raw_info.summary = er.summary
            raw_info.enriched_address = er.address
            raw_info.enriched_rent = er.costs.rent
            raw_info.enriched_rent_currency = er.costs.rent_currency
            raw_info.enriched_admin_rent = er.costs.admin_rent
            raw_info.enriched_admin_rent_currency = er.costs.admin_rent_currency
            raw_info.total_monthly_cost = er.costs.total_monthly
            raw_info.total_monthly_cost_currency = er.costs.total_monthly_currency
            raw_info.enriched_at = now

            # Store maintenance data from notes
            if er.notes:
                raw_info.maintenance_data = MaintenanceData.model_validate_json(
                    er.notes
                )

        # Mark offer for consolidation
        offers_to_consolidate[source.offer_id] = source.offer

    # Consolidate all affected offers
    for offer in offers_to_consolidate.values():
        # Load all raw infos for this offer
        raw_info_stmt = (
            select(OfferRawInfo)
            .join(OfferSource, OfferRawInfo.offer_source_id == OfferSource.id)
            .where(OfferSource.offer_id == offer.id)
        )
        raw_infos = (await session.execute(raw_info_stmt)).scalars().all()
        consolidate_offer(offer, raw_infos)

    return list(offers_to_consolidate.values())
