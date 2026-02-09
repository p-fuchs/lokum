from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import get_current_user
from src.base.dependencies import get_session
from src.query.models import Query, QueryResult
from src.scraping.interface import SearchEngineType
from src.user.models import User

router = APIRouter(prefix="/queries")


class QueryCreate(BaseModel):
    name: str
    search_query: str
    location: str
    search_engine: SearchEngineType = SearchEngineType.OLX
    max_pages: int = 1
    run_interval_hours: int = 24


class QueryUpdate(BaseModel):
    name: str | None = None
    search_query: str | None = None
    location: str | None = None
    search_engine: SearchEngineType | None = None
    max_pages: int | None = None
    run_interval_hours: int | None = None
    is_active: bool | None = None


class QueryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    search_query: str
    location: str
    search_engine: SearchEngineType
    max_pages: int
    is_active: bool
    run_interval_hours: int
    last_run_at: datetime | None
    last_error: str | None
    last_error_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class QueryResultResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    offer_source_id: UUID
    found_at: datetime


async def _get_user_query(
    query_id: UUID,
    user: User,
    session: AsyncSession,
) -> Query:
    stmt = select(Query).where(Query.id == query_id, Query.user_id == user.id)
    query = (await session.execute(stmt)).scalar_one_or_none()
    if query is None:
        raise HTTPException(status_code=404, detail="Query not found")
    return query


@router.get("", response_model=list[QueryResponse])
async def list_queries(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Query]:
    stmt = select(Query).where(Query.user_id == user.id)
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=QueryResponse, status_code=201)
async def create_query(
    body: QueryCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Query:
    query = Query(user_id=user.id, **body.model_dump())
    session.add(query)
    await session.flush()
    return query


@router.get("/{query_id}", response_model=QueryResponse)
async def get_query(
    query_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Query:
    return await _get_user_query(query_id, user, session)


@router.patch("/{query_id}", response_model=QueryResponse)
async def update_query(
    query_id: UUID,
    body: QueryUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Query:
    query = await _get_user_query(query_id, user, session)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(query, key, value)
    await session.flush()
    return query


@router.delete("/{query_id}", status_code=204)
async def delete_query(
    query_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    query = await _get_user_query(query_id, user, session)
    await session.delete(query)


@router.get("/{query_id}/results", response_model=list[QueryResultResponse])
async def list_query_results(
    query_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[QueryResult]:
    await _get_user_query(query_id, user, session)
    stmt = (
        select(QueryResult)
        .where(QueryResult.query_id == query_id)
        .order_by(QueryResult.found_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())
