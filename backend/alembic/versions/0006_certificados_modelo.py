"""certificados: FK -> equipamentos (catálogo) + certificado_imagens

Revision ID: 0006_certificados_modelo
Revises: 0005_caixas_drop_status
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_certificados_modelo"
down_revision = "0005_caixas_drop_status"
branch_labels = None
depends_on = None


def upgrade():
    # 1) nova coluna equipamento -> catálogo
    op.add_column("certificados", sa.Column("equipamento", sa.Integer(), nullable=True))
    # backfill: o valor antigo (em equipamento_cliente) já é o id do catálogo legado
    op.execute(
        "UPDATE certificados SET equipamento = equipamento_cliente "
        "WHERE equipamento_cliente IN (SELECT id FROM equipamentos)"
    )
    # remove linhas que não casaram com o catálogo (defensivo — verificado: 0)
    op.execute("DELETE FROM certificados WHERE equipamento IS NULL")
    # dedup defensivo: manter só o maior id por equipamento
    op.execute(
        "DELETE FROM certificados a USING certificados b "
        "WHERE a.equipamento = b.equipamento AND a.id < b.id"
    )
    # 2) dropar a FK/coluna antiga
    op.drop_constraint("certificados_equipamento_cliente_fkey", "certificados", type_="foreignkey")
    op.drop_column("certificados", "equipamento_cliente")
    # 3) FK + unique no novo vínculo
    op.create_foreign_key("certificados_equipamento_fkey", "certificados", "equipamentos", ["equipamento"], ["id"])
    op.create_unique_constraint("uq_certificados_equipamento", "certificados", ["equipamento"])
    # 4) tabela de imagens
    op.create_table(
        "certificado_imagens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("arquivo", sa.String(length=120), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=True),
        sa.Column("datacad", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("certificado_imagens")
    op.drop_constraint("uq_certificados_equipamento", "certificados", type_="unique")
    op.drop_constraint("certificados_equipamento_fkey", "certificados", type_="foreignkey")
    op.add_column("certificados", sa.Column("equipamento_cliente", sa.Integer(), nullable=True))
    op.execute("UPDATE certificados SET equipamento_cliente = equipamento")
    op.create_foreign_key(
        "certificados_equipamento_cliente_fkey", "certificados", "equipamentos_cliente",
        ["equipamento_cliente"], ["id"],
    )
    op.drop_column("certificados", "equipamento")
