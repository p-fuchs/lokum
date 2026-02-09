from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.offer.models import OfferSourceType
from src.query.models import Query, QueryResult
from src.scheduler import run_pending_queries
from src.scraping.interface import SearchEngineType, SearchResult
from src.user.models import User


async def _make_user_and_query(session: AsyncSession) -> Query:
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


def _make_search_results(count: int = 2) -> list[SearchResult]:
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


@pytest.fixture
def test_session_factory(
    db_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


class TestRunPendingQueries:
    async def test_processes_query_and_stores_results(
        self,
        db_session: AsyncSession,
        test_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        query = await _make_user_and_query(db_session)
        await db_session.commit()
        query_id = query.id

        search_results = _make_search_results(2)
        mock_engine = AsyncMock()
        mock_engine.search.return_value = search_results

        with (
            patch("src.scheduler.async_session", test_session_factory),
            patch("src.scheduler.create_engine", return_value=mock_engine),
        ):
            await run_pending_queries()

        async with test_session_factory() as verify_session:
            results = (
                (
                    await verify_session.execute(
                        select(QueryResult).where(QueryResult.query_id == query_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(results) == 2

            updated_query = await verify_session.get(Query, query_id)
            assert updated_query is not None
            assert updated_query.last_run_at is not None
            assert updated_query.last_error is None

    async def test_stores_error_on_scraping_failure(
        self,
        db_session: AsyncSession,
        test_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        query = await _make_user_and_query(db_session)
        await db_session.commit()
        query_id = query.id

        mock_engine = AsyncMock()
        mock_engine.search.side_effect = RuntimeError("connection timeout")

        with (
            patch("src.scheduler.async_session", test_session_factory),
            patch("src.scheduler.create_engine", return_value=mock_engine),
        ):
            await run_pending_queries()

        async with test_session_factory() as verify_session:
            updated_query = await verify_session.get(Query, query_id)
            assert updated_query is not None
            assert updated_query.last_error is not None
            assert "connection timeout" in updated_query.last_error
            assert updated_query.last_error_at is not None

    async def test_skips_when_no_pending_queries(
        self,
        db_session: AsyncSession,
        test_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        with patch("src.scheduler.async_session", test_session_factory):
            await run_pending_queries()

    async def test_one_failure_does_not_block_others(
        self,
        db_session: AsyncSession,
        test_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        user = User(name="Test", email="test@example.com")
        db_session.add(user)
        await db_session.flush()

        q1 = Query(
            user_id=user.id,
            name="q1",
            search_query="a",
            location="b",
            search_engine=SearchEngineType.OLX,
        )
        q2 = Query(
            user_id=user.id,
            name="q2",
            search_query="c",
            location="d",
            search_engine=SearchEngineType.OLX,
        )
        db_session.add_all([q1, q2])
        await db_session.flush()
        await db_session.commit()
        q1_id, q2_id = q1.id, q2.id

        call_count = 0

        async def mock_search(params: object) -> list[SearchResult]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("fail first")
            return _make_search_results(1)

        mock_engine = AsyncMock()
        mock_engine.search.side_effect = mock_search

        with (
            patch("src.scheduler.async_session", test_session_factory),
            patch("src.scheduler.create_engine", return_value=mock_engine),
        ):
            await run_pending_queries()

        async with test_session_factory() as verify_session:
            failed = await verify_session.get(Query, q1_id)
            assert failed is not None
            assert failed.last_error is not None

            succeeded = await verify_session.get(Query, q2_id)
            assert succeeded is not None
            assert succeeded.last_error is None
            assert succeeded.last_run_at is not None
