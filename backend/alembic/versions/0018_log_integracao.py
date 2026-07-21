"""logs de integracao: eventos de saida (taskhs/growthhs)"""
import sqlalchemy as sa
from alembic import op

revision = "0018_log_integracao"
down_revision = "0017_certificado_venda"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "logs_integracao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("integracao", sa.String(length=20), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("referencia_os", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("motivo", sa.String(length=50), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("resposta", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_logs_integracao_id"), "logs_integracao", ["id"])
    op.create_index(op.f("ix_logs_integracao_criado_em"), "logs_integracao", ["criado_em"])
    op.create_index(op.f("ix_logs_integracao_referencia_os"), "logs_integracao", ["referencia_os"])


def downgrade() -> None:
    op.drop_index(op.f("ix_logs_integracao_referencia_os"), table_name="logs_integracao")
    op.drop_index(op.f("ix_logs_integracao_criado_em"), table_name="logs_integracao")
    op.drop_index(op.f("ix_logs_integracao_id"), table_name="logs_integracao")
    op.drop_table("logs_integracao")
