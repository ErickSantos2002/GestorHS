"""proposta: coluna faturada (+ faturada_em/por)"""
import sqlalchemy as sa
from alembic import op

revision = "0022_proposta_faturada"
down_revision = "0021_caixa_cliente_principal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("propostas", sa.Column("faturada", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("propostas", sa.Column("faturada_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("propostas", sa.Column("faturada_por", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("propostas", "faturada_por")
    op.drop_column("propostas", "faturada_em")
    op.drop_column("propostas", "faturada")
