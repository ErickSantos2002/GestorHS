"""elo phoebus<->modulo: instalacoes com historico

Revision ID: 0016_instalacao_modulo
Revises: 0015_certificado_geral
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_instalacao_modulo"
down_revision = "0015_certificado_geral"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "instalacoes_modulo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("modulo", sa.Integer(), sa.ForeignKey("equipamentos_cliente.id"), nullable=False),
        sa.Column("phoebus", sa.Integer(), sa.ForeignKey("equipamentos_cliente.id"), nullable=False),
        sa.Column("entrou_em", sa.Date(), nullable=True),
        sa.Column("saiu_em", sa.Date(), nullable=True),
        sa.Column("origem", sa.String(100), nullable=True),
    )
    op.create_index("uq_instalacao_modulo_aberta", "instalacoes_modulo", ["modulo"],
                    unique=True, postgresql_where=sa.text("saiu_em IS NULL"))
    op.create_index("uq_instalacao_phoebus_aberta", "instalacoes_modulo", ["phoebus"],
                    unique=True, postgresql_where=sa.text("saiu_em IS NULL"))


def downgrade():
    op.drop_index("uq_instalacao_phoebus_aberta", table_name="instalacoes_modulo")
    op.drop_index("uq_instalacao_modulo_aberta", table_name="instalacoes_modulo")
    op.drop_table("instalacoes_modulo")
