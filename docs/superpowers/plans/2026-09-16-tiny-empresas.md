# Empresa no Tiny ERP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empresa criada ou editada no GestorHS passa a existir e a ser atualizada como contato no Tiny ERP, sem duplicar contato e sem apagar o que só existe lá.

**Architecture:** Núcleo puro em `core/tiny.py` (monta o contato, lê a resposta), I/O em `integrations/tiny_client.py` (httpx + `log_integracao`, best-effort, gating por `TINY_TOKEN`), disparado por `BackgroundTasks` depois do commit. O estado do envio mora em quatro colunas de `empresas` e aparece na tela, com botão de reenviar e script de acerto para o que já existe.

**Tech Stack:** FastAPI · SQLAlchemy 2 · Pydantic v2 · Alembic · httpx (+ `httpx.MockTransport` nos testes) · pytest (SQLite in-memory) · React 19 · TypeScript · Vitest.

**Spec:** `docs/superpowers/specs/2026-09-16-tiny-empresas-design.md`

## Global Constraints

- Idioma do domínio em PT-BR: modelos, rotas, variáveis e mensagens.
- Commits: Conventional Commits em português **sem acentos**, uma linha, **sem corpo e sem trailer de co-autor**.
- Nunca `git add -A`: arquivo por arquivo. Conferir `git branch --show-current` antes de cada commit.
- **NUNCA rodar `alembic upgrade` sem `--sql` nesta máquina**: o `backend/.env` aponta para o banco de PRODUÇÃO.
- **NENHUM teste pode chamar a API do Tiny de verdade.** Todo teste de I/O usa `httpx.MockTransport`. O token no `.env` é real e o Tiny **não tem ambiente de teste**: uma chamada de teste cria contato de verdade na conta da empresa.
- Integração desligada sem `TINY_TOKEN` (já declarado em `core/config.py`): no-op, nada marcado. `TINY_BASE_URL` padrão `https://api.tiny.com.br/api2`.
- O Tiny responde **HTTP 200 sempre**; o que vale é `retorno.status` e `retorno.codigo_erro`.
- Códigos: **20** = não encontrado (não é falha), **30** = duplicidade, **31** = validação, **6/11** = bloqueio por limite (vira `pendente`, não `erro`), **2** = token inválido.
- `tipos_contato` só na **criação** (`[{"tipo": "Cliente"}]`); na edição vai o que veio do Tiny (o campo acumula).
- `contato.alterar.php` **apaga o que não for enviado**: a edição lê o contato antes e reenvia inteiro.
- `nome` cortado em 50 caracteres no envio; o cadastro local fica inteiro.
- Campo vazio não entra no payload.
- Limite desta conta: **20 chamadas por minuto** (`x-limit-api`); cada empresa gasta duas.
- Backend: rodar de `backend/` com `source .venv/bin/activate`. Falhas pré-existentes conhecidas (ignorar): `test_certificados_gerais::test_anexar_lista_e_link`, `::test_excluir_remove`, `test_publico_certificado_geral::test_download_publico_com_token_valido`, `::test_download_publico_token_invalido_403`.
- Frontend: `npm run lint && npx tsc -b --noEmit && npm run build && npm test` antes de fechar.

## File Structure

**Backend — criar**
- `backend/app/core/tiny.py` — puro: mapeamento, contato de criação, mesclagem da edição, leitura da resposta, códigos.
- `backend/app/integrations/tiny_client.py` — httpx + log + `sincronizar_empresa`.
- `backend/alembic/versions/0031_empresa_tiny.py` — quatro colunas em `empresas`.
- `backend/app/scripts/enviar_empresas_tiny.py` — acerto das empresas já cadastradas.
- Testes: `tests/test_tiny_core.py`, `tests/test_tiny_client.py`, `tests/test_empresas_tiny.py`, `tests/test_enviar_empresas_tiny.py`.

**Backend — modificar**
- `app/models/empresa.py` (colunas), `app/schemas/empresa.py` (`EmpresaOut`), `app/api/empresas.py` (agendamento, rota de reenvio, filtro), `app/core/proposta_servico.py` + `app/api/propostas.py` (agendar a Empresa nova da proposta), `app/core/log_integracao.py` (`classificar_tipo` para `tiny`).

**Frontend — modificar**
- `src/app/empresas/api.ts` (campos e `reenviarTiny`), `src/app/empresas/EmpresasPage.tsx` (coluna, botão, filtro), `src/app/empresas/EmpresaModal.tsx` (estado no rodapé), `src/app/empresas/EmpresasPage.test.tsx`, `src/app/changelog/data.ts`.

**Docs**
- Criar `docs/operacao-tiny-empresas.md`; modificar `CLAUDE.md`.

---

### Task 0: Branch e baseline

**Files:** nenhum.

- [ ] **Step 1: Criar a branch**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current          # esperado: main
git switch -c feat/tiny-empresas
```

- [ ] **Step 2: Baseline**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5
cd ../frontend && npx vitest run 2>&1 | tail -3
```
Esperado: backend com as 4 falhas conhecidas; frontend limpo. Guardar os números.

---

### Task 1: Núcleo puro `app/core/tiny.py`

**Files:**
- Create: `backend/app/core/tiny.py`
- Test: `backend/tests/test_tiny_core.py`

**Interfaces:**
- Produces:
  - Constantes `NAO_ENCONTRADO = 20`, `DUPLICIDADE = 30`, `VALIDACAO = 31`, `TOKEN_INVALIDO = 2`, `LIMITE = (6, 11)`.
  - `@dataclass Resultado`: `ok: bool`, `id: int | None`, `codigo_erro: int | None`, `mensagem: str`; propriedades `nao_encontrado`, `duplicidade`, `deve_tentar_de_novo`.
  - `montar_contato(empresa) -> dict`
  - `contato_para_criar(empresa) -> dict`
  - `contato_para_alterar(empresa, atual: dict) -> dict`
  - `ler_resposta(corpo: dict) -> Resultado`

- [ ] **Step 1: Escrever os testes**

```python
# backend/tests/test_tiny_core.py
from types import SimpleNamespace

from app.core import tiny


def _empresa(**kw):
    base = dict(id=1, nome="ACME Filial Norte", cgc="36312056000552", cpf=None,
                insc_est="123456", endereco="BR 101", numero="S/N", complemento="KM 196",
                bairro="Zona Rural", municipio="Joao Neiva", estado="ES", cep="29680000",
                email="f@acme.com", telefone="2733330000")
    base.update(kw)
    return SimpleNamespace(**base)


def test_montar_contato_mapeia_os_campos():
    c = tiny.montar_contato(_empresa())
    assert c == {
        "nome": "ACME Filial Norte", "cpf_cnpj": "36312056000552", "tipo_pessoa": "J",
        "ie": "123456", "endereco": "BR 101", "numero": "S/N", "complemento": "KM 196",
        "bairro": "Zona Rural", "cidade": "Joao Neiva", "uf": "ES", "cep": "29680000",
        "email": "f@acme.com", "fone": "2733330000",
    }


def test_montar_contato_corta_o_nome_em_50():
    nome = "A" * 80
    assert tiny.montar_contato(_empresa(nome=nome))["nome"] == "A" * 50


def test_montar_contato_deixa_campo_vazio_de_fora():
    c = tiny.montar_contato(_empresa(insc_est=None, bairro="", email="   "))
    assert "ie" not in c and "bairro" not in c and "email" not in c


def test_montar_contato_cpf_vira_pessoa_fisica():
    c = tiny.montar_contato(_empresa(cgc=None, cpf="12345678909"))
    assert c["cpf_cnpj"] == "12345678909" and c["tipo_pessoa"] == "F"


def test_contato_para_criar_marca_como_cliente():
    # Sem tipos_contato o Tiny cria o contato como "Outro" (verificado em 16/09/2026).
    c = tiny.contato_para_criar(_empresa())
    assert c["sequencia"] == 1 and c["situacao"] == "A"
    assert c["tipos_contato"] == [{"tipo": "Cliente"}]
    assert "id" not in c and "codigo" not in c


def test_contato_para_alterar_preserva_o_que_e_do_tiny():
    # `contato.alterar.php` apaga o que nao for enviado: o que veio do Tiny volta inteiro.
    atual = {
        "id": "610661344", "codigo": "12527", "nome": "NOME ANTIGO", "cidade": "Cidade Velha",
        "tipos_contato": [{"tipo": "Cliente"}, {"tipo": "Fornecedor"}],
        "fantasia": "Apelido", "email_nfe": "nfe@acme.com", "obs": "cliente antigo",
        "pessoas_contato": [{"nome": "Maria"}], "nome_vendedor": "Joao",
    }
    c = tiny.contato_para_alterar(_empresa(), atual)
    assert c["id"] == "610661344"
    assert c["sequencia"] == 1 and c["situacao"] == "A"
    assert c["nome"] == "ACME Filial Norte" and c["cidade"] == "Joao Neiva"
    assert c["codigo"] == "12527"
    assert c["tipos_contato"] == [{"tipo": "Cliente"}, {"tipo": "Fornecedor"}]
    assert c["fantasia"] == "Apelido" and c["email_nfe"] == "nfe@acme.com"
    assert c["obs"] == "cliente antigo" and c["pessoas_contato"] == [{"nome": "Maria"}]
    assert c["nome_vendedor"] == "Joao"


def test_contato_para_alterar_nao_acrescenta_tipos():
    c = tiny.contato_para_alterar(_empresa(), {"id": "1", "tipos_contato": [{"tipo": "Outro"}]})
    assert c["tipos_contato"] == [{"tipo": "Outro"}]


def test_contato_para_alterar_sem_tipos_no_tiny_nao_inventa():
    assert "tipos_contato" not in tiny.contato_para_alterar(_empresa(), {"id": "1"})


def test_ler_resposta_sucesso_de_inclusao():
    r = tiny.ler_resposta({"retorno": {"status_processamento": "3", "status": "OK",
                                       "registros": [{"registro": {"sequencia": "1", "status": "OK", "id": 610661344}}]}})
    assert r.ok and r.id == 610661344 and r.codigo_erro is None


def test_ler_resposta_sucesso_de_pesquisa():
    r = tiny.ler_resposta({"retorno": {"status": "OK", "contatos": [
        {"contato": {"id": "565052083", "nome": "SUMA BRASIL"}}]}})
    assert r.ok and r.id == 565052083


def test_ler_resposta_nao_encontrado():
    r = tiny.ler_resposta({"retorno": {"status": "Erro", "codigo_erro": "20",
                                       "erros": [{"erro": "A consulta não retornou registros"}]}})
    assert not r.ok and r.nao_encontrado and r.codigo_erro == 20
    assert not r.deve_tentar_de_novo


def test_ler_resposta_duplicidade_e_validacao():
    dup = tiny.ler_resposta({"retorno": {"status": "Erro", "codigo_erro": "30",
                                         "erros": [{"erro": "Erro de Duplicidade de Registro"}]}})
    assert dup.duplicidade and not dup.ok
    val = tiny.ler_resposta({"retorno": {"status": "Erro", "codigo_erro": "31",
                                         "erros": [{"erro": "Cidade não encontrada"}]}})
    assert not val.ok and val.codigo_erro == 31 and "Cidade" in val.mensagem


def test_ler_resposta_limite_pede_nova_tentativa():
    for codigo in (6, 11):
        r = tiny.ler_resposta({"retorno": {"status": "Erro", "codigo_erro": str(codigo),
                                           "erros": [{"erro": "API bloqueada momentaneamente"}]}})
        assert r.deve_tentar_de_novo and not r.ok


def test_ler_resposta_erro_no_registro():
    # status_processamento 2: a requisicao passou, o registro nao.
    r = tiny.ler_resposta({"retorno": {"status_processamento": "2", "status": "OK", "registros": [
        {"registro": {"sequencia": "1", "status": "Erro", "erros": [{"erro": "Nome é obrigatório"}]}}]}})
    assert not r.ok and "Nome" in r.mensagem


def test_ler_resposta_corpo_estranho_nao_explode():
    r = tiny.ler_resposta({"qualquer": "coisa"})
    assert not r.ok and r.id is None and r.mensagem
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_tiny_core.py -q`
Expected: FAIL com `ImportError: cannot import name 'tiny'`.

