"""certificado: documentos auxiliares (gas, termohigrometro, barometro) que viram QR"""
import sqlalchemy as sa
from alembic import op

revision = "0025_certificado_docs_qr"
down_revision = "0024_certificado_config_padroes"
branch_labels = None
depends_on = None

_COLUNAS = ("doc_gas_id", "doc_termohigrometro_id", "doc_barometro_id")


def upgrade() -> None:
    for coluna in _COLUNAS:
        op.add_column("certificado_config", sa.Column(coluna, sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_certificado_config_{coluna}", "certificado_config",
            "certificados_gerais", [coluna], ["id"],
        )


def downgrade() -> None:
    for coluna in reversed(_COLUNAS):
        op.drop_constraint(f"fk_certificado_config_{coluna}", "certificado_config", type_="foreignkey")
        op.drop_column("certificado_config", coluna)
