# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Lokum is a Python 3.12 project managed with [uv](https://docs.astral.sh/uv/). Entry point is `main.py`.

## Commands

- **Install dependencies:** `uv sync`
- **Run:** `uv run python main.py`
- **Type check:** `uv run mypy .`

## Dependencies

- `httpx` — HTTP client
- `mypy` — static type checking (dev dependency listed in main deps)