- [ ] **Step 3: Implementar**

```python
# backend/app/core/tiny.py
"""Regras puras da integracao com o Tiny ERP (API v2). Sem I/O.

O que a API do Tiny faz de diferente, verificado na conta da empresa em
16/09/2026 (ver a spec):

- HTTP e' sempre 200; o que vale e' `retorno.status` / `retorno.codigo_erro`.
- "nao encontrado" e' o ERRO 20, nao uma lista vazia.
- Sem `tipos_contato`, o contato nasce como "Outro" — os contatos da empresa
  sao "Cliente". E o campo ACUMULA a cada alteracao.
- `contato.alterar.php` APAGA o que nao for enviado: por isso a edicao le o
  contato antes e devolve inteiro o que e' do Tiny (codigo, tipos, fantasia,
  pessoas de contato, e-mail de NFe...).
- O Tiny casa o municipio pela tabela dele: aceitou "Araucaria" sem acento e
  preencheu a UF sozinho. Nao normalizamos nada aqui.
"""
from dataclasses import dataclass
from typing import Optional

NAO_ENCONTRADO = 20
DUPLICIDADE = 30
VALIDACAO = 31
TOKEN_INVALIDO = 2
LIMITE = (6, 11)

# Limite de caracteres do Tiny para o nome do contato.
_MAX_NOME = 50


@dataclass
class Resultado:
    """Leitura do `retorno` do Tiny, seja de pesquisa, inclusao ou alteracao."""
    ok: bool
    id: Optional[int] = None
    codigo_erro: Optional[int] = None
    mensagem: str = ""

    @property
    def nao_encontrado(self) -> bool:
        return self.codigo_erro == NAO_ENCONTRADO

    @property
    def duplicidade(self) -> bool:
        return self.codigo_erro == DUPLICIDADE

    @property
    def deve_tentar_de_novo(self) -> bool:
        """Bloqueio por excesso de chamadas: passa sozinho, nao e' erro de dado."""
        return self.codigo_erro in LIMITE


def _texto(v) -> str:
    return str(v or "").strip()


def montar_contato(empresa) -> dict:
    """Campos que o GestorHS e' dono. Campo vazio fica de fora do payload."""
    cgc, cpf = _texto(empresa.cgc), _texto(empresa.cpf)
    contato = {
        "nome": _texto(empresa.nome)[:_MAX_NOME],
        "cpf_cnpj": cgc or cpf,
        "tipo_pessoa": "J" if cgc else "F",
        "ie": _texto(empresa.insc_est),
        "endereco": _texto(empresa.endereco),
        "numero": _texto(empresa.numero),
        "complemento": _texto(empresa.complemento),
        "bairro": _texto(empresa.bairro),
        "cidade": _texto(empresa.municipio),
        "uf": _texto(empresa.estado),
        "cep": _texto(empresa.cep),
        "email": _texto(empresa.email),
        "fone": _texto(empresa.telefone),
    }
    return {k: v for k, v in contato.items() if v != ""}


def contato_para_criar(empresa) -> dict:
    """`tipos_contato` SO aqui: na alteracao ele acumularia."""
    return {
        "sequencia": 1,
        "situacao": "A",
        **montar_contato(empresa),
        "tipos_contato": [{"tipo": "Cliente"}],
    }


def contato_para_alterar(empresa, atual: dict) -> dict:
    """Contato INTEIRO: o que veio do Tiny por baixo, os nossos campos por cima."""
    contato = dict(atual)
    contato.update(montar_contato(empresa))
    contato["sequencia"] = 1
    contato["situacao"] = "A"
    return contato


def _mensagem(erros) -> str:
    if isinstance(erros, list):
        return "; ".join(_texto(e.get("erro") if isinstance(e, dict) else e) for e in erros).strip("; ")
    return _texto(erros)


def ler_resposta(corpo: dict) -> Resultado:
    retorno = (corpo or {}).get("retorno")
    if not isinstance(retorno, dict):
        return Resultado(ok=False, mensagem="resposta do Tiny fora do formato esperado")

    if _texto(retorno.get("status")) != "OK":
        try:
            codigo = int(retorno.get("codigo_erro"))
        except (TypeError, ValueError):
            codigo = None
        return Resultado(ok=False, codigo_erro=codigo,
                         mensagem=_mensagem(retorno.get("erros")) or "erro sem descricao")

    registros = retorno.get("registros") or []
    if registros:
        registro = registros[0].get("registro", {})
        if _texto(registro.get("status")) != "OK":
            return Resultado(ok=False, mensagem=_mensagem(registro.get("erros")) or "registro recusado")
        try:
            return Resultado(ok=True, id=int(registro.get("id")))
        except (TypeError, ValueError):
            return Resultado(ok=False, mensagem="registro sem id")

    contatos = retorno.get("contatos") or []
    if contatos:
        try:
            return Resultado(ok=True, id=int(contatos[0].get("contato", {}).get("id")))
        except (TypeError, ValueError):
            return Resultado(ok=False, mensagem="contato sem id")

    return Resultado(ok=False, mensagem="resposta OK sem registros nem contatos")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_tiny_core.py -q`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/tiny.py backend/tests/test_tiny_core.py
git commit -m "feat(tiny): nucleo puro do contato e da leitura da resposta"
```

---

### Task 2: Colunas de estado em `empresas` e migração `0031`

**Files:**
- Create: `backend/alembic/versions/0031_empresa_tiny.py`
- Modify: `backend/app/models/empresa.py`, `backend/app/schemas/empresa.py`
- Test: `backend/tests/test_tiny_core.py` (acrescentar no fim)

**Interfaces:**
- Produces: `Empresa.tiny_id: int | None`, `Empresa.tiny_status: str | None` (`pendente`/`enviada`/`erro`), `Empresa.tiny_erro: str | None`, `Empresa.tiny_em: datetime | None`; os mesmos quatro campos em `EmpresaOut`.

- [ ] **Step 1: Escrever os testes**

Acrescentar ao fim de `backend/tests/test_tiny_core.py`:

```python
def test_model_empresa_nasce_sem_estado_do_tiny(db_session):
    from app.models import Empresa
    e = Empresa(nome="Filial", cgc="36312056000552")
    db_session.add(e); db_session.commit(); db_session.refresh(e)
    assert e.tiny_id is None and e.tiny_status is None
    assert e.tiny_erro is None and e.tiny_em is None


def test_empresa_out_expoe_o_estado_do_tiny(db_session):
    from datetime import datetime, timezone
    from app.core.empresa_servico import saida_empresa
    from app.models import Empresa
    e = Empresa(nome="Filial", cgc="36312056000552", tiny_id=610661344,
                tiny_status="erro", tiny_erro="Cidade não encontrada",
                tiny_em=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc))
    db_session.add(e); db_session.commit(); db_session.refresh(e)
    saida = saida_empresa(e)
    assert saida.tiny_id == 610661344 and saida.tiny_status == "erro"
    assert saida.tiny_erro == "Cidade não encontrada" and saida.tiny_em is not None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_tiny_core.py -q -k tiny_id or empresa_out`
Expected: FAIL (`TypeError: 'tiny_id' is an invalid keyword argument`).

- [ ] **Step 3: Colunas no model**

Em `backend/app/models/empresa.py`, depois de `ativo` e antes de `created_at`:

```python
    # Estado do espelhamento no Tiny ERP. Nulo = nunca entrou na fila (integracao
    # desligada ou cadastro anterior a ela). Ver core/tiny.py e integrations/tiny_client.py.
    tiny_id = Column(Integer, nullable=True, index=True)      # id do contato no Tiny
    tiny_status = Column(String(10), nullable=True)           # pendente | enviada | erro
    tiny_erro = Column(String(255), nullable=True)            # ultima recusa, para a tela
    tiny_em = Column(DateTime(timezone=True), nullable=True)  # ultima tentativa
