from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.query.executor import get_pending_queries
from src.query.models import Query
from src.scraping.interface import SearchEngineType
from src.user.models import User


async def _make_user(session: AsyncSession) -> User:
    user = User(name="Test", email="test@example.com")
    session.add(user)
    await session.flush()
    return user


async def _make_query(
    session: AsyncSession,
    user: User,
    *,
    is_active: bool = True,
    run_interval_hours: int = 24,
    last_run_at: datetime | None = None,
) -> Query:
    query = Query(
        user_id=user.id,
        name="Test query",
        search_query="kawalerka",
        location="warszawa",
        search_engine=SearchEngineType.OLX,
        is_active=is_active,
        run_interval_hours=run_interval_hours,
        last_run_at=last_run_at,
    )
    session.add(query)
    await session.flush()
    return query


class TestGetPendingQueries:
    async def test_returns_never_run_queries(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        await _make_query(db_session, user, last_run_at=None)

        pending = await get_pending_queries(db_session)
        assert len(pending) == 1

    async def test_returns_queries_past_interval(
        self, db_session: AsyncSession
    ) -> None:
        user = await _make_user(db_session)
        long_ago = datetime.now(timezone.utc) - timedelta(hours=48)
        await _make_query(db_session, user, run_interval_hours=24, last_run_at=long_ago)

        pending = await get_pending_queries(db_session)
        assert len(pending) == 1

    async def test_skips_inactive_queries(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        await _make_query(db_session, user, is_active=False)

        pending = await get_pending_queries(db_session)
        assert len(pending) == 0

    async def test_skips_recently_run_queries(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        await _make_query(db_session, user, run_interval_hours=24, last_run_at=recent)

        pending = await get_pending_queries(db_session)
        assert len(pending) == 0

    async def test_mixed_queries(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session)
        # Should be returned: never run
        await _make_query(db_session, user, last_run_at=None)
        # Should be skipped: inactive
        await _make_query(db_session, user, is_active=False)
        # Should be skipped: ran recently
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        await _make_query(db_session, user, run_interval_hours=24, last_run_at=recent)

        pending = await get_pending_queries(db_session)
        assert len(pending) == 1
