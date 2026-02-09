from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.base.dependencies import get_session
from src.user.models import User


async def get_current_user(
    x_user: str = Header(),
    session: AsyncSession = Depends(get_session),
) -> User:
    if ":" not in x_user:
        raise HTTPException(status_code=400, detail="X-User must be 'name:email'")

    name, email = x_user.split(":", maxsplit=1)
    if not name or not email:
        raise HTTPException(
            status_code=400, detail="X-User name and email must not be empty"
        )

    stmt = select(User).where(User.email == email)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user is None:
        user = User(name=name, email=email)
        session.add(user)
        await session.flush()

    return user