```

- [ ] **Step 4: Campos no schema**

Em `backend/app/schemas/empresa.py`, em `EmpresaOut`, depois de `ativo`:

```python
    tiny_id: Optional[int] = None
    tiny_status: Optional[str] = None
    tiny_erro: Optional[str] = None
    tiny_em: Optional[datetime] = None
```

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_tiny_core.py tests/test_empresas.py -q`
Expected: PASS.

- [ ] **Step 6: Migração**

```python
# backend/alembic/versions/0031_empresa_tiny.py
"""estado do espelhamento da empresa no Tiny ERP

Quatro colunas em `empresas`: o id do contato no Tiny e o resultado da ultima
tentativa (status, motivo e quando), que alimentam a coluna "Tiny" da tela e o
botao de reenviar.

Aditiva: nenhuma linha existente e' tocada. Com `TINY_TOKEN` vazio a integracao
fica desligada e as colunas seguem nulas.
"""
import sqlalchemy as sa
from alembic import op

revision = "0031_empresa_tiny"
down_revision = "0030_empresas"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("empresas", sa.Column("tiny_id", sa.Integer, nullable=True))
    op.create_index("ix_empresas_tiny_id", "empresas", ["tiny_id"])
    op.add_column("empresas", sa.Column("tiny_status", sa.String(10), nullable=True))
    op.add_column("empresas", sa.Column("tiny_erro", sa.String(255), nullable=True))
    op.add_column("empresas", sa.Column("tiny_em", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("empresas", "tiny_em")
    op.drop_column("empresas", "tiny_erro")
    op.drop_column("empresas", "tiny_status")
    op.drop_index("ix_empresas_tiny_id", table_name="empresas")
    op.drop_column("empresas", "tiny_id")
```

- [ ] **Step 7: Validar a migração OFFLINE**

```bash
alembic upgrade 0030_empresas:0031_empresa_tiny --sql | grep -E "ALTER TABLE empresas|CREATE INDEX"
alembic downgrade 0031_empresa_tiny:0030_empresas --sql | grep -E "DROP"
```
Expected: o SQL aparece, sem erro. **Não** rodar sem `--sql`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/empresa.py backend/app/schemas/empresa.py \
  backend/alembic/versions/0031_empresa_tiny.py backend/tests/test_tiny_core.py
git commit -m "feat(tiny): colunas de estado do envio na empresa (migracao 0031)"
```

---
### Task 3: Cliente HTTP `app/integrations/tiny_client.py`

**Files:**
- Create: `backend/app/integrations/tiny_client.py`
- Modify: `backend/app/core/log_integracao.py` (`classificar_tipo`)
- Test: `backend/tests/test_tiny_client.py`

**Interfaces:**
- Consumes: `app.core.tiny` (Task 1).
- Produces:
  - `integracao_ativa() -> bool`
  - `pesquisar_contato(documento: str) -> Resultado`
  - `obter_contato(tiny_id: int) -> Resultado` e `obter_contato_bruto(tiny_id: int) -> dict | None`
  - `incluir_contato(contato: dict) -> Resultado`
  - `alterar_contato(contato: dict) -> Resultado`
  - Todas devolvem `Resultado` (nunca levantam) e registram em `log_integracao` com `integracao="tiny"`.

> Os testes seguem o padrão de `tests/test_taskhs_client.py`: `monkeypatch` em `httpx.post` e em `registrar_log_integracao`. Nenhuma chamada real — o token do `.env` é o de produção.

- [ ] **Step 1: Escrever os testes**

```python
# backend/tests/test_tiny_client.py
import json

import httpx
import pytest

from app.core.config import settings
from app.integrations import tiny_client


class FakeResp:
    def __init__(self, corpo, status_code=200):
        self.status_code = status_code
        self._corpo = corpo
        self.text = json.dumps(corpo)
        self.headers = {"x-limit-api": "20"}

    def json(self):
        return self._corpo


@pytest.fixture()
def ativa(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")
    monkeypatch.setattr(settings, "TINY_BASE_URL", "https://api.tiny.test/api2")


@pytest.fixture(autouse=True)
def _sem_banco(monkeypatch):
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: None)


def _captura(monkeypatch, corpo):
    capturado = {}

    def fake_post(url, data=None, timeout=None):
        capturado["url"] = url
        capturado["data"] = data
        capturado["timeout"] = timeout
        return FakeResp(corpo)

    monkeypatch.setattr(httpx, "post", fake_post)
    return capturado


def test_integracao_ativa_depende_do_token(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    assert tiny_client.integracao_ativa() is False
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok")
    assert tiny_client.integracao_ativa() is True


def test_desligado_nao_faz_chamada(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    chamou = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: chamou.append(1))
    r = tiny_client.incluir_contato({"nome": "X"})
    assert chamou == [] and not r.ok


def test_pesquisar_contato_encontrado(monkeypatch, ativa):
    cap = _captura(monkeypatch, {"retorno": {"status": "OK", "contatos": [
        {"contato": {"id": "565052083", "nome": "SUMA BRASIL"}}]}})
    r = tiny_client.pesquisar_contato("16565111002048")
    assert r.ok and r.id == 565052083
    assert cap["url"] == "https://api.tiny.test/api2/contatos.pesquisa.php"
    assert cap["data"]["token"] == "tok-123" and cap["data"]["formato"] == "json"
    assert cap["data"]["cpf_cnpj"] == "16565111002048"


def test_pesquisar_contato_nao_encontrado(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "Erro", "codigo_erro": "20",
                                       "erros": [{"erro": "A consulta não retornou registros"}]}})
    r = tiny_client.pesquisar_contato("36312056000552")
    assert not r.ok and r.nao_encontrado


def test_incluir_contato_manda_o_json_no_campo_contato(monkeypatch, ativa):
    cap = _captura(monkeypatch, {"retorno": {"status": "OK", "registros": [
        {"registro": {"sequencia": "1", "status": "OK", "id": 610661344}}]}})
    r = tiny_client.incluir_contato({"nome": "Filial", "situacao": "A", "sequencia": 1})
    assert r.ok and r.id == 610661344
    assert cap["url"].endswith("/contato.incluir.php")
    enviado = json.loads(cap["data"]["contato"])
    assert enviado == {"contatos": [{"contato": {"nome": "Filial", "situacao": "A", "sequencia": 1}}]}


def test_alterar_contato_usa_o_endpoint_de_alteracao(monkeypatch, ativa):
    cap = _captura(monkeypatch, {"retorno": {"status": "OK", "registros": [
        {"registro": {"sequencia": "1", "status": "OK", "id": 610661344}}]}})
    r = tiny_client.alterar_contato({"id": 610661344, "nome": "Filial", "situacao": "A", "sequencia": 1})
    assert r.ok and cap["url"].endswith("/contato.alterar.php")


def test_obter_contato_bruto_devolve_o_contato(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "OK", "contato": {
        "id": "610661344", "codigo": "12527", "nome": "Filial"}}})
    atual = tiny_client.obter_contato_bruto(610661344)
    assert atual["codigo"] == "12527"


def test_obter_contato_bruto_devolve_none_quando_falha(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "Erro", "codigo_erro": "20", "erros": []}})
    assert tiny_client.obter_contato_bruto(1) is None


def test_erro_de_rede_nao_propaga(monkeypatch, ativa):
    def explode(*a, **k):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(httpx, "post", explode)
    r = tiny_client.incluir_contato({"nome": "X"})
    assert not r.ok and r.deve_tentar_de_novo and "sem rede" in r.mensagem


def test_corpo_nao_json_nao_propaga(monkeypatch, ativa):
    class Bruto(FakeResp):
        def json(self):
            raise ValueError("nao e json")

    monkeypatch.setattr(httpx, "post", lambda *a, **k: Bruto({"x": 1}))
    r = tiny_client.pesquisar_contato("1")
    assert not r.ok


def test_registra_no_log_de_integracao(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "OK", "registros": [
        {"registro": {"status": "OK", "id": 7}}]}})
    linhas = []
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: linhas.append(kw))
    tiny_client.incluir_contato({"nome": "Filial"})
    assert linhas and linhas[0]["integracao"] == "tiny" and linhas[0]["status"] == "sucesso"


def test_classificar_tipo_do_tiny():
    from app.core.log_integracao import classificar_tipo
    assert classificar_tipo("tiny", None) == "empresa_contato"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_tiny_client.py -q`
Expected: FAIL (`ModuleNotFoundError: app.integrations.tiny_client`).

- [ ] **Step 3: Implementar o cliente**

```python
# backend/app/integrations/tiny_client.py
"""Cliente HTTP do Tiny ERP (API v2). Best-effort, gating por TINY_TOKEN.

Nenhuma funcao levanta: todas devolvem `Resultado` (app/core/tiny.py) e
registram em `log_integracao`. O Tiny responde HTTP 200 mesmo em erro — quem
manda e' o corpo.
"""
import json
import logging
from typing import Optional

import httpx

from app.core import tiny
from app.core.config import settings
from app.integrations.log_integracao import registrar_log_integracao

logger = logging.getLogger(__name__)

TIMEOUT = 20


def integracao_ativa() -> bool:
    return bool(settings.TINY_TOKEN)


