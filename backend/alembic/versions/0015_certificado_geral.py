"""certificados gerais: documento PDF avulso com link publico

Revision ID: 0015_certificado_geral
Revises: 0014_certificado_avulso
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_certificado_geral"
down_revision = "0014_certificado_avulso"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "certificados_gerais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("arquivo", sa.String(64), nullable=False),
        sa.Column("usuario", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("data_upload", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("certificados_gerais")
