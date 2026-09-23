# Cliente de proposta no Tiny ERP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Todo Cliente que recebe proposta passa a ter contato no Tiny ERP — adotado se já existe lá, criado se não existe, nunca alterado — com o estado gravado em `clientes` e uma carga retroativa para quem já tem proposta.

**Architecture:** Quatro colunas de estado em `clientes` (migração `0032`, espelho da `0031` da Empresa). Um adaptador puro em `core/tiny.py` transforma o Cliente no contato do Tiny reaproveitando `contato_para_criar`. `integrations/tiny_client.sincronizar_cliente` faz só pesquisar → adotar ou criar. A rota de propostas agenda o sync em `BackgroundTasks` (criar, editar, duplicar); o worker `tiny_pendentes` reenvia os `pendente`; o script `enviar_clientes_tiny` faz a carga dos antigos.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · pytest (SQLite in-memory) · React 19 + TS + Vitest.

**Spec:** [docs/superpowers/specs/2026-09-23-tiny-clientes-proposta-design.md](../specs/2026-09-23-tiny-clientes-proposta-design.md)

## Global Constraints

- **Nunca** chamar `contato.alterar.php` (nem `alterar_contato`/`obter_contato_bruto`) para Cliente.
- **Cliente inativo também entra** — no gatilho, no worker e no script. (A criação de proposta *nova* para cliente inativo continua recusada por `DestinatarioInativo`; não mexer nisso.)
- Cliente com `tiny_id` preenchido **não gera chamada nenhuma** ao Tiny.
- Só o erro **20** significa "não existe lá". Qualquer outra falha de pesquisa → `pendente`, **nunca** criar.
- Proposta nunca falha por causa do Tiny (best-effort, `except` que loga).
- Testes **nunca** chamam o Tiny de verdade (`httpx`/funções mockadas). A fixture autouse `_tiny_desligado` do `conftest.py` zera o `TINY_TOKEN`; testes que precisam da integração ligada fazem `monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")`.
- Código, nomes e mensagens em **PT-BR**. Commits: `tipo(escopo): descricao` em português **sem acento**, uma linha, **sem corpo e sem trailer de co-autor**.
- `git add` só dos arquivos da task — **nunca** `git add -A` (há arquivos não rastreados no repo que não são desta entrega).
- Baseline: 4 testes do backend já falham nesta máquina antes de qualquer mudança (ver memória `gestorhs-falhas-teste-preexistentes`). Rodar `pytest -q` uma vez antes da Task 1 e anotar quais são; regressão é só o que aparecer **além** deles.
- Comandos do backend rodam em `backend/` com `source .venv/bin/activate`; do frontend, em `frontend/`.

## Review Focus

1. **Cliente sem `nome`** (a coluna é nullable no legado) — o Tiny exige `nome`; `montar_contato` manda `""` e o campo cai fora do payload. Esperado: o Tiny recusa e o cliente fica `erro` com a mensagem, sem exceção. Teste na Task 3.
2. **Proposta para Empresa cuja matriz é um Cliente sem `tiny_id`** — não pode agendar o Cliente (só o destinatário conta). Teste na Task 4.
3. **Editar proposta antiga de cliente inativo** — deve agendar normalmente (o spec inclui inativos). Teste na Task 4.
4. **Dois syncs simultâneos do mesmo cliente** (criar proposta e duplicar logo em seguida) — a trava `FOR UPDATE OF clientes` + a checagem de `tiny_id` depois da trava impedem o segundo contato. O SQLite não trava; o que dá para pinar é o SQL compilado e o "já tem `tiny_id` → não chama". Testes na Task 3.
5. **Complemento só com traços/espaços** (`"-"`, `" - "`, `"--"`) — deve sair do payload, não virar complemento `-` no ERP. Teste na Task 2.

## Mapa de arquivos

| Arquivo | Papel |
|---|---|
| `backend/alembic/versions/0032_cliente_tiny.py` (novo) | 4 colunas em `clientes` |
| `backend/app/models/cliente.py` | colunas no model |
| `backend/app/schemas/clientes.py` | expõe o estado em `ClienteListOut` e `ClienteOut` |
| `backend/app/core/tiny.py` | `contato_cliente_para_criar` (puro) |
| `backend/app/integrations/tiny_client.py` | `stmt_travar_cliente`, `sincronizar_cliente`; `_marcar`/`_aplicar` genéricos |
| `backend/app/api/propostas.py` | `_agendar_cliente_no_tiny` em criar/atualizar/duplicar |
| `backend/app/tarefas/tiny_pendentes.py` | `pendentes_clientes` + volta com os dois |
| `backend/app/scripts/enviar_clientes_tiny.py` (novo) | carga retroativa |
| `frontend/src/app/empresas/api.ts` | `rotuloTiny` aceita qualquer `{ tiny_status }` |
| `frontend/src/app/clientes/SeloTiny.tsx` (novo) | selo do status |
| `frontend/src/app/clientes/api.ts`, `ClientesPage.tsx`, `ClienteLayout.tsx` | tipos + uso do selo |
| `frontend/src/app/changelog/data.ts`, `CLAUDE.md`, `docs/operacao-tiny-empresas.md` | documentação |

---

### Task 1: Migração `0032` + colunas no model + schemas

**Files:**
- Create: `backend/alembic/versions/0032_cliente_tiny.py`
- Modify: `backend/app/models/cliente.py` (depois de `ativo`)
- Modify: `backend/app/schemas/clientes.py` (`ClienteListOut`, `ClienteOut`)
- Test: `backend/tests/test_clientes_tiny_estado.py` (novo)

**Interfaces:**
- Produces: `Cliente.tiny_id: int|None`, `Cliente.tiny_status: str|None` (`pendente`|`enviada`|`erro`), `Cliente.tiny_erro: str|None`, `Cliente.tiny_em: datetime|None`; `GET /clientes` e `GET /clientes/{id}` devolvem `tiny_id`, `tiny_status`, `tiny_erro`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_clientes_tiny_estado.py`:

```python
from app.models import Cliente


def test_cliente_nasce_sem_estado_do_tiny(db_session):
    c = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    assert c.tiny_id is None and c.tiny_status is None
    assert c.tiny_erro is None and c.tiny_em is None


def test_listagem_e_detalhe_expoem_o_estado_do_tiny(client_comercial, db_session):
    c = Cliente(nome="ACME", cgc="08857492000148", tiny_id=610662219,
                tiny_status="enviada", tiny_erro=None)
    db_session.add(c); db_session.commit()

    item = client_comercial.get("/clientes").json()["items"][0]
    assert item["tiny_id"] == 610662219 and item["tiny_status"] == "enviada"
    assert item["tiny_erro"] is None

    detalhe = client_comercial.get(f"/clientes/{c.id}").json()
    assert detalhe["tiny_id"] == 610662219 and detalhe["tiny_status"] == "enviada"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_clientes_tiny_estado.py -v`
Expected: FAIL — `TypeError: 'tiny_id' is an invalid keyword argument for Cliente`.

- [ ] **Step 3: Write minimal implementation**

`backend/alembic/versions/0032_cliente_tiny.py`:

```python
"""estado do espelhamento do cliente no Tiny ERP

Quatro colunas em `clientes`, espelho da 0031 (empresas): o id do contato no
Tiny e o resultado da ultima tentativa. So o Cliente que recebe proposta e'
espelhado — e so criado ou adotado, nunca alterado (ver a spec de 23/09/2026).

Aditiva: nenhuma linha existente e' tocada.
"""
import sqlalchemy as sa
from alembic import op