def _chamar(endpoint: str, dados: dict, *, referencia: Optional[str] = None) -> tiny.Resultado:
    if not integracao_ativa():
        registrar_log_integracao(integracao="tiny", status="pulado", motivo="desligado",
                                 payload={"endpoint": endpoint, "external_id": referencia})
        return tiny.Resultado(ok=False, mensagem="integracao com o Tiny desligada")

    url = f"{settings.TINY_BASE_URL.rstrip('/')}/{endpoint}"
    payload = {"endpoint": endpoint, "external_id": referencia}
    try:
        resp = httpx.post(url, data={"token": settings.TINY_TOKEN, "formato": "json", **dados},
                          timeout=TIMEOUT)
    except Exception as e:  # noqa: BLE001 - best-effort: rede nunca derruba o chamador
        registrar_log_integracao(integracao="tiny", status="erro", payload=payload, resposta=str(e))
        logger.warning("falha de rede no Tiny (%s): %s", endpoint, e)
        # Falha de rede passa sozinha: tratada como "tentar de novo" (codigo de limite).
        return tiny.Resultado(ok=False, codigo_erro=tiny.LIMITE[0], mensagem=str(e))

    try:
        corpo = resp.json()
    except Exception:  # noqa: BLE001 - corpo fora do formato tambem e' falha, nao excecao
        registrar_log_integracao(integracao="tiny", status="erro", payload=payload,
                                 http_status=resp.status_code, resposta=resp.text)
        return tiny.Resultado(ok=False, mensagem="resposta do Tiny nao e' JSON")

    resultado = tiny.ler_resposta(corpo)
    registrar_log_integracao(
        integracao="tiny",
        status="sucesso" if resultado.ok else "erro",
        payload=payload,
        http_status=resp.status_code,
        resposta=resp.text,
        motivo=None if resultado.ok else f"codigo_erro={resultado.codigo_erro}",
    )
    return resultado


def pesquisar_contato(documento: str) -> tiny.Resultado:
    """Acha o contato pelo CNPJ/CPF. `nao_encontrado` = erro 20, que NAO e' falha."""
    return _chamar("contatos.pesquisa.php",
                   {"pesquisa": "", "cpf_cnpj": documento}, referencia=documento)


def obter_contato(tiny_id: int) -> tiny.Resultado:
    return _chamar("contato.obter.php", {"id": tiny_id}, referencia=str(tiny_id))


def obter_contato_bruto(tiny_id: int) -> Optional[dict]:
    """O contato como o Tiny guarda — base da alteracao, que apaga o que faltar."""
    if not integracao_ativa():
        return None
    url = f"{settings.TINY_BASE_URL.rstrip('/')}/contato.obter.php"
    try:
        resp = httpx.post(url, data={"token": settings.TINY_TOKEN, "formato": "json", "id": tiny_id},
                          timeout=TIMEOUT)
        corpo = resp.json()
    except Exception as e:  # noqa: BLE001
        registrar_log_integracao(integracao="tiny", status="erro",
                                 payload={"endpoint": "contato.obter.php", "external_id": str(tiny_id)},
                                 resposta=str(e))
        return None
    contato = (corpo.get("retorno") or {}).get("contato")
    return contato if isinstance(contato, dict) else None


def incluir_contato(contato: dict) -> tiny.Resultado:
    return _chamar("contato.incluir.php", {"contato": _envelope(contato)},
                   referencia=contato.get("cpf_cnpj"))


def alterar_contato(contato: dict) -> tiny.Resultado:
    return _chamar("contato.alterar.php", {"contato": _envelope(contato)},
                   referencia=str(contato.get("id")))


def _envelope(contato: dict) -> str:
    """A v2 recebe o contato como JSON dentro de um campo de formulario."""
    return json.dumps({"contatos": [{"contato": contato}]}, ensure_ascii=False)
```

- [ ] **Step 4: Classificar o tipo no log**

Em `backend/app/core/log_integracao.py`, dentro de `classificar_tipo`, antes do `return "desconhecido"`:

```python
    if integracao == "tiny":
        return "empresa_contato"
```

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_tiny_client.py tests/test_taskhs_client_log.py tests/test_hsgrowth_client_log.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrations/tiny_client.py backend/app/core/log_integracao.py backend/tests/test_tiny_client.py
git commit -m "feat(tiny): cliente http com gating por token e log de integracao"
```

---

### Task 4: `sincronizar_empresa` — o fluxo completo

**Files:**
- Modify: `backend/app/integrations/tiny_client.py` (acrescentar no fim)
- Test: `backend/tests/test_tiny_client.py` (acrescentar no fim)

**Interfaces:**
- Consumes: `pesquisar_contato`, `obter_contato_bruto`, `incluir_contato`, `alterar_contato` (Task 3); `contato_para_criar`, `contato_para_alterar` (Task 1); colunas da Task 2.
- Produces: `sincronizar_empresa(empresa_id: int, *, db=None) -> None` — alvo do `BackgroundTasks`. Abre sessão própria quando `db` não vem, grava `tiny_id`/`tiny_status`/`tiny_erro`/`tiny_em` e **nunca propaga exceção**.

- [ ] **Step 1: Escrever os testes**

```python
# acrescentar ao fim de backend/tests/test_tiny_client.py
from app.core import tiny as tiny_core
from app.models import Empresa


def _empresa(db, **kw):
    base = dict(nome="Filial Norte", cgc="36312056000552", municipio="Joao Neiva", estado="ES")
    base.update(kw)
    e = Empresa(**base)
    db.add(e); db.commit(); db.refresh(e)
    return e


@pytest.fixture()
def falso_tiny(monkeypatch, ativa):
    """Substitui as 4 chamadas HTTP por respostas controladas."""
    chamadas = {"pesquisa": [], "incluir": [], "alterar": [], "obter": []}
    respostas = {
        "pesquisa": tiny_core.Resultado(ok=False, codigo_erro=20, mensagem="sem registros"),
        "incluir": tiny_core.Resultado(ok=True, id=999),
        "alterar": tiny_core.Resultado(ok=True, id=999),
        "obter": {"id": "999", "codigo": "12527", "tipos_contato": [{"tipo": "Cliente"}]},
    }
    monkeypatch.setattr(tiny_client, "pesquisar_contato",
                        lambda doc: (chamadas["pesquisa"].append(doc), respostas["pesquisa"])[1])
    monkeypatch.setattr(tiny_client, "incluir_contato",
                        lambda c: (chamadas["incluir"].append(c), respostas["incluir"])[1])
    monkeypatch.setattr(tiny_client, "alterar_contato",
                        lambda c: (chamadas["alterar"].append(c), respostas["alterar"])[1])
    monkeypatch.setattr(tiny_client, "obter_contato_bruto",
                        lambda i: (chamadas["obter"].append(i), respostas["obter"])[1])
    return chamadas, respostas


def test_sincronizar_cria_quando_nao_existe_no_tiny(db_session, falso_tiny):
    chamadas, _ = falso_tiny
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_id == 999 and e.tiny_status == "enviada" and e.tiny_erro is None
    assert e.tiny_em is not None
    assert chamadas["pesquisa"] == ["36312056000552"]
    assert chamadas["incluir"][0]["tipos_contato"] == [{"tipo": "Cliente"}]
    assert chamadas["alterar"] == []


def test_sincronizar_adota_contato_que_ja_existe(db_session, falso_tiny):
    chamadas, respostas = falso_tiny
    respostas["pesquisa"] = tiny_core.Resultado(ok=True, id=565052083)
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_id == 565052083 and e.tiny_status == "enviada"
    assert chamadas["incluir"] == []  # nada criado: adotou


def test_sincronizar_com_tiny_id_le_antes_de_alterar(db_session, falso_tiny):
    chamadas, _ = falso_tiny
    e = _empresa(db_session, tiny_id=999, tiny_status="enviada")
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert chamadas["obter"] == [999]
    enviado = chamadas["alterar"][0]
    assert enviado["id"] == "999" and enviado["codigo"] == "12527"      # preservados
    assert enviado["tipos_contato"] == [{"tipo": "Cliente"}]            # sem acumular
    assert enviado["nome"] == "Filial Norte"                            # nosso campo por cima
    assert e.tiny_status == "enviada"


def test_sincronizar_contato_sumiu_do_tiny_recria(db_session, falso_tiny):
    chamadas, respostas = falso_tiny
    respostas["obter"] = None
    e = _empresa(db_session, tiny_id=999)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert chamadas["alterar"] == [] and chamadas["incluir"]
    assert e.tiny_id == 999 and e.tiny_status == "enviada"


def test_sincronizar_duplicidade_adota(db_session, falso_tiny, monkeypatch):
    chamadas, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=30, mensagem="duplicidade")
    saidas = iter([tiny_core.Resultado(ok=False, codigo_erro=20),          # 1a pesquisa: nao achou
                   tiny_core.Resultado(ok=True, id=777)])                  # apos o 30: achou
    monkeypatch.setattr(tiny_client, "pesquisar_contato",
                        lambda doc: (chamadas["pesquisa"].append(doc), next(saidas))[1])
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_id == 777 and e.tiny_status == "enviada"


def test_sincronizar_validacao_marca_erro_com_a_mensagem(db_session, falso_tiny):
    _, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=31, mensagem="Cidade não encontrada")
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_status == "erro" and e.tiny_erro == "Cidade não encontrada"
    assert e.tiny_id is None


def test_sincronizar_limite_fica_pendente_sem_erro(db_session, falso_tiny):
    _, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=6, mensagem="API bloqueada")
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_status == "pendente" and e.tiny_erro is None


def test_sincronizar_desligado_nao_marca_nada(db_session, monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_status is None and e.tiny_id is None


def test_sincronizar_empresa_inexistente_nao_explode(db_session, falso_tiny):
    tiny_client.sincronizar_empresa(99999, db=db_session)  # sem excecao
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_tiny_client.py -q -k sincronizar`
Expected: FAIL (`AttributeError: module has no attribute 'sincronizar_empresa'`).

- [ ] **Step 3: Implementar**

Acrescentar ao fim de `backend/app/integrations/tiny_client.py`:

