# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Lokum is a flat rental offer aggregator. It scrapes listings from sites like OLX, parses structured data, and persists deduplicated offers to a database. Python 3.12, managed with [uv](https://docs.astral.sh/uv/).

## Commands

- **Install dependencies:** `uv sync`
- **Run:** `uv run python playground.py`
- **Type check:** `uv run mypy .`
- **Run all tests:** `uv run pytest tests/`
- **Run a single test file:** `uv run pytest tests/unit/scraping/olx/test_scrape.py`
- **Run a single test:** `uv run pytest tests/unit/scraping/olx/test_scrape.py::TestParseAd::test_price`
- **Database requires:** `LOKUM_DATABASE_URI` env var (async SQLAlchemy URI)

## Architecture

The pipeline has three stages: **search** → **scrape** → **resolve**.

### Scraping layer (`src/scraping/`)

Two parallel ABC hierarchies in `interface.py`, both using the same factory pattern:
- **`SearchEngine`** — searches listing pages, returns `SearchResult` (lightweight: title, price string, URL)
- **`ScrapingEngine`** — scrapes individual offer pages, returns `ScrapingResult` (parsed: float price, area, rooms, photos, etc.)

Both use `create(cls, client: httpx.AsyncClient) -> Self` classmethod pattern. Factories in `__init__.py`: `create_engine()` and `create_scraper()`.

OLX implementation (`src/scraping/olx/`):
- **`OlxSearchEngine`** — regex-based HTML parsing of search result pages (no BeautifulSoup)
- **`OlxOfferScraper`** — extracts `window.__PRERENDERED_STATE__` JSON from offer pages (structured data, not HTML parsing). The JSON lives at `state["ad"]["ad"]`.

### Offer layer (`src/offer/`)

- **`models.py`** — SQLAlchemy models: `Offer` (deduplicated listing) has many `OfferSource` (per-site occurrence). `OfferSourceType` enum tracks which site.
- **`resolver.py`** — `resolve_offers()` deduplicates by URL: updates existing or creates new `Offer`+`OfferSource` pairs. `search_and_resolve()` orchestrates concurrent search + resolve.
- **`price.py`** — `Currency` enum, `ParsedPrice` pydantic model, `parse_price()` for raw price string parsing.

### Base layer (`src/base/`)

- `models.py` — `BaseDbModel` with UUID pk and timestamp columns, `UTCDateTime` type
- `schemas.py` — `PydanticJSONB` SQLAlchemy type for storing pydantic models as JSON/JSONB
- `db.py` — async engine/session factory (reads `LOKUM_DATABASE_URI`)

## Conventions

- Interface types are **frozen dataclasses**. Pydantic models are used only for serialization (`ParsedPrice`).
- HTML parsing uses **regex** (no BeautifulSoup dependency).
- Imports are to be present at the top of a module!
- All scraping engines receive an `httpx.AsyncClient` via `create()`, not `__init__` directly.
- Tests live in `tests/unit/` and `tests/integration/`. HTML fixtures in `tests/fixtures/`. Shared fixtures in `tests/conftest.py`.
- pytest runs with `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio`).
- **SQLAlchemy ORM objects are bound to the session that loaded them.** Never use an ORM object after its session is closed — access to attributes (especially lazy-loaded) will fail. When data needs to cross session boundaries, map it to a plain DTO (frozen dataclass) while the session is still open.
- **Keep DB sessions short — never hold one open during long-running work** (HTTP requests, scraping, external API calls). Pattern: open session → fetch data → map to DTOs → close session → do slow work → open new session → write results. See `src/scheduler.py` for the reference implementation.
- **Always run `uv run mypy .` after making changes** and fix any type errors before considering the task done.
- **Always consider adding tests** for new or changed code. Tests should cover the happy path and key edge cases. Router tests use `httpx.AsyncClient` with `ASGITransport` and dependency overrides.

## API & Scheduler (dirty notes)

- FastAPI app in `src/app.py`, run with `./lokum.py app` or `uv run uvicorn src.app:app --reload`
- Mock auth via `X-User: name:email` header — auto-creates users, defined in `src/auth.py`
- Session dependency in `src/base/dependencies.py` (auto-commit/rollback)
- Query CRUD router in `src/query/router.py`: GET/POST /queries, GET/PATCH/DELETE /queries/{id}, GET /queries/{id}/results
- APScheduler v3 (AsyncIOScheduler) runs in FastAPI lifespan, interval via LOKUM_SCHEDULER_INTERVAL_MINUTES (default 5)
- Scheduler logic in `src/scheduler.py`: per-query error handling, stores last_error on Query model
- Docker: `docker-compose.yml` has postgres only, app runs locally
- Management: `python lokum.py` — click CLI with subcommands: app, db up/down/migrate/revision, test, lint
- DB URI: LOKUM_DATABASE_URI=postgresql+asyncpg://lokum:lokum@localhost:5432/lokum
