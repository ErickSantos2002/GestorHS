"""usuario: e-mail vira a credencial (NOT NULL + UNIQUE) e a coluna login sai

Revision ID: 0012_usuario_email_credencial
Revises: 0011_usuario_ativo
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_usuario_email_credencial"
down_revision = "0011_usuario_ativo"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # 1) normaliza os e-mails existentes (todos os usuarios ja tem e-mail, sem duplicatas)
    conn.execute(sa.text("UPDATE usuarios SET email = lower(trim(email)) WHERE email IS NOT NULL"))
    # 2) e-mail obrigatorio e unico
    op.alter_column("usuarios", "email", existing_type=sa.String(200), nullable=False)
    op.create_unique_constraint("uq_usuarios_email", "usuarios", ["email"])
    # 3) o login deixa de existir
    op.drop_column("usuarios", "login")


def downgrade():
    op.add_column("usuarios", sa.Column("login", sa.String(20), nullable=True))
    op.drop_constraint("uq_usuarios_email", "usuarios", type_="unique")
    op.alter_column("usuarios", "email", existing_type=sa.String(200), nullable=True)