```python
def _marcar(db, empresa, *, status: str, erro: Optional[str] = None,
            tiny_id: Optional[int] = None) -> None:
    from datetime import datetime, timezone

    if tiny_id is not None:
        empresa.tiny_id = tiny_id
    empresa.tiny_status = status
    empresa.tiny_erro = (erro or "")[:255] or None
    empresa.tiny_em = datetime.now(timezone.utc)
    db.commit()


def sincronizar_empresa(empresa_id: int, *, db=None) -> None:
    """Alvo do BackgroundTask: espelha UMA Empresa no Tiny. Nunca propaga.

    Sem `tiny_id`: pesquisa pelo documento e ADOTA o contato que existir (as
    filiais ja estao cadastradas la); so cria o que faltar.
    Com `tiny_id`: le o contato e reenvia INTEIRO — `contato.alterar.php` apaga
    o que nao for enviado.
    """
    from app.models import Empresa
    from app.models.database import SessionLocal

    if not integracao_ativa():
        return

    propria = db is None
    db = db or SessionLocal()
    try:
        empresa = db.get(Empresa, empresa_id)
        if empresa is None:
            return
        documento = empresa.cgc or empresa.cpf or ""

        if empresa.tiny_id:
            atual = obter_contato_bruto(empresa.tiny_id)
            if atual is not None:
                resultado = alterar_contato(tiny.contato_para_alterar(empresa, atual))
                _aplicar(db, empresa, resultado, manter_id=True)
                return
            # Contato sumiu do Tiny: cai no caminho de criacao.

        achado = pesquisar_contato(documento) if documento else tiny.Resultado(ok=False)
        if achado.ok and achado.id:
            _marcar(db, empresa, status="enviada", tiny_id=achado.id)
            return
        if achado.deve_tentar_de_novo:
            _marcar(db, empresa, status="pendente")
            return

        resultado = incluir_contato(tiny.contato_para_criar(empresa))
        if resultado.duplicidade and documento:
            # Rede de seguranca: alguem criou entre a pesquisa e a inclusao.
            achado = pesquisar_contato(documento)
            if achado.ok and achado.id:
                _marcar(db, empresa, status="enviada", tiny_id=achado.id)
                return
        _aplicar(db, empresa, resultado)
    except Exception:  # noqa: BLE001 - best-effort: nunca derruba quem agendou
        logger.exception("falha ao sincronizar a empresa %s com o Tiny", empresa_id)
    finally:
        if propria:
            db.close()


def _aplicar(db, empresa, resultado: tiny.Resultado, *, manter_id: bool = False) -> None:
    if resultado.ok:
        _marcar(db, empresa, status="enviada",
                tiny_id=None if manter_id else resultado.id)
    elif resultado.deve_tentar_de_novo:
        # Limite ou rede: passa sozinho, entao nao e' erro de dado.
        _marcar(db, empresa, status="pendente")
    else:
        _marcar(db, empresa, status="erro", erro=resultado.mensagem)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_tiny_client.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrations/tiny_client.py backend/tests/test_tiny_client.py
git commit -m "feat(tiny): sincronizacao da empresa com adocao de contato existente"
```

---
### Task 5: Rotas — agendamento, reenvio e filtro

**Files:**
- Modify: `backend/app/api/empresas.py`, `backend/app/api/propostas.py`, `backend/app/core/proposta_servico.py`
- Test: `backend/tests/test_empresas_tiny.py` (novo)

**Interfaces:**
- Consumes: `tiny_client.sincronizar_empresa`, `tiny_client.integracao_ativa` (Tasks 3-4); colunas da Task 2.
- Produces:
  - `agendar_tiny(db, background_tasks, empresa)` em `app/api/empresas.py` — marca `pendente` e agenda `sincronizar_empresa(empresa.id)`; no-op com integração desligada.
  - `POST /empresas/{id}/tiny` → `EmpresaOut` (Comercial Pós-Vendas, Financeiro, Administrador).
  - `GET /empresas?tiny_status=erro` (também `pendente`, `enviada`).
  - `criar_proposta`/`atualizar_proposta` passam a devolver, em `proposta.empresa_criada_id`, o id da Empresa criada pelo destinatário `nova_empresa` (atributo simples no objeto, não coluna), para a rota agendar depois do commit.

- [ ] **Step 1: Escrever os testes**

```python
# backend/tests/test_empresas_tiny.py
import pytest

from app.core.config import settings
from app.integrations import tiny_client
from app.models import Cliente, Empresa

CNPJ_A = "36312056000552"
CNPJ_B = "11222333000181"


@pytest.fixture(autouse=True)
def integracao_ligada(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")


@pytest.fixture()
def agendados(monkeypatch):
    """Registra quem foi agendado, sem falar com o Tiny."""
    ids = []
    monkeypatch.setattr(tiny_client, "sincronizar_empresa", lambda eid, **kw: ids.append(eid))
    import app.api.empresas as api_empresas
    monkeypatch.setattr(api_empresas.tiny_client, "sincronizar_empresa", lambda eid, **kw: ids.append(eid))
    return ids


def _payload(**kw):
    base = {"documento": CNPJ_A, "nome": "Filial Norte", "cliente": None}
    base.update(kw)
    return base


def test_criar_empresa_agenda_o_envio(client_comercial, agendados, db_session):
    r = client_comercial.post("/empresas", json=_payload())
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["tiny_status"] == "pendente" and corpo["tiny_id"] is None
    assert agendados == [corpo["id"]]


def test_editar_empresa_agenda_o_envio(client_comercial, agendados):
    eid = client_comercial.post("/empresas", json=_payload()).json()["id"]
    agendados.clear()
    r = client_comercial.put(f"/empresas/{eid}", json=_payload(nome="Filial Sul"))
    assert r.status_code == 200 and agendados == [eid]


def test_desativar_nao_agenda(client_comercial, agendados):
    eid = client_comercial.post("/empresas", json=_payload()).json()["id"]
    agendados.clear()
    assert client_comercial.post(f"/empresas/{eid}/desativar").status_code == 200
    assert agendados == []


def test_integracao_desligada_nao_agenda_nem_marca(client_comercial, agendados, monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    r = client_comercial.post("/empresas", json=_payload())
    assert r.json()["tiny_status"] is None and agendados == []


def test_reenviar_pela_rota(client_comercial, agendados, db_session):
    eid = client_comercial.post("/empresas", json=_payload()).json()["id"]
    agendados.clear()
    emp = db_session.get(Empresa, eid)
    emp.tiny_status, emp.tiny_erro = "erro", "Cidade não encontrada"
    db_session.commit()

    r = client_comercial.post(f"/empresas/{eid}/tiny")
    assert r.status_code == 200
    assert r.json()["tiny_status"] == "pendente" and r.json()["tiny_erro"] is None
    assert agendados == [eid]


def test_reenviar_exige_funcao(client_lab, db_session):
    emp = Empresa(nome="Filial", cgc=CNPJ_A)
    db_session.add(emp); db_session.commit()
    assert client_lab.post(f"/empresas/{emp.id}/tiny").status_code == 403


def test_reenviar_empresa_inexistente_404(client_comercial):
    assert client_comercial.post("/empresas/9999/tiny").status_code == 404


def test_listar_filtra_por_tiny_status(client_comercial, db_session):
    db_session.add_all([
        Empresa(nome="Com erro", cgc=CNPJ_A, tiny_status="erro", tiny_erro="Cidade"),
        Empresa(nome="Enviada", cgc=CNPJ_B, tiny_status="enviada", tiny_id=999),
    ])
    db_session.commit()
    assert client_comercial.get("/empresas?tiny_status=erro").json()["total"] == 1
    assert client_comercial.get("/empresas?tiny_status=enviada").json()["items"][0]["tiny_id"] == 999
    assert client_comercial.get("/empresas").json()["total"] == 2


def test_empresa_nova_pela_proposta_agenda_depois_do_commit(client_comercial, agendados, db_session):
    cli = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add(cli); db_session.commit()
    r = client_comercial.post("/propostas", json={
        "destinatario": {"tipo": "nova_empresa", "documento": CNPJ_A, "matriz": cli.id,
                         "nome": "Filial da Proposta", "email": "f@acme.com", "telefone": "8130001111"},
    })
    assert r.status_code == 201
    empresa_id = r.json()["empresa"]
    assert agendados == [empresa_id]
    assert db_session.get(Empresa, empresa_id).tiny_status == "pendente"


def test_falha_do_tiny_nao_derruba_a_proposta(client_comercial, monkeypatch, db_session):
    def explode(*a, **k):
        raise RuntimeError("Tiny fora do ar")

    import app.api.propostas as api_propostas
    monkeypatch.setattr(api_propostas.tiny_client, "sincronizar_empresa", explode)
    cli = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add(cli); db_session.commit()
    r = client_comercial.post("/propostas", json={
        "destinatario": {"tipo": "nova_empresa", "documento": CNPJ_B, "matriz": cli.id,
                         "nome": "Filial", "email": "f@acme.com", "telefone": "8130001111"},
    })
    assert r.status_code == 201  # a proposta foi salva mesmo assim
```

> O `TestClient` do FastAPI roda os `BackgroundTasks` de forma síncrona ao fim da request, por isso `agendados` já está preenchido quando a resposta volta — e uma exceção dentro da task apareceria na request. É por isso que o agendamento da proposta passa por `_tiny_seguro` (Step 4), que engole a falha: a proposta não pode cair por causa do Tiny.

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_empresas_tiny.py -q`
Expected: FAIL (`tiny_status` inexistente na saída, 404 em `/empresas/{id}/tiny`).

- [ ] **Step 3: Agendamento em `empresas.py`**

Imports no topo de `backend/app/api/empresas.py`:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.integrations import tiny_client
```

Helper depois de `_gravar`:

```python
def agendar_tiny(db: Session, background_tasks: BackgroundTasks, empresa: Empresa) -> None:
    """Marca `pendente` e agenda o espelhamento no Tiny para DEPOIS da resposta.
    No-op com a integracao desligada: nada e' enviado e nada e' marcado."""
    if not tiny_client.integracao_ativa():
        return
    empresa.tiny_status = "pendente"
    empresa.tiny_erro = None
    db.commit()
    background_tasks.add_task(tiny_client.sincronizar_empresa, empresa.id)
```

