"""add_users_queries_and_error_fields

Revision ID: 5036af908fac
Revises: e7af82dec41a
Create Date: 2026-02-08 01:40:24.290252

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5036af908fac"
down_revision: Union[str, Sequence[str], None] = "e7af82dec41a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "queries",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("search_query", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column(
            "search_engine", sa.Enum("OLX", name="searchenginetype"), nullable=False
        ),
        sa.Column("max_pages", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("run_interval_hours", sa.Integer(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "query_results",
        sa.Column("query_id", sa.Uuid(), nullable=False),
        sa.Column("offer_source_id", sa.Uuid(), nullable=False),
        sa.Column("found_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["offer_source_id"],
            ["offer_sources.id"],
        ),
        sa.ForeignKeyConstraint(
            ["query_id"],
            ["queries.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("query_id", "offer_source_id", name="uq_query_source"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("query_results")
    op.drop_table("queries")
    op.drop_table("users")
