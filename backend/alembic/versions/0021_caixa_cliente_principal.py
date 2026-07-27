"""caixa multi-cliente: caixas.cliente_principal + backfill"""
import sqlalchemy as sa
from alembic import op

revision = "0021_caixa_cliente_principal"
down_revision = "0020_propostas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("caixas", sa.Column("cliente_principal", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_caixas_cliente_principal", "caixas", "clientes",
                          ["cliente_principal"], ["id"])
    # Backfill: cliente_principal = o cliente das OS da caixa (hoje single-client).
    # Usa o menor id de OS da caixa como representante (determinístico).
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE caixas SET cliente_principal = sub.cliente
        FROM (
            SELECT o.caixa AS caixa_id, o.cliente AS cliente
            FROM ordens o
            JOIN (SELECT caixa, MIN(id) AS min_id FROM ordens WHERE caixa IS NOT NULL GROUP BY caixa) m
              ON o.caixa = m.caixa AND o.id = m.min_id
        ) sub
        WHERE caixas.id = sub.caixa_id
    """))


def downgrade() -> None:
    op.drop_constraint("fk_caixas_cliente_principal", "caixas", type_="foreignkey")
    op.drop_column("caixas", "cliente_principal")
