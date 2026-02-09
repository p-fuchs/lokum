import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from src.query.router import router as query_router
from src.scheduler import run_pending_queries, run_pending_scrapes

logging.basicConfig(level=logging.INFO)

SCHEDULER_INTERVAL_MINUTES = int(
    os.environ.get("LOKUM_SCHEDULER_INTERVAL_MINUTES", "5")
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_pending_queries,
        "interval",
        minutes=SCHEDULER_INTERVAL_MINUTES,
        id="run_pending_queries",
    )
    scheduler.add_job(
        run_pending_scrapes,
        "interval",
        minutes=SCHEDULER_INTERVAL_MINUTES,
        id="run_pending_scrapes",
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Lokum", lifespan=lifespan)
app.include_router(query_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
