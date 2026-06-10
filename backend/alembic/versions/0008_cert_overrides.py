"""ordens.cert_overrides (JSON) — sobrescritas de identidade do certificado

Revision ID: 0008_cert_overrides
Revises: 0007_os_certificados
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_cert_overrides"
down_revision = "0007_os_certificados"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ordens", sa.Column("cert_overrides", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("ordens", "cert_overrides")
