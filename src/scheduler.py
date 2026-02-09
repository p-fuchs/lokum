import logging
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from src.base.db import async_session
from src.offer.resolver import resolve_offers
from src.query.executor import get_pending_queries
from src.query.models import Query, QueryResult
from src.scraping import create_engine
from collections.abc import Sequence

from src.scraping.interface import SearchEngineType, SearchParams, SearchResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PendingQuery:
    id: UUID
    search_query: str
    location: str
    search_engine: SearchEngineType
    max_pages: int


async def run_pending_queries() -> None:
    # 1. Fetch pending queries → DTOs. Session closed before any slow work.
    async with async_session() as session:
        queries = await get_pending_queries(session)
        pending = [
            _PendingQuery(
                id=q.id,
                search_query=q.search_query,
                location=q.location,
                search_engine=q.search_engine,
                max_pages=q.max_pages,
            )
            for q in queries
        ]

    if not pending:
        return

    # 2. Scrape all queries — no DB session open during HTTP work.
    scraped: list[tuple[_PendingQuery, Sequence[SearchResult]]] = []
    failed: list[tuple[_PendingQuery, str]] = []

    for pq in pending:
        try:
            params = SearchParams(
                query=pq.search_query,
                location=pq.location,
                search_engine=pq.search_engine,
                max_pages=pq.max_pages,
            )
            engine = create_engine(pq.search_engine)
            results = await engine.search(params)
            scraped.append((pq, results))
        except Exception:
            failed.append((pq, traceback.format_exc()[:2000]))
            logger.exception("Query %s scraping failed", pq.id)

    # 3. Single short session for all DB writes.
    async with async_session() as session:
        now = datetime.now(timezone.utc)

        for pq, search_results in scraped:
            offers = await resolve_offers(session, search_results)
            await session.flush()

            source_ids = {s.id for o in offers for s in o.sources}
            existing_stmt = select(QueryResult.offer_source_id).where(
                QueryResult.query_id == pq.id,
                QueryResult.offer_source_id.in_(source_ids),
            )
            existing_ids = set((await session.execute(existing_stmt)).scalars().all())

            new_count = 0
            for offer in offers:
                for source in offer.sources:
                    if source.id in existing_ids:
                        continue
                    session.add(
                        QueryResult(
                            query_id=pq.id,
                            offer_source_id=source.id,
                            found_at=now,
                        )
                    )
                    new_count += 1

            query = await session.get(Query, pq.id)
            if query:
                query.last_run_at = now
                query.last_error = None
                query.last_error_at = None

            logger.info("Query %s: %d new results", pq.id, new_count)

        for pq, tb in failed:
            query = await session.get(Query, pq.id)
            if query:
                query.last_error = tb
                query.last_error_at = now

        await session.commit()
