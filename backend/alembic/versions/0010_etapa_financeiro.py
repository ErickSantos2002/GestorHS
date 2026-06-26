"""etapa financeiro: coluna data_pagamento + funcao Financeiro + fase 10

Revision ID: 0010_etapa_financeiro
Revises: 0009_transferencias_equipamento
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_etapa_financeiro"
down_revision = "0009_transferencias_equipamento"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ordens", sa.Column("data_pagamento", sa.DateTime(timezone=True), nullable=True))
    conn = op.get_bind()
    conn.execute(sa.text(
        "INSERT INTO funcoes (descricao) VALUES ('Financeiro') ON CONFLICT (descricao) DO NOTHING"
    ))
    fid = conn.execute(sa.text("SELECT id FROM funcoes WHERE descricao = 'Financeiro'")).scalar()
    conn.execute(
        sa.text(
            "INSERT INTO fases (id, descricao, cor, funcao_responsavel) "
            "VALUES (10, 'Financeiro', 'a855f7', :fid) ON CONFLICT (id) DO NOTHING"
        ),
        {"fid": fid},
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM fases WHERE id = 10"))
    conn.execute(sa.text("DELETE FROM funcoes WHERE descricao = 'Financeiro'"))
    op.drop_column("ordens", "data_pagamento")
