"""estado do espelhamento do cliente no Tiny ERP

Quatro colunas em `clientes`, espelho da 0031 (empresas): o id do contato no
Tiny e o resultado da ultima tentativa. So o Cliente que recebe proposta e'
espelhado — e so criado ou adotado, nunca alterado (ver a spec de 23/09/2026).

Aditiva: nenhuma linha existente e' tocada.
"""
import sqlalchemy as sa
from alembic import op

revision = "0032_cliente_tiny"
down_revision = "0031_empresa_tiny"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clientes", sa.Column("tiny_id", sa.Integer, nullable=True))
    op.create_index("ix_clientes_tiny_id", "clientes", ["tiny_id"])
    op.add_column("clientes", sa.Column("tiny_status", sa.String(10), nullable=True))
    op.add_column("clientes", sa.Column("tiny_erro", sa.String(255), nullable=True))
    op.add_column("clientes", sa.Column("tiny_em", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("clientes", "tiny_em")
    op.drop_column("clientes", "tiny_erro")
    op.drop_column("clientes", "tiny_status")
    op.drop_index("ix_clientes_tiny_id", table_name="clientes")
    op.drop_column("clientes", "tiny_id")
