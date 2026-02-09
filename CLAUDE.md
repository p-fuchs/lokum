# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Lokum is a flat rental offer aggregator. It scrapes listings from sites like OLX, parses structured data, and persists deduplicated offers to a database. Python 3.12, managed with [uv](https://docs.astral.sh/uv/).

## Commands

- **Install dependencies:** `uv sync`
- **Start app:** `./lokum.py app` or `uv run uvicorn src.app:app --reload`
- **Type check:** `uv run mypy .` or `./lokum.py lint`
- **Run all tests:** `uv run pytest tests/` or `./lokum.py test`
- **Run a single test file:** `uv run pytest tests/unit/scraping/olx/test_scrape.py`
- **Run a single test:** `uv run pytest tests/unit/scraping/olx/test_scrape.py::TestParseAd::test_price`
- **Database:** `./lokum.py db up` (start), `./lokum.py db down` (stop), `./lokum.py db migrate` (apply migrations)
- **Create migration:** `./lokum.py db revision "description"` (autogenerate from model changes)

### Environment Variables

- **`LOKUM_DATABASE_URI`** (required) — async SQLAlchemy URI (e.g., `postgresql+asyncpg://lokum:lokum@localhost:5432/lokum`)
- **`GOOGLE_API_KEY`** (required for enrichment) — Google AI Studio API key for LLM enrichment
- **`LOKUM_SCHEDULER_INTERVAL_MINUTES`** (optional, default 5) — interval for search and scraping jobs

## Architecture

The system runs two independent scheduled jobs:

1. **Search Job** (`run_pending_queries`) — Fast, runs frequently
   - Searches listing pages → discovers URLs
   - Creates/updates `Offer` + `OfferSource` pairs (lightweight)

2. **Scraping + Enrichment Job** (`run_pending_scrapes`) — Slow, runs independently
   - Fetches `OfferSource` records without data or with stale data (>2 weeks)
   - Scrapes individual pages → extracts detailed structured data
   - Enriches with LLM (Google Gemini) → extracts addresses, summaries, cost breakdowns
   - Stores in `OfferRawInfo` (1:1 with `OfferSource`)
   - Consolidates data back into `Offer` records

### Scraping Layer (`src/scraping/`)

Three ABC hierarchies in `interface.py`, all using factory pattern with `create(cls, client: httpx.AsyncClient) -> Self`:

- **`SearchEngine`** → `SearchResult` (lightweight: title, price string, URL)
- **`ScrapingEngine`** → `ScrapingResult` (parsed: price float, area, rooms, floor, furnished, pets, elevator, parking, building_type, photos)
- **`EnrichmentEngine`** → `EnrichmentResult` (LLM-extracted: summary, geocodable address, cost breakdown)

Factories in `__init__.py`: `create_engine()`, `create_scraper()`, `create_enricher()`.

**OLX implementation** (`src/scraping/olx/`):
- `OlxSearchEngine` — regex-based HTML parsing of search result pages (no BeautifulSoup)
- `OlxOfferScraper` — extracts `window.__PRERENDERED_STATE__` JSON from offer pages. JSON at `state["ad"]["ad"]`.

**Pipeline** (`src/scraping/pipeline.py`):
- `PipelineItem` — tracks items through scraping → enrichment stages
- `run_pipeline()` — orchestrates per-item scraping + enrichment with failure isolation

**Enrichment** (`src/scraping/enrichment/`):
- `LangChainEnrichmentEngine` — uses Google Gemini 2.5 Flash Lite via LangChain
- Extracts: compact summaries, street-level addresses for geocoding, cost breakdowns
- Stores traceability info in `MaintenanceData` (model name, duration, notes)

### Offer Layer (`src/offer/`)

**Data Model Hierarchy:**
```
Offer (deduplicated listing, consolidated view)
  ├─ OfferSource (per-site URL, 1 per scraping source)
  │    └─ OfferRawInfo (1:1, all scraped + enriched data)
  └─ QueryResult (N:M join with Query)
```

- **`models.py`** — `Offer`, `OfferSource`, `OfferRawInfo`. `OfferSourceType` enum tracks which site.
- **`resolver.py`** — `resolve_offers()` deduplicates by URL, `persist_pipeline_results()` saves scraping/enrichment results
- **`consolidation.py`** — `consolidate_offer()` updates `Offer` from its `OfferRawInfo` records (enriched data wins)
- **`price.py`** — `Currency` enum, `ParsedPrice` pydantic model, `parse_price()` for raw price string parsing

### Scheduler (`src/scheduler.py`)

Two independent jobs (both scheduled in `src/app.py` lifespan):
- `run_pending_queries()` — search job (lightweight)
- `run_pending_scrapes()` — scraping + enrichment job (heavy)

**Critical pattern:** Never hold DB session during HTTP/LLM work. Pattern is:
1. Open session → fetch data → map to DTOs (frozen dataclasses) → close session
2. Do slow work (HTTP, LLM) with DTOs
3. Open new session → write results → close session

### API & Query Management (`src/query/`)

- **Query model** — user-defined search (location, search_query, interval, active flag)
- **QueryResult** — N:M join tracking which OfferSources match which Queries
- **Router** (`src/query/router.py`) — CRUD endpoints: GET/POST /queries, GET/PATCH/DELETE /queries/{id}, GET /queries/{id}/results

### Base Layer (`src/base/`)

- `models.py` — `BaseDbModel` with UUID pk and timestamp columns, `UTCDateTime` type
- `schemas.py` — `PydanticJSONB` SQLAlchemy type for storing pydantic models as JSON/JSONB
- `maintenance.py` — `MaintenanceData` pydantic model for LLM traceability
- `db.py` — async engine/session factory (reads `LOKUM_DATABASE_URI`)
- `dependencies.py` — FastAPI dependencies (session with auto-commit/rollback)

## Conventions

### Code Style & Structure

- **Interface types are frozen dataclasses.** Pydantic models are used only for serialization/JSONB storage (`ParsedPrice`, `MaintenanceData`).
- **Imports at the top of the module** (use `TYPE_CHECKING` for circular imports).
- **HTML parsing uses regex** (no BeautifulSoup dependency).
- **All scraping engines** receive `httpx.AsyncClient` via `create()` classmethod, not `__init__` directly.

### Database & Sessions

- **SQLAlchemy ORM objects are bound to the session that loaded them.** Never use an ORM object after its session is closed — access to attributes (especially lazy-loaded) will fail. When data needs to cross session boundaries, map it to a plain DTO (frozen dataclass) while the session is still open.
- **Keep DB sessions short — never hold one open during long-running work** (HTTP requests, scraping, external API calls, LLM calls). Pattern: open session → fetch data → map to DTOs → close session → do slow work → open new session → write results. See `src/scheduler.py` for the reference implementation.

### Testing

- Tests live in `tests/unit/` and `tests/integration/`. HTML fixtures in `tests/fixtures/`. Shared fixtures in `tests/conftest.py`.
- pytest runs with `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio`).
- **Always run `uv run mypy .` after making changes** and fix any type errors before considering the task done.
- **Always consider adding tests** for new or changed code. Tests should cover the happy path and key edge cases. Router tests use `httpx.AsyncClient` with `ASGITransport` and dependency overrides.

### API Details

- FastAPI app in `src/app.py`
- Mock auth via `X-User: name:email` header — auto-creates users (defined in `src/auth.py`)
- APScheduler v3 (AsyncIOScheduler) runs in FastAPI lifespan
- Docker: `docker-compose.yml` runs PostgreSQL only, app runs locally
- Management CLI: `./lokum.py` — click CLI with subcommands (app, db, test, lint)