Em `criar` e `atualizar`, receber `background_tasks: BackgroundTasks` e chamar `agendar_tiny(db, background_tasks, empresa)` **depois** do `_gravar`:

```python
@router.post("", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def criar(dados: EmpresaIn, background_tasks: BackgroundTasks,
          db: Session = Depends(get_db), _: Usuario = Depends(_escrever)):
    empresa = _executar(db, es.criar_empresa, dados)
    saida = _gravar(db, empresa)
    agendar_tiny(db, background_tasks, empresa)
    return es.saida_empresa(empresa)
```

(`atualizar` segue o mesmo formato.) `desativar` e `reativar` **não** agendam.

Rota nova, depois de `reativar`:

```python
@router.post("/{empresa_id}/tiny", response_model=EmpresaOut)
def reenviar_tiny(empresa_id: int, background_tasks: BackgroundTasks,
                  db: Session = Depends(get_db), _: Usuario = Depends(_escrever)):
    """Reenvia ao Tiny o que ficou em erro ou pendente."""
    empresa = _empresa_ou_404(db, empresa_id)
    agendar_tiny(db, background_tasks, empresa)
    db.refresh(empresa)
    return es.saida_empresa(empresa)
```

Filtro na listagem, junto dos outros:

```python
    tiny_status: str | None = None,
```
e, no corpo, depois do filtro de `ativo`:

```python
    if tiny_status is not None:
        query = query.filter(Empresa.tiny_status == tiny_status)
```

- [ ] **Step 4: Agendar a Empresa criada pela proposta**

Em `backend/app/core/proposta_servico.py`, dentro de `_aplicar_destinatario`, no ramo `nova_empresa`, logo depois de `empresa = criar_empresa(...)`:

```python
        # A rota agenda o Tiny DEPOIS do commit: a proposta nao pode falhar por
        # causa da integracao (ver api/propostas.py).
        proposta.empresa_criada_id = empresa.id
```

Em `backend/app/api/propostas.py`: importar `BackgroundTasks` e `from app.integrations import tiny_client`, receber `background_tasks: BackgroundTasks` em `criar` e `atualizar`, e depois de montar a saída:

```python
def _tiny_seguro(empresa_id: int) -> None:
    """Envio best-effort: a proposta ja foi salva, entao falha aqui nao volta
    para a request (o BackgroundTask roda dentro dela no TestClient)."""
    try:
        tiny_client.sincronizar_empresa(empresa_id)
    except Exception:  # noqa: BLE001
        logger.exception("falha ao agendar a empresa %s no Tiny", empresa_id)


def _agendar_empresa_no_tiny(db: Session, background_tasks: BackgroundTasks, proposta) -> None:
    criada = getattr(proposta, "empresa_criada_id", None)
    if criada is None or not tiny_client.integracao_ativa():
        return
    empresa = db.get(Empresa, criada)
    if empresa is not None:
        empresa.tiny_status = "pendente"
        db.commit()
    background_tasks.add_task(_tiny_seguro, criada)
```

Chamar `_agendar_empresa_no_tiny(db, background_tasks, proposta)` em `criar` e em `atualizar`, depois do `ps.montar_saida(...)`. `logger` vem de `logging.getLogger(__name__)` no topo do arquivo, e `Empresa` do `from app.models import ...` que a rota já usa.

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_empresas_tiny.py tests/test_empresas.py tests/test_propostas_destinatario.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/empresas.py backend/app/api/propostas.py backend/app/core/proposta_servico.py backend/tests/test_empresas_tiny.py
git commit -m "feat(tiny): agendamento no cadastro de empresa e rota de reenvio"
```

---

### Task 6: Script `enviar_empresas_tiny`

**Files:**
- Create: `backend/app/scripts/enviar_empresas_tiny.py`
- Test: `backend/tests/test_enviar_empresas_tiny.py`

**Interfaces:**
- Consumes: `tiny_client.pesquisar_contato`, `incluir_contato`, `integracao_ativa`; `tiny.contato_para_criar`.
- Produces: `planejar(db, limite=None) -> list[Empresa]`; `processar(db, empresas, *, aplicar: bool, pausa: float = 3.0) -> dict`; `main(argv=None)`.

- [ ] **Step 1: Escrever os testes**

```python
# backend/tests/test_enviar_empresas_tiny.py
import pytest

from app.core import tiny as tiny_core
from app.core.config import settings
from app.integrations import tiny_client
from app.models import Empresa
from app.scripts import enviar_empresas_tiny as script

CNPJS = ["36312056000552", "11222333000181", "08857492000148"]


@pytest.fixture(autouse=True)
def sem_pausa_e_ligado(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")
    monkeypatch.setattr(script.time, "sleep", lambda s: None)


@pytest.fixture()
def tiny_falso(monkeypatch):
    estado = {"pesquisa": {}, "incluidos": [], "resultado_incluir": tiny_core.Resultado(ok=True, id=555)}
    monkeypatch.setattr(tiny_client, "pesquisar_contato",
                        lambda doc: estado["pesquisa"].get(doc, tiny_core.Resultado(ok=False, codigo_erro=20)))
    monkeypatch.setattr(tiny_client, "incluir_contato",
                        lambda c: (estado["incluidos"].append(c), estado["resultado_incluir"])[1])
    return estado


def _empresas(db, quantos=2, **kw):
    criadas = []
    for i in range(quantos):
        e = Empresa(nome=f"Filial {i}", cgc=CNPJS[i], municipio="Recife", estado="PE", **kw)
        db.add(e); criadas.append(e)
    db.commit()
    return criadas


def test_planejar_pega_so_ativa_sem_tiny_id(db_session):
    a, b = _empresas(db_session)
    b.tiny_id = 999
    db_session.add(Empresa(nome="Inativa", cgc=CNPJS[2], ativo=False))
    db_session.commit()
    assert [e.id for e in script.planejar(db_session)] == [a.id]


def test_planejar_respeita_o_limite(db_session):
    _empresas(db_session, 2)
    assert len(script.planejar(db_session, limite=1)) == 1


def test_simulacao_nao_grava_nem_chama(db_session, tiny_falso):
    a, _ = _empresas(db_session)
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=False)
    db_session.refresh(a)
    assert a.tiny_id is None and a.tiny_status is None
    assert tiny_falso["incluidos"] == []
    assert resumo["candidatas"] == 2


def test_aplicar_adota_quem_ja_existe_e_cria_o_resto(db_session, tiny_falso):
    a, b = _empresas(db_session)
    tiny_falso["pesquisa"][CNPJS[0]] = tiny_core.Resultado(ok=True, id=565052083)
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True)
    db_session.refresh(a); db_session.refresh(b)
    assert a.tiny_id == 565052083 and a.tiny_status == "enviada"
    assert b.tiny_id == 555 and b.tiny_status == "enviada"
    assert len(tiny_falso["incluidos"]) == 1              # so a que faltava
    assert resumo == {"candidatas": 2, "adotadas": 1, "criadas": 1, "erros": 0, "interrompido": False}


def test_erro_de_validacao_marca_erro_e_segue(db_session, tiny_falso):
    a, b = _empresas(db_session)
    tiny_falso["resultado_incluir"] = tiny_core.Resultado(ok=False, codigo_erro=31,
                                                          mensagem="Cidade não encontrada")
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True)
    db_session.refresh(a)
    assert a.tiny_status == "erro" and a.tiny_erro == "Cidade não encontrada"
    assert resumo["erros"] == 2 and resumo["interrompido"] is False


def test_bloqueio_por_limite_interrompe(db_session, tiny_falso):
    _empresas(db_session, 2)
    tiny_falso["resultado_incluir"] = tiny_core.Resultado(ok=False, codigo_erro=6,
                                                          mensagem="API bloqueada")
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True)
    assert resumo["interrompido"] is True and resumo["criadas"] == 0


def test_idempotente(db_session, tiny_falso):
    _empresas(db_session)
    script.processar(db_session, script.planejar(db_session), aplicar=True)
    assert script.planejar(db_session) == []


