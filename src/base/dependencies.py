from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.base.db import async_session


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
