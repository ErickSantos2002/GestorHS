"""certificados.tipo (C/M) + tabela os_certificados

Revision ID: 0007_os_certificados
Revises: 0006_certificados_modelo
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_os_certificados"
down_revision = "0006_certificados_modelo"
branch_labels = None
depends_on = None


def upgrade():
    # tipo nos modelos de certificado
    op.add_column("certificados", sa.Column("tipo", sa.String(length=1), nullable=False, server_default="C"))
    op.create_check_constraint("certificados_tipo_check", "certificados", "tipo IN ('C','M')")
    # unicidade passa a ser (equipamento, tipo)
    op.drop_constraint("uq_certificados_equipamento", "certificados", type_="unique")
    op.create_unique_constraint("uq_certificados_equipamento_tipo", "certificados", ["equipamento", "tipo"])
    # certificados gerados por OS
    op.create_table(
        "os_certificados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("os", sa.Integer(), sa.ForeignKey("ordens.id"), nullable=False),
        sa.Column("tipo", sa.String(length=1), nullable=False),
        sa.Column("html", sa.Text(), nullable=True),
        sa.Column("pdf", sa.String(length=50), nullable=True),
        sa.Column("data_geracao", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tipo IN ('C','M')", name="os_certificados_tipo_check"),
        sa.UniqueConstraint("os", "tipo", name="uq_os_certificados_os_tipo"),
    )


def downgrade():
    op.drop_table("os_certificados")
    op.drop_constraint("uq_certificados_equipamento_tipo", "certificados", type_="unique")
    op.create_unique_constraint("uq_certificados_equipamento", "certificados", ["equipamento"])
    op.drop_constraint("certificados_tipo_check", "certificados", type_="check")
    op.drop_column("certificados", "tipo")
