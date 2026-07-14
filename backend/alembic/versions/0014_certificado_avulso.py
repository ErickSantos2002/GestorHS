"""certificados avulsos: certificado sem OS/cliente/aparelho (POC)

Revision ID: 0014_certificado_avulso
Revises: 0013_nota_fiscal
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_certificado_avulso"
down_revision = "0013_nota_fiscal"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "certificados_avulsos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(1), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("nomecli", sa.String(200), nullable=True),
        sa.Column("serie", sa.String(50), nullable=True),
        sa.Column("calib_cert", sa.String(50), nullable=True),
        sa.Column("data_calibracao", sa.Date(), nullable=True),
        sa.Column("usuario", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("data_geracao", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("certificados_avulsos")
