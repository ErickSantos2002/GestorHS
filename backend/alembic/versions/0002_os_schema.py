"""schema da OS: colunas de ordens/fotos/fases + redefinicao das fases

Revision ID: 0002_os_schema
Revises: 0001_auth_hardening
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_os_schema"
down_revision = "0001_auth_hardening"
branch_labels = None
depends_on = None


# (id, nova descricao, cor, descricao da funcao responsavel | None)
_FASES = [
    (4, "Recebido", "3b82f6", "Expedição"),
    (5, "Laboratório", "6366f1", "Laboratório"),
    (6, "Pós-Vendas", "f59e0b", "Comercial Pós-Vendas"),
    (7, "Preparando Retorno", "14b8a6", "Expedição"),
    (8, "Finalizada", "10b981", None),
    (9, "Cancelada", "ef4444", None),
]


def upgrade():
    # 1) Colunas novas
    op.add_column("ordens", sa.Column("tipo_servico", sa.String(length=1), nullable=True))
    op.create_check_constraint("ck_ordens_tipo_servico", "ordens", "tipo_servico IN ('C','M','A')")
    op.add_column("ordens", sa.Column("condicao_chegada", sa.Text(), nullable=True))
    op.add_column("ordens", sa.Column("acessorios", sa.Text(), nullable=True))
    op.add_column("ordens", sa.Column("aceite", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("ordens", sa.Column("data_aceite", sa.DateTime(timezone=True), nullable=True))
    op.add_column("fotos", sa.Column("os", sa.Integer(), sa.ForeignKey("ordens.id"), nullable=True))
    op.add_column("fases", sa.Column("funcao_responsavel", sa.Integer(), sa.ForeignKey("funcoes.id"), nullable=True))

    conn = op.get_bind()

    # 2) Guarda: as fases 1-3 (extintas) devem estar vazias
    em_uso = conn.execute(sa.text("SELECT count(*) FROM ordens WHERE fase IN (1, 2, 3)")).scalar()
    if em_uso:
        raise RuntimeError(
            f"Abortando 0002: {em_uso} OS ainda nas fases 1-3 (Inicio/Com etiqueta/Enviado). "
            "Remapeie-as antes de migrar."
        )

    # 3) Redefinir as fases 4-9 no lugar (descricao, cor, funcao_responsavel)
    for fid, desc, cor, papel in _FASES:
        conn.execute(
            sa.text(
                "UPDATE fases SET descricao = :d, cor = :c, "
                "funcao_responsavel = (SELECT id FROM funcoes WHERE descricao = :p) "
                "WHERE id = :i"
            ),
            {"d": desc, "c": cor, "p": papel, "i": fid},
        )

    # 4) Deletar as fases legadas vazias
    conn.execute(sa.text("DELETE FROM fases WHERE id IN (1, 2, 3)"))


def downgrade():
    conn = op.get_bind()
    legado = [
        (4, "Recebido"), (5, "Realizando"), (6, "Pronto"),
        (7, "Retornando"), (8, "Entregue/Finalizada"), (9, "Cancelada"),
    ]
    for fid, desc in legado:
        conn.execute(
            sa.text("UPDATE fases SET descricao = :d, cor = '000000', funcao_responsavel = NULL WHERE id = :i"),
            {"d": desc, "i": fid},
        )
    conn.execute(
        sa.text(
            "INSERT INTO fases (id, descricao, cor) VALUES "
            "(1, 'Inicio', '000000'), (2, 'Com etiqueta', '000000'), (3, 'Enviado', '000000') "
            "ON CONFLICT (id) DO NOTHING"
        )
    )
    op.drop_column("fases", "funcao_responsavel")
    op.drop_column("fotos", "os")
    op.drop_constraint("ck_ordens_tipo_servico", "ordens", type_="check")
    op.drop_column("ordens", "data_aceite")
    op.drop_column("ordens", "aceite")
    op.drop_column("ordens", "acessorios")
    op.drop_column("ordens", "condicao_chegada")
    op.drop_column("ordens", "tipo_servico")
