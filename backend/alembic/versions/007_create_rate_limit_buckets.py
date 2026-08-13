"""create rate_limit_buckets

Revision ID: 007
Revises: 006
Create Date: 2026-08-12

Rate limiting real (upload de áudio, refinamento via chat, registro e
login) — regra listada como inegociável no CLAUDE.md mas nunca implementada
até agora. Ver app/core/rate_limit.py.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", "window_start", name="uq_rate_limit_bucket"),
    )
    op.create_index(
        "ix_rate_limit_buckets_key", "rate_limit_buckets", ["key"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_rate_limit_buckets_key", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
