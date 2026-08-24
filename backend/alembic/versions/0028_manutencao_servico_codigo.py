"""manutencao_servicos: codigo do servico, para amarrar ao catalogo comercial

O relatorio de manutencao diz o que foi feito; a proposta cobra por isso. Sem o
codigo nao ha como ligar os dois — e a lista de manutencao nasce a partir da
tabela `servicos`, que ja usa esse mesmo codigo como SKU.

Nulo e permitido: servico cadastrado a mao pelo laboratorio, para um defeito que
ainda nao existe no catalogo comercial, nao tem codigo.
"""
import sqlalchemy as sa
from alembic import op

revision = "0028_manutencao_servico_codigo"
down_revision = "0027_manutencao"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manutencao_servicos", sa.Column("codigo", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("manutencao_servicos", "codigo")
