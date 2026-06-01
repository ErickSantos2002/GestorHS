"""auth hardening: funcoes, senha->text, unicidade e flag de redefinicao

Revision ID: 0001_auth_hardening
Revises:
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_auth_hardening"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "funcoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("descricao", sa.String(length=100), nullable=False, unique=True),
    )
    op.bulk_insert(
        sa.table("funcoes", sa.column("descricao", sa.String)),
        [
            {"descricao": "Administrador"},
            {"descricao": "Expedição"},
            {"descricao": "Laboratório"},
            {"descricao": "Comercial Pós-Vendas"},
        ],
    )

    op.alter_column("usuarios", "senha", type_=sa.Text(), existing_nullable=False)
    op.add_column("usuarios", sa.Column("funcao_id", sa.Integer(), sa.ForeignKey("funcoes.id"), nullable=True))
    op.add_column("usuarios", sa.Column("precisa_redefinir_senha", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE usuarios SET senha = '', precisa_redefinir_senha = true")

    op.alter_column("usuarios_cliente", "senha", type_=sa.Text(), existing_nullable=False)
    op.add_column("usuarios_cliente", sa.Column("precisa_redefinir_senha", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_unique_constraint("uq_usuarios_cliente_login", "usuarios_cliente", ["cliente", "login"])
    op.execute("UPDATE usuarios_cliente SET senha = '', precisa_redefinir_senha = true")


def downgrade():
    op.drop_constraint("uq_usuarios_cliente_login", "usuarios_cliente", type_="unique")
    op.drop_column("usuarios_cliente", "precisa_redefinir_senha")
    op.drop_column("usuarios", "precisa_redefinir_senha")
    op.drop_column("usuarios", "funcao_id")
    op.drop_table("funcoes")
