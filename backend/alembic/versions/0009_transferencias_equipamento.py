"""transferencias_equipamento — auditoria de transferencia de aparelho entre empresas

Revision ID: 0009_transferencias_equipamento
Revises: 0008_cert_overrides
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_transferencias_equipamento"
down_revision = "0008_cert_overrides"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transferencias_equipamento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("equipamento_cliente", sa.Integer(), sa.ForeignKey("equipamentos_cliente.id"), nullable=False),
        sa.Column("de_cliente", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("para_cliente", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("data", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usuario", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("obs", sa.Text(), nullable=True),
    )
    op.create_index("ix_transferencias_equipamento_id", "transferencias_equipamento", ["id"])


def downgrade():
    op.drop_index("ix_transferencias_equipamento_id", table_name="transferencias_equipamento")
    op.drop_table("transferencias_equipamento")