def test_main_sem_aplicar_so_simula(db_session, tiny_falso, monkeypatch, capsys):
    _empresas(db_session)
    monkeypatch.setattr(script, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    script.main([])
    assert "SIMULACAO" in capsys.readouterr().out
    assert tiny_falso["incluidos"] == []


def test_main_recusa_com_integracao_desligada(db_session, monkeypatch, capsys):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    monkeypatch.setattr(script, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    with pytest.raises(SystemExit):
        script.main([])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_enviar_empresas_tiny.py -q`
Expected: FAIL com `ImportError`.

- [ ] **Step 3: Implementar**

```python
# backend/app/scripts/enviar_empresas_tiny.py
"""Acerta no Tiny as Empresas que ja existem no GestorHS.

Para cada Empresa ativa sem `tiny_id`: pesquisa o documento no Tiny e ADOTA o
contato que existir; so cria o que faltar. Na base de 16/09/2026, 9 das 10
filiais ja estavam la — sem a pesquisa, o primeiro uso criaria 9 duplicados.

    python -m app.scripts.enviar_empresas_tiny                 # so simula
    python -m app.scripts.enviar_empresas_tiny --aplicar       # grava
    python -m app.scripts.enviar_empresas_tiny --aplicar --limite 5

O limite desta conta e' de 20 chamadas por minuto (cabecalho `x-limit-api`) e
cada empresa gasta duas, dai a pausa entre elas. Levando bloqueio (codigo 6/11),
o script PARA e diz quantas faltaram — e' so rodar de novo depois.

Idempotente: empresa com `tiny_id` nao e' tocada.
"""
import argparse
import time
from datetime import datetime, timezone
from typing import Optional

from app.core import tiny
from app.integrations import tiny_client
from app.models import Empresa
from app.models.database import SessionLocal

PAUSA_PADRAO = 3.0


def planejar(db, limite: Optional[int] = None) -> list:
    """Empresas ativas ainda sem contato no Tiny, em ordem de id."""
    query = (db.query(Empresa)
             .filter(Empresa.ativo.is_(True), Empresa.tiny_id.is_(None))
             .order_by(Empresa.id))
    if limite:
        query = query.limit(limite)
    return query.all()


def _marcar(db, empresa, *, status: str, tiny_id=None, erro=None) -> None:
    if tiny_id is not None:
        empresa.tiny_id = tiny_id
    empresa.tiny_status = status
    empresa.tiny_erro = (erro or "")[:255] or None
    empresa.tiny_em = datetime.now(timezone.utc)
    db.commit()


def processar(db, empresas, *, aplicar: bool, pausa: float = PAUSA_PADRAO) -> dict:
    resumo = {"candidatas": len(empresas), "adotadas": 0, "criadas": 0,
              "erros": 0, "interrompido": False}
    if not aplicar:
        for e in empresas:
            print(f"  ? {e.id:5} {e.nome[:40]:40} {e.cgc or e.cpf}")
        return resumo

    for i, empresa in enumerate(empresas):
        if i:
            time.sleep(pausa)
        documento = empresa.cgc or empresa.cpf or ""
        achado = tiny_client.pesquisar_contato(documento) if documento else tiny.Resultado(ok=False)
        if achado.ok and achado.id:
            _marcar(db, empresa, status="enviada", tiny_id=achado.id)
            resumo["adotadas"] += 1
            print(f"  = {empresa.id:5} {empresa.nome[:40]:40} adotou contato {achado.id}")
            continue
        if achado.deve_tentar_de_novo:
            resumo["interrompido"] = True
            break

        resultado = tiny_client.incluir_contato(tiny.contato_para_criar(empresa))
        if resultado.ok:
            _marcar(db, empresa, status="enviada", tiny_id=resultado.id)
            resumo["criadas"] += 1
            print(f"  + {empresa.id:5} {empresa.nome[:40]:40} criou contato {resultado.id}")
        elif resultado.deve_tentar_de_novo:
            resumo["interrompido"] = True
            break
        else:
            _marcar(db, empresa, status="erro", erro=resultado.mensagem)
            resumo["erros"] += 1
            print(f"  ! {empresa.id:5} {empresa.nome[:40]:40} {resultado.mensagem}")

    if resumo["interrompido"]:
        feitas = resumo["adotadas"] + resumo["criadas"] + resumo["erros"]
        print(f"\nPAROU: o Tiny bloqueou por excesso de chamadas. "
              f"{resumo['candidatas'] - feitas} empresa(s) ficaram para a proxima rodada.")
    return resumo


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aplicar", action="store_true", help="grava (padrao: so simula)")
    parser.add_argument("--limite", type=int, default=None, help="processa no maximo N empresas")
    args = parser.parse_args(argv)

    if not tiny_client.integracao_ativa():
        raise SystemExit("TINY_TOKEN vazio: integracao desligada, nada a fazer.")

    db = SessionLocal()
    try:
        empresas = planejar(db, args.limite)
        print(f"Empresas ativas sem contato no Tiny: {len(empresas)}")
        resumo = processar(db, empresas, aplicar=args.aplicar)
        if not args.aplicar:
            print("\nSIMULACAO — nada enviado. Rode com --aplicar para valer.")
            return
        print(f"\nResultado: {resumo}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_enviar_empresas_tiny.py -q`
Expected: PASS.

- [ ] **Step 5: Suíte inteira do backend**

Run: `pytest -q`
Expected: só as 4 falhas da baseline.

- [ ] **Step 6: Commit**

```bash
git add backend/app/scripts/enviar_empresas_tiny.py backend/tests/test_enviar_empresas_tiny.py
git commit -m "feat(tiny): script de acerto das empresas ja cadastradas"
```

---
### Task 7: Frontend — coluna Tiny, botão de reenviar e filtro

**Files:**
- Modify: `frontend/src/app/empresas/api.ts`, `frontend/src/app/empresas/EmpresasPage.tsx`, `frontend/src/app/empresas/EmpresaModal.tsx`, `frontend/src/app/empresas/EmpresasPage.test.tsx`

**Interfaces:**
- Consumes: `EmpresaOut` com `tiny_id`, `tiny_status`, `tiny_erro`, `tiny_em` (Task 2); `POST /empresas/{id}/tiny` e `GET /empresas?tiny_status=` (Task 5).
- Produces: `Empresa` com os quatro campos; `ListarEmpresasParams.tiny_status?: 'pendente' | 'enviada' | 'erro'`; `empresasApi.reenviarTiny(id: number): Promise<Empresa>`; `rotuloTiny(e: Empresa): string` exportado de `api.ts` para a tela e o modal usarem o mesmo texto.

- [ ] **Step 1: Escrever os testes**

Acrescentar em `frontend/src/app/empresas/EmpresasPage.test.tsx` (a fixture `EMPRESA` ganha `tiny_id: null, tiny_status: null, tiny_erro: null, tiny_em: null`):

```tsx
  it('mostra o estado do Tiny de cada empresa', async () => {
    vi.spyOn(empresasApi, 'listar').mockResolvedValue({
      items: [
        { ...EMPRESA, id: 1, nome: 'Enviada', tiny_status: 'enviada', tiny_id: 610661344 },
        { ...EMPRESA, id: 2, nome: 'Com erro', tiny_status: 'erro', tiny_erro: 'Cidade não encontrada' },
        { ...EMPRESA, id: 3, nome: 'Na fila', tiny_status: 'pendente' },
        { ...EMPRESA, id: 4, nome: 'Fora', tiny_status: null },
      ],
      total: 4,
    })
    renderPagina()
    expect(await screen.findByText('Enviada')).toBeInTheDocument()
    expect(screen.getByText('610661344')).toBeInTheDocument()
    expect(screen.getByTitle('Cidade não encontrada')).toBeInTheDocument()
    expect(screen.getByText('Pendente')).toBeInTheDocument()
  })

  it('botao de reenviar aparece so em erro e pendente', async () => {
    vi.spyOn(empresasApi, 'listar').mockResolvedValue({
      items: [
        { ...EMPRESA, id: 1, nome: 'Enviada', tiny_status: 'enviada', tiny_id: 7 },
        { ...EMPRESA, id: 2, nome: 'Com erro', tiny_status: 'erro', tiny_erro: 'x' },
      ],
      total: 2,
    })
    renderPagina()
    await screen.findByText('Com erro')
    expect(screen.getAllByRole('button', { name: 'Reenviar ao Tiny' })).toHaveLength(1)
  })

  it('reenviar chama a api e recarrega', async () => {
    const listar = vi.spyOn(empresasApi, 'listar').mockResolvedValue({
      items: [{ ...EMPRESA, id: 2, nome: 'Com erro', tiny_status: 'erro', tiny_erro: 'x' }],
      total: 1,
    })
    const reenviar = vi.spyOn(empresasApi, 'reenviarTiny').mockResolvedValue({ ...EMPRESA, tiny_status: 'pendente' })
    renderPagina()
    await screen.findByText('Com erro')
    fireEvent.click(screen.getByRole('button', { name: 'Reenviar ao Tiny' }))
    await waitFor(() => expect(reenviar).toHaveBeenCalledWith(2))
    await waitFor(() => expect(listar).toHaveBeenCalledTimes(2))
  })

  it('filtro de erro no Tiny passa o parametro', async () => {
    const listar = vi.spyOn(empresasApi, 'listar').mockResolvedValue({ items: [EMPRESA], total: 1 })
    renderPagina()
    await screen.findByText('Filial Norte')
    fireEvent.click(screen.getByLabelText('Só com erro no Tiny'))
    await waitFor(() => expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ tiny_status: 'erro' })))
  })

  it('quem nao gerencia nao ve o botao de reenviar', async () => {
    mockUser = { ...mockUser, funcao: 'Laboratório' }
    vi.spyOn(empresasApi, 'listar').mockResolvedValue({
      items: [{ ...EMPRESA, tiny_status: 'erro', tiny_erro: 'x' }], total: 1,
    })
    renderPagina()
    await screen.findByText('Filial Norte')
    expect(screen.queryByRole('button', { name: 'Reenviar ao Tiny' })).toBeNull()
  })
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `frontend/`): `npx vitest run src/app/empresas/EmpresasPage.test.tsx`
Expected: FAIL (coluna e botão inexistentes).

- [ ] **Step 3: Tipos e cliente HTTP**

Em `frontend/src/app/empresas/api.ts`, em `interface Empresa`, depois de `ativo`:

```ts
  tiny_id: number | null
  tiny_status: 'pendente' | 'enviada' | 'erro' | null
  tiny_erro: string | null
  tiny_em: string | null
```

Em `ListarEmpresasParams`: `tiny_status?: 'pendente' | 'enviada' | 'erro'`; e no `listar`, junto dos outros filtros:

```ts
    if (params.tiny_status) sp.set('tiny_status', params.tiny_status)
```

Em `empresasApi`, depois de `reativar`:

```ts
  reenviarTiny: (id: number) => apiJson<Empresa>(`/empresas/${id}/tiny`, { method: 'POST' }),
```

E, no fim do arquivo, o rótulo compartilhado entre a tela e o modal:

```ts
/** Texto da coluna "Tiny". Vazio = integração desligada ou cadastro anterior a ela. */
export function rotuloTiny(e: Empresa): string {
  if (e.tiny_status === 'enviada') return 'Enviada'
  if (e.tiny_status === 'pendente') return 'Pendente'
  if (e.tiny_status === 'erro') return 'Erro'
  return '—'
}
```

- [ ] **Step 4: Coluna, botão e filtro na página**

Em `frontend/src/app/empresas/EmpresasPage.tsx`:

Estado novo, junto dos outros:

```tsx
  const [soErroTiny, setSoErroTiny] = useState(false)
```

No `useEffect` da listagem, passar o filtro e incluir `soErroTiny` nas dependências:

```tsx
    empresasApi.listar({ q: busca || undefined, tiny_status: soErroTiny ? 'erro' : undefined,
                         offset, limit: LIMITE })
```

Abaixo da `SearchBar`:

```tsx
      <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
        <input type="checkbox" checked={soErroTiny}
          onChange={(e) => { setOffset(0); setSoErroTiny(e.target.checked) }}
          className="h-4 w-4 rounded border-border text-primary focus:ring-primary/50" />
        Só com erro no Tiny
      </label>
```

Handler junto de `alternarAtivo`:

```tsx
  async function reenviarTiny(emp: Empresa) {
    try {
      await empresasApi.reenviarTiny(emp.id)
      setRecarga((n) => n + 1)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao reenviar ao Tiny')
    }
  }
```

Cabeçalho da tabela: acrescentar `<TH>Tiny</TH>` antes de `<TH>Ações</TH>`. Célula nova, antes da de ações:

```tsx
              <TD>
                <span className={cn('text-xs', emp.tiny_status === 'erro' && 'font-semibold text-danger')}
                  title={emp.tiny_erro ?? undefined}>
                  {rotuloTiny(emp)}
                </span>
                {emp.tiny_id != null && (
                  <span className="block text-xs text-slate-500">{emp.tiny_id}</span>
                )}
              </TD>
```

Dentro do `IconButtonGroup`, depois do botão de desativar:

```tsx
                  {podeEditar && (emp.tiny_status === 'erro' || emp.tiny_status === 'pendente') && (
                    <IconButton label="Reenviar ao Tiny" tone="baixar" onClick={() => void reenviarTiny(emp)}>
                      <IconRestore className="w-4 h-4" />
                    </IconButton>
                  )}
```

Imports novos: `rotuloTiny` de `./api` e `cn` de `../../lib/utils`.

- [ ] **Step 5: Estado no modal**

Em `frontend/src/app/empresas/EmpresaModal.tsx`, dentro do `<form>`, depois do `DadosEmpresaForm` (só quando editando):

```tsx
        {empresa && (
          <p className="text-xs text-slate-500">
            Tiny: {rotuloTiny(empresa)}
            {empresa.tiny_id != null && ` · contato ${empresa.tiny_id}`}
            {empresa.tiny_erro && ` · ${empresa.tiny_erro}`}
          </p>
        )}
```

com `rotuloTiny` importado de `./api`.

- [ ] **Step 6: Rodar e ver passar**

Run: `npx vitest run src/app/empresas && npm run lint && npx tsc -b --noEmit`
Expected: PASS e sem erro de lint/tipos.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/empresas/api.ts frontend/src/app/empresas/EmpresasPage.tsx \
  frontend/src/app/empresas/EmpresaModal.tsx frontend/src/app/empresas/EmpresasPage.test.tsx
git commit -m "feat(tiny): coluna de estado, reenvio e filtro na pagina de empresas"
```

---

### Task 8: Documentação, changelog e verificação final

**Files:**
- Create: `docs/operacao-tiny-empresas.md`
- Modify: `CLAUDE.md`, `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Doc de operação**

```markdown
# Operação: Empresa no Tiny ERP

Entrega v1.54.0 (set/2026). Empresa criada ou editada no GestorHS vira contato no
Tiny (API v2, token). Nada volta do Tiny para cá.

## Ligar

1. Deploy + `alembic upgrade head` (`0031`: quatro colunas em `empresas`, aditiva).
2. Com `TINY_TOKEN` **vazio** nada acontece — dá para subir o código antes de ligar.
3. Pôr o `TINY_TOKEN` nas variáveis de ambiente do EasyPanel (o token sai do próprio
   Tiny, em Configurações > Token da API) e reiniciar.
4. `python -m app.scripts.enviar_empresas_tiny` (simula) → conferir → `--aplicar`.
   Em 16/09/2026 o esperado era: 9 adotadas, 1 criada.

## O que cada estado quer dizer

| Coluna "Tiny" | Significa |
|---|---|
| Enviada | Contato existe no Tiny e o id está guardado |
| Pendente | Na fila, ou o Tiny bloqueou por excesso de chamadas — o botão "Reenviar ao Tiny" resolve |
| Erro | O Tiny recusou; o motivo aparece ao passar o mouse |
| — | Integração desligada ou cadastro anterior a ela |

## Erros mais comuns

| Código | Mensagem típica | O que fazer |
|---|---|---|
| 31 | "Cidade não encontrada" | Corrigir o município na Empresa e reenviar. O Tiny casa pela tabela dele (aceita sem acento e completa a UF) |
| 30 | "Erro de Duplicidade de Registro" | O sistema já pesquisa e adota sozinho; se aparecer, reenviar resolve |
| 2 | "token inválido ou não encontrado" | Conferir o `TINY_TOKEN` no EasyPanel |
| 6 / 11 | "API bloqueada momentaneamente" | Esperar um minuto e reenviar. O limite desta conta é 20 chamadas/minuto (`x-limit-api`) |

## Coisas que não estão óbvias no código

- **A alteração do Tiny apaga o que não for enviado.** Por isso a integração lê o
  contato antes de alterar e devolve inteiro o que é de lá (código, tipos de contato,
  fantasia, pessoas de contato, e-mail de NFe). Nunca mande alteração parcial na mão.
- **`tipos_contato` acumula.** Só a criação manda `Cliente`; a edição devolve o que veio.
- **"Não encontrado" é o erro 20**, não uma lista vazia.
- **O Tiny não tem ambiente de teste:** qualquer ensaio com o token real cria contato
  de verdade. Os testes automatizados nunca chamam a API.
- **Nome acima de 50 caracteres é cortado no envio**; o cadastro daqui fica inteiro.
- Cliente (matriz) não vai para o Tiny; desativar e reativar não mexem lá.
```

- [ ] **Step 2: `CLAUDE.md`**

Na lista de comandos do backend, depois da linha de `migrar_filiais_propostas`:

```
python -m app.scripts.enviar_empresas_tiny                          # SIMULA: acerta as empresas no Tiny (--aplicar grava)
```

Na seção "Empresas e destinatário da proposta", no fim, acrescentar:

```markdown
- **Espelhamento no Tiny ERP (API v2):** Empresa criada ou editada vira contato no Tiny, em segundo plano e best-effort ([core/tiny.py](backend/app/core/tiny.py) puro + [integrations/tiny_client.py](backend/app/integrations/tiny_client.py)). Nasce desligada: sem `TINY_TOKEN` é no-op. O estado fica em `empresas.tiny_id/tiny_status/tiny_erro/tiny_em` e aparece na página Empresas, com botão de reenviar.
- ⚠️ **`contato.alterar.php` APAGA o que não for enviado** e **`tipos_contato` ACUMULA**: a edição lê o contato (`contato.obter.php`) e reenvia inteiro, preservando código, tipos, fantasia, pessoas de contato e e-mail de NFe. "Não encontrado" na pesquisa é o **erro 20**, não lista vazia.
- ⚠️ **O Tiny não tem ambiente de teste** e o token vale para a empresa toda: teste automatizado nunca chama a API (tudo com `httpx` mockado). Procedimento em [docs/operacao-tiny-empresas.md](docs/operacao-tiny-empresas.md).
```

Na seção "Migrações Alembic", trocar `(0001–0030)` por `(0001–0031)` e citar o estado do Tiny na `0031`.

- [ ] **Step 3: Changelog**

Nova primeira entrada em `frontend/src/app/changelog/data.ts`:

```ts
  {
    versao: '1.54.0',
    data: 'DD/MM/2026', // data do merge
    itens: [
      { tipo: 'novidade', texto: 'Empresa cadastrada aqui agora é criada também no Tiny, sem precisar digitar de novo lá. Se o CNPJ já existir no Tiny, o cadastro é ligado ao contato que já está lá, em vez de criar outro.' },
      { tipo: 'novidade', texto: 'Editar os dados de uma empresa atualiza o contato no Tiny, preservando o que só existe lá (código, tipos de contato, pessoas de contato e e-mail de NFe).' },
      { tipo: 'melhoria', texto: 'A página Empresas mostra a situação de cada uma no Tiny e traz um botão para reenviar o que deu erro, com o motivo informado pelo próprio Tiny.' },
    ],
  },
```

- [ ] **Step 4: Verificação final**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -6
cd ../frontend && npm run lint && npx tsc -b --noEmit && npm run build && npm test 2>&1 | tail -5
```
Expected: backend só com as 4 falhas da baseline; frontend limpo. `frontend/dist` não entra no commit.

- [ ] **Step 5: Commits**

```bash
git add docs/operacao-tiny-empresas.md CLAUDE.md
git commit -m "docs: integracao da empresa com o tiny erp e operacao"
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.54.0 — empresa no tiny erp"
```

Merge na `main` e push **só quando o Erick pedir**, no formato `merge: empresa no tiny erp (v1.54.0) — …`.

---

## Ensaio local antes do merge (controller)

Depois da Task 8 e antes de fechar a branch, com a API local rodando contra o banco de `~/projetos/gestorhs-local/`:

1. `~/projetos/gestorhs-local/ambiente.sh alembic upgrade head` (aplica a `0031` no banco local).
2. Acrescentar `TINY_TOKEN` ao `ambiente.sh` **apenas se o Erick autorizar o ensaio com o Tiny real** — o Tiny não tem ambiente de teste e qualquer envio cria ou altera contato de verdade.
3. `~/projetos/gestorhs-local/ambiente.sh py app.scripts.enviar_empresas_tiny` (simulação) e mostrar o resumo ao Erick.
4. Só com o ok dele: `--aplicar`. O esperado é **10 adotadas, 0 criadas** (as 9 que já existiam mais a filial da Ibema criada no teste manual, contato 610661344).
