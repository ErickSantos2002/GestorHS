"""solicitacoes: pedidos de recalibracao do portal

Revision ID: 0003_solicitacoes
Revises: 0002_os_schema
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_solicitacoes"
down_revision = "0002_os_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "solicitacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cliente", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("equipamento_cliente", sa.Integer(), sa.ForeignKey("equipamentos_cliente.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pendente"),
        sa.Column("data_solicitacao", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_atendimento", sa.DateTime(timezone=True), nullable=True),
        sa.Column("atendido_por", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("obs", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_table("solicitacoes")
