"""caixa: coluna numero_proposta (numero da proposta vinda do GrowthHS)"""
import sqlalchemy as sa
from alembic import op

revision = "0023_caixa_numero_proposta"
down_revision = "0022_proposta_faturada"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("caixas", sa.Column("numero_proposta", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("caixas", "numero_proposta")
