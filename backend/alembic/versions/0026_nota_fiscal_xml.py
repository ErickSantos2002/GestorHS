"""nota fiscal: arquivo XML separado do PDF

Ate aqui `ordens.nota_fiscal` guardava UM arquivo, que podia ser o PDF ou o XML.
O Financeiro sempre recebe os dois juntos, entao passam a ser dois campos: o PDF
continua em `nota_fiscal` e o XML ganha coluna propria.

Linhas antigas ficam como estao — algumas tem o XML gravado em `nota_fiscal`.
Nao da para separar automaticamente sem abrir arquivo por arquivo, e o avanco
delas ja aconteceu; quem precisar corrige reanexando pela tela.
"""
import sqlalchemy as sa
from alembic import op

revision = "0026_nota_fiscal_xml"
down_revision = "0025_certificado_docs_qr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ordens", sa.Column("nota_fiscal_xml", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("ordens", "nota_fiscal_xml")
