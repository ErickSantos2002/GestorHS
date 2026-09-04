"""notas fiscais por CAIXA (varias por caixa) + backfill do que ja existe

Ate aqui a nota fiscal eram tres colunas em `ordens` e so cabia UMA por OS. O
Financeiro precisa anexar mais de uma na mesma caixa (a do servico e a de
remessa do envio), e precisa poder remover a errada para corrigir.

As colunas antigas de `ordens` NAO sao apagadas e param de receber escrita:
existem para continuar servindo `GET /ordens/{id}/nota-fiscal` e o link publico
`nf:{ordem_id}`, que ja estao publicados nos cards do TaskHS.

O backfill NAO move arquivo nenhum: cada linha criada aponta, por `ordem`, para
a OS em cujo subdir os arquivos ja estao.
"""
import sqlalchemy as sa
from alembic import op

revision = "0029_notas_fiscais"
down_revision = "0028_manutencao_servico_codigo"
branch_labels = None
depends_on = None

# Uma linha por caixa. Representante = a primeira OS (por id) com PDF **e** XML.
# OS antiga so com PDF fica de fora: `arquivo_xml` e' NOT NULL. Essas caixas
# seguem servidas pelas colunas legadas, e o guard de avanco aceita as duas
# fontes justamente para elas nao travarem no Financeiro.
BACKFILL = """
INSERT INTO notas_fiscais (caixa, numero, arquivo_pdf, arquivo_xml, ordem, criado_em)
SELECT DISTINCT ON (o.caixa)
       o.caixa,
       COALESCE(NULLIF(BTRIM(o.nota_fiscal_numero), ''), 's/n'),
       o.nota_fiscal,
       o.nota_fiscal_xml,
       o.id,
       NOW()
  FROM ordens o
 WHERE o.caixa IS NOT NULL
   AND o.nota_fiscal IS NOT NULL AND o.nota_fiscal <> ''
   AND o.nota_fiscal_xml IS NOT NULL AND o.nota_fiscal_xml <> ''
 ORDER BY o.caixa, o.id
"""


def upgrade() -> None:
    op.create_table(
        "notas_fiscais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("caixa", sa.Integer(), sa.ForeignKey("caixas.id"), nullable=False),
        sa.Column("numero", sa.String(50), nullable=False),
        sa.Column("arquivo_pdf", sa.String(50), nullable=False),
        sa.Column("arquivo_xml", sa.String(50), nullable=False),
        sa.Column("ordem", sa.Integer(), sa.ForeignKey("ordens.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("criado_por", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
    )
    op.create_index("ix_notas_fiscais_caixa", "notas_fiscais", ["caixa"])
    op.execute(BACKFILL)


def downgrade() -> None:
    op.drop_index("ix_notas_fiscais_caixa", table_name="notas_fiscais")
    op.drop_table("notas_fiscais")
