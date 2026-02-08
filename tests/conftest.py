from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from src.base.models import BaseDbModel

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def olx_offer_html() -> str:
    return (FIXTURES_DIR / "olx_offer.html").read_text()


@pytest.fixture
def olx_search_html() -> str:
    return (FIXTURES_DIR / "olx_search.html").read_text()


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str]:
    with PostgresContainer("postgres:17") as pg:
        # Convert sync URL to async (postgresql:// -> postgresql+asyncpg://)
        sync_url = pg.get_connection_url()
        yield sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")


@pytest.fixture
async def db_engine(postgres_url: str) -> AsyncGenerator[AsyncEngine]:
    # Import all models so metadata knows about them
    import src.user.models  # noqa: F401
    import src.offer.models  # noqa: F401
    import src.query.models  # noqa: F401

    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(BaseDbModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(BaseDbModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()
