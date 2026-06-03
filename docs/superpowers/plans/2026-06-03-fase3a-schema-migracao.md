# Fase 3A (Schema & migração da OS) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **GATE HUMANO:** entre a Task 2 (dry-run) e a Task 3 (aplicar no banco real) há uma APROVAÇÃO HUMANA OBRIGATÓRIA. NÃO aplique a migração no 9998 sem o usuário aprovar as contagens do dry-run.

**Goal:** Migração Alembic `0002_os_schema` que adiciona as colunas da OS e redefine as 9 fases legadas para as 5 novas + Cancelada, remapeando as 10.168 OS — aplicada ao banco real com dry-run e aprovação.

**Architecture:** Uma migração Alembic reversível usando `op.*` e SQL bruto via `op.get_bind()` (as tabelas `ordens`/`fotos`/`fases` já existem no banco; não há modelos SQLAlchemy ainda — eles vêm no 3B). Renomeia as fases no lugar (mantém ids 4–9, não toca em `ordens`), deleta as 3 fases vazias, com guarda anti-perda-de-dados. Verificação por dry-run (contagens) + checagens pós-apply, não por pytest.

**Tech Stack:** Alembic, SQLAlchemy core (`op`, `sa.text`), PostgreSQL.

**Referências:**
- Spec: `docs/superpowers/specs/2026-06-03-fase3a-schema-migracao-design.md`
- Padrão: `backend/alembic/versions/0001_auth_hardening.py` (revision/down_revision, `op.add_column`, `op.bulk_insert`). `backend/alembic/env.py` lê `settings.DATABASE_URL` (9998) e roda online.
- Mapa de fases (confirmado): 4→Recebido(Expedição, `3b82f6`), 5→Laboratório(Laboratório, `6366f1`), 6→Pós-Vendas(Comercial Pós-Vendas, `f59e0b`), 7→Preparando Retorno(Expedição, `14b8a6`), 8→Finalizada(`10b981`, sem responsável), 9→Cancelada(`ef4444`, sem responsável); deletar 1,2,3.
- Distribuição esperada das OS pós-apply: Recebido 35, Laboratório 40, Pós-Vendas 290, Preparando Retorno 14, Finalizada 9.583, Cancelada 206 (total 10.168).

**Comandos:** rodam no container, da raiz `d:\GitHub\GestorHS` (com `docker compose up -d`): `docker compose exec -T backend alembic <cmd>` e `docker compose exec -T backend python -c "..."`. Git via `git -C /d/GitHub/GestorHS`.

