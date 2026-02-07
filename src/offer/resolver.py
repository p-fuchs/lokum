from datetime import datetime, timezone
from typing import Sequence

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.offer.models import Offer, OfferSource
from src.offer.price import parse_price
from src.scraping import create_engine
from src.scraping.interface import SearchParams, SearchResult


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
