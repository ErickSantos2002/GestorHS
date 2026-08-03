"""certificado: tabelas de configuracao e de padroes (cilindros), 5 medicoes na OS"""
import sqlalchemy as sa
from alembic import op

revision = "0024_certificado_config_padroes"
down_revision = "0023_caixa_numero_proposta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    config = op.create_table(
        "certificado_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("valor_referencia", sa.Numeric(10, 4), nullable=True),
        sa.Column("limite_minimo", sa.Numeric(10, 4), nullable=True),
        sa.Column("limite_maximo", sa.Numeric(10, 4), nullable=True),
        sa.Column("resolucao_instrumento", sa.Numeric(10, 4), nullable=True),
        sa.Column("incerteza_padrao_temp", sa.Numeric(10, 4), nullable=True),
        sa.Column("resolucao_pressao", sa.Numeric(10, 4), nullable=True),
        sa.Column("incerteza_padrao_pressao", sa.Numeric(10, 4), nullable=True),
        sa.Column("fator_k", sa.Numeric(4, 2), nullable=True),
        sa.Column("tecnico_nome", sa.String(100), nullable=True),
        sa.Column("tecnico_cargo", sa.String(100), nullable=True),
        sa.Column("equipamentos_auxiliares", sa.Text(), nullable=True),
        sa.Column("margem_temperatura", sa.String(50), nullable=True),
    )
    # linha unica com os valores da planilha EPS-LAB-002 como ponto de partida
    op.bulk_insert(config, [{
        "id": 1,
        "valor_referencia": 0.1,
        "limite_minimo": 0.15,
        "limite_maximo": 0.19,
        "resolucao_instrumento": 0.1,
        "incerteza_padrao_temp": 0.052,
        "resolucao_pressao": None,
        "incerteza_padrao_pressao": None,
        "fator_k": 2,
        "tecnico_nome": "Walbert Santos",
        "tecnico_cargo": "Técnico em Metrologia",
        "equipamentos_auxiliares": (
            "• TESTO 622 - Monitorização de ambientes científicos - Termo-Higrômetro "
            "digital 39533693 - Certificado: 95239/1, 95239/2 e LV06079-33193-22-R0."
        ),
        "margem_temperatura": "20 ºC ~ 24 ºC",
    }])

    op.create_table(
        "certificado_padrao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero_cilindro", sa.String(50), nullable=False),
        sa.Column("numero_certificado", sa.String(50), nullable=True),
        sa.Column("concentracao", sa.Numeric(10, 4), nullable=True),
        sa.Column("incerteza_concentracao", sa.Numeric(10, 4), nullable=True),
        sa.Column("unidade", sa.String(20), nullable=True),
        sa.Column("vigencia_inicio", sa.Date(), nullable=True),
        sa.Column("vigencia_fim", sa.Date(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.add_column("ordens", sa.Column("calib_teste4", sa.String(50), nullable=True))
    op.add_column("ordens", sa.Column("calib_teste5", sa.String(50), nullable=True))
    op.add_column("ordens", sa.Column("padrao_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_ordens_padrao_id", "ordens", "certificado_padrao", ["padrao_id"], ["id"]
    )

    op.add_column("equipamentos_cliente", sa.Column("calib_teste4", sa.String(50), nullable=True))
    op.add_column("equipamentos_cliente", sa.Column("calib_teste5", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("equipamentos_cliente", "calib_teste5")
    op.drop_column("equipamentos_cliente", "calib_teste4")
    op.drop_constraint("fk_ordens_padrao_id", "ordens", type_="foreignkey")
    op.drop_column("ordens", "padrao_id")
    op.drop_column("ordens", "calib_teste5")
    op.drop_column("ordens", "calib_teste4")
    op.drop_table("certificado_padrao")
    op.drop_table("certificado_config")
