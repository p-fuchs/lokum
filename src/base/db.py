import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URI = os.environ["LOKUM_DATABASE_URI"]

engine = create_async_engine(DATABASE_URI)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