**Branch:** `feat/fase3a-schema`. Antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase3a-schema
```

---

### Task 1: Escrever a migração `0002_os_schema`

**Files:**
- Create: `backend/alembic/versions/0002_os_schema.py`

- [ ] **Step 1: Escrever a migração** — crie `backend/alembic/versions/0002_os_schema.py`:

```python
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
```

- [ ] **Step 2: Verificar que a migração carrega e encadeia (sem tocar no banco)**

Run (da raiz): `docker compose exec -T backend alembic history`
Expected: lista mostrando `0001_auth_hardening -> 0002_os_schema (head)`. Também `docker compose exec -T backend alembic heads` deve mostrar `0002_os_schema (head)`. Isso confirma que o arquivo parseia e o `down_revision` liga corretamente — nenhuma alteração no banco.

- [ ] **Step 3: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/alembic/versions/0002_os_schema.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): migracao 0002 — colunas da OS + redefinicao das fases (nao aplicada)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 2: Dry-run (read-only) — contagens antes de aplicar

**Files:** nenhum (script inline, somente leitura).

- [ ] **Step 1: Rodar o dry-run** (não altera nada)

Run (da raiz):
```bash
docker compose exec -T backend python -c "
import psycopg2, os
con = psycopg2.connect(os.environ['DATABASE_URL'].replace('postgresql+psycopg2','postgresql'))
cur = con.cursor()
print('alembic_version atual:')
cur.execute('SELECT version_num FROM alembic_version'); print(' ', cur.fetchone()[0])
print('OS nas fases 1-3 (devem ser 0):')
cur.execute('SELECT count(*) FROM ordens WHERE fase IN (1,2,3)'); print(' ', cur.fetchone()[0])
print('Distribuicao atual por fase id (= distribuicao pos-rename, pois mantemos os ids):')
mapa = {4:'Recebido',5:'Laboratorio',6:'Pos-Vendas',7:'Preparando Retorno',8:'Finalizada',9:'Cancelada'}
cur.execute('SELECT fase, count(*) FROM ordens GROUP BY fase ORDER BY fase')
for fid, n in cur.fetchall(): print(f'  fase {fid} -> {mapa.get(fid, \"?\")}: {n}')
con.close()
"
```
Expected:
- `OS nas fases 1-3` = **0** (senão a migração abortaria — pare e escale).
- Distribuição: fase 4→35, 5→40, 6→290, 7→14, 8→9583, 9→206.

- [ ] **Step 2: Reportar ao controlador** o output exato do dry-run (versão atual do alembic, contagem 1-3, distribuição). 

> **⛔ GATE HUMANO:** o controlador apresenta este dry-run ao usuário e AGUARDA aprovação explícita ("pode aplicar") antes da Task 3. Não prossiga sem isso.

---

### Task 3: Aplicar no 9998 + verificar + reversibilidade *(somente após aprovação humana)*

**Files:** nenhum (operação de banco; o arquivo da migração já foi commitado na Task 1).

- [ ] **Step 1: Aplicar a migração**

Run (da raiz): `docker compose exec -T backend alembic upgrade head`
Expected: `Running upgrade 0001_auth_hardening -> 0002_os_schema` sem erro.

- [ ] **Step 2: Verificar estrutura e dados pós-apply**

Run:
```bash
docker compose exec -T backend python -c "
import psycopg2, os
con = psycopg2.connect(os.environ['DATABASE_URL'].replace('postgresql+psycopg2','postgresql'))
cur = con.cursor()
print('FASES apos migracao:')
cur.execute('SELECT id, descricao, cor, funcao_responsavel FROM fases ORDER BY id')
for r in cur.fetchall(): print(' ', r)
print('OS por fase:')
cur.execute('SELECT fase, count(*) FROM ordens GROUP BY fase ORDER BY fase')
for r in cur.fetchall(): print(' ', r)
print('Colunas novas em ordens:')
cur.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='ordens' AND column_name IN ('tipo_servico','condicao_chegada','acessorios','aceite','data_aceite') ORDER BY column_name\")
print(' ', [r[0] for r in cur.fetchall()])
cur.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='fotos' AND column_name='os'\"); print('  fotos.os:', cur.fetchone() is not None)
cur.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='fases' AND column_name='funcao_responsavel'\"); print('  fases.funcao_responsavel:', cur.fetchone() is not None)
con.close()
"
```
Expected: `fases` com 6 linhas (ids 4–9) — Recebido/Laboratório/Pós-Vendas/Preparando Retorno/Finalizada/Cancelada, cores certas, `funcao_responsavel` setado em 4–7 (ids das funções) e nulo em 8–9. OS por fase: 4→35, 5→40, 6→290, 7→14, 8→9583, 9→206. As 5 colunas novas de `ordens` presentes; `fotos.os` e `fases.funcao_responsavel` = True.

- [ ] **Step 3: Testar reversibilidade (downgrade → upgrade), terminando em head**

Run:
```bash
docker compose exec -T backend alembic downgrade -1
docker compose exec -T backend python -c "
import psycopg2, os
con = psycopg2.connect(os.environ['DATABASE_URL'].replace('postgresql+psycopg2','postgresql')); cur = con.cursor()
cur.execute('SELECT count(*) FROM fases'); print('fases apos downgrade (espera 9):', cur.fetchone()[0])
cur.execute('SELECT version_num FROM alembic_version'); print('versao:', cur.fetchone()[0])
con.close()
"
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend python -c "
import psycopg2, os
con = psycopg2.connect(os.environ['DATABASE_URL'].replace('postgresql+psycopg2','postgresql')); cur = con.cursor()
cur.execute('SELECT count(*) FROM fases'); print('fases apos re-upgrade (espera 6):', cur.fetchone()[0])
cur.execute('SELECT version_num FROM alembic_version'); print('versao:', cur.fetchone()[0])
con.close()
"
```
Expected: downgrade → 9 fases, versão `0001_auth_hardening`; re-upgrade → 6 fases, versão `0002_os_schema`. Confirma reversibilidade estrutural e deixa o banco no estado migrado (head). Se o downgrade ou o re-upgrade falhar, **pare e escale** (o banco pode ter ficado em estado intermediário — reportar a versão atual).

- [ ] **Step 4: Confirmar a suíte pytest segue verde (não afetada)**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: 74 passed (a suíte usa SQLite via modelos, não Alembic — não muda).

*(Sem commit nesta task — a aplicação é operação de banco; o arquivo da migração já está versionado.)*

---

## Notas para o executor

- **NÃO aplique a Task 3 sem a aprovação humana** registrada após a Task 2. A Task 3 altera o banco real (9998).
- A migração usa `op.get_bind()` + `sa.text(...)` porque não há modelos para essas tabelas (eles chegam no 3B); as tabelas já existem no banco.
- A guarda na `upgrade` aborta se alguma OS estiver nas fases 1–3 — proteção contra perda de dados; o dry-run confirma que são 0.
- O `downgrade` é estrutural (restaura nomes/cores legados e recria 1–3); não reverte a interpretação semântica das OS já remapeadas — documentado no spec §4.3.
- Container precisa estar de pé (`docker compose up -d`). O `alembic` roda de `/app` (WORKDIR), lendo `alembic.ini` e `env.py` que pegam o `DATABASE_URL` do `.env`.
