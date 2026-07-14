"""ordens: anexo e numero da nota fiscal de servico

Revision ID: 0013_nota_fiscal
Revises: 0012_usuario_email_credencial
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_nota_fiscal"
down_revision = "0012_usuario_email_credencial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ordens", sa.Column("nota_fiscal", sa.String(50), nullable=True))
    op.add_column("ordens", sa.Column("nota_fiscal_numero", sa.String(50), nullable=True))


def downgrade():
    op.drop_column("ordens", "nota_fiscal_numero")
    op.drop_column("ordens", "nota_fiscal")
