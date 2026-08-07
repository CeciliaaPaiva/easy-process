"""make timestamp columns timezone-aware

Revision ID: 004
Revises: 003
Create Date: 2026-07-15

Todas as colunas `created_at`/`updated_at` foram criadas como
`TIMESTAMP WITHOUT TIME ZONE`, mas sempre armazenaram instantes em UTC
(`datetime.utcnow()` no ORM / `now()` no server_default, que no Postgres
retorna o horário da sessão, não necessariamente UTC). Sem o offset, o
frontend interpretava a string ISO como horário local do navegador em vez
de UTC, exibindo os horários adiantados (ver painel "Uso de IA").

Esta migration converte as colunas para `TIMESTAMP WITH TIME ZONE`,
assumindo que os valores existentes já estão em UTC.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | None = None
depends_on: str | None = None

_COLUMNS = [
    ("tenants", "created_at"),
    ("users", "created_at"),
    ("projects", "created_at"),
    ("projects", "updated_at"),
    ("processes", "created_at"),
    ("processes", "updated_at"),
    ("process_versions", "created_at"),
    ("chat_messages", "created_at"),
    ("llm_usage_logs", "created_at"),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=True),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
            existing_nullable=False,
        )


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=False),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
            existing_nullable=False,
        )
