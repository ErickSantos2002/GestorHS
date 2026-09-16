"""empresas (filiais) + destinatario da proposta

A proposta passa a ter como destinatario um Cliente ou uma Empresa. A Empresa e'
uma filial: so dados cadastrais, matriz opcional em `cliente`.

`propostas.destinatario` e' a copia congelada dos dados do destinatario. NAO ha
backfill aqui: a regra de montagem mora em app/core/empresa.py e o repo nao
importa `app` em migracao. Enquanto a copia estiver nula, a API e o PDF montam
o mesmo resultado de antes (cadastro + cliente_override); o script
`migrar_filiais_propostas --aplicar` congela as antigas.

`cliente_override` NAO e' apagado.
"""
import sqlalchemy as sa
from alembic import op

revision = "0030_empresas"
down_revision = "0029_notas_fiscais"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "empresas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cliente", sa.Integer, sa.ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("cgc", sa.String(14), nullable=True),
        sa.Column("cpf", sa.String(11), nullable=True),
        sa.Column("endereco", sa.String(100), nullable=True),
        sa.Column("numero", sa.String(20), nullable=True),
        sa.Column("complemento", sa.String(60), nullable=True),
        sa.Column("bairro", sa.String(100), nullable=True),
        sa.Column("municipio", sa.String(100), nullable=True),
        sa.Column("estado", sa.String(2), nullable=True),
        sa.Column("cep", sa.String(8), nullable=True),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("telefone", sa.String(50), nullable=True),
        sa.Column("insc_est", sa.String(20), nullable=True),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("(cgc IS NULL) <> (cpf IS NULL)", name="ck_empresas_um_documento"),
        sa.UniqueConstraint("cgc", name="uq_empresas_cgc"),
        sa.UniqueConstraint("cpf", name="uq_empresas_cpf"),
    )
    op.create_index("ix_empresas_id", "empresas", ["id"])
    op.create_index("ix_empresas_cliente", "empresas", ["cliente"])

    op.add_column("propostas", sa.Column("empresa", sa.Integer, nullable=True))
    op.create_foreign_key("fk_propostas_empresa", "propostas", "empresas", ["empresa"], ["id"], ondelete="SET NULL")
    op.create_index("ix_propostas_empresa", "propostas", ["empresa"])
    op.add_column("propostas", sa.Column("destinatario", sa.JSON, nullable=True))


def downgrade():
    # Proposta salva depois da 0030 nao tem override: sem a copia, o PDF dela
    # volta a sair so com o cadastro do cliente. Ver docs/operacao-empresas-migracao.md.
    op.drop_column("propostas", "destinatario")
    op.drop_index("ix_propostas_empresa", table_name="propostas")
    op.drop_constraint("fk_propostas_empresa", "propostas", type_="foreignkey")
    op.drop_column("propostas", "empresa")
    op.drop_index("ix_empresas_cliente", table_name="empresas")
    op.drop_index("ix_empresas_id", table_name="empresas")
    op.drop_table("empresas")
