import logging
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.base.db import async_session
from src.offer.models import OfferSource, OfferSourceType, OfferRawInfo
from src.offer.resolver import persist_pipeline_results, resolve_offers
from src.query.executor import get_pending_queries
from src.query.models import Query, QueryResult
from src.scraping import create_enricher, create_engine, create_scraper
from collections.abc import Sequence

from src.scraping.interface import SearchEngineType, SearchParams, SearchResult
from src.scraping.pipeline import PipelineItem, run_pipeline

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


@dataclass(frozen=True)
class _PendingScrape:
    """DTO for an OfferSource that needs scraping."""

    offer_source_id: UUID
    url: str
    source_type: OfferSourceType


async def run_pending_scrapes() -> None:
    """
    Run the scraping + enrichment pipeline for OfferSources needing work.

    Three phases:
    1. Fetch OfferSources needing work → DTOs (short DB session)
       - No OfferRawInfo exists
       - OR OfferRawInfo.scraped_at older than 2 weeks
    2. Pipeline: scrape + enrich each (no DB session)
    3. Persist OfferRawInfo + consolidate Offer (short DB session)
    """
    staleness_threshold = timedelta(weeks=2)

    # Phase 1: Fetch OfferSources needing work
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        cutoff = now - staleness_threshold

        # Find OfferSources without OfferRawInfo or with stale data
        stmt = (
            select(OfferSource)
            .outerjoin(OfferRawInfo)
            .where(
                (OfferRawInfo.id.is_(None))  # No raw info
                | (OfferRawInfo.scraped_at < cutoff)  # Stale
            )
            .options(selectinload(OfferSource.raw_info))
        )
        sources = (await session.execute(stmt)).scalars().all()

        pending = [
            _PendingScrape(
                offer_source_id=s.id,
                url=s.url,
                source_type=s.source_type,
            )
            for s in sources
        ]

    if not pending:
        return

    logger.info("Found %d OfferSources needing scraping", len(pending))

    # Phase 2: Run pipeline (no DB session during HTTP/LLM work)
    items = [
        PipelineItem(
            url=ps.url,
            source_type=ps.source_type,
            offer_source_id=ps.offer_source_id,
        )
        for ps in pending
    ]

    # Create engines once for all items (they're stateless)
    scraper = create_scraper(OfferSourceType.OLX)  # TODO: support multiple types
    enricher = create_enricher()

    try:
        processed_items = await run_pipeline(items, scraper, enricher)
    except Exception:
        logger.exception("Pipeline execution failed")
        return

    # Phase 3: Persist results
    async with async_session() as session:
        try:
            offers = await persist_pipeline_results(session, processed_items)
            await session.commit()
            logger.info(
                "Scraping pipeline completed: %d items processed, %d offers updated",
                len(processed_items),
                len(offers),
            )
        except Exception:
            await session.rollback()
            logger.exception("Failed to persist pipeline results")
            raise