revision = "0032_cliente_tiny"
down_revision = "0031_empresa_tiny"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clientes", sa.Column("tiny_id", sa.Integer, nullable=True))
    op.create_index("ix_clientes_tiny_id", "clientes", ["tiny_id"])
    op.add_column("clientes", sa.Column("tiny_status", sa.String(10), nullable=True))
    op.add_column("clientes", sa.Column("tiny_erro", sa.String(255), nullable=True))
    op.add_column("clientes", sa.Column("tiny_em", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("clientes", "tiny_em")
    op.drop_column("clientes", "tiny_erro")
    op.drop_column("clientes", "tiny_status")
    op.drop_index("ix_clientes_tiny_id", table_name="clientes")
    op.drop_column("clientes", "tiny_id")
```

`backend/app/models/cliente.py` — acrescentar `DateTime` ao import do `sqlalchemy` e, logo após `ativo = ...`:

```python
    # Espelhamento no Tiny ERP (0032). So o Cliente destinatario de proposta e'
    # espelhado, e so criado/adotado — nunca alterado. Ver integrations/tiny_client.py.
    tiny_id = Column(Integer, nullable=True, index=True)      # id do contato no Tiny
    tiny_status = Column(String(10), nullable=True)           # pendente | enviada | erro
    tiny_erro = Column(String(255), nullable=True)            # ultima recusa, para a tela
    tiny_em = Column(DateTime(timezone=True), nullable=True)  # ultima tentativa
```

`backend/app/schemas/clientes.py` — em **`ClienteListOut`** e em **`ClienteOut`**, antes do `model_config`:

```python
    tiny_id: Optional[int] = None
    tiny_status: Optional[str] = None
    tiny_erro: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_clientes_tiny_estado.py tests/test_clientes*.py -q`
Expected: PASS (nada de clientes regrediu).

Conferir a cadeia do Alembic sem aplicar: `alembic heads` → `0032_cliente_tiny (head)`.
**Não** rodar `alembic upgrade head` — o `.env` aponta para o banco de produção; aplicar é passo de deploy.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0032_cliente_tiny.py backend/app/models/cliente.py backend/app/schemas/clientes.py backend/tests/test_clientes_tiny_estado.py
git commit -m "feat(tiny): estado do espelhamento do cliente no tiny (migracao 0032)"
```

---

### Task 2: Contato do Tiny a partir do Cliente (`core/tiny.py`)

**Files:**
- Modify: `backend/app/core/tiny.py` (depois de `contato_para_alterar`)
- Test: `backend/tests/test_tiny_core.py` (acrescentar no fim)

**Interfaces:**
- Consumes: `montar_contato(empresa)`, `contato_para_criar(empresa)` (existentes; leem atributos `nome, cgc, cpf, insc_est, endereco, numero, complemento, bairro, municipio, estado, cep, email, telefone`).
- Produces: `contato_cliente_para_criar(cliente) -> dict` — payload de `contato.incluir.php` para um `Cliente`.

- [ ] **Step 1: Write the failing tests** (no fim de `tests/test_tiny_core.py`)

```python
def _cliente(**kw):
    """Cliente do legado: `numero` inteiro, `telefones` (plural), complemento "-"."""
    base = dict(id=692, nome="IMETAME METALMECANICA LTDA", cgc="31790710000196", cpf=None,
                insc_est=None, endereco="RODOVIA DEMOCRITO MOREIRA", numero=643, complemento="-",
                bairro="FATIMA", municipio="ARACRUZ", estado="ES", cep="29192243",
                email="gmoscon@imetame.com.br", telefones="27 99619-1347")
    base.update(kw)
    return SimpleNamespace(**base)


def test_contato_do_cliente_traduz_o_legado():
    c = tiny.contato_cliente_para_criar(_cliente())
    assert c["numero"] == "643"                       # BigInteger vira texto
    assert c["fone"] == "27 99619-1347"               # `telefones` -> `fone`
    assert "complemento" not in c                     # "-" e' vazio
    assert c["cpf_cnpj"] == "31790710000196" and c["tipo_pessoa"] == "J"
    assert c["tipos_contato"] == [{"tipo": "Cliente"}] and c["situacao"] == "A"
    assert c["sequencia"] == 1
    assert "ie" not in c                              # sem IE no cadastro


def test_contato_do_cliente_complemento_so_de_tracos_e_espacos_sai():
    for lixo in ("-", " - ", "--", "  "):
        assert "complemento" not in tiny.contato_cliente_para_criar(_cliente(complemento=lixo))
    assert tiny.contato_cliente_para_criar(_cliente(complemento="Galpao 2"))["complemento"] == "Galpao 2"


def test_contato_do_cliente_sem_numero():
    assert "numero" not in tiny.contato_cliente_para_criar(_cliente(numero=None))


def test_contato_do_cliente_pessoa_fisica():
    c = tiny.contato_cliente_para_criar(_cliente(cgc=None, cpf="52998224725"))
    assert c["cpf_cnpj"] == "52998224725" and c["tipo_pessoa"] == "F"


def test_contato_do_cliente_corta_o_nome_em_50():
    assert tiny.contato_cliente_para_criar(_cliente(nome="B" * 90))["nome"] == "B" * 50


def test_contato_do_cliente_nunca_leva_id_nem_codigo():
    c = tiny.contato_cliente_para_criar(_cliente())
    assert "id" not in c and "codigo" not in c
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tiny_core.py -k contato_do_cliente -v`
Expected: FAIL — `AttributeError: module 'app.core.tiny' has no attribute 'contato_cliente_para_criar'`.

- [ ] **Step 3: Write minimal implementation** (em `core/tiny.py`, depois de `contato_para_alterar`; acrescentar `from types import SimpleNamespace` aos imports)

```python
def _complemento_do_cliente(valor) -> str:
    """O legado preenchia complemento vazio com "-": so traco/espaco e' vazio."""
    texto = _texto(valor)
    return "" if not texto.strip("- ") else texto


def _cliente_como_empresa(cliente) -> SimpleNamespace:
    """Traduz o Cliente para os nomes que `montar_contato` le.

    Diferencas do legado: `numero` e' BigInteger, o telefone mora em
    `telefones` (plural) e o complemento vazio veio como "-".
    """
    return SimpleNamespace(
        nome=cliente.nome, cgc=cliente.cgc, cpf=cliente.cpf, insc_est=cliente.insc_est,
        endereco=cliente.endereco,
        numero=None if cliente.numero is None else str(cliente.numero),
        complemento=_complemento_do_cliente(cliente.complemento),
        bairro=cliente.bairro, municipio=cliente.municipio, estado=cliente.estado,
        cep=cliente.cep, email=cliente.email, telefone=cliente.telefones,
    )


def contato_cliente_para_criar(cliente) -> dict:
    """Payload de inclusao para o Cliente destinatario de proposta.

    So existe a CRIACAO: contato de Cliente que ja existe no Tiny e' adotado e
    nunca alterado — o cadastro do legado tende a ser pior que o de la.
    """
    return contato_para_criar(_cliente_como_empresa(cliente))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tiny_core.py -q`
Expected: PASS (inclusive os testes antigos de `montar_contato`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/tiny.py backend/tests/test_tiny_core.py
git commit -m "feat(tiny): contato do tiny a partir do cliente do legado"
```

---

### Task 3: `sincronizar_cliente` (`integrations/tiny_client.py`)

**Files:**
- Modify: `backend/app/integrations/tiny_client.py`
- Test: `backend/tests/test_tiny_clientes_sync.py` (novo)

**Interfaces:**
- Consumes: `tiny.contato_cliente_para_criar(cliente)` (Task 2); colunas `Cliente.tiny_*` (Task 1); `pesquisar_contato`, `incluir_contato`, `_marcar`, `_aplicar` (existentes).
- Produces: `stmt_travar_cliente(cliente_id: int)` (Select com `FOR UPDATE OF clientes`); `sincronizar_cliente(cliente_id: int, *, db=None) -> None` (nunca levanta).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_tiny_clientes_sync.py`:

```python
import pytest

from app.core import tiny as tiny_core
from app.core.config import settings
from app.integrations import tiny_client
from app.models import Cliente

CNPJ = "31790710000196"


@pytest.fixture(autouse=True)
def _sem_log(monkeypatch):
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: None)


@pytest.fixture()
def falso_tiny(monkeypatch):
    """Substitui as chamadas HTTP; `alterar`/`obter` explodem se alguem chamar."""
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")
    chamadas = {"pesquisa": [], "incluir": []}
    respostas = {
        "pesquisa": [tiny_core.Resultado(ok=False, codigo_erro=20, mensagem="sem registros")],
        "incluir": tiny_core.Resultado(ok=True, id=999),
    }

    def pesquisar(doc):
        chamadas["pesquisa"].append(doc)
        fila = respostas["pesquisa"]
        return fila.pop(0) if len(fila) > 1 else fila[0]

    def proibido(*a, **k):
        raise AssertionError("Cliente nunca e' alterado no Tiny")

    monkeypatch.setattr(tiny_client, "pesquisar_contato", pesquisar)
    monkeypatch.setattr(tiny_client, "incluir_contato",
                        lambda c: (chamadas["incluir"].append(c), respostas["incluir"])[1])
    monkeypatch.setattr(tiny_client, "alterar_contato", proibido)
    monkeypatch.setattr(tiny_client, "obter_contato_bruto", proibido)
    return chamadas, respostas


def _cliente(db, **kw):
    base = dict(nome="IMETAME METALMECANICA LTDA", cgc=CNPJ, numero=643, complemento="-",
                municipio="ARACRUZ", estado="ES", telefones="27 99619-1347")
    base.update(kw)
    c = Cliente(**base); db.add(c); db.commit(); db.refresh(c)
    return c


def test_cria_quando_nao_existe_no_tiny(db_session, falso_tiny):
    chamadas, _ = falso_tiny
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_id == 999 and c.tiny_status == "enviada" and c.tiny_erro is None
    assert c.tiny_em is not None
    assert chamadas["pesquisa"] == [CNPJ]
    assert chamadas["incluir"][0]["fone"] == "27 99619-1347"
    assert chamadas["incluir"][0]["tipos_contato"] == [{"tipo": "Cliente"}]


def test_adota_o_que_existe_sem_mandar_nada(db_session, falso_tiny):
    chamadas, respostas = falso_tiny
    respostas["pesquisa"] = [tiny_core.Resultado(ok=True, id=610662219)]
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_id == 610662219 and c.tiny_status == "enviada"
    assert chamadas["incluir"] == []


def test_com_tiny_id_nao_chama_o_tiny(db_session, falso_tiny):
    """Segundo sync do mesmo cliente (duplo agendamento): a checagem vem DEPOIS
    da trava, entao quem chega por ultimo ve o tiny_id e sai."""
    chamadas, _ = falso_tiny
    c = _cliente(db_session, tiny_id=123, tiny_status="enviada")
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    assert chamadas["pesquisa"] == [] and chamadas["incluir"] == []


def test_sem_documento_marca_erro_sem_chamar(db_session, falso_tiny):
    chamadas, _ = falso_tiny
    c = _cliente(db_session, cgc=None, cpf=None)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_status == "erro" and c.tiny_erro == "cliente sem CNPJ/CPF"
    assert chamadas["pesquisa"] == []


@pytest.mark.parametrize("pesquisa", [
    tiny_core.Resultado(ok=False, codigo_erro=6, mensagem="bloqueado"),
    tiny_core.Resultado(ok=False, tentar_de_novo=True, mensagem="timeout"),
    tiny_core.Resultado(ok=False, mensagem="contato encontrado com documento diferente"),
    tiny_core.Resultado(ok=False, mensagem="resposta do Tiny nao e' JSON"),
])
def test_pesquisa_que_nao_e_erro_20_fica_pendente_e_nao_cria(db_session, falso_tiny, pesquisa):
    chamadas, respostas = falso_tiny
    respostas["pesquisa"] = [pesquisa]
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_status == "pendente" and c.tiny_id is None
    assert chamadas["incluir"] == []


def test_recusa_na_inclusao_marca_erro_com_a_mensagem(db_session, falso_tiny):
    _, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=31, mensagem="Cidade nao encontrada")
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_status == "erro" and c.tiny_erro == "Cidade nao encontrada"


def test_cliente_sem_nome_vira_erro_sem_excecao(db_session, falso_tiny):
    """`clientes.nome` e' nullable no legado e o Tiny exige nome: a recusa vira
    `erro` visivel, nao excecao."""
    chamadas, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=31, mensagem="nome obrigatorio")
    c = _cliente(db_session, nome=None)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert "nome" not in chamadas["incluir"][0]
    assert c.tiny_status == "erro" and c.tiny_erro == "nome obrigatorio"


def test_limite_na_inclusao_fica_pendente(db_session, falso_tiny):
    _, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=6, mensagem="bloqueado")
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_status == "pendente" and c.tiny_erro is None


def test_duplicidade_pesquisa_de_novo_e_adota(db_session, falso_tiny):
    chamadas, respostas = falso_tiny
    respostas["pesquisa"] = [tiny_core.Resultado(ok=False, codigo_erro=20),
                             tiny_core.Resultado(ok=True, id=777)]
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=30, mensagem="duplicado")
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_id == 777 and c.tiny_status == "enviada"
    assert len(chamadas["pesquisa"]) == 2


def test_cliente_inativo_tambem_e_sincronizado(db_session, falso_tiny):
    c = _cliente(db_session, ativo=False)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_id == 999 and c.tiny_status == "enviada"


def test_desligado_nao_marca_nada(db_session, monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_status is None


def test_cliente_inexistente_nao_explode(db_session, falso_tiny):
    tiny_client.sincronizar_cliente(99999, db=db_session)


def test_nao_propaga_excecao(db_session, falso_tiny, monkeypatch):
    def explode(doc):
        raise RuntimeError("boom")
    monkeypatch.setattr(tiny_client, "pesquisar_contato", explode)
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)   # nao levanta


def test_trava_do_cliente_e_for_update_of_clientes():
    """Mesma licao de 17/09 (empresas): o SQLite ignora FOR UPDATE, so o SQL
    compilado no dialeto do Postgres pega uma trava errada."""
    from sqlalchemy.dialects import postgresql

    sql = str(tiny_client.stmt_travar_cliente(1).compile(dialect=postgresql.dialect()))
    assert sql.rstrip().endswith("FOR UPDATE OF clientes")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tiny_clientes_sync.py -v`
Expected: FAIL — `AttributeError: module 'app.integrations.tiny_client' has no attribute 'sincronizar_cliente'`.

- [ ] **Step 3: Write minimal implementation**

Em `integrations/tiny_client.py`:

1. Renomear o parâmetro `empresa` → `registro` em `_marcar` e `_aplicar` (corpo idêntico, só o nome; servem aos dois models). Atualizar a docstring de `_marcar`, se houver, para "Empresa ou Cliente".
2. Depois de `sincronizar_empresa`, acrescentar:

```python
def stmt_travar_cliente(cliente_id: int):
    """`SELECT ... FOR UPDATE OF clientes` do Cliente a espelhar.

    `OF clientes` pelo mesmo motivo de `stmt_travar_empresa`: se um dia o model
    ganhar relacionamento lazy="joined", um `FOR UPDATE` cru volta a quebrar no
    Postgres — e o SQLite dos testes nao avisa.
    """
    from sqlalchemy import select

    from app.models import Cliente

    return select(Cliente).where(Cliente.id == cliente_id).with_for_update(of=Cliente)


def sincronizar_cliente(cliente_id: int, *, db=None) -> None:
    """Alvo do BackgroundTask: garante que o Cliente destinatario de proposta
    existe no Tiny. Nunca propaga.

    So PESQUISAR -> ADOTAR ou CRIAR. Diferente da Empresa, nao ha caminho de
    alteracao: contato que ja existe la fica como esta (spec de 23/09/2026).
    Cliente inativo tambem entra — teve proposta, pode ser faturado.
    """
    from app.models.database import SessionLocal

    if not integracao_ativa():
        return

    propria = db is None
    db = db or SessionLocal()
    try:
        # A checagem de tiny_id vem DEPOIS da trava: dois syncs do mesmo cliente
        # (criar e duplicar em seguida) pesquisariam os dois antes de qualquer um
        # gravar — e criariam dois contatos.
        cliente = db.execute(stmt_travar_cliente(cliente_id)).scalars().first()
        if cliente is None or cliente.tiny_id:
            return
        documento = cliente.cgc or cliente.cpf or ""
        if not documento:
            _marcar(db, cliente, status="erro", erro="cliente sem CNPJ/CPF")
            return

        achado = pesquisar_contato(documento)
        if achado.ok and achado.id:
            _marcar(db, cliente, status="enviada", tiny_id=achado.id)
            return
        if not achado.nao_encontrado:
            # So o erro 20 e' "nao existe la". Limite, rede, corpo invalido ou
            # documento divergente deixam em aberto — criar geraria DUPLICADO.
            _marcar(db, cliente, status="pendente")
            return

        resultado = incluir_contato(tiny.contato_cliente_para_criar(cliente))
        if resultado.duplicidade:
            # Rede de seguranca: alguem criou entre a pesquisa e a inclusao.
            achado = pesquisar_contato(documento)
            if achado.ok and achado.id:
                _marcar(db, cliente, status="enviada", tiny_id=achado.id)
                return
        _aplicar(db, cliente, resultado)
    except Exception:  # noqa: BLE001 - best-effort: nunca derruba quem agendou
        try:
            db.rollback()
        except Exception:  # noqa: BLE001 - a sessao pode nao ter transacao aberta
            pass
        logger.exception("falha ao sincronizar o cliente %s com o Tiny", cliente_id)
    finally:
        if propria:
            db.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tiny_clientes_sync.py tests/test_tiny_client.py tests/test_empresas_tiny.py -q`
Expected: PASS (a renomeação de `_marcar`/`_aplicar` não quebrou a Empresa).

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrations/tiny_client.py backend/tests/test_tiny_clientes_sync.py
git commit -m "feat(tiny): sincronizar cliente adota ou cria o contato, nunca altera"
```

---

### Task 4: Gatilho na proposta (`api/propostas.py`)

**Files:**
- Modify: `backend/app/api/propostas.py` (helpers perto de `_agendar_empresa_no_tiny`; rotas `criar`, `atualizar`, `duplicar`)
- Test: `backend/tests/test_propostas_tiny_cliente.py` (novo)

**Interfaces:**
- Consumes: `tiny_client.sincronizar_cliente(cliente_id)` (Task 3); `Cliente.tiny_id/tiny_status/tiny_erro` (Task 1).
- Produces: `_agendar_cliente_no_tiny(db, background_tasks, proposta) -> None` (nunca levanta).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_propostas_tiny_cliente.py`:

```python
import pytest

from app.core.config import settings
from app.integrations import tiny_client
from app.models import Cliente, Empresa

CNPJ_CLIENTE = "08857492000148"
CNPJ_FILIAL = "36312056000552"


@pytest.fixture(autouse=True)
def integracao_ligada(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")


@pytest.fixture()
def agendados(monkeypatch):
    """Quem foi agendado, sem falar com o Tiny."""
    registro = {"clientes": [], "empresas": []}
    monkeypatch.setattr(tiny_client, "sincronizar_cliente",
                        lambda cid, **kw: registro["clientes"].append(cid))
    monkeypatch.setattr(tiny_client, "sincronizar_empresa",
                        lambda eid, **kw: registro["empresas"].append(eid))
    return registro


def _cliente(db, **kw):
    base = dict(nome="ACME", cgc=CNPJ_CLIENTE)
    base.update(kw)
    c = Cliente(**base); db.add(c); db.commit(); db.refresh(c)
    return c


def _dest(cliente_id):
    return {"tipo": "cliente", "id": cliente_id, "nome": "ACME"}


def test_criar_proposta_para_cliente_sem_tiny_agenda(client_comercial, agendados, db_session):
    c = _cliente(db_session)
    r = client_comercial.post("/propostas", json={"destinatario": _dest(c.id)})
    assert r.status_code == 201, r.text
    assert agendados["clientes"] == [c.id]
    db_session.refresh(c)
    assert c.tiny_status == "pendente" and c.tiny_erro is None


def test_cliente_com_tiny_id_nao_agenda_nem_marca(client_comercial, agendados, db_session):
    c = _cliente(db_session, tiny_id=610662219, tiny_status="enviada")
    r = client_comercial.post("/propostas", json={"destinatario": _dest(c.id)})
    assert r.status_code == 201
    assert agendados["clientes"] == []
    db_session.refresh(c)
    assert c.tiny_status == "enviada"


def test_editar_proposta_agenda(client_comercial, agendados, db_session):
    c = _cliente(db_session)
    pid = client_comercial.post("/propostas", json={"destinatario": _dest(c.id)}).json()["id"]
    agendados["clientes"].clear()
    r = client_comercial.put(f"/propostas/{pid}", json={"destinatario": _dest(c.id)})
    assert r.status_code == 200 and agendados["clientes"] == [c.id]


def test_editar_proposta_de_cliente_inativo_agenda(client_comercial, agendados, db_session):
    c = _cliente(db_session)
    pid = client_comercial.post("/propostas", json={"destinatario": _dest(c.id)}).json()["id"]
    c.ativo = False; db_session.commit()
    agendados["clientes"].clear()
    r = client_comercial.put(f"/propostas/{pid}", json={"destinatario": _dest(c.id)})
    assert r.status_code == 200 and agendados["clientes"] == [c.id]


def test_duplicar_proposta_agenda(client_comercial, agendados, db_session):
    c = _cliente(db_session)
    pid = client_comercial.post("/propostas", json={"destinatario": _dest(c.id)}).json()["id"]
    agendados["clientes"].clear()
    r = client_comercial.post(f"/propostas/{pid}/duplicar")
    assert r.status_code == 201 and agendados["clientes"] == [c.id]


def test_proposta_para_empresa_nao_agenda_a_matriz(client_comercial, agendados, db_session):
    """So o DESTINATARIO conta: a matriz de uma filial nao entra por tabela."""
    matriz = _cliente(db_session)
    emp = Empresa(nome="Filial", cgc=CNPJ_FILIAL, cliente=matriz.id)
    db_session.add(emp); db_session.commit()
    r = client_comercial.post("/propostas", json={"destinatario": {
        "tipo": "empresa", "id": emp.id, "matriz": matriz.id, "nome": "Filial"}})
    assert r.status_code == 201, r.text
    assert agendados["clientes"] == [] and agendados["empresas"] == [emp.id]


def test_integracao_desligada_nao_agenda_nem_marca(client_comercial, agendados, db_session, monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    c = _cliente(db_session)
    assert client_comercial.post("/propostas", json={"destinatario": _dest(c.id)}).status_code == 201
    db_session.refresh(c)
    assert agendados["clientes"] == [] and c.tiny_status is None


def test_falha_do_tiny_nao_derruba_a_proposta(client_comercial, db_session, monkeypatch):
    def explode(*a, **k):
        raise RuntimeError("Tiny fora do ar")
    monkeypatch.setattr(tiny_client, "sincronizar_cliente", explode)
    c = _cliente(db_session)
    assert client_comercial.post("/propostas", json={"destinatario": _dest(c.id)}).status_code == 201


def test_falha_ao_marcar_pendente_nao_levanta():
    from types import SimpleNamespace
    from app.api.propostas import _agendar_cliente_no_tiny

    class BancoQuebrado:
        def get(self, *a, **k):
            raise RuntimeError("banco fora do ar")

        def rollback(self):
            pass

    tarefas = SimpleNamespace(add_task=lambda *a, **k: None)
    _agendar_cliente_no_tiny(BancoQuebrado(), tarefas,
                             SimpleNamespace(empresa=None, cliente=1))   # nao levanta
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_propostas_tiny_cliente.py -v`
Expected: FAIL — os de agendamento com `agendados["clientes"] == []`; o último com `ImportError: cannot import name '_agendar_cliente_no_tiny'`.

- [ ] **Step 3: Write minimal implementation**

Em `api/propostas.py`, acrescentar `Cliente` ao import de `app.models` (se ainda não estiver) e, logo depois de `_agendar_empresa_no_tiny`:

```python
def _tiny_cliente_seguro(cliente_id: int) -> None:
    """Envio best-effort do Cliente: a proposta ja foi salva."""
    try:
        tiny_client.sincronizar_cliente(cliente_id)
    except Exception:  # noqa: BLE001
        logger.exception("falha ao agendar o cliente %s no Tiny", cliente_id)


def _agendar_cliente_no_tiny(db: Session, background_tasks: BackgroundTasks, proposta) -> None:
    """Cliente destinatario de proposta precisa existir no Tiny (spec 23/09/2026).

    Decide pela proposta salva, nao por marcador do servico: assim criar,
    editar e DUPLICAR (que nao passa bloco `destinatario`) caem no mesmo lugar.
    So o destinatario conta — proposta para Empresa nao agenda a matriz dela.
    Cliente com `tiny_id` nao gasta chamada: "se ja existe, ignora".
    """
    if proposta.empresa is not None or proposta.cliente is None:
        return
    if not tiny_client.integracao_ativa():
        return
    try:
        cliente = db.get(Cliente, proposta.cliente)
        if cliente is None or cliente.tiny_id:
            return
        cliente.tiny_status = "pendente"
        cliente.tiny_erro = None
        db.commit()
    except Exception:  # noqa: BLE001 - a proposta ja foi salva
        logger.exception("falha ao marcar o cliente %s como pendente no Tiny", proposta.cliente)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
    background_tasks.add_task(_tiny_cliente_seguro, proposta.cliente)
```

Nas rotas:

- `criar`: depois de `_agendar_empresa_no_tiny(db, background_tasks, proposta)` → `_agendar_cliente_no_tiny(db, background_tasks, proposta)`.
- `atualizar`: depois de `_agendar_empresa_no_tiny(db, background_tasks, atualizado)` → `_agendar_cliente_no_tiny(db, background_tasks, atualizado)`.
- `duplicar`: acrescentar o parâmetro `background_tasks: BackgroundTasks,` (logo depois de `proposta_id: int,`) e trocar o `return ps.montar_saida(db, nova)` por:

```python
    saida = ps.montar_saida(db, nova)
    _agendar_cliente_no_tiny(db, background_tasks, nova)
    return saida
```

(`duplicar` continua **sem** agendar Empresa: a filial não foi editada.)

Observação: se o `db.get` falhar, o agendamento ainda acontece — o `sincronizar_cliente` relê o cliente e decide sozinho. É o mesmo comportamento da Empresa.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_propostas_tiny_cliente.py tests/test_empresas_tiny.py tests/test_propostas*.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/propostas.py backend/tests/test_propostas_tiny_cliente.py
git commit -m "feat(propostas): cliente destinatario sem tiny_id e enviado ao tiny"
```

---

### Task 5: Worker de reenvio pega os Clientes pendentes

**Files:**
- Modify: `backend/app/tarefas/tiny_pendentes.py`
- Test: `backend/tests/test_tarefa_tiny_pendentes.py` (acrescentar)

**Interfaces:**
- Consumes: `tiny_client.sincronizar_cliente` (Task 3), `Cliente.tiny_status/tiny_em` (Task 1).
- Produces: `pendentes_clientes(db, limite: int) -> list[Cliente]`; `_rodar_job` devolve `{"tentadas": N}` somando Empresas + Clientes.

- [ ] **Step 1: Write the failing tests** (no fim de `tests/test_tarefa_tiny_pendentes.py`; acrescentar `Cliente` ao import de `app.models`)

```python
def _cliente(db, documento, **kw):
    c = Cliente(nome="Cliente", cgc=documento, **kw)
    db.add(c); db.commit(); db.refresh(c)
    return c


def test_pendentes_clientes_inclui_inativo_e_so_pendente(db_session):
    ativo = _cliente(db_session, CNPJ, tiny_status="pendente")
    inativo = _cliente(db_session, "11222333000181", tiny_status="pendente", ativo=False)
    _cliente(db_session, "08857492000148", tiny_status="erro")
    _cliente(db_session, "05571228000150", tiny_status="enviada")
    _cliente(db_session, "99988877000166", tiny_status=None)

    ids = [c.id for c in tiny_pendentes.pendentes_clientes(db_session, limite=10)]
    assert sorted(ids) == sorted([ativo.id, inativo.id])


def test_pendentes_clientes_com_limite_zero_nao_consulta(db_session):
    _cliente(db_session, CNPJ, tiny_status="pendente")
    assert tiny_pendentes.pendentes_clientes(db_session, limite=0) == []


def test_rodar_job_divide_o_teto_empresas_primeiro(db_session, monkeypatch):
    monkeypatch.setattr(settings, "JOB_TINY_LIMITE", 3)
    monkeypatch.setattr(tiny_pendentes, "SessionLocal", lambda: db_session)
    feitos = []
    monkeypatch.setattr(tiny_pendentes.tiny_client, "sincronizar_empresa",
                        lambda eid, **kw: feitos.append(("empresa", eid)))
    monkeypatch.setattr(tiny_pendentes.tiny_client, "sincronizar_cliente",
                        lambda cid, **kw: feitos.append(("cliente", cid)))

    e1 = _empresa(db_session, CNPJ, tiny_status="pendente")
    e2 = _empresa(db_session, "11222333000181", tiny_status="pendente")
    c1 = _cliente(db_session, "08857492000148", tiny_status="pendente")
    _cliente(db_session, "05571228000150", tiny_status="pendente")   # fica para a proxima volta

    resumo = tiny_pendentes._rodar_job(pausa=0)

    assert sorted(feitos[:2]) == sorted([("empresa", e1.id), ("empresa", e2.id)])
    assert feitos[2:] == [("cliente", c1.id)]
    assert resumo["tentadas"] == 3


def test_rodar_job_so_com_cliente_pendente(db_session, monkeypatch):
    monkeypatch.setattr(tiny_pendentes, "SessionLocal", lambda: db_session)
    feitos = []
    monkeypatch.setattr(tiny_pendentes.tiny_client, "sincronizar_cliente",
                        lambda cid, **kw: feitos.append(cid))
    c = _cliente(db_session, CNPJ, tiny_status="pendente")
    assert tiny_pendentes._rodar_job(pausa=0)["tentadas"] == 1 and feitos == [c.id]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tarefa_tiny_pendentes.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'pendentes_clientes'`.

- [ ] **Step 3: Write minimal implementation**

Em `tarefas/tiny_pendentes.py`: import `from app.models import Cliente, Empresa`; depois de `pendentes`:

```python
def pendentes_clientes(db, limite: int) -> list:
    """Clientes parados em `pendente`, o mais antigo primeiro.

    SEM filtro de `ativo`, de proposito: o Cliente so vira `pendente` por ter
    recebido proposta, e cliente inativo com proposta tambem pode ser faturado.
    """
    if limite <= 0:
        return []
    return (db.query(Cliente)
            .filter(Cliente.tiny_status == "pendente")
            .order_by(Cliente.tiny_em.asc().nullsfirst(), Cliente.id)
            .limit(limite)
            .all())
```

Trocar o corpo de `_rodar_job` por:

```python
    db = SessionLocal()
    try:
        empresas = pendentes(db, settings.JOB_TINY_LIMITE)
        # O teto da volta e' UM so para os dois: cada item gasta 2 das 20
        # chamadas/minuto da conta. Empresas primeiro — ja estavam na fila.
        clientes = pendentes_clientes(db, settings.JOB_TINY_LIMITE - len(empresas))
        fila = ([(tiny_client.sincronizar_empresa, e.id) for e in empresas]
                + [(tiny_client.sincronizar_cliente, c.id) for c in clientes])
        if not fila:
            return {"tentadas": 0}
        logger.info("job tiny: %s empresa(s) e %s cliente(s) pendente(s) para reenviar",
                    len(empresas), len(clientes))
        for i, (sincronizar, registro_id) in enumerate(fila):
            if i and pausa:
                time.sleep(pausa)
            # Nunca levanta: marca o proprio estado do registro e loga.
            sincronizar(registro_id)
        return {"tentadas": len(fila)}
    finally:
        db.close()
```

Atualizar a docstring do módulo: acrescentar um parágrafo dizendo que desde 23/09/2026 a volta também reenvia **Clientes** `pendente` (destinatários de proposta, inclusive inativos), dividindo o mesmo teto. **Atenção:** o `tiny_client.sincronizar_empresa` precisa ser lido **dentro** de `_rodar_job` (como acima), não capturado no import — os testes fazem monkeypatch no atributo do módulo.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tarefa_tiny_pendentes.py -q`
Expected: PASS (inclusive os testes antigos das Empresas).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tarefas/tiny_pendentes.py backend/tests/test_tarefa_tiny_pendentes.py
git commit -m "feat(tiny): worker de reenvio tambem pega clientes pendentes"
```

---

### Task 6: Script de carga `enviar_clientes_tiny`

**Files:**
- Create: `backend/app/scripts/enviar_clientes_tiny.py`
- Test: `backend/tests/test_enviar_clientes_tiny.py` (novo)

**Interfaces:**
- Consumes: `tiny_client.pesquisar_contato`, `tiny_client.incluir_contato`, `tiny.contato_cliente_para_criar` (Task 2), `Cliente.tiny_*` (Task 1), `Proposta` (model existente: `propostas.cliente`, `propostas.empresa`).
- Produces: `planejar(db, limite=None) -> list[Cliente]`; `processar(db, clientes, *, aplicar: bool, pausa=7.0) -> dict` com chaves `candidatas, adotadas, criadas, erros, puladas, sem_documento, interrompido, pendencias` (`pendencias`: lista de dicts `cliente_id, cliente, documento, motivo`); `main(argv=None)`.

**Proposta desabilitada (`is_deleted`) não conta** para a fila — detalhe que a spec não cobria.

**Desvio consciente da spec:** a spec diz que o `--aplicar` "chama `sincronizar_cliente`". O script segue o molde de `enviar_empresas_tiny` (laço próprio com `pesquisar_contato`/`incluir_contato`), porque precisa distinguir **bloqueio** (parar tudo) de **pesquisa inconclusiva** (pular e seguir) — distinção que `sincronizar_cliente` não devolve — e porque a simulação precisa do mesmo laço sem gravar. As decisões são as mesmas.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_enviar_clientes_tiny.py`:

```python
import csv

import pytest

from app.core import tiny as tiny_core
from app.core.config import settings
from app.integrations import tiny_client
from app.models import Cliente, Empresa, Proposta
from app.scripts import enviar_clientes_tiny as script

CNPJS = ["31790710000196", "11222333000181", "08857492000148", "36312056000552"]


@pytest.fixture(autouse=True)
def sem_pausa_e_ligado(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")
    monkeypatch.setattr(script.time, "sleep", lambda s: None)


@pytest.fixture()
def tiny_falso(monkeypatch):
    estado = {"pesquisa": {}, "pesquisados": [], "incluidos": [],
              "resultado_incluir": tiny_core.Resultado(ok=True, id=555)}
    monkeypatch.setattr(tiny_client, "pesquisar_contato",
                        lambda doc: (estado["pesquisados"].append(doc),
                                     estado["pesquisa"].get(doc, tiny_core.Resultado(ok=False, codigo_erro=20)))[1])
    monkeypatch.setattr(tiny_client, "incluir_contato",
                        lambda c: (estado["incluidos"].append(c), estado["resultado_incluir"])[1])
    return estado


def _com_proposta(db, cgc, **kw):
    c = Cliente(nome=f"Cliente {cgc[:4]}", cgc=cgc, **kw)
    db.add(c); db.flush()
    db.add(Proposta(numero=int(cgc[:6]), cliente=c.id))
    db.commit(); db.refresh(c)
    return c


def test_planejar_pega_quem_tem_proposta_propria_e_nao_tem_tiny_id(db_session):
    alvo = _com_proposta(db_session, CNPJS[0])
    inativo = _com_proposta(db_session, CNPJS[1], ativo=False)
    _com_proposta(db_session, CNPJS[2], tiny_id=999)                 # ja tem
    db_session.add(Cliente(nome="Sem proposta", cgc=CNPJS[3]))       # nunca recebeu proposta
    db_session.commit()
    assert [c.id for c in script.planejar(db_session)] == sorted([alvo.id, inativo.id])


def test_planejar_ignora_matriz_de_proposta_para_empresa(db_session):
    matriz = Cliente(nome="Matriz", cgc=CNPJS[0]); db_session.add(matriz); db_session.flush()
    emp = Empresa(nome="Filial", cgc=CNPJS[1], cliente=matriz.id); db_session.add(emp); db_session.flush()
    db_session.add(Proposta(numero=1, cliente=matriz.id, empresa=emp.id)); db_session.commit()
    assert script.planejar(db_session) == []


def test_planejar_ignora_proposta_desabilitada(db_session):
    c = _com_proposta(db_session, CNPJS[0])
    for p in db_session.query(Proposta).filter(Proposta.cliente == c.id):
        p.is_deleted = True
    db_session.commit()
    assert script.planejar(db_session) == []


def test_planejar_nao_repete_cliente_com_varias_propostas(db_session):
    c = _com_proposta(db_session, CNPJS[0])
    db_session.add(Proposta(numero=2, cliente=c.id)); db_session.commit()
    assert [x.id for x in script.planejar(db_session)] == [c.id]


def test_planejar_respeita_o_limite(db_session):
    _com_proposta(db_session, CNPJS[0]); _com_proposta(db_session, CNPJS[1])
    assert len(script.planejar(db_session, limite=1)) == 1


def test_simulacao_nao_grava_nem_cria(db_session, tiny_falso):
    a = _com_proposta(db_session, CNPJS[0])
    tiny_falso["pesquisa"][CNPJS[1]] = tiny_core.Resultado(ok=True, id=777)
    b = _com_proposta(db_session, CNPJS[1])
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=False, pausa=0)
    db_session.refresh(a); db_session.refresh(b)
    assert a.tiny_id is None and a.tiny_status is None
    assert b.tiny_id is None and b.tiny_status is None
    assert tiny_falso["incluidos"] == []
    assert resumo["criadas"] == 1 and resumo["adotadas"] == 1


def test_aplicar_adota_quem_existe_e_cria_o_resto(db_session, tiny_falso):
    tiny_falso["pesquisa"][CNPJS[0]] = tiny_core.Resultado(ok=True, id=610662219)
    a = _com_proposta(db_session, CNPJS[0])
    b = _com_proposta(db_session, CNPJS[1], numero=643, complemento="-")
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    db_session.refresh(a); db_session.refresh(b)
    assert a.tiny_id == 610662219 and a.tiny_status == "enviada"
    assert b.tiny_id == 555 and b.tiny_status == "enviada"
    assert len(tiny_falso["incluidos"]) == 1
    assert tiny_falso["incluidos"][0]["numero"] == "643"
    assert "complemento" not in tiny_falso["incluidos"][0]
    assert resumo["adotadas"] == 1 and resumo["criadas"] == 1


def test_sem_documento_vai_para_pendencias_sem_chamar(db_session, tiny_falso):
    c = _com_proposta(db_session, CNPJS[0])
    c.cgc = None; db_session.commit()
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    assert tiny_falso["pesquisados"] == []
    assert resumo["sem_documento"] == 1
    assert resumo["pendencias"][0]["motivo"] == "sem CNPJ/CPF"
    db_session.refresh(c)
    assert c.tiny_status == "erro"


def test_pesquisa_inconclusiva_pula_e_segue(db_session, tiny_falso):
    tiny_falso["pesquisa"][CNPJS[0]] = tiny_core.Resultado(ok=False, mensagem="contato encontrado com documento diferente")
    _com_proposta(db_session, CNPJS[0]); b = _com_proposta(db_session, CNPJS[1])
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    db_session.refresh(b)
    assert resumo["puladas"] == 1 and b.tiny_id == 555
    assert resumo["pendencias"][0]["motivo"] == "contato encontrado com documento diferente"


def test_recusa_na_inclusao_marca_erro_e_segue(db_session, tiny_falso):
    tiny_falso["resultado_incluir"] = tiny_core.Resultado(ok=False, codigo_erro=31, mensagem="Cidade nao encontrada")
    a = _com_proposta(db_session, CNPJS[0])
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    db_session.refresh(a)
    assert a.tiny_status == "erro" and a.tiny_erro == "Cidade nao encontrada"
    assert resumo["erros"] == 1


def test_bloqueio_interrompe(db_session, tiny_falso):
    tiny_falso["pesquisa"][CNPJS[0]] = tiny_core.Resultado(ok=False, codigo_erro=6)
    _com_proposta(db_session, CNPJS[0]); _com_proposta(db_session, CNPJS[1])
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    assert resumo["interrompido"] is True
    assert tiny_falso["pesquisados"] == [CNPJS[0]]


def test_idempotente(db_session, tiny_falso):
    _com_proposta(db_session, CNPJS[0])
    script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    assert script.planejar(db_session) == []


def test_main_simula_e_grava_o_csv(db_session, tiny_falso, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(script, "SessionLocal", lambda: db_session)
    c = _com_proposta(db_session, CNPJS[0])
    c.cgc = None; db_session.commit()
    caminho = tmp_path / "p.csv"
    script.main(["--pendencias", str(caminho)])
    assert "SIMULACAO" in capsys.readouterr().out
    db_session.refresh(c)
    assert c.tiny_status is None                          # simulacao nao grava
    linhas = list(csv.DictReader(caminho.open(encoding="utf-8")))
    assert linhas[0]["cliente_id"] == str(c.id) and linhas[0]["motivo"] == "sem CNPJ/CPF"


def test_main_recusa_com_integracao_desligada(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    with pytest.raises(SystemExit):
        script.main([])
```

> `Proposta(numero=..., cliente=...)` é o menor registro válido (ver `tests/test_propostas.py::test_models_proposta_basico`); `numero` é UNIQUE, por isso `_com_proposta` deriva o número do CNPJ.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_enviar_clientes_tiny.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.scripts.enviar_clientes_tiny'`.

- [ ] **Step 3: Write minimal implementation**

`backend/app/scripts/enviar_clientes_tiny.py`:

```python
"""Garante no Tiny o Cliente que ja recebeu proposta (carga de 23/09/2026).

Para cada Cliente — ATIVO OU NAO — que e' destinatario de pelo menos uma
proposta (`propostas.empresa IS NULL`) e ainda nao tem `tiny_id`: pesquisa o
documento no Tiny e ADOTA o contato que existir; so cria o que faltar. Contato
que ja existe NUNCA e' alterado.

    python -m app.scripts.enviar_clientes_tiny                  # simula (pesquisa, nao cria nem grava)
    python -m app.scripts.enviar_clientes_tiny --aplicar        # grava
    python -m app.scripts.enviar_clientes_tiny --aplicar --limite 20

Limite da conta: 20 chamadas por minuto; cada cliente gasta ate duas, dai ~7s
entre eles. Levando bloqueio (codigo 6/11) ou caindo a rede, o script PARA e diz
quantos faltaram — e' so rodar de novo. Idempotente: quem tem `tiny_id` sai da fila.

Os que pedem atencao (sem documento, pesquisa inconclusiva, recusa do Tiny) saem
no stdout e num CSV (`--pendencias`, padrao `relatorios/` na pasta atual).
"""
import argparse
import csv
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from app.core import tiny
from app.integrations import tiny_client
from app.models import Cliente, Proposta
from app.models.database import SessionLocal

PAUSA_PADRAO = 7.0


def planejar(db, limite: Optional[int] = None) -> list:
    """Clientes com proposta propria e sem contato no Tiny, em ordem de id."""
    com_proposta = (db.query(Proposta.cliente)
                    .filter(Proposta.empresa.is_(None), Proposta.cliente.isnot(None),
                            Proposta.is_deleted.is_(False)))
    query = (db.query(Cliente)
             .filter(Cliente.tiny_id.is_(None), Cliente.id.in_(com_proposta))
             .order_by(Cliente.id))
    if limite:
        query = query.limit(limite)
    return query.all()


def _marcar(db, cliente, *, status: str, tiny_id=None, erro=None) -> None:
    if tiny_id is not None:
        cliente.tiny_id = tiny_id
    cliente.tiny_status = status
    cliente.tiny_erro = (erro or "")[:255] or None
    cliente.tiny_em = datetime.now(timezone.utc)
    db.commit()


def processar(db, clientes, *, aplicar: bool, pausa: float = PAUSA_PADRAO) -> dict:
    """Pesquisa cada cliente, adota o que existir e so cria o que faltar.

    A SIMULACAO pesquisa de verdade (leitura) — e' o unico jeito de responder
    "vai criar quantos?" antes de valer — mas nao grava nada no banco.
    """
    resumo = {"candidatas": len(clientes), "adotadas": 0, "criadas": 0, "erros": 0,
              "puladas": 0, "sem_documento": 0, "interrompido": False, "pendencias": []}

    def pendencia(cliente, documento, motivo):
        resumo["pendencias"].append({"cliente_id": cliente.id, "cliente": cliente.nome or "",
                                     "documento": documento, "motivo": motivo})

    chamou = False
    for cliente in clientes:
        documento = cliente.cgc or cliente.cpf or ""
        rotulo = f"{cliente.id:5} {(cliente.nome or '')[:40]:40}"
        if not documento:
            if aplicar:
                _marcar(db, cliente, status="erro", erro="cliente sem CNPJ/CPF")
            resumo["sem_documento"] += 1
            pendencia(cliente, "", "sem CNPJ/CPF")
            print(f"  ! {rotulo} sem CNPJ/CPF")
            continue

        if chamou and pausa:
            time.sleep(pausa)                      # a pesquisa tambem gasta chamada
        chamou = True
        achado = tiny_client.pesquisar_contato(documento)

        if achado.ok and achado.id:
            if aplicar:
                _marcar(db, cliente, status="enviada", tiny_id=achado.id)
            resumo["adotadas"] += 1
            print(f"  = {rotulo} {'adotou' if aplicar else 'adotaria'} contato {achado.id}")
            continue
        if achado.deve_tentar_de_novo:
            resumo["interrompido"] = True
            break
        if not achado.nao_encontrado:
            # So o erro 20 e' "nao existe la": o resto deixa em aberto se o
            # contato ja existe — criar aqui geraria DUPLICADO no ERP.
            resumo["puladas"] += 1
            motivo = achado.mensagem or "pesquisa sem resposta clara"
            pendencia(cliente, documento, motivo)
            print(f"  ~ {rotulo} pulado: {motivo}")
            continue

        if not aplicar:
            resumo["criadas"] += 1
            print(f"  + {rotulo} criaria contato novo")
            continue

        resultado = tiny_client.incluir_contato(tiny.contato_cliente_para_criar(cliente))
        if resultado.ok and resultado.id is not None:
            _marcar(db, cliente, status="enviada", tiny_id=resultado.id)
            resumo["criadas"] += 1
            print(f"  + {rotulo} criou contato {resultado.id}")
        elif resultado.deve_tentar_de_novo:
            resumo["interrompido"] = True
            break
        else:
            _marcar(db, cliente, status="erro", erro=resultado.mensagem or "recusado sem id")
            resumo["erros"] += 1
            pendencia(cliente, documento, resultado.mensagem or "recusado sem id")
            print(f"  ! {rotulo} {resultado.mensagem}")

    if resumo["interrompido"]:
        feitos = (resumo["adotadas"] + resumo["criadas"] + resumo["erros"]
                  + resumo["puladas"] + resumo["sem_documento"])
        print(f"\nPAROU: o Tiny bloqueou por excesso de chamadas (ou a rede caiu). "
              f"{resumo['candidatas'] - feitos} cliente(s) ficaram para a proxima rodada.")
    return resumo


def _escrever_csv(caminho: Path, pendencias: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["cliente_id", "cliente", "documento", "motivo"])
        writer.writeheader()
        writer.writerows(pendencias)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aplicar", action="store_true", help="grava (padrao: so simula)")
    parser.add_argument("--limite", type=int, default=None, help="processa no maximo N clientes")
    parser.add_argument("--pendencias", default=None,
                        help="CSV dos que pedem atencao (padrao: relatorios/pendencias-clientes-tiny-<data>.csv)")
    args = parser.parse_args(argv)

    if not tiny_client.integracao_ativa():
        raise SystemExit("TINY_TOKEN vazio: integracao desligada, nada a fazer.")

    db = SessionLocal()
    try:
        clientes = planejar(db, args.limite)
        print(f"Clientes com proposta e sem contato no Tiny: {len(clientes)}")
        resumo = processar(db, clientes, aplicar=args.aplicar)
        caminho = Path(args.pendencias or f"relatorios/pendencias-clientes-tiny-{date.today().isoformat()}.csv")
        _escrever_csv(caminho, resumo["pendencias"])
        print(f"\nResultado: { {k: v for k, v in resumo.items() if k != 'pendencias'} }")
        print(f"Pendencias ({len(resumo['pendencias'])}) em {caminho}")
        if not args.aplicar:
            print("SIMULACAO — a pesquisa rodou (leitura), mas nada foi criado nem "
                  "gravado. Rode com --aplicar para valer.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_enviar_clientes_tiny.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/scripts/enviar_clientes_tiny.py backend/tests/test_enviar_clientes_tiny.py
git commit -m "feat(tiny): script de carga dos clientes com proposta no tiny"
```

---

### Task 7: Selo do Tiny na tela de Clientes

**Files:**
- Modify: `frontend/src/app/empresas/api.ts:96` (`rotuloTiny`)
- Create: `frontend/src/app/clientes/SeloTiny.tsx`
- Create: `frontend/src/app/clientes/SeloTiny.test.tsx`
- Modify: `frontend/src/app/clientes/api.ts` (`ClienteListItem`, `Cliente`)
- Modify: `frontend/src/app/clientes/ClientesPage.tsx:83-91` (coluna nova)
- Modify: `frontend/src/app/clientes/ClienteLayout.tsx:62` (selo ao lado do nome)
- Test: `frontend/src/app/clientes/ClientesPage.test.tsx` (acrescentar)

**Interfaces:**
- Consumes: `GET /clientes` e `GET /clientes/{id}` com `tiny_id`, `tiny_status`, `tiny_erro` (Task 1).
- Produces: `SeloTiny({ tiny_id, tiny_status, tiny_erro })`; `rotuloTiny(e: { tiny_status: TinyStatus })`; tipo `TinyStatus = 'pendente' | 'enviada' | 'erro' | null` exportado de `empresas/api.ts`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/app/clientes/SeloTiny.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SeloTiny } from './SeloTiny'

describe('SeloTiny', () => {
  it('enviada mostra o rótulo e o id do contato', () => {
    render(<SeloTiny tiny_id={610662219} tiny_status="enviada" tiny_erro={null} />)
    expect(screen.getByText('Enviada')).toBeInTheDocument()
    expect(screen.getByText('610662219')).toBeInTheDocument()
  })

  it('erro traz a mensagem no title', () => {
    render(<SeloTiny tiny_id={null} tiny_status="erro" tiny_erro="Cidade não encontrada" />)
    expect(screen.getByText('Erro')).toHaveAttribute('title', 'Cidade não encontrada')
  })

  it('pendente mostra o rótulo', () => {
    render(<SeloTiny tiny_id={null} tiny_status="pendente" tiny_erro={null} />)
    expect(screen.getByText('Pendente')).toBeInTheDocument()
  })

  it('sem status não renderiza nada', () => {
    const { container } = render(<SeloTiny tiny_id={null} tiny_status={null} tiny_erro={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
```

Em `ClientesPage.test.tsx`, trocar o `CLIENTE` para incluir `tiny_id: 610662219, tiny_status: 'enviada', tiny_erro: null` e acrescentar dentro do `describe`:

```tsx
  it('mostra a coluna do Tiny com o status', async () => {
    render(
      <MemoryRouter>
        <ClientesPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Tiny')).toBeInTheDocument()
    expect(screen.getByText('Enviada')).toBeInTheDocument()
  })
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/app/clientes/SeloTiny.test.tsx src/app/clientes/ClientesPage.test.tsx`
Expected: FAIL — `Failed to resolve import "./SeloTiny"` e coluna "Tiny" não encontrada.

- [ ] **Step 3: Write minimal implementation**

`frontend/src/app/empresas/api.ts` — trocar a tipagem do status e de `rotuloTiny` (o corpo não muda):

```ts
export type TinyStatus = 'pendente' | 'enviada' | 'erro' | null
```

Na interface `Empresa`, `tiny_status: TinyStatus`. E:

```ts
export function rotuloTiny(e: { tiny_status: TinyStatus }): string {
```

`frontend/src/app/clientes/api.ts` — em `ClienteListItem` e em `Cliente`, acrescentar (com `import type { TinyStatus } from '../empresas/api'` no topo):

```ts
  tiny_id: number | null
  tiny_status: TinyStatus
  tiny_erro: string | null
```

`frontend/src/app/clientes/SeloTiny.tsx`:

```tsx
import { cn } from '../../lib/utils'
import { rotuloTiny, type TinyStatus } from '../empresas/api'

interface Props {
  tiny_id: number | null
  tiny_status: TinyStatus
  tiny_erro: string | null
}

/** Status do contato no Tiny, no mesmo visual da coluna da página Empresas.
 *  Cliente só é espelhado quando recebe proposta; sem status, não mostra nada. */
export function SeloTiny({ tiny_id, tiny_status, tiny_erro }: Props) {
  if (!tiny_status) return null
  return (
    <span className="text-xs">
      <span className={cn(tiny_status === 'erro' && 'font-semibold text-danger')} title={tiny_erro ?? undefined}>
        {rotuloTiny({ tiny_status })}
      </span>
      {tiny_id != null && <span className="block text-slate-500">{tiny_id}</span>}
    </span>
  )
}
```

`ClientesPage.tsx` — no `head`, depois de `<TH>Ativo</TH>` acrescentar `<TH>Tiny</TH>`; na linha, depois do `<TD>` do Ativo:

```tsx
                <TD><SeloTiny tiny_id={c.tiny_id} tiny_status={c.tiny_status} tiny_erro={c.tiny_erro} /></TD>
```

(+ `import { SeloTiny } from './SeloTiny'`). Se a tabela tiver `colSpan` de linha vazia/carregando, somar 1.

`ClienteLayout.tsx` — trocar o `<h1 ...>` isolado por:

```tsx
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-extrabold text-slate-100">{cliente.nome || 'Cliente'}</h1>
          <SeloTiny tiny_id={cliente.tiny_id} tiny_status={cliente.tiny_status} tiny_erro={cliente.tiny_erro} />
        </div>
```

(+ `import { SeloTiny } from './SeloTiny'`).

Mocks de `Cliente` em outros testes que o `tsc` passe a recusar por faltar `tiny_*`: acrescentar `tiny_id: null, tiny_status: null, tiny_erro: null`.

- [ ] **Step 4: Run tests and the full frontend check**

Run: `npx vitest run src/app/clientes src/app/empresas && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: tudo PASS / sem erro.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/empresas/api.ts frontend/src/app/clientes/
git commit -m "feat(ui): status do tiny na listagem e no detalhe do cliente"
```

(Conferir com `git status` que só entraram arquivos desta task em `frontend/src/app/clientes/`.)

---

### Task 8: Documentação e changelog

**Files:**
- Modify: `CLAUDE.md` (raiz do repo)
- Modify: `docs/operacao-tiny-empresas.md`
- Modify: `frontend/src/app/changelog/data.ts`

**Interfaces:** nenhuma.

- [ ] **Step 1: `CLAUDE.md`**

1. Na lista de comandos do backend, depois da linha do `enviar_empresas_tiny`:

```
python -m app.scripts.enviar_clientes_tiny                          # SIMULA: garante no Tiny os clientes com proposta (--aplicar grava)
```

2. Na seção "Empresas e destinatário da proposta", depois do bullet do worker `tiny_pendentes`, acrescentar:

```markdown
- **Cliente destinatário de proposta também vai para o Tiny** (set/2026), mas **só é criado ou adotado, nunca alterado** — o cadastro do legado tende a ser pior que o de lá. Criar, editar ou **duplicar** proposta para Cliente sem `tiny_id` marca `clientes.tiny_status = 'pendente'` e agenda `sincronizar_cliente`; com `tiny_id`, nenhuma chamada. **Cliente inativo entra** (teve proposta, pode ser faturado). Só o destinatário conta: proposta para Empresa não leva a matriz. O worker de reenvio atende Empresas primeiro e divide o mesmo teto com os Clientes. A carga dos antigos é `app.scripts.enviar_clientes_tiny`. O cliente 692 (IMETAME) foi criado à mão em 22/09/2026 (contato 610662219) e é adotado pela carga.
```

3. Na seção "Migrações Alembic": trocar `(`0001`–`0031`)` por `(`0001`–`0032`)` e acrescentar ao fim da frase: `e o mesmo estado para o Cliente destinatário de proposta (`0032`, aditiva)`.

- [ ] **Step 2: `docs/operacao-tiny-empresas.md`** — acrescentar no fim uma seção `## Clientes destinatários de proposta (set/2026)` com: o que é espelhado (só criar/adotar); a ordem de deploy (código → `alembic upgrade head` → `enviar_clientes_tiny` sem flag → conferir resumo e CSV em `relatorios/` → `--aplicar`, ~25 min para ~212); o que fazer com cada motivo do CSV (sem CNPJ/CPF → corrigir o cadastro na página de Clientes e editar a proposta; documento diferente → conferir no Tiny à mão; recusa → a mensagem é a do Tiny); e a consulta de conferência:

```sql
select tiny_status, count(*) from clientes
where id in (select cliente from propostas where empresa is null)
group by 1;
```

- [ ] **Step 3: changelog** — nova primeira entrada em `CHANGELOG` de `frontend/src/app/changelog/data.ts`:

```ts
  {
    versao: '1.57.0',
    data: '23/09/2026',
    itens: [
      { tipo: 'novidade', texto: 'Cliente que recebe proposta passa a ter cadastro no Tiny: se já existe lá, o GestorHS só guarda o vínculo; se não existe, cria. O cadastro que já está no Tiny nunca é alterado. A lista e a página do cliente mostram o status do envio.' },
    ],
  },
```

- [ ] **Step 4: Verificação final**

Run (em `backend/`): `pytest -q`
Expected: só as falhas pré-existentes anotadas no início (ver Global Constraints).

Run (em `frontend/`): `npm test && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/operacao-tiny-empresas.md frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.57.0 — cliente de proposta no tiny erp"
```

---

## Depois do merge (Erick, fora do plano)

1. Deploy no EasyPanel + `alembic upgrade head` (aplica a `0032`).
2. `python -m app.scripts.enviar_clientes_tiny` → conferir resumo e CSV.
3. `python -m app.scripts.enviar_clientes_tiny --aplicar`.
4. Se ainda não estiver: `JOB_TINY_ATIVO=true` no ambiente, para o worker reenviar os `pendente`.
