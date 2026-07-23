"""propostas tecnicas: catalogos servico/produto + proposta/itens/aparelhos/versoes"""
import sqlalchemy as sa
from alembic import op

revision = "0020_propostas"
down_revision = "0019_caixa_unidade_movimento"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "servicos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("unidade", sa.String(length=20), nullable=True),
        sa.Column("preco", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("codigo_servico", sa.String(length=100), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_servicos_sku", "servicos", ["sku"], unique=True)
    op.create_table(
        "produtos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("unidade", sa.String(length=20), nullable=True),
        sa.Column("preco", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("ncm", sa.String(length=20), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_produtos_sku", "produtos", ["sku"], unique=True)
    op.create_table(
        "propostas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("cliente", sa.Integer(), sa.ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contato", sa.String(length=255), nullable=True),
        sa.Column("vendedor", sa.String(length=255), nullable=True),
        sa.Column("data", sa.Date(), nullable=True),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column("outros_itens", sa.Text(), nullable=True),
        sa.Column("desconto", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("frete", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("forma_envio", sa.String(length=100), nullable=True),
        sa.Column("forma_frete", sa.String(length=100), nullable=True),
        sa.Column("transportador", sa.String(length=255), nullable=True),
        sa.Column("condicao_pagamento", sa.String(length=255), nullable=True),
        sa.Column("validade_dias", sa.Integer(), nullable=True),
        sa.Column("data_entrega", sa.Date(), nullable=True),
        sa.Column("descricao_entrega", sa.String(length=500), nullable=True),
        sa.Column("endereco_entrega_diferente", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("endereco_entrega", sa.JSON(), nullable=True),
        sa.Column("cliente_override", sa.JSON(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("assinatura", sa.String(length=255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_propostas_numero", "propostas", ["numero"], unique=True)
    op.create_table(
        "proposta_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposta", sa.Integer(), sa.ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("descricao", sa.String(length=500), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("quantidade", sa.Numeric(12, 4), nullable=False, server_default="1"),
        sa.Column("unidade", sa.String(length=20), nullable=True),
        sa.Column("preco_un", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.create_table(
        "proposta_aparelhos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposta", sa.Integer(), sa.ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("equipamento_cliente", sa.Integer(), sa.ForeignKey("equipamentos_cliente.id", ondelete="SET NULL"), nullable=True),
        sa.Column("serie", sa.String(length=100), nullable=True),
        sa.Column("modelo", sa.String(length=255), nullable=True),
        sa.Column("patrimonio", sa.String(length=100), nullable=True),
        sa.Column("prox_calibragem", sa.Date(), nullable=True),
    )
    op.create_table(
        "proposta_versoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposta", sa.Integer(), sa.ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero_versao", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("alterado_por", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("proposta_versoes")
    op.drop_table("proposta_aparelhos")
    op.drop_table("proposta_itens")
    op.drop_index("ix_propostas_numero", table_name="propostas")
    op.drop_table("propostas")
    op.drop_index("ix_produtos_sku", table_name="produtos")
    op.drop_table("produtos")
    op.drop_index("ix_servicos_sku", table_name="servicos")
    op.drop_table("servicos")
