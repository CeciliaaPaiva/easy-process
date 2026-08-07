"""add is_platform_admin to users

Revision ID: 005
Revises: 004
Create Date: 2026-07-15

Distingue admin de tenant (role="admin", gerencia membros do próprio
workspace) de admin da plataforma (is_platform_admin=True, acessa dados
agregados entre tenants como o painel de Uso de IA). Sem essa coluna,
qualquer cliente com role="admin" no seu próprio tenant conseguia acessar
/admin/usage.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_platform_admin")
