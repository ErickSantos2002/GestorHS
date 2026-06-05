"""caixas: FK ordens.caixa -> caixas.id

Revision ID: 0004_caixas_fk
Revises: 0003_solicitacoes
Create Date: 2026-06-05
"""
from alembic import op

revision = "0004_caixas_fk"
down_revision = "0003_solicitacoes"
branch_labels = None
depends_on = None


def upgrade():
    # Solta órfãos: OS apontando para caixa inexistente viraria violação de FK.
    op.execute(
        "UPDATE ordens SET caixa = NULL "
        "WHERE caixa IS NOT NULL AND caixa NOT IN (SELECT id FROM caixas)"
    )
    op.create_foreign_key(
        "fk_ordens_caixa", "ordens", "caixas",
        ["caixa"], ["id"], ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_ordens_caixa", "ordens", type_="foreignkey")
