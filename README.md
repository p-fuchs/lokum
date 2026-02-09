# Lokum 🍬

A flat rental offer aggregator for Poland. Scrapes listings from OLX, enriches them with an LLM, and serves them through a REST API.

> **lokum** — *Turkish delight; also Polish slang for a cozy apartment*

## How it works

```
                     ┌──────────────────────────────────┐
                     │          FastAPI + Scheduler      │
                     └──┬──────────────────────────┬────┘
                        │                          │
              ┌─────────▼─────────┐    ┌───────────▼───────────┐
              │   Search Job      │    │   Scraping Job         │
              │   (fast, frequent)│    │   (slow, independent)  │
              └─────────┬─────────┘    └───────────┬───────────┘
                        │                          │
              Search listing pages         For each OfferSource:
              Discover URLs                ┌───────┴────────┐
              Create Offer+OfferSource     │  Scrape page   │
                                           │  (OLX JSON)    │
                                           └───────┬────────┘
                                                   │
                                           ┌───────┴────────┐
                                           │  LLM Enrich    │
                                           │  (Gemini)      │
                                           └───────┬────────┘
                                                   │
                                           ┌───────┴────────┐
                                           │  Consolidate   │
                                           │  → Offer       │
                                           └────────────────┘
```

**Search** discovers listings and stores lightweight references. **Scraping** fills in the details — structured data from the page plus LLM-extracted summaries, street addresses, and cost breakdowns. Both jobs run independently on a schedule.

## Data model

```
Offer (consolidated, deduplicated)
  ├── OfferSource (one per site/URL)
  │     └── OfferRawInfo (scraped + enriched data)
  └── QueryResult (links to user Queries)
```

## Tech stack

| Layer | Tech |
|---|---|
| Runtime | Python 3.12, uv |
| API | FastAPI, uvicorn |
| DB | PostgreSQL, SQLAlchemy 2 (async), Alembic |
| Scraping | httpx, regex (no BS4) |
| Enrichment | LangChain + Google Gemini 2.5 Flash Lite |
| Scheduling | APScheduler v3 |

## Quick start

```bash
# Install
uv sync

# Start Postgres
./lokum.py db up

# Run migrations
./lokum.py db migrate

# Start the app (includes scheduler)
./lokum.py app
```

Requires `LOKUM_DATABASE_URI` and `GOOGLE_API_KEY` env vars. See `CLAUDE.md` for full details.

## CLI

```
./lokum.py app                          # start uvicorn with --reload
./lokum.py db up|down|migrate|revision  # manage postgres + migrations
./lokum.py test                         # run pytest
./lokum.py lint                         # run mypy
```
