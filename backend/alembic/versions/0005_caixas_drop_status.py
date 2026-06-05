"""caixas: remove a coluna status (caixa não tem ciclo de vida próprio)

Revision ID: 0005_caixas_drop_status
Revises: 0004_caixas_fk
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_caixas_drop_status"
down_revision = "0004_caixas_fk"
branch_labels = None
depends_on = None


def upgrade():
    # A caixa virou só um agrupamento de acesso rápido às OS — sem status próprio
    # (a OS já tem o seu fechamento). A CHECK constraint do status sai junto com a coluna.
    op.drop_column("caixas", "status")


def downgrade():
    op.add_column(
        "caixas",
        sa.Column("status", sa.String(length=1), nullable=False, server_default="P"),
    )
    op.create_check_constraint(
        "caixas_status_check", "caixas", "status IN ('P','A','F')"
    )
