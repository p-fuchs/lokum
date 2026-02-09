from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from src.base.dependencies import get_session
from src.query.models import Query, QueryResult
from src.query.router import router
from src.scraping.interface import SearchEngineType
from src.user.models import User


@pytest.fixture
def app(db_session: AsyncSession) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)

    async def override_session() -> AsyncSession:  # type: ignore[misc]
        yield db_session  # type: ignore[misc]

    test_app.dependency_overrides[get_session] = override_session
    return test_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(name="Test", email="test@example.com")
    db_session.add(u)
    await db_session.flush()
    return u


@pytest.fixture
def auth_header() -> dict[str, str]:
    return {"X-User": "Test:test@example.com"}


@pytest.fixture
async def sample_query(db_session: AsyncSession, user: User) -> Query:
    q = Query(
        user_id=user.id,
        name="My query",
        search_query="kawalerka",
        location="warszawa",
        search_engine=SearchEngineType.OLX,
    )
    db_session.add(q)
    await db_session.flush()
    return q


class TestCreateQuery:
    async def test_creates_query(
        self, client: httpx.AsyncClient, user: User, auth_header: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/queries",
            json={
                "name": "New query",
                "search_query": "kawalerka",
                "location": "warszawa",
            },
            headers=auth_header,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New query"
        assert data["search_engine"] == "olx"
        assert data["max_pages"] == 1
        assert data["is_active"] is True

    async def test_requires_auth(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/queries",
            json={"name": "x", "search_query": "y", "location": "z"},
        )

        assert resp.status_code == 422


class TestListQueries:
    async def test_lists_own_queries(
        self,
        client: httpx.AsyncClient,
        sample_query: Query,
        auth_header: dict[str, str],
    ) -> None:
        resp = await client.get("/queries", headers=auth_header)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "My query"

    async def test_does_not_list_other_users_queries(
        self,
        client: httpx.AsyncClient,
        sample_query: Query,
    ) -> None:
        resp = await client.get(
            "/queries", headers={"X-User": "Other:other@example.com"}
        )

        assert resp.status_code == 200
        assert resp.json() == []


class TestGetQuery:
    async def test_returns_query(
        self,
        client: httpx.AsyncClient,
        sample_query: Query,
        auth_header: dict[str, str],
    ) -> None:
        resp = await client.get(f"/queries/{sample_query.id}", headers=auth_header)

        assert resp.status_code == 200
        assert resp.json()["name"] == "My query"

    async def test_404_for_nonexistent(
        self, client: httpx.AsyncClient, user: User, auth_header: dict[str, str]
    ) -> None:
        resp = await client.get(f"/queries/{uuid4()}", headers=auth_header)

        assert resp.status_code == 404

    async def test_404_for_other_users_query(
        self,
        client: httpx.AsyncClient,
        sample_query: Query,
    ) -> None:
        resp = await client.get(
            f"/queries/{sample_query.id}",
            headers={"X-User": "Other:other@example.com"},
        )

        assert resp.status_code == 404


class TestUpdateQuery:
    async def test_partial_update(
        self,
        client: httpx.AsyncClient,
        sample_query: Query,
        auth_header: dict[str, str],
    ) -> None:
        resp = await client.patch(
            f"/queries/{sample_query.id}",
            json={"name": "Updated", "is_active": False},
            headers=auth_header,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated"
        assert data["is_active"] is False
        assert data["search_query"] == "kawalerka"  # unchanged


class TestDeleteQuery:
    async def test_deletes_query(
        self,
        client: httpx.AsyncClient,
        sample_query: Query,
        auth_header: dict[str, str],
    ) -> None:
        resp = await client.delete(f"/queries/{sample_query.id}", headers=auth_header)

        assert resp.status_code == 204

        resp = await client.get(f"/queries/{sample_query.id}", headers=auth_header)
        assert resp.status_code == 404


class TestListQueryResults:
    async def test_lists_results(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        sample_query: Query,
        auth_header: dict[str, str],
    ) -> None:
        from datetime import datetime, timezone
        from src.offer.models import Offer, OfferSource, OfferSourceType

        offer = Offer(title="Test", location="Warszawa")
        db_session.add(offer)
        await db_session.flush()

        source = OfferSource(
            offer_id=offer.id,
            source_type=OfferSourceType.OLX,
            url="https://olx.pl/test",
            scraped_at=datetime.now(timezone.utc),
        )
        db_session.add(source)
        await db_session.flush()

        result = QueryResult(
            query_id=sample_query.id,
            offer_source_id=source.id,
            found_at=datetime.now(timezone.utc),
        )
        db_session.add(result)
        await db_session.flush()

        resp = await client.get(
            f"/queries/{sample_query.id}/results", headers=auth_header
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["offer_source_id"] == str(source.id)

    async def test_404_for_nonexistent_query(
        self, client: httpx.AsyncClient, user: User, auth_header: dict[str, str]
    ) -> None:
        resp = await client.get(f"/queries/{uuid4()}/results", headers=auth_header)

        assert resp.status_code == 404
