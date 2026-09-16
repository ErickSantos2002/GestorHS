"""estado do espelhamento da empresa no Tiny ERP

Quatro colunas em `empresas`: o id do contato no Tiny e o resultado da ultima
tentativa (status, motivo e quando), que alimentam a coluna "Tiny" da tela e o
botao de reenviar.

Aditiva: nenhuma linha existente e' tocada. Com `TINY_TOKEN` vazio a integracao
fica desligada e as colunas seguem nulas.
"""
import sqlalchemy as sa
from alembic import op

revision = "0031_empresa_tiny"
down_revision = "0030_empresas"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("empresas", sa.Column("tiny_id", sa.Integer, nullable=True))
    op.create_index("ix_empresas_tiny_id", "empresas", ["tiny_id"])
    op.add_column("empresas", sa.Column("tiny_status", sa.String(10), nullable=True))
    op.add_column("empresas", sa.Column("tiny_erro", sa.String(255), nullable=True))
    op.add_column("empresas", sa.Column("tiny_em", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("empresas", "tiny_em")
    op.drop_column("empresas", "tiny_erro")
    op.drop_column("empresas", "tiny_status")
    op.drop_index("ix_empresas_tiny_id", table_name="empresas")
    op.drop_column("empresas", "tiny_id")
