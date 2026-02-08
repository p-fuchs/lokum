from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.offer.models import OfferSourceType
from src.query.executor import execute_query
from src.query.models import Query, QueryResult
from src.scraping.interface import SearchEngineType, SearchResult
from src.user.models import User


def _make_search_results(count: int = 3) -> list[SearchResult]:
    return [
        SearchResult(
            url=f"https://www.olx.pl/d/oferta/test-{i}.html",
            title=f"Test offer {i}",
            source_type=OfferSourceType.OLX,
            price=f"{1000 + i * 100} zł",
            location="Warszawa",
        )
        for i in range(count)
    ]


async def _setup_user_and_query(session: AsyncSession) -> Query:
    user = User(name="Test", email="test@example.com")
    session.add(user)
    await session.flush()

    query = Query(
        user_id=user.id,
        name="Test query",
        search_query="kawalerka",
        location="warszawa",
        search_engine=SearchEngineType.OLX,
    )
    session.add(query)
    await session.flush()
    return query


class TestExecuteQuery:
    async def test_creates_query_results(self, db_session: AsyncSession) -> None:
        query = await _setup_user_and_query(db_session)
        search_results = _make_search_results(3)

        with patch("src.query.executor.search_and_resolve") as mock_resolve:
            # search_and_resolve returns offers; we need to simulate the
            # full pipeline to get real Offer+OfferSource objects in the DB
            from src.offer.resolver import resolve_offers

            offers = await resolve_offers(db_session, search_results)
            await db_session.flush()
            mock_resolve.return_value = offers

            results = await execute_query(db_session, query)

        assert len(results) == 3
        for r in results:
            assert r.query_id == query.id
            assert r.offer_source_id is not None

    async def test_updates_last_run_at(self, db_session: AsyncSession) -> None:
        query = await _setup_user_and_query(db_session)
        assert query.last_run_at is None

        with patch("src.query.executor.search_and_resolve") as mock_resolve:
            from src.offer.resolver import resolve_offers

            offers = await resolve_offers(db_session, _make_search_results(1))
            await db_session.flush()
            mock_resolve.return_value = offers

            await execute_query(db_session, query)

        assert query.last_run_at is not None
        assert (datetime.now(timezone.utc) - query.last_run_at).total_seconds() < 5

    async def test_no_duplicate_results_on_rerun(
        self, db_session: AsyncSession
    ) -> None:
        query = await _setup_user_and_query(db_session)
        search_results = _make_search_results(2)

        with patch("src.query.executor.search_and_resolve") as mock_resolve:
            from src.offer.resolver import resolve_offers

            offers = await resolve_offers(db_session, search_results)
            await db_session.flush()
            mock_resolve.return_value = offers

            first_run = await execute_query(db_session, query)
            await db_session.flush()
            assert len(first_run) == 2

            # Re-run with same offers
            second_run = await execute_query(db_session, query)
            assert len(second_run) == 0

        # Total in DB should still be 2
        all_results = (await db_session.execute(select(QueryResult))).scalars().all()
        assert len(all_results) == 2

    async def test_empty_search_results(self, db_session: AsyncSession) -> None:
        query = await _setup_user_and_query(db_session)

        with patch(
            "src.query.executor.search_and_resolve",
            new_callable=AsyncMock,
            return_value=[],
        ):
            results = await execute_query(db_session, query)

        assert len(results) == 0
        assert query.last_run_at is not None

    async def test_results_link_to_correct_sources(
        self, db_session: AsyncSession
    ) -> None:
        query = await _setup_user_and_query(db_session)
        search_results = _make_search_results(2)

        with patch("src.query.executor.search_and_resolve") as mock_resolve:
            from src.offer.resolver import resolve_offers

            offers = await resolve_offers(db_session, search_results)
            await db_session.flush()
            mock_resolve.return_value = offers

            results = await execute_query(db_session, query)

        # Look up the actual OfferSource objects by ID
        source_ids = {r.offer_source_id for r in results}
        from src.offer.models import OfferSource

        stmt = select(OfferSource).where(OfferSource.id.in_(source_ids))
        sources = (await db_session.execute(stmt)).scalars().all()
        source_urls = {s.url for s in sources}

        expected_urls = {sr.url for sr in search_results}
        assert source_urls == expected_urls
