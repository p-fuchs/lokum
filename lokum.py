#!/usr/bin/env python3
"""Lokum management CLI."""

import os
import subprocess
import sys

import click


def _run(args: list[str], *, replace: bool = False) -> None:
    click.echo(
        f"  {click.style('>', dim=True)} {click.style(' '.join(args), dim=True)}\n"
    )
    if replace:
        os.execvp(args[0], args)
    result = subprocess.run(args)
    if result.returncode != 0:
        click.echo(
            f"  {click.style('✗', fg='red')} exited with code {result.returncode}"
        )
        sys.exit(result.returncode)


def _ok(text: str) -> None:
    click.echo(f"  {click.style('✓', fg='green')} {text}")


def _header(text: str) -> None:
    click.echo(f"\n  {click.style(text, fg='cyan', bold=True)}\n")


@click.group()
def cli() -> None:
    """Lokum management CLI."""


@cli.command()
@click.argument("uvicorn_args", nargs=-1)
def app(uvicorn_args: tuple[str, ...]) -> None:
    """Start uvicorn with --reload."""
    _header("Starting Lokum")
    _run(
        ["uv", "run", "uvicorn", "src.app:app", "--reload", *uvicorn_args], replace=True
    )


@cli.group()
def db() -> None:
    """Database management commands."""


@db.command()
def up() -> None:
    """Start PostgreSQL (docker compose up)."""
    _header("Starting PostgreSQL")
    _run(["docker", "compose", "up", "-d"])
    _ok("PostgreSQL is running")


@db.command()
def down() -> None:
    """Stop PostgreSQL (docker compose down)."""
    _header("Stopping PostgreSQL")
    _run(["docker", "compose", "down"])
    _ok("PostgreSQL stopped")


@db.command()
def migrate() -> None:
    """Run alembic upgrade head."""
    _header("Running migrations")
    _run(["uv", "run", "alembic", "upgrade", "head"])
    _ok("Migrations applied")


@db.command()
@click.argument("message", default="auto")
def revision(message: str) -> None:
    """Generate alembic migration."""
    _header(f"Generating migration: {message}")
    _run(["uv", "run", "alembic", "revision", "--autogenerate", "-m", message])
    _ok("Migration generated")


@cli.command()
@click.argument("pytest_args", nargs=-1)
def test(pytest_args: tuple[str, ...]) -> None:
    """Run pytest."""
    _header("Running tests")
    _run(["uv", "run", "pytest", "tests/", "-v", *pytest_args], replace=True)


@cli.command()
def lint() -> None:
    """Run mypy."""
    _header("Running mypy")
    _run(["uv", "run", "mypy", "."])
    _ok("Type check passed")


if __name__ == "__main__":
    cli()
