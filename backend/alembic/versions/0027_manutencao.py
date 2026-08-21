"""manutencao: registro do servico feito na bancada e o catalogo de servicos"""
import sqlalchemy as sa
from alembic import op

revision = "0027_manutencao"
down_revision = "0026_nota_fiscal_xml"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manutencao_servicos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("descricao", sa.String(200), nullable=False, unique=True),
        sa.Column("resumo_padrao", sa.Text(), nullable=False, server_default=""),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_table(
        "manutencoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("os", sa.Integer(), sa.ForeignKey("ordens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero", sa.String(50), nullable=True),
        sa.Column("data_manutencao", sa.Date(), nullable=True),
        sa.Column("resumo", sa.Text(), nullable=True),
        sa.Column("criado_por", sa.String(255), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_manutencoes_os", "manutencoes", ["os"])
    op.create_unique_constraint("uq_manutencoes_os", "manutencoes", ["os"])
    op.create_table(
        "manutencao_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manutencao", sa.Integer(), sa.ForeignKey("manutencoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("servico", sa.Integer(), sa.ForeignKey("manutencao_servicos.id"), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_manutencao_itens_manutencao", "manutencao_itens", ["manutencao"])
    op.create_unique_constraint("uq_manutencao_itens_servico", "manutencao_itens", ["manutencao", "servico"])


def downgrade() -> None:
    op.drop_table("manutencao_itens")
    op.drop_table("manutencoes")
    op.drop_table("manutencao_servicos")
