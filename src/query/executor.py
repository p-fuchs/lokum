from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.offer.resolver import search_and_resolve
from src.query.models import Query, QueryResult
from src.scraping.interface import SearchParams


async def get_pending_queries(session: AsyncSession) -> list[Query]:
    """Return active queries that are due for execution."""
    now = datetime.now(timezone.utc)

    stmt = select(Query).where(
        Query.is_active.is_(True),
        or_(
            Query.last_run_at.is_(None),
            Query.last_run_at
            < now - func.make_interval(0, 0, 0, 0, Query.run_interval_hours),
        ),
    )
    return list((await session.execute(stmt)).scalars().all())


async def execute_query(session: AsyncSession, query: Query) -> list[QueryResult]:
    """Execute a query: search, resolve offers, link sources to query."""
    params = SearchParams(
        query=query.search_query,
        location=query.location,
        search_engine=query.search_engine,
        max_pages=query.max_pages,
    )

    offers = await search_and_resolve(session, [params])
    await session.flush()

    source_ids = {source.id for offer in offers for source in offer.sources}

    existing_stmt = select(QueryResult.offer_source_id).where(
        QueryResult.query_id == query.id,
        QueryResult.offer_source_id.in_(source_ids),
    )
    existing_source_ids = set((await session.execute(existing_stmt)).scalars().all())

    now = datetime.now(timezone.utc)
    new_results: list[QueryResult] = []

    for offer in offers:
        for source in offer.sources:
            if source.id in existing_source_ids:
                continue
            result = QueryResult(
                query_id=query.id,
                offer_source_id=source.id,
                found_at=now,
            )
            session.add(result)
            new_results.append(result)

    query.last_run_at = now

    return new_results
