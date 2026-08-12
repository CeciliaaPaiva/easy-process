"""add error_message to processes

Revision ID: 006
Revises: 005
Create Date: 2026-08-12

Quando o pipeline falha (status="error"), a causa real da falha só ia pro
log do servidor (`logger.exception` em `workers/process_audio.py`) — o
usuário via só um "Erro no processamento" genérico na UI, sem nenhuma pista
do que aconteceu (ex: "não foi possível identificar fala no áudio enviado",
"transcrição muito curta"). Esta coluna guarda a mensagem da exceção que
derrubou o pipeline, para exibir ao usuário.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "processes",
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("processes", "error_message")
