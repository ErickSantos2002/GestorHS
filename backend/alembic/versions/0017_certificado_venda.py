"""certificado de venda: primeiro certificado do aparelho, sem OS"""
import sqlalchemy as sa
from alembic import op

revision = "0017_certificado_venda"
down_revision = "0016_instalacao_modulo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "certificados_venda",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("equipamento_cliente", sa.Integer(), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("calib_cert", sa.String(length=50), nullable=True),
        sa.Column("data_calibracao", sa.Date(), nullable=True),
        sa.Column("usuario", sa.Integer(), nullable=True),
        sa.Column("data_geracao", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["equipamento_cliente"], ["equipamentos_cliente.id"]),
        sa.ForeignKeyConstraint(["usuario"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipamento_cliente", name="uq_certificados_venda_equip"),
    )
    op.create_index(op.f("ix_certificados_venda_id"), "certificados_venda", ["id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_certificados_venda_id"), table_name="certificados_venda")
    op.drop_table("certificados_venda")
