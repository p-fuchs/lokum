from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import get_current_user
from src.user.models import User

import pytest
from fastapi import HTTPException


class TestGetCurrentUser:
    async def test_creates_new_user(self, db_session: AsyncSession) -> None:
        user = await get_current_user(
            x_user="Alice:alice@example.com", session=db_session
        )

        assert user.name == "Alice"
        assert user.email == "alice@example.com"
        assert user.id is not None

    async def test_returns_existing_user(self, db_session: AsyncSession) -> None:
        existing = User(name="Bob", email="bob@example.com")
        db_session.add(existing)
        await db_session.flush()

        user = await get_current_user(x_user="Bob:bob@example.com", session=db_session)

        assert user.id == existing.id

    async def test_rejects_missing_colon(self, db_session: AsyncSession) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(x_user="nocolon", session=db_session)

        assert exc_info.value.status_code == 400

    async def test_rejects_empty_name(self, db_session: AsyncSession) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(x_user=":email@example.com", session=db_session)

        assert exc_info.value.status_code == 400

    async def test_rejects_empty_email(self, db_session: AsyncSession) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(x_user="name:", session=db_session)

        assert exc_info.value.status_code == 400

    async def test_name_with_colons(self, db_session: AsyncSession) -> None:
        user = await get_current_user(
            x_user="First:Last:extra@example.com", session=db_session
        )

        assert user.name == "First"
        assert user.email == "Last:extra@example.com"
