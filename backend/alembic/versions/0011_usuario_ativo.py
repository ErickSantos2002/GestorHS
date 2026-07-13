"""usuario: coluna ativo (soft delete)

Revision ID: 0011_usuario_ativo
Revises: 0010_etapa_financeiro
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_usuario_ativo"
down_revision = "0010_etapa_financeiro"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "usuarios",
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade():
    op.drop_column("usuarios", "ativo")
