"""funcao Consulta (somente leitura)

Insere a funcao "Consulta" em `funcoes`, para vendedores e SDRs que so consultam
clientes, empresas e frota. A trava de escrita e' de codigo (app/api/deps.py);
aqui so nasce a linha, para a tela Usuarios oferecer a funcao.

Idempotente: nao insere se ja existir. O downgrade so apaga se nenhum usuario
estiver com ela.
"""
from alembic import op

revision = "0033_funcao_consulta"
down_revision = "0032_cliente_tiny"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "INSERT INTO funcoes (descricao) "
        "SELECT 'Consulta' WHERE NOT EXISTS (SELECT 1 FROM funcoes WHERE descricao = 'Consulta')"
    )


def downgrade():
    op.execute(
        "DELETE FROM funcoes WHERE descricao = 'Consulta' "
        "AND NOT EXISTS (SELECT 1 FROM usuarios u WHERE u.funcao_id = funcoes.id)"
    )
