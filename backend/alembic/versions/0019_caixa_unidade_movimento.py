"""caixa unidade de movimento: caixas.fase + ordens.desfecho_lab + backfill"""
import sqlalchemy as sa
from alembic import op

revision = "0019_caixa_unidade_movimento"
down_revision = "0018_log_integracao"
branch_labels = None
depends_on = None

# Ordem logica das fases (espelha app/core/os_workflow.ORDEM_FASES).
# Fase > Laboratorio(pos 1) ja passou do lab -> desfecho concluido no backfill.
ORDEM_FASES = {4: 0, 5: 1, 6: 2, 10: 3, 7: 4, 8: 5}
POS_LAB = 1


def upgrade() -> None:
    op.add_column("caixas", sa.Column("fase", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_caixas_fase", "caixas", "fases", ["fase"], ["id"])
    op.add_column("ordens", sa.Column("desfecho_lab", sa.String(length=20),
                                      nullable=False, server_default="pendente"))
    op.add_column("ordens", sa.Column("desfecho_lab_obs", sa.Text(), nullable=True))

    conn = op.get_bind()
    # 1) caixa.fase = a menor fase (por posicao logica) entre as OS ativas da caixa;
    #    caixas so com OS terminais ou vazias ficam com fase NULL (nao andam mais).
    caixas = conn.execute(sa.text(
        "SELECT DISTINCT caixa FROM ordens WHERE caixa IS NOT NULL"
    )).fetchall()
    for (caixa_id,) in caixas:
        fases = conn.execute(sa.text(
            "SELECT fase FROM ordens WHERE caixa = :c AND fase IS NOT NULL"
        ), {"c": caixa_id}).fetchall()
        ativas = [f for (f,) in fases if f in ORDEM_FASES and f != 8 and f != 9]
        if not ativas:
            continue
        menor = min(ativas, key=lambda f: ORDEM_FASES[f])
        conn.execute(sa.text("UPDATE caixas SET fase = :f WHERE id = :c"),
                     {"f": menor, "c": caixa_id})

    # 2) desfecho_lab: OS ativas cuja fase ja passou do laboratorio -> concluido.
    #    As demais ficam no default 'pendente'. Conservador (operador reconfirma).
    ja_passou = [str(f) for f, pos in ORDEM_FASES.items() if pos > POS_LAB and f != 8]
    if ja_passou:
        conn.execute(sa.text(
            f"UPDATE ordens SET desfecho_lab = 'concluido' "
            f"WHERE fase IN ({','.join(ja_passou)})"
        ))


def downgrade() -> None:
    op.drop_column("ordens", "desfecho_lab_obs")
    op.drop_column("ordens", "desfecho_lab")
    op.drop_constraint("fk_caixas_fase", "caixas", type_="foreignkey")
    op.drop_column("caixas", "fase")
