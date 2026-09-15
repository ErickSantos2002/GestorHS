# Empresas e destinatário da proposta — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar o cadastro de Empresas (filiais com matriz opcional) e fazer a proposta ter como destinatário um Cliente ou uma Empresa, gravando os dados editados no cadastro e guardando uma cópia congelada na proposta, no lugar do `cliente_override`.

**Architecture:** Tabela `empresas` nova + FK `propostas.empresa` + JSON `propostas.destinatario` (cópia congelada escrita só pelo servidor). O salvamento da proposta recebe um bloco `destinatario` e, numa transação, atualiza/cria o cadastro, acerta as FKs, valida os aparelhos contra a frota da matriz e congela a cópia. Regras puras em `app/core/empresa.py`; acesso ao banco em `app/core/empresa_servico.py` e `app/core/proposta_servico.py`. No frontend, um formulário compartilhado (`DadosEmpresaForm`) serve a página Empresas e o modal da proposta.

**Tech Stack:** FastAPI · SQLAlchemy 2 · Pydantic v2 · Alembic · pytest (SQLite in-memory) · React 19 · TypeScript · Vite 8 · Tailwind v4 · Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-15-empresas-destinatario-proposta-design.md`

## Global Constraints

- Idioma do domínio em PT-BR: nomes de modelos, rotas, variáveis e mensagens.
- Commits: Conventional Commits em português **sem acentos**, uma linha, **sem corpo e sem trailer de co-autor** (regra do repo, prevalece sobre qualquer outra instrução de atribuição).
- Nunca `git add -A` / `git add .`: adicionar arquivo por arquivo. Conferir a branch (`git branch --show-current`) antes de cada commit — pode haver outra sessão no mesmo repo.
- **NUNCA rodar `alembic upgrade` nesta máquina**: o `backend/.env` aponta para o banco de PRODUÇÃO. Migração se valida só em modo offline (`--sql`).
- Scripts de dados simulam por padrão e só gravam com `--aplicar`.
- Quem escreve Empresa e dados do destinatário: `"Comercial Pós-Vendas"`, `"Financeiro"`, `"Administrador"`. Leitura: qualquer usuário interno.
- Documento (CNPJ/CPF) é único **somando** `clientes` e `empresas`; do lado de `clientes` a checagem olha **só** `empresas` (duplicata antiga entre clientes não pode travar edição).
- `propostas.cliente_override` fica congelada: nenhum caminho novo escreve nela.
- Backend: rodar a partir de `backend/` com `source .venv/bin/activate`. Há falhas pré-existentes nesta máquina — rodar `pytest -q` **antes** de começar e guardar a lista como baseline; regressão é só o que falhar além dela.
- Frontend: verificação antes de commitar: `npm run lint && npx tsc -b --noEmit && npm run build` (a partir de `frontend/`).

## Desvios da spec (decididos ao ler o código)

1. **Backfill da cópia congelada vai para o script, não para a migração.** Nenhuma migração do repo importa código de `app/`, e a regra de montagem precisa ser a mesma do PDF. A `0030` fica só com DDL; `montar_saida` e o PDF usam `destinatario_legado(cliente, cliente_override)` quando `destinatario` é nulo (o resultado é idêntico ao de hoje), e `migrar_filiais_propostas` congela todas as propostas antigas além de criar as filiais.
2. **`destinatario` é opcional também no `POST` do backend.** Dez testes existentes criam proposta sem cliente, e há 6 propostas assim em produção. Quem exige destinatário é o modal (`validacao.ts`).
3. **409 de documento duplicado devolve `detail` string** ("Documento já cadastrado como Cliente: NOME"). `apiJson` só lê `detail` string; o modal descobre o cadastro existente chamando `/propostas/destinatarios?q=<documento>`.
4. **Busca da listagem de propostas por JOIN** em `clientes` e `empresas` (nome e documento), não por operador JSON.
5. **`unificar_clientes.REFERENCIAS` ganha `("empresas", "cliente")`** — sem isso o script recusa rodar (ele confere toda FK para `clientes`).

## File Structure

**Backend — criar**
- `backend/app/core/empresa.py` — puro: validação/normalização de documento, `dados_destinatario`, `destinatario_legado`, `linha_endereco`.
- `backend/app/models/empresa.py` — model `Empresa`.
- `backend/alembic/versions/0030_empresas.py` — DDL.
- `backend/app/schemas/empresa.py` — `EmpresaIn`, `EmpresaOut`, `EmpresasPage`.
- `backend/app/core/empresa_servico.py` — unicidade entre tabelas, criar/atualizar Empresa.
- `backend/app/api/empresas.py` — rotas `/empresas`.
- `backend/app/scripts/migrar_filiais_propostas.py` — congela cópias e cria filiais do legado.
- Testes: `tests/test_empresa_core.py`, `tests/test_empresas.py`, `tests/test_propostas_destinatario.py`, `tests/test_migrar_filiais_propostas.py`.

**Backend — modificar**
- `app/models/proposta.py`, `app/models/__init__.py`, `app/main.py`
- `app/schemas/proposta.py`, `app/core/proposta_servico.py`, `app/api/propostas.py`, `app/core/proposta_pdf.py`
- `app/api/clientes.py` (409 contra Empresa)
- `app/core/enderecos.py` (número/complemento/bairro separados)
- `app/scripts/unificar_clientes.py` (`REFERENCIAS`)
- Testes existentes: `test_propostas.py`, `test_caixas_proposta.py`, `test_propostas_desabilitar.py`, `test_proposta_pdf.py`, `test_enderecos.py`, `test_clientes.py`

**Frontend — criar**
- `src/app/empresas/api.ts` — tipos e clientes HTTP de Empresa e da busca de destinatário.
- `src/app/empresas/dadosEmpresa.ts` — puro: tipo `DadosEmpresa`, conversões de Cliente/Empresa, obrigatórios.
- `src/app/empresas/buscaEndereco.ts` — movido de `propostas/`, retipado para `DadosEmpresa`.
- `src/app/empresas/DadosEmpresaForm.tsx` — formulário compartilhado.
- `src/app/empresas/MatrizSelect.tsx` — seletor de Cliente matriz com busca.
- `src/app/empresas/EmpresaModal.tsx`, `src/app/empresas/EmpresasPage.tsx`
- `src/app/clientes/EmpresasVinculadasSection.tsx`
- `src/app/propostas/destinatario.ts` — puro: `Selecao`, cliente da frota, payload.
- `src/app/propostas/DestinatarioBusca.tsx`
- Testes `*.test.ts(x)` ao lado de cada um.

**Frontend — modificar**
- `src/auth/roles.ts`, `src/app/routes.tsx`, `src/layout/Sidebar.tsx`
- `src/app/clientes/ClienteDadosTab.tsx`
- `src/app/propostas/api.ts`, `validacao.ts`, `PropostaModal.tsx`, `PropostasPage.tsx` (+ testes)
- `src/app/changelog/data.ts`

**Frontend — apagar**
- `src/app/propostas/clienteOverride.ts`, `clienteOverride.test.ts`, `OverrideDetalhe.tsx`

**Docs**
- Criar `docs/operacao-empresas-migracao.md`; modificar `CLAUDE.md`.

---

### Task 0: Branch e baseline

**Files:** nenhum.

- [ ] **Step 1: Criar a branch a partir da main atualizada**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current          # esperado: main
git fetch origin && git status -sb # conferir que main nao esta atras
git switch -c feat/empresas
```

- [ ] **Step 2: Baseline do backend**

```bash
cd backend && source .venv/bin/activate
pytest -q 2>&1 | tail -15
```
Guardar a lista de testes que falham (esperado: as falhas pré-existentes conhecidas, alheias a propostas/clientes).

- [ ] **Step 3: Baseline do frontend**

```bash
cd ../frontend && npm test 2>&1 | tail -15
```
Guardar a lista de falhas pré-existentes.

---

### Task 1: Núcleo puro `app/core/empresa.py`

**Files:**
- Create: `backend/app/core/empresa.py`
- Test: `backend/tests/test_empresa_core.py`

**Interfaces:**
- Produces:
  - `class DocumentoInvalido(ValueError)`
  - `so_digitos(v) -> str`
  - `cnpj_valido(d: str) -> bool`, `cpf_valido(d: str) -> bool`
  - `normalizar_documento(texto) -> tuple[str | None, str | None]` — `(cgc, cpf)`; levanta `DocumentoInvalido`
  - `dados_destinatario(registro, *, tipo: Literal["cliente","empresa"], matriz=None) -> dict`
  - `destinatario_legado(cliente, override: dict | None) -> dict`
  - `linha_endereco(dest: dict) -> str`

- [ ] **Step 1: Escrever os testes**

```python
# backend/tests/test_empresa_core.py
from types import SimpleNamespace

import pytest

from app.core import empresa


def test_cnpj_valido():
    assert empresa.cnpj_valido("08857492000148")
    assert empresa.cnpj_valido("36312056000552")
    assert not empresa.cnpj_valido("08857492000149")
    assert not empresa.cnpj_valido("11111111111111")
    assert not empresa.cnpj_valido("0885749200014")


def test_cpf_valido():
    assert empresa.cpf_valido("12345678909")
    assert empresa.cpf_valido("11144477735")
    assert not empresa.cpf_valido("12345678900")
    assert not empresa.cpf_valido("00000000000")


def test_normalizar_documento_cnpj_com_mascara():
    assert empresa.normalizar_documento("08.857.492/0001-48") == ("08857492000148", None)


def test_normalizar_documento_cpf():
    assert empresa.normalizar_documento("123.456.789-09") == (None, "12345678909")


@pytest.mark.parametrize("texto", ["", None, "123", "08857492000149", "12345678900"])
def test_normalizar_documento_invalido(texto):
    with pytest.raises(empresa.DocumentoInvalido):
        empresa.normalizar_documento(texto)


def _cliente(**kw):
    base = dict(id=5, nome="ACME", cgc="08857492000148", cpf=None, cep="50000000",
                endereco="Rua X", numero=10, complemento=None, bairro="Boa Vista",
                municipio="Recife", estado="PE", email="a@acme.com",
                telefones=None, celular="81999990000", whatsapp=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _empresa(**kw):
    base = dict(id=9, nome="ACME Filial", cgc="36312056000552", cpf=None, cep="29680000",
                endereco="BR 101", numero="S/N", complemento="KM 196", bairro="Zona Rural",
                municipio="Joao Neiva", estado="ES", email="f@acme.com", telefone="2733330000")
    base.update(kw)
    return SimpleNamespace(**base)


def test_dados_destinatario_cliente_prefere_telefones_e_numero_vira_texto():
    d = empresa.dados_destinatario(_cliente(telefones="8130001111"), tipo="cliente")
    assert d["tipo"] == "cliente" and d["id"] == 5
    assert d["documento"] == "08857492000148"
    assert d["numero"] == "10"
    assert d["telefone"] == "8130001111"
    assert "matriz_id" not in d


def test_dados_destinatario_cliente_sem_telefones_cai_no_celular():
    assert empresa.dados_destinatario(_cliente(), tipo="cliente")["telefone"] == "81999990000"


def test_dados_destinatario_empresa_com_matriz():
    d = empresa.dados_destinatario(_empresa(), tipo="empresa", matriz=_cliente())
    assert d["tipo"] == "empresa" and d["id"] == 9
    assert d["numero"] == "S/N"
    assert d["telefone"] == "2733330000"
    assert d["matriz_id"] == 5 and d["matriz_nome"] == "ACME"


def test_dados_destinatario_empresa_sem_matriz():
    d = empresa.dados_destinatario(_empresa(), tipo="empresa")
    assert d["matriz_id"] is None and d["matriz_nome"] is None


def test_destinatario_legado_reproduz_o_pdf_de_hoje():
    # O PDF antigo nao imprimia numero/bairro do cadastro e lia celular antes de telefones.
    d = empresa.destinatario_legado(_cliente(telefones="8130001111"), {"nome": "ACME SP", "cep": "01000000"})
    assert d["tipo"] == "cliente" and d["id"] == 5
    assert d["nome"] == "ACME SP"
    assert d["cep"] == "01000000"
    assert d["endereco"] == "Rua X"
    assert d["numero"] is None and d["bairro"] is None
    assert d["telefone"] == "81999990000"


def test_destinatario_legado_sem_cliente_usa_so_o_override():
    d = empresa.destinatario_legado(None, {"nome": "Avulso", "documento": "123.456.789-09"})
    assert d["id"] is None
    assert d["nome"] == "Avulso"
    assert d["documento"] == "12345678909"


def test_destinatario_legado_vazio():
    d = empresa.destinatario_legado(None, None)
    assert d["nome"] is None and d["documento"] is None


def test_linha_endereco():
    assert empresa.linha_endereco({"endereco": "BR 101", "numero": "S/N", "complemento": "KM 196", "bairro": "Zona Rural"}) == "BR 101, S/N KM 196 - Zona Rural"
    assert empresa.linha_endereco({"endereco": "Rua X, 10", "numero": None}) == "Rua X, 10"
    assert empresa.linha_endereco({}) == ""
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_empresa_core.py -q`
Expected: FAIL com `ImportError: cannot import name 'empresa'`.

- [ ] **Step 3: Implementar**

```python
# backend/app/core/empresa.py
"""Regras puras de Empresa (filial) e do destinatario da proposta. Sem I/O.

O destinatario da proposta e' um Cliente (matriz, dono da frota) ou uma Empresa
(filial, sem frota, com matriz opcional). A proposta guarda uma COPIA CONGELADA
dos dados do destinatario no momento em que foi salva (`propostas.destinatario`),
para o PDF antigo nao mudar quando o cadastro mudar. `dados_destinatario` e' a
unica funcao que conhece o formato desse JSON.
"""
import re
from typing import Literal, Optional


class DocumentoInvalido(ValueError):
    """CNPJ/CPF com tamanho ou digito verificador errado."""


def so_digitos(v) -> str:
    return re.sub(r"\D", "", str(v or ""))


def _dv(base: str, pesos: list[int]) -> str:
    resto = sum(int(x) * p for x, p in zip(base, pesos)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(d: str) -> bool:
    if len(d) != 14 or not d.isdigit() or d == d[0] * 14:
        return False
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = _dv(d[:12], p1)
    d2 = _dv(d[:12] + d1, [6] + p1)
    return d[12:] == d1 + d2


def cpf_valido(d: str) -> bool:
    if len(d) != 11 or not d.isdigit() or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10) % 11 % 10 != int(d[n]):
            return False
    return True


def normalizar_documento(texto) -> tuple[Optional[str], Optional[str]]:
    """Devolve (cgc, cpf) so com digitos — exatamente um dos dois preenchido."""
    d = so_digitos(texto)
    if len(d) == 14:
        if not cnpj_valido(d):
            raise DocumentoInvalido("CNPJ invalido")
        return d, None
    if len(d) == 11:
        if not cpf_valido(d):
            raise DocumentoInvalido("CPF invalido")
        return None, d
    raise DocumentoInvalido("Documento deve ser CNPJ (14 digitos) ou CPF (11 digitos)")


def _texto(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def dados_destinatario(registro, *, tipo: Literal["cliente", "empresa"], matriz=None) -> dict:
    """Copia congelada a partir do cadastro ja salvo.

    Cliente: telefone vem de `telefones` (onde a proposta grava), com celular e
    whatsapp de reserva; `numero` e' inteiro no cadastro e vira texto aqui.
    """
    if tipo == "cliente":
        telefone = registro.telefones or registro.celular or registro.whatsapp
    else:
        telefone = registro.telefone
    dados = {
        "tipo": tipo,
        "id": registro.id,
        "nome": _texto(registro.nome),
        "documento": registro.cgc or registro.cpf,
        "cep": _texto(registro.cep),
        "endereco": _texto(registro.endereco),
        "numero": _texto(registro.numero),
        "complemento": _texto(registro.complemento),
        "bairro": _texto(registro.bairro),
        "municipio": _texto(registro.municipio),
        "estado": _texto(registro.estado),
        "email": _texto(registro.email),
        "telefone": _texto(telefone),
    }
    if tipo == "empresa":
        dados["matriz_id"] = matriz.id if matriz is not None else None
        dados["matriz_nome"] = matriz.nome if matriz is not None else None
    return dados


def destinatario_legado(cliente, override: Optional[dict]) -> dict:
    """O que o PDF mostrava ANTES das Empresas: cadastro do cliente com o
    `cliente_override` por cima, campo a campo.

    Reproduz as escolhas do PDF antigo de proposito — nao imprimia numero nem
    bairro do cadastro, e lia celular antes de telefones — para uma proposta
    antiga sair igual depois da mudanca.
    """
    ov = override or {}

    def campo(chave: str, do_cadastro):
        return _texto(ov.get(chave)) or _texto(do_cadastro)

    c = cliente
    return {
        "tipo": "cliente",
        "id": c.id if c is not None else None,
        "nome": campo("nome", c.nome if c else None),
        "documento": so_digitos(ov.get("documento")) or ((c.cgc or c.cpf) if c else None) or None,
        "cep": so_digitos(ov.get("cep")) or (_texto(c.cep) if c else None) or None,
        "endereco": campo("endereco", c.endereco if c else None),
        "numero": None,
        "complemento": None,
        "bairro": None,
        "municipio": campo("municipio", c.municipio if c else None),
        "estado": campo("estado", c.estado if c else None),
        "email": campo("email", c.email if c else None),
        "telefone": campo("telefone", (c.celular or c.whatsapp or c.telefones) if c else None),
    }


def linha_endereco(dest: dict) -> str:
    """`Endereco, numero complemento - bairro`, pulando o que estiver vazio."""
    linha = _texto(dest.get("endereco")) or ""
    numero = _texto(dest.get("numero"))
    complemento = _texto(dest.get("complemento"))
    bairro = _texto(dest.get("bairro"))
    if numero:
        linha = f"{linha}, {numero}" if linha else numero
    if complemento:
        linha = f"{linha} {complemento}".strip()
    if bairro:
        linha = f"{linha} - {bairro}" if linha else bairro
    return linha
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_empresa_core.py -q`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git branch --show-current   # feat/empresas
git add backend/app/core/empresa.py backend/tests/test_empresa_core.py
git commit -m "feat(empresas): nucleo puro de documento e copia do destinatario"
```

---

### Task 2: Model `Empresa`, colunas da proposta e migração `0030`

**Files:**
- Create: `backend/app/models/empresa.py`, `backend/alembic/versions/0030_empresas.py`
- Modify: `backend/app/models/proposta.py`, `backend/app/models/__init__.py`, `backend/app/scripts/unificar_clientes.py:50-64`
- Test: `backend/tests/test_empresa_core.py` (acrescentar testes de model)

**Interfaces:**
- Produces: `app.models.Empresa` (colunas abaixo, `matriz_rel` → `Cliente`); `Proposta.empresa: int | None`, `Proposta.destinatario: dict | None`, `Proposta.empresa_rel`.

- [ ] **Step 1: Escrever os testes de model**

Acrescentar ao fim de `backend/tests/test_empresa_core.py`:

```python
def test_model_empresa_com_matriz(db_session):
    from app.models import Cliente, Empresa
    cli = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add(cli); db_session.flush()
    e = Empresa(nome="ACME Filial", cgc="36312056000552", cliente=cli.id)
    db_session.add(e); db_session.flush()
    db_session.refresh(e)
    assert e.ativo is True
    assert e.matriz_rel.nome == "ACME"


def test_model_empresa_cgc_unico(db_session):
    from sqlalchemy.exc import IntegrityError
    from app.models import Empresa
    db_session.add(Empresa(nome="A", cgc="36312056000552")); db_session.flush()
    db_session.add(Empresa(nome="B", cgc="36312056000552"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_model_empresa_exige_exatamente_um_documento(db_session):
    from sqlalchemy.exc import IntegrityError
    from app.models import Empresa
    db_session.add(Empresa(nome="Sem documento"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_model_proposta_aponta_para_empresa(db_session):
    from app.models import Empresa, Proposta
    e = Empresa(nome="Filial", cpf="12345678909")
    db_session.add(e); db_session.flush()
    p = Proposta(numero=1, empresa=e.id, destinatario={"tipo": "empresa", "id": e.id})
    db_session.add(p); db_session.flush(); db_session.refresh(p)
    assert p.empresa_rel.nome == "Filial"
    assert p.destinatario["tipo"] == "empresa"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_empresa_core.py -q -k model`
Expected: FAIL com `ImportError: cannot import name 'Empresa'`.

- [ ] **Step 3: Criar o model**

```python
# backend/app/models/empresa.py
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.database import Base


class Empresa(Base):
    """Filial: so dados cadastrais, sem frota. Os aparelhos vem da matriz
    (`cliente`), que e' opcional. Documento unico somando `clientes` e
    `empresas` — a checagem cruzada vive em core/empresa_servico.py."""
    __tablename__ = "empresas"
    __table_args__ = (
        CheckConstraint("(cgc IS NULL) <> (cpf IS NULL)", name="ck_empresas_um_documento"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True, index=True)
    nome = Column(String(100), nullable=False)
    cgc = Column(String(14), nullable=True, unique=True)
    cpf = Column(String(11), nullable=True, unique=True)
    endereco = Column(String(100), nullable=True)
    numero = Column(String(20), nullable=True)
    complemento = Column(String(60), nullable=True)
    bairro = Column(String(100), nullable=True)
    municipio = Column(String(100), nullable=True)
    estado = Column(String(2), nullable=True)
    cep = Column(String(8), nullable=True)
    email = Column(String(100), nullable=True)
    telefone = Column(String(50), nullable=True)
    insc_est = Column(String(20), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True, server_default=sa.text("true"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    matriz_rel = relationship("Cliente", lazy="joined")
```

- [ ] **Step 4: Colunas novas na proposta**

Em `backend/app/models/proposta.py`, logo abaixo da linha `cliente = Column(...)`:

```python
    # Destinatario Empresa (filial). Com ela preenchida, `cliente` e' a matriz dela.
    empresa = Column(Integer, ForeignKey("empresas.id", ondelete="SET NULL"), nullable=True, index=True)
```

Logo abaixo de `cliente_override = Column(JSON, nullable=True)`:

```python
    # CONGELADA desde as Empresas (set/2026): nenhum caminho novo escreve aqui.
    # Proposta antiga ainda e' lida por core/empresa.destinatario_legado.
    # Copia dos dados do destinatario no momento do salvamento — escrita so pelo servidor.
    destinatario = Column(JSON, nullable=True)
```

(A primeira linha de comentário vai **acima** de `cliente_override`; mova-a para lá.) E junto de `cliente_rel`:

```python
    empresa_rel = relationship("Empresa", lazy="joined")
```

- [ ] **Step 5: Registrar o model**

Em `backend/app/models/__init__.py`, depois de `from app.models.cliente import Cliente`:

```python
from app.models.empresa import Empresa
```

e acrescentar `"Empresa"` na lista `__all__`, logo após `"Cliente"`.

- [ ] **Step 6: Rodar e ver passar**

Run: `pytest tests/test_empresa_core.py -q`
Expected: PASS.

- [ ] **Step 7: FK nova no script de unificação**

Run primeiro: `pytest tests/test_unificar_clientes.py::test_referencias_cobre_toda_FK_declarada_para_clientes -q`
Expected: FAIL (`{('empresas', 'cliente')}`).

Em `backend/app/scripts/unificar_clientes.py`, na tupla `REFERENCIAS`, depois de `("caixas", "cliente_principal"),`:

```python
    ("empresas", "cliente"),
```

Run de novo: Expected PASS.

- [ ] **Step 8: Migração**

```python
# backend/alembic/versions/0030_empresas.py
"""empresas (filiais) + destinatario da proposta

A proposta passa a ter como destinatario um Cliente ou uma Empresa. A Empresa e'
uma filial: so dados cadastrais, matriz opcional em `cliente`.

`propostas.destinatario` e' a copia congelada dos dados do destinatario. NAO ha
backfill aqui: a regra de montagem mora em app/core/empresa.py e o repo nao
importa `app` em migracao. Enquanto a copia estiver nula, a API e o PDF montam
o mesmo resultado de antes (cadastro + cliente_override); o script
`migrar_filiais_propostas --aplicar` congela as antigas.

`cliente_override` NAO e' apagado.
"""
import sqlalchemy as sa
from alembic import op

revision = "0030_empresas"
down_revision = "0029_notas_fiscais"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "empresas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cliente", sa.Integer, sa.ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("cgc", sa.String(14), nullable=True),
        sa.Column("cpf", sa.String(11), nullable=True),
        sa.Column("endereco", sa.String(100), nullable=True),
        sa.Column("numero", sa.String(20), nullable=True),
        sa.Column("complemento", sa.String(60), nullable=True),
        sa.Column("bairro", sa.String(100), nullable=True),
        sa.Column("municipio", sa.String(100), nullable=True),
        sa.Column("estado", sa.String(2), nullable=True),
        sa.Column("cep", sa.String(8), nullable=True),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("telefone", sa.String(50), nullable=True),
        sa.Column("insc_est", sa.String(20), nullable=True),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("(cgc IS NULL) <> (cpf IS NULL)", name="ck_empresas_um_documento"),
        sa.UniqueConstraint("cgc", name="uq_empresas_cgc"),
        sa.UniqueConstraint("cpf", name="uq_empresas_cpf"),
    )
    op.create_index("ix_empresas_id", "empresas", ["id"])
    op.create_index("ix_empresas_cliente", "empresas", ["cliente"])

    op.add_column("propostas", sa.Column("empresa", sa.Integer, nullable=True))
    op.create_foreign_key("fk_propostas_empresa", "propostas", "empresas", ["empresa"], ["id"], ondelete="SET NULL")
    op.create_index("ix_propostas_empresa", "propostas", ["empresa"])
    op.add_column("propostas", sa.Column("destinatario", sa.JSON, nullable=True))


def downgrade():
    # Proposta salva depois da 0030 nao tem override: sem a copia, o PDF dela
    # volta a sair so com o cadastro do cliente. Ver docs/operacao-empresas-migracao.md.
    op.drop_column("propostas", "destinatario")
    op.drop_index("ix_propostas_empresa", table_name="propostas")
    op.drop_constraint("fk_propostas_empresa", "propostas", type_="foreignkey")
    op.drop_column("propostas", "empresa")
    op.drop_index("ix_empresas_cliente", table_name="empresas")
    op.drop_index("ix_empresas_id", table_name="empresas")
    op.drop_table("empresas")
```

- [ ] **Step 9: Validar a migração OFFLINE (sem tocar em banco)**

```bash
alembic upgrade 0029_notas_fiscais:0030_empresas --sql | grep -E "CREATE TABLE empresas|ALTER TABLE propostas|CREATE INDEX"
alembic downgrade 0030_empresas:0029_notas_fiscais --sql | grep -E "DROP"
```
Expected: o SQL aparece e nenhum erro. **Não** rodar sem `--sql`.

- [ ] **Step 10: Suíte de models e unificação**

Run: `pytest tests/test_empresa_core.py tests/test_unificar_clientes.py tests/test_propostas.py -q`
Expected: PASS (fora da baseline).

- [ ] **Step 11: Commit**

```bash
git add backend/app/models/empresa.py backend/app/models/proposta.py backend/app/models/__init__.py \
  backend/alembic/versions/0030_empresas.py backend/app/scripts/unificar_clientes.py backend/tests/test_empresa_core.py
git commit -m "feat(empresas): tabela empresas e destinatario da proposta (migracao 0030)"
```

---
### Task 3: Schemas de Empresa e serviço de cadastro

**Files:**
- Create: `backend/app/schemas/empresa.py`, `backend/app/core/empresa_servico.py`
- Test: `backend/tests/test_empresas.py` (parte de serviço)

**Interfaces:**
- Consumes: `app.core.empresa.normalizar_documento`, `DocumentoInvalido`; `app.models.Empresa`, `Cliente`.
- Produces:
  - `EmpresaIn` (Pydantic): `documento: str`, `cliente: int | None`, `nome: str`, `cep`, `endereco`, `numero`, `complemento`, `bairro`, `municipio`, `estado`, `email`, `telefone`, `insc_est` (todos `str | None`).
  - `EmpresaOut`: colunas do model + `matriz_nome: str | None`. `EmpresasPage`: `items: list[EmpresaOut]`, `total: int`.
  - `class DocumentoDuplicado(Exception)` com `.tipo` (`"cliente"|"empresa"`), `.id`, `.nome`; `str(e)` = `"Documento já cadastrado como Cliente: NOME"` / `"... como Empresa: NOME"`.
  - `class MatrizInexistente(ValueError)`.
  - `checar_documento_livre(db, cgc, cpf, *, empresa_id=None, cliente_id=None, incluir_clientes=True) -> None`
  - `CAMPOS_EMPRESA: tuple[str, ...]`
  - `criar_empresa(db, dados: EmpresaIn) -> Empresa` (faz `flush`, **não** `commit`)
  - `atualizar_empresa(db, empresa: Empresa, dados: EmpresaIn) -> Empresa` (idem)
  - `saida_empresa(empresa: Empresa) -> EmpresaOut`

- [ ] **Step 1: Escrever os testes do serviço**

```python
# backend/tests/test_empresas.py
import pytest

from app.core import empresa_servico as es
from app.core.empresa import DocumentoInvalido
from app.models import Cliente, Empresa
from app.schemas.empresa import EmpresaIn

CNPJ_A = "08857492000148"
CNPJ_B = "36312056000552"
CNPJ_C = "11222333000181"


def _in(**kw):
    base = dict(documento=CNPJ_B, nome="Filial", cliente=None)
    base.update(kw)
    return EmpresaIn(**base)


# --- servico ----------------------------------------------------------------

def test_criar_empresa_normaliza_documento_e_liga_matriz(db_session):
    cli = Cliente(nome="ACME", cgc=CNPJ_A); db_session.add(cli); db_session.flush()
    e = es.criar_empresa(db_session, _in(documento="36.312.056/0005-52", cliente=cli.id, estado="pe", cep="29680-000"))
    assert e.id is not None
    assert (e.cgc, e.cpf) == (CNPJ_B, None)
    assert e.estado == "PE" and e.cep == "29680000"
    assert e.cliente == cli.id


def test_criar_empresa_com_cpf(db_session):
    e = es.criar_empresa(db_session, _in(documento="123.456.789-09"))
    assert (e.cgc, e.cpf) == (None, "12345678909")


def test_criar_empresa_documento_invalido(db_session):
    with pytest.raises(DocumentoInvalido):
        es.criar_empresa(db_session, _in(documento="08857492000149"))


def test_criar_empresa_documento_de_cliente_e_duplicado(db_session):
    cli = Cliente(nome="ACME", cgc=CNPJ_B); db_session.add(cli); db_session.flush()
    with pytest.raises(es.DocumentoDuplicado) as exc:
        es.criar_empresa(db_session, _in())
    assert exc.value.tipo == "cliente" and exc.value.id == cli.id
    assert str(exc.value) == "Documento já cadastrado como Cliente: ACME"


def test_criar_empresa_documento_de_outra_empresa_e_duplicado(db_session):
    es.criar_empresa(db_session, _in(nome="Primeira"))
    with pytest.raises(es.DocumentoDuplicado) as exc:
        es.criar_empresa(db_session, _in(nome="Segunda"))
    assert exc.value.tipo == "empresa"


def test_criar_empresa_matriz_inexistente(db_session):
    with pytest.raises(es.MatrizInexistente):
        es.criar_empresa(db_session, _in(cliente=999))


def test_atualizar_empresa_mantendo_o_proprio_documento(db_session):
    e = es.criar_empresa(db_session, _in())
    es.atualizar_empresa(db_session, e, _in(nome="Renomeada", bairro="Centro"))
    assert e.nome == "Renomeada" and e.bairro == "Centro"


def test_atualizar_empresa_para_documento_ocupado(db_session):
    es.criar_empresa(db_session, _in(documento=CNPJ_C, nome="Outra"))
    e = es.criar_empresa(db_session, _in())
    with pytest.raises(es.DocumentoDuplicado):
        es.atualizar_empresa(db_session, e, _in(documento=CNPJ_C))


def test_checagem_do_lado_do_cliente_ignora_duplicata_entre_clientes(db_session):
    # Duplicata antiga entre clientes nao pode travar a edicao do cliente.
    db_session.add_all([Cliente(nome="A", cgc=CNPJ_A), Cliente(nome="B", cgc=CNPJ_A)]); db_session.flush()
    es.checar_documento_livre(db_session, CNPJ_A, None, incluir_clientes=False)


def test_schema_campos_vazios_viram_none():
    d = _in(email="  ", bairro="")
    assert d.email is None and d.bairro is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_empresas.py -q`
Expected: FAIL com `ModuleNotFoundError: app.core.empresa_servico`.

- [ ] **Step 3: Schemas**

```python
# backend/app/schemas/empresa.py
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmpresaIn(BaseModel):
    """Criacao e edicao (PUT substitui tudo). `documento` aceita mascara; a
    validacao do digito verificador fica no servico, que devolve 422 proprio."""
    model_config = ConfigDict(str_strip_whitespace=True)

    documento: str
    cliente: Optional[int] = None
    nome: str = Field(min_length=1, max_length=100)
    cep: Optional[str] = Field(default=None, max_length=9)
    endereco: Optional[str] = Field(default=None, max_length=100)
    numero: Optional[str] = Field(default=None, max_length=20)
    complemento: Optional[str] = Field(default=None, max_length=60)
    bairro: Optional[str] = Field(default=None, max_length=100)
    municipio: Optional[str] = Field(default=None, max_length=100)
    estado: Optional[str] = Field(default=None, max_length=2)
    email: Optional[str] = Field(default=None, max_length=100)
    telefone: Optional[str] = Field(default=None, max_length=50)
    insc_est: Optional[str] = Field(default=None, max_length=20)

    @field_validator("cep", "endereco", "numero", "complemento", "bairro", "municipio",
                     "estado", "email", "telefone", "insc_est", mode="after")
    @classmethod
    def _vazio_vira_none(cls, v: Optional[str], info) -> Optional[str]:
        if v is None or v == "":
            return None
        if info.field_name == "cep":
            d = re.sub(r"\D", "", v)
            return d[:8] or None
        if info.field_name == "estado":
            return v.upper()
        return v


class EmpresaOut(BaseModel):
    id: int
    cliente: Optional[int] = None
    matriz_nome: Optional[str] = None
    nome: str
    cgc: Optional[str] = None
    cpf: Optional[str] = None
    cep: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    insc_est: Optional[str] = None
    ativo: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class EmpresasPage(BaseModel):
    items: list[EmpresaOut]
    total: int
```

- [ ] **Step 4: Serviço**

```python
# backend/app/core/empresa_servico.py
"""Cadastro de Empresa com acesso ao banco: unicidade do documento somando
`clientes` e `empresas`, criar e atualizar. Nunca faz commit — quem chama decide,
porque o modal da proposta cria a Empresa na MESMA transacao da proposta.
"""
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.empresa import normalizar_documento
from app.models import Cliente, Empresa
from app.schemas.empresa import EmpresaIn, EmpresaOut

CAMPOS_EMPRESA = ("nome", "cep", "endereco", "numero", "complemento", "bairro",
                  "municipio", "estado", "email", "telefone", "insc_est")

_ROTULO = {"cliente": "Cliente", "empresa": "Empresa"}


class DocumentoDuplicado(Exception):
    def __init__(self, tipo: str, id_: int, nome: Optional[str]):
        self.tipo = tipo
        self.id = id_
        self.nome = nome
        super().__init__(f"Documento já cadastrado como {_ROTULO[tipo]}: {nome or f'#{id_}'}")


class MatrizInexistente(ValueError):
    """`cliente` informado como matriz nao existe."""


def _procurar(db: Session, model, cgc, cpf, ignorar_id):
    filtros = []
    if cgc:
        filtros.append(model.cgc == cgc)
    if cpf:
        filtros.append(model.cpf == cpf)
    if not filtros:
        return None
    query = db.query(model).filter(or_(*filtros))
    if ignorar_id is not None:
        query = query.filter(model.id != ignorar_id)
    return query.first()


def checar_documento_livre(db: Session, cgc: Optional[str], cpf: Optional[str], *,
                           empresa_id: Optional[int] = None, cliente_id: Optional[int] = None,
                           incluir_clientes: bool = True) -> None:
    """Levanta DocumentoDuplicado se o documento ja existe.

    `incluir_clientes=False` e' o uso do cadastro de CLIENTES: la ainda aparece
    duplicata antiga entre clientes (ver operacao-unificar-clientes-duplicados),
    e ela nao pode travar a edicao — so a colisao com Empresa interessa.
    """
    if incluir_clientes:
        achado = _procurar(db, Cliente, cgc, cpf, cliente_id)
        if achado is not None:
            raise DocumentoDuplicado("cliente", achado.id, achado.nome)
    achado = _procurar(db, Empresa, cgc, cpf, empresa_id)
    if achado is not None:
        raise DocumentoDuplicado("empresa", achado.id, achado.nome)


def _conferir_matriz(db: Session, cliente_id: Optional[int]) -> None:
    if cliente_id is not None and db.get(Cliente, cliente_id) is None:
        raise MatrizInexistente("cliente matriz nao encontrado")


def criar_empresa(db: Session, dados: EmpresaIn) -> Empresa:
    cgc, cpf = normalizar_documento(dados.documento)
    checar_documento_livre(db, cgc, cpf)
    _conferir_matriz(db, dados.cliente)
    empresa = Empresa(cgc=cgc, cpf=cpf, cliente=dados.cliente,
                      **{c: getattr(dados, c) for c in CAMPOS_EMPRESA})
    db.add(empresa)
    db.flush()
    return empresa


def atualizar_empresa(db: Session, empresa: Empresa, dados: EmpresaIn) -> Empresa:
    cgc, cpf = normalizar_documento(dados.documento)
    checar_documento_livre(db, cgc, cpf, empresa_id=empresa.id)
    _conferir_matriz(db, dados.cliente)
    empresa.cgc, empresa.cpf, empresa.cliente = cgc, cpf, dados.cliente
    for campo in CAMPOS_EMPRESA:
        setattr(empresa, campo, getattr(dados, campo))
    db.flush()
    return empresa


def saida_empresa(empresa: Empresa) -> EmpresaOut:
    saida = EmpresaOut.model_validate(empresa)
    saida.matriz_nome = empresa.matriz_rel.nome if empresa.matriz_rel is not None else None
    return saida
```

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_empresas.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/empresa.py backend/app/core/empresa_servico.py backend/tests/test_empresas.py
git commit -m "feat(empresas): servico de cadastro com documento unico entre clientes e empresas"
```

---

### Task 4: Rotas `/empresas` e trava do lado de Clientes

**Files:**
- Create: `backend/app/api/empresas.py`
- Modify: `backend/app/main.py` (import e `include_router`), `backend/app/api/clientes.py` (`criar`, `atualizar`)
- Test: `backend/tests/test_empresas.py` (acrescentar), `backend/tests/test_clientes.py` (acrescentar)

**Interfaces:**
- Consumes: tudo de `empresa_servico` (Task 3).
- Produces (HTTP):
  - `GET /empresas?q=&cliente=&ativo=&offset=0&limit=25` → `EmpresasPage` (qualquer interno)
  - `GET /empresas/{id}` → `EmpresaOut` (qualquer interno)
  - `POST /empresas` (201), `PUT /empresas/{id}`, `POST /empresas/{id}/desativar`, `POST /empresas/{id}/reativar` → `EmpresaOut` (Comercial Pós-Vendas, Financeiro, Administrador)
  - Erros: 422 documento inválido ou matriz inexistente; 409 documento duplicado (`detail` string); 404.
  - `POST /clientes` e `PATCH /clientes/{id}` → 409 quando o `cgc`/`cpf` é de uma Empresa.

- [ ] **Step 1: Escrever os testes de rota**

Acrescentar a `backend/tests/test_empresas.py` (cada teste pede **um** client só — as fixtures de client são o mesmo objeto):

```python
# --- rotas ------------------------------------------------------------------

def _payload(**kw):
    base = {"documento": CNPJ_B, "nome": "Filial Norte", "cliente": None,
            "municipio": "Recife", "estado": "PE"}
    base.update(kw)
    return base


def test_comercial_cria_e_le_empresa(client_comercial, db_session):
    cli = Cliente(nome="ACME", cgc=CNPJ_A); db_session.add(cli); db_session.commit()
    r = client_comercial.post("/empresas", json=_payload(cliente=cli.id))
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["cgc"] == CNPJ_B and corpo["matriz_nome"] == "ACME" and corpo["ativo"] is True
    r = client_comercial.get(f"/empresas/{corpo['id']}")
    assert r.status_code == 200 and r.json()["nome"] == "Filial Norte"


def test_financeiro_cria_empresa(client_fin):
    assert client_fin.post("/empresas", json=_payload()).status_code == 201


def test_laboratorio_le_mas_nao_escreve(client_lab, db_session):
    db_session.add(Empresa(nome="Existente", cgc=CNPJ_C)); db_session.commit()
    assert client_lab.get("/empresas").status_code == 200
    assert client_lab.post("/empresas", json=_payload()).status_code == 403


def test_documento_invalido_422(client_comercial):
    r = client_comercial.post("/empresas", json=_payload(documento="08857492000149"))
    assert r.status_code == 422
    assert r.json()["detail"] == "CNPJ invalido"


def test_documento_de_cliente_409(client_comercial, db_session):
    db_session.add(Cliente(nome="ACME", cgc=CNPJ_B)); db_session.commit()
    r = client_comercial.post("/empresas", json=_payload())
    assert r.status_code == 409
    assert r.json()["detail"] == "Documento já cadastrado como Cliente: ACME"


def test_matriz_inexistente_422(client_comercial):
    assert client_comercial.post("/empresas", json=_payload(cliente=999)).status_code == 422


def test_listar_filtra_por_busca_matriz_e_ativo(client_comercial, db_session):
    cli = Cliente(nome="ACME", cgc=CNPJ_A); db_session.add(cli); db_session.flush()
    db_session.add_all([
        Empresa(nome="Filial Norte", cgc=CNPJ_B, cliente=cli.id),
        Empresa(nome="Outra Coisa", cgc=CNPJ_C, ativo=False),
    ]); db_session.commit()
    assert client_comercial.get("/empresas?q=norte").json()["total"] == 1
    assert client_comercial.get("/empresas?q=36.312.056").json()["total"] == 1
    assert client_comercial.get(f"/empresas?cliente={cli.id}").json()["total"] == 1
    assert client_comercial.get("/empresas?ativo=false").json()["items"][0]["nome"] == "Outra Coisa"
    assert client_comercial.get("/empresas").json()["total"] == 2


def test_put_atualiza_e_desativar_reativar(client_comercial):
    eid = client_comercial.post("/empresas", json=_payload()).json()["id"]
    r = client_comercial.put(f"/empresas/{eid}", json=_payload(nome="Filial Sul", bairro="Centro"))
    assert r.status_code == 200 and r.json()["nome"] == "Filial Sul"
    assert client_comercial.post(f"/empresas/{eid}/desativar").json()["ativo"] is False
    assert client_comercial.post(f"/empresas/{eid}/reativar").json()["ativo"] is True


def test_put_inexistente_404(client_comercial):
    assert client_comercial.put("/empresas/999", json=_payload()).status_code == 404
```

Acrescentar a `backend/tests/test_clientes.py` (usar o client com permissão de criar/editar cliente que o arquivo já usa — confira as fixtures no topo do arquivo; `client_admin` serve para os dois):

```python
def test_criar_cliente_com_documento_de_empresa_409(client_admin, db_session):
    from app.models import Empresa
    db_session.add(Empresa(nome="Filial X", cgc="36312056000552")); db_session.commit()
    r = client_admin.post("/clientes", json={"nome": "Novo", "cgc": "36.312.056/0005-52"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Documento já cadastrado como Empresa: Filial X"


def test_editar_cliente_para_documento_de_empresa_409(client_admin, db_session):
    from app.models import Cliente, Empresa
    cli = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add_all([cli, Empresa(nome="Filial X", cgc="36312056000552")]); db_session.commit()
    r = client_admin.patch(f"/clientes/{cli.id}", json={"cgc": "36312056000552"})
    assert r.status_code == 409


def test_editar_cliente_com_duplicata_antiga_entre_clientes_continua_permitido(client_admin, db_session):
    from app.models import Cliente
    a = Cliente(nome="A", cgc="08857492000148")
    db_session.add_all([a, Cliente(nome="B", cgc="08857492000148")]); db_session.commit()
    r = client_admin.patch(f"/clientes/{a.id}", json={"cgc": "08857492000148", "nome": "A2"})
    assert r.status_code == 200
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_empresas.py tests/test_clientes.py -q`
Expected: FAIL (rotas 404, clientes 201/200 onde se espera 409).

- [ ] **Step 3: Router**

```python
# backend/app/api/empresas.py
"""Cadastro de Empresas (filiais). Camada fina sobre core/empresa_servico.py."""
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario, require_funcao
from app.core import empresa_servico as es
from app.core.empresa import DocumentoInvalido
from app.models import Empresa, Usuario
from app.models.database import get_db
from app.schemas.empresa import EmpresaIn, EmpresaOut, EmpresasPage

router = APIRouter(prefix="/empresas", tags=["empresas"])

# Mesmo trio de quem faz proposta: o modal da proposta cria e edita Empresa.
_escrever = require_funcao("Comercial Pós-Vendas", "Financeiro", "Administrador")


def _empresa_ou_404(db: Session, empresa_id: int) -> Empresa:
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    return empresa


def _gravar(db: Session, empresa: Empresa) -> EmpresaOut:
    """Commit traduzindo a corrida de dois POST com o mesmo documento: o indice
    unico estoura aqui depois de a checagem ter passado nos dois."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Documento já cadastrado")
    db.refresh(empresa)
    return es.saida_empresa(empresa)


def _executar(db: Session, fn, *args):
    try:
        return fn(db, *args)
    except (DocumentoInvalido, es.MatrizInexistente) as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except es.DocumentoDuplicado as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=EmpresasPage)
def listar(
    q: str | None = None,
    cliente: int | None = None,
    ativo: bool | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Empresa)
    if q:
        termo = f"%{q.strip()}%"
        filtros = [Empresa.nome.ilike(termo), Empresa.municipio.ilike(termo)]
        digitos = re.sub(r"\D", "", q)
        if digitos:
            filtros += [Empresa.cgc.ilike(f"%{digitos}%"), Empresa.cpf.ilike(f"%{digitos}%")]
        query = query.filter(or_(*filtros))
    if cliente is not None:
        query = query.filter(Empresa.cliente == cliente)
    if ativo is not None:
        query = query.filter(Empresa.ativo.is_(ativo))
    total = query.count()
    itens = query.order_by(Empresa.nome).offset(offset).limit(limit).all()
    return EmpresasPage(items=[es.saida_empresa(e) for e in itens], total=total)


@router.get("/{empresa_id}", response_model=EmpresaOut)
def obter(empresa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return es.saida_empresa(_empresa_ou_404(db, empresa_id))


@router.post("", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def criar(dados: EmpresaIn, db: Session = Depends(get_db), _: Usuario = Depends(_escrever)):
    empresa = _executar(db, es.criar_empresa, dados)
    return _gravar(db, empresa)


@router.put("/{empresa_id}", response_model=EmpresaOut)
def atualizar(empresa_id: int, dados: EmpresaIn, db: Session = Depends(get_db), _: Usuario = Depends(_escrever)):
    empresa = _empresa_ou_404(db, empresa_id)
    _executar(db, es.atualizar_empresa, empresa, dados)
    return _gravar(db, empresa)


@router.post("/{empresa_id}/desativar", response_model=EmpresaOut)
def desativar(empresa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrever)):
    empresa = _empresa_ou_404(db, empresa_id)
    empresa.ativo = False
    return _gravar(db, empresa)


@router.post("/{empresa_id}/reativar", response_model=EmpresaOut)
def reativar(empresa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrever)):
    empresa = _empresa_ou_404(db, empresa_id)
    empresa.ativo = True
    return _gravar(db, empresa)
```

- [ ] **Step 4: Registrar no `main.py`**

Na linha `from app.api import auth, ..., manutencoes`, acrescentar `, empresas` ao fim. Depois de `app.include_router(manutencoes.router)`:

```python
app.include_router(empresas.router)
```

- [ ] **Step 5: Trava em `clientes.py`**

Imports no topo de `backend/app/api/clientes.py`:

```python
from app.core.empresa_servico import DocumentoDuplicado, checar_documento_livre
```

Helper logo abaixo de `ADMIN = "Administrador"`:

```python
def _conferir_contra_empresas(db: Session, cgc, cpf, cliente_id=None) -> None:
    """Documento e' unico somando clientes e empresas. Daqui so se olha Empresa:
    duplicata antiga entre clientes nao pode travar o cadastro."""
    try:
        checar_documento_livre(db, cgc, cpf, cliente_id=cliente_id, incluir_clientes=False)
    except DocumentoDuplicado as e:
        raise HTTPException(status_code=409, detail=str(e))
```

Em `criar`, antes de `obj = Cliente(...)`:

```python
    _conferir_contra_empresas(db, dados.cgc, dados.cpf)
```

Em `atualizar`, depois do 404 e antes do `for`:

```python
    mudancas = dados.model_dump(exclude_unset=True)
    if "cgc" in mudancas or "cpf" in mudancas:
        _conferir_contra_empresas(db, mudancas.get("cgc"), mudancas.get("cpf"), cliente_id=obj.id)
```

e trocar o `for` para iterar `mudancas.items()`.

- [ ] **Step 6: Rodar e ver passar**

Run: `pytest tests/test_empresas.py tests/test_clientes.py tests/test_clientes_saneamento.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/empresas.py backend/app/main.py backend/app/api/clientes.py backend/tests/test_empresas.py backend/tests/test_clientes.py
git commit -m "feat(empresas): rotas de empresas e trava de documento no cadastro de clientes"
```

---

### Task 5: Busca de CEP/CNPJ com número, complemento e bairro separados

**Files:**
- Modify: `backend/app/core/enderecos.py` (`mapear_brasilapi_cep`, `mapear_viacep`, `mapear_brasilapi_cnpj`)
- Test: `backend/tests/test_enderecos.py` (atualizar os três testes de mapeamento)

**Interfaces:**
- Produces: `GET /integracoes/cep/{cep}` → `{cep, endereco, bairro, municipio, estado}`; `GET /integracoes/cnpj/{cnpj}` → `{documento, nome, endereco, numero, complemento, bairro, municipio, estado, cep, situacao}`. `endereco` passa a ser **só o logradouro**.

- [ ] **Step 1: Atualizar os testes**

Em `backend/tests/test_enderecos.py`:
- `test_mapear_brasilapi_cep`: incluir `"neighborhood": "SANTO ANTONIO"` nos dados e `"bairro": "Santo Antonio"` no dicionário esperado.
- `test_mapear_viacep`: incluir `"bairro": "SANTO ANTONIO"` nos dados e `"bairro": "Santo Antonio"` no esperado.
- `test_mapear_brasilapi_cnpj_monta_endereco_completo` → renomear para `test_mapear_brasilapi_cnpj_separa_numero_complemento_e_bairro` e trocar o esperado por:

```python
    assert enderecos.mapear_brasilapi_cnpj(dados) == {
        "documento": "36312056000552",
        "nome": "CBF Industria de Gusa S/A",
        "endereco": "BR 101",
        "numero": "S/N",
        "complemento": "KM 196,5",
        "bairro": "Zona Rural",
        "municipio": "Joao Neiva",
        "estado": "ES",
        "cep": "29680000",
        "situacao": "ATIVA",
    }
```

- `test_mapear_brasilapi_cnpj_sem_numero_nem_complemento`: acrescentar `assert r["numero"] == "" and r["complemento"] == ""`.
- `test_mapear_brasilapi_cnpj_campos_ausentes_viram_string_vazia`: se ele lista chaves, acrescentar `numero`, `complemento`, `bairro`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_enderecos.py -q`
Expected: FAIL nos mapeamentos.

- [ ] **Step 3: Implementar**

Em `backend/app/core/enderecos.py`:

```python
def mapear_brasilapi_cep(dados: dict) -> dict:
    return {
        "cep": so_digitos(dados.get("cep")),
        "endereco": capitalizar(dados.get("street")),
        "bairro": capitalizar(dados.get("neighborhood")),
        "municipio": capitalizar(dados.get("city")),
        "estado": str(dados.get("state") or "").upper(),
    }


def mapear_viacep(dados: dict) -> dict:
    # A ViaCEP sinaliza CEP inexistente com HTTP 200 + {"erro": true}.
    if dados.get("erro"):
        raise NaoEncontrado("CEP nao encontrado")
    return {
        "cep": so_digitos(dados.get("cep")),
        "endereco": capitalizar(dados.get("logradouro")),
        "bairro": capitalizar(dados.get("bairro")),
        "municipio": capitalizar(dados.get("localidade")),
        "estado": str(dados.get("uf") or "").upper(),
    }


def mapear_brasilapi_cnpj(dados: dict) -> dict:
    """Numero, complemento e bairro vem SEPARADOS desde as Empresas (set/2026):
    o cadastro guarda cada um na sua coluna e o Tiny vai exigir assim."""
    return {
        "documento": so_digitos(dados.get("cnpj")),
        "nome": capitalizar(dados.get("razao_social")),
        "endereco": capitalizar(dados.get("logradouro")),
        "numero": str(dados.get("numero") or "").strip(),
        "complemento": capitalizar(dados.get("complemento")),
        "bairro": capitalizar(dados.get("bairro")),
        "municipio": capitalizar(dados.get("municipio")),
        "estado": str(dados.get("uf") or "").upper(),
        "cep": so_digitos(dados.get("cep")),
        "situacao": str(dados.get("descricao_situacao_cadastral") or "").upper(),
    }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_enderecos.py tests/test_enderecos_client.py -q`
Expected: PASS. Se `test_enderecos_client.py` comparar o dicionário inteiro, ajustar o esperado com as chaves novas.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/enderecos.py backend/tests/test_enderecos.py backend/tests/test_enderecos_client.py
git commit -m "feat(propostas): busca de cep e cnpj devolve numero complemento e bairro separados"
```

---
### Task 6: Salvar a proposta com destinatário (serviço, schemas e rotas existentes)

**Files:**
- Modify: `backend/app/schemas/proposta.py`, `backend/app/core/proposta_servico.py`, `backend/app/api/propostas.py`
- Test: `backend/tests/test_propostas_destinatario.py` (novo); ajustar `test_propostas.py`, `test_caixas_proposta.py`

**Interfaces:**
- Consumes: `dados_destinatario`, `destinatario_legado`, `DocumentoInvalido` (Task 1); `Empresa` (Task 2); `EmpresaIn`, `criar_empresa`, `DocumentoDuplicado`, `MatrizInexistente` (Task 3).
- Produces:
  - `DestinatarioIn` (Pydantic): `tipo: Literal["cliente","empresa","nova_empresa"]`, `id: int | None`, `matriz: int | None`, `nome: str`, `documento: str | None`, `cep`, `endereco`, `numero`, `complemento`, `bairro`, `municipio`, `estado` (`str | None`), `email: str`, `telefone: str`.
  - `PropostaCreate.destinatario: DestinatarioIn | None`; `PropostaUpdate.destinatario: DestinatarioIn | None`. **Saem** `cliente` e `cliente_override` da entrada.
  - `PropostaOut` ganha `cliente: int | None`, `empresa: int | None`, `destinatario: dict | None`; **sai** `cliente_override`.
  - Em `proposta_servico`: `class DestinatarioInvalido(ValueError)`, `class DestinatarioInativo(Exception)`, `destinatario_atual(proposta) -> dict`, `criar_proposta(db, dados, vendedor, *, vinculo: tuple[int | None, int | None] | None = None)`.
  - HTTP: `POST /propostas` e `PUT /propostas/{id}` → 422 (`DocumentoInvalido`, `DestinatarioInvalido`, `MatrizInexistente`), 409 (`DocumentoDuplicado`, `DestinatarioInativo`).

- [ ] **Step 1: Escrever os testes novos**

```python
# backend/tests/test_propostas_destinatario.py
from app.models import Cliente, Empresa, EquipamentoCliente, Proposta

CNPJ_MATRIZ = "08857492000148"
CNPJ_FILIAL = "36312056000552"


def _cliente(db, **kw):
    base = dict(nome="ACME", cgc=CNPJ_MATRIZ, obs="nao mexer", whatsapp="81911112222")
    base.update(kw)
    c = Cliente(**base); db.add(c); db.commit(); db.refresh(c)
    return c


def _aparelho(db, cliente_id):
    ec = EquipamentoCliente(cliente=cliente_id, serie="SN-1")
    db.add(ec); db.commit(); db.refresh(ec)
    return ec


def _dest(tipo, **kw):
    base = {"tipo": tipo, "nome": "ACME Atualizada", "email": "novo@acme.com", "telefone": "8130001111",
            "cep": "50000-000", "endereco": "Rua Nova", "numero": "S/N", "bairro": "Centro",
            "municipio": "Recife", "estado": "PE"}
    base.update(kw)
    return base


def test_destinatario_cliente_atualiza_so_os_campos_do_modal(client_comercial, db_session):
    cli = _cliente(db_session)
    r = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id), "itens": []})
    assert r.status_code == 201, r.text
    corpo = r.json()
    db_session.refresh(cli)
    assert cli.nome == "ACME Atualizada" and cli.email == "novo@acme.com"
    assert cli.telefones == "8130001111" and cli.cep == "50000000"
    assert cli.numero is None            # "S/N" nao cabe no BigInteger do cliente
    assert cli.obs == "nao mexer" and cli.whatsapp == "81911112222"
    assert corpo["cliente"] == cli.id and corpo["empresa"] is None
    assert corpo["destinatario"]["tipo"] == "cliente"
    assert corpo["destinatario"]["numero"] is None
    assert corpo["cliente_nome"] == "ACME Atualizada"


def test_documento_enviado_para_cliente_existente_e_ignorado(client_comercial, db_session):
    cli = _cliente(db_session)
    r = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id, documento=CNPJ_FILIAL)})
    assert r.status_code == 201
    db_session.refresh(cli)
    assert cli.cgc == CNPJ_MATRIZ


def test_destinatario_empresa_usa_a_matriz_como_cliente(client_comercial, db_session):
    cli = _cliente(db_session)
    emp = Empresa(nome="Filial", cgc=CNPJ_FILIAL, cliente=cli.id); db_session.add(emp); db_session.commit()
    ec = _aparelho(db_session, cli.id)
    r = client_comercial.post("/propostas", json={
        "destinatario": _dest("empresa", id=emp.id, nome="Filial Norte"),
        "aparelhos": [{"equipamento_cliente": ec.id}],
    })
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["empresa"] == emp.id and corpo["cliente"] == cli.id
    assert corpo["destinatario"]["matriz_nome"] == "ACME"
    assert corpo["destinatario"]["numero"] == "S/N"
    db_session.refresh(emp)
    assert emp.nome == "Filial Norte" and emp.telefone == "8130001111"


def test_nova_empresa_e_criada_na_mesma_transacao(client_comercial, db_session):
    cli = _cliente(db_session)
    r = client_comercial.post("/propostas", json={
        "destinatario": _dest("nova_empresa", documento="36.312.056/0005-52", matriz=cli.id, nome="Filial Nova"),
    })
    assert r.status_code == 201, r.text
    emp = db_session.query(Empresa).one()
    assert emp.nome == "Filial Nova" and emp.cgc == CNPJ_FILIAL and emp.cliente == cli.id
    assert r.json()["empresa"] == emp.id


def test_falha_na_proposta_desfaz_a_empresa_nova(client_comercial, db_session):
    outro = _cliente(db_session, nome="Outro", cgc="11222333000181")
    ec = _aparelho(db_session, outro.id)
    r = client_comercial.post("/propostas", json={
        "destinatario": _dest("nova_empresa", documento=CNPJ_FILIAL, matriz=None),
        "aparelhos": [{"equipamento_cliente": ec.id}],   # empresa sem matriz nao tem frota
    })
    assert r.status_code == 422
    assert db_session.query(Empresa).count() == 0
    assert db_session.query(Proposta).count() == 0


def test_falha_na_proposta_desfaz_a_edicao_do_cliente(client_comercial, db_session):
    cli = _cliente(db_session)
    outro = _cliente(db_session, nome="Outro", cgc="11222333000181")
    ec = _aparelho(db_session, outro.id)
    r = client_comercial.post("/propostas", json={
        "destinatario": _dest("cliente", id=cli.id),
        "aparelhos": [{"equipamento_cliente": ec.id}],   # aparelho de outra frota
    })
    assert r.status_code == 422
    db_session.expire_all()
    assert db_session.get(Cliente, cli.id).nome == "ACME"


def test_nova_empresa_com_documento_de_cliente_409(client_comercial, db_session):
    _cliente(db_session, cgc=CNPJ_FILIAL)
    r = client_comercial.post("/propostas", json={"destinatario": _dest("nova_empresa", documento=CNPJ_FILIAL)})
    assert r.status_code == 409
    assert r.json()["detail"].startswith("Documento já cadastrado como Cliente")


def test_nova_empresa_documento_invalido_422(client_comercial):
    r = client_comercial.post("/propostas", json={"destinatario": _dest("nova_empresa", documento="08857492000149")})
    assert r.status_code == 422


def test_destinatario_desativado_em_proposta_nova_409(client_comercial, db_session):
    cli = _cliente(db_session, ativo=False)
    r = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id)})
    assert r.status_code == 409


def test_proposta_antiga_de_destinatario_desativado_continua_salvando(client_comercial, db_session):
    cli = _cliente(db_session)
    pid = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id)}).json()["id"]
    cli.ativo = False; db_session.commit()
    r = client_comercial.put(f"/propostas/{pid}", json={"destinatario": _dest("cliente", id=cli.id), "desconto": 5})
    assert r.status_code == 200, r.text


def test_destinatario_do_payload_nao_e_gravado_como_copia(client_comercial, db_session):
    cli = _cliente(db_session)
    r = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id)})
    p = db_session.get(Proposta, r.json()["id"])
    # a copia tem as chaves do cadastro (vindas de dados_destinatario), nao o bloco de entrada
    assert "matriz" not in p.destinatario and p.destinatario["documento"] == CNPJ_MATRIZ


def test_put_sem_destinatario_refaz_a_copia_com_o_cadastro_atual(client_comercial, db_session):
    cli = _cliente(db_session)
    pid = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id)}).json()["id"]
    cli.municipio = "Olinda"; db_session.commit()
    r = client_comercial.put(f"/propostas/{pid}", json={"desconto": 10})
    assert r.status_code == 200
    assert r.json()["destinatario"]["municipio"] == "Olinda"


def test_trocar_para_empresa_sem_matriz_com_aparelhos_antigos_422(client_comercial, db_session):
    cli = _cliente(db_session)
    ec = _aparelho(db_session, cli.id)
    pid = client_comercial.post("/propostas", json={
        "destinatario": _dest("cliente", id=cli.id), "aparelhos": [{"equipamento_cliente": ec.id}],
    }).json()["id"]
    emp = Empresa(nome="Solta", cgc=CNPJ_FILIAL); db_session.add(emp); db_session.commit()
    r = client_comercial.put(f"/propostas/{pid}", json={"destinatario": _dest("empresa", id=emp.id)})
    assert r.status_code == 422


def test_proposta_sem_destinatario_continua_permitida(client_comercial):
    r = client_comercial.post("/propostas", json={"itens": []})
    assert r.status_code == 201
    assert r.json()["cliente"] is None and r.json()["destinatario"] is None


def test_montar_saida_cai_no_legado_quando_nao_ha_copia(db_session):
    from app.core import proposta_servico as ps
    cli = _cliente(db_session)
    p = Proposta(numero=50, cliente=cli.id, cliente_override={"nome": "ACME Filial", "documento": "99988877000166"})
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    saida = ps.montar_saida(db_session, p)
    assert saida.cliente_nome == "ACME Filial"
    assert saida.cliente_documento == "99988877000166"


def test_listar_encontra_pelo_nome_e_documento_da_empresa(client_comercial, db_session):
    emp = Empresa(nome="Filial Busca", cgc=CNPJ_FILIAL); db_session.add(emp); db_session.commit()
    client_comercial.post("/propostas", json={"destinatario": _dest("empresa", id=emp.id, nome="Filial Busca")})
    assert client_comercial.get("/propostas", params={"q": "Filial Busca"}).json()["total"] == 1
    assert client_comercial.get("/propostas", params={"q": "36.312.056/0005-52"}).json()["total"] == 1


def test_duplicar_copia_o_vinculo_com_a_empresa(client_comercial, db_session):
    cli = _cliente(db_session)
    emp = Empresa(nome="Filial", cgc=CNPJ_FILIAL, cliente=cli.id); db_session.add(emp); db_session.commit()
    ec = _aparelho(db_session, cli.id)
    pid = client_comercial.post("/propostas", json={
        "destinatario": _dest("empresa", id=emp.id), "aparelhos": [{"equipamento_cliente": ec.id}],
    }).json()["id"]
    r = client_comercial.post(f"/propostas/{pid}/duplicar")
    assert r.status_code == 201, r.text
    nova = r.json()
    assert nova["empresa"] == emp.id and nova["cliente"] == cli.id
    assert nova["destinatario"]["tipo"] == "empresa"
    assert len(nova["aparelhos"]) == 1
```

> Se `EquipamentoCliente` exigir outras colunas NOT NULL no model, preencher no helper `_aparelho` com o mínimo que o model pede (conferir `app/models/equipamento_cliente.py`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_propostas_destinatario.py -q`
Expected: FAIL (campos `destinatario`/`empresa` inexistentes na saída; 201 onde se espera 422/409).

- [ ] **Step 3: Schemas**

Em `backend/app/schemas/proposta.py`:

1. Imports: `import re`, `from typing import Literal, Optional, List`, `from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator`.
2. Antes de `class PropostaBase`, acrescentar:

```python
class DestinatarioIn(BaseModel):
    """Dados do destinatario como estao no modal. O servidor grava no cadastro
    (Cliente/Empresa) e monta a copia congelada a partir do cadastro salvo —
    este bloco NUNCA vai direto para `propostas.destinatario`."""
    model_config = ConfigDict(str_strip_whitespace=True)

    tipo: Literal["cliente", "empresa", "nova_empresa"]
    id: Optional[int] = None
    matriz: Optional[int] = None
    nome: str = Field(min_length=1, max_length=100)
    documento: Optional[str] = None
    cep: Optional[str] = Field(default=None, max_length=9)
    endereco: Optional[str] = Field(default=None, max_length=100)
    numero: Optional[str] = Field(default=None, max_length=20)
    complemento: Optional[str] = Field(default=None, max_length=60)
    bairro: Optional[str] = Field(default=None, max_length=100)
    municipio: Optional[str] = Field(default=None, max_length=100)
    estado: Optional[str] = Field(default=None, max_length=2)
    email: str = Field(min_length=1, max_length=100)
    telefone: str = Field(min_length=1, max_length=50)

    @field_validator("cep", "endereco", "numero", "complemento", "bairro", "municipio", "estado", mode="after")
    @classmethod
    def _vazio_vira_none(cls, v: Optional[str], info) -> Optional[str]:
        if not v:
            return None
        if info.field_name == "cep":
            return re.sub(r"\D", "", v)[:8] or None
        if info.field_name == "estado":
            return v.upper()
        return v

    @model_validator(mode="after")
    def _coerente(self):
        if self.tipo == "nova_empresa":
            if not self.documento:
                raise ValueError("documento obrigatorio para cadastrar empresa")
        elif self.id is None:
            raise ValueError("id obrigatorio para cliente ou empresa existente")
        return self
```

3. Em `PropostaBase`: **remover** `cliente` e `cliente_override`.
4. Em `PropostaCreate`: acrescentar `destinatario: Optional[DestinatarioIn] = None`.
5. Em `PropostaUpdate`: **remover** `cliente` e `cliente_override`; acrescentar `destinatario: Optional[DestinatarioIn] = None`.
6. Em `PropostaOut`: acrescentar

```python
    cliente: Optional[int] = None
    empresa: Optional[int] = None
    destinatario: Optional[dict] = None
```

- [ ] **Step 4: Serviço**

Em `backend/app/core/proposta_servico.py`:

Imports (acrescentar):

```python
from app.core.empresa import dados_destinatario, destinatario_legado
from app.core.empresa_servico import CAMPOS_EMPRESA, criar_empresa
from app.models import Cliente, Empresa, EquipamentoCliente
from app.schemas.empresa import EmpresaIn
from app.schemas.proposta import DestinatarioIn
```

(e remover o `from app.models import EquipamentoCliente` local de `_aplicar_aparelhos`, que passa a usar o import do topo).

Novas exceções e helpers, logo abaixo de `NON_NULLABLE`:

```python
class DestinatarioInvalido(ValueError):
    """Destinatario inexistente ou aparelhos incompativeis com ele (422)."""


class DestinatarioInativo(Exception):
    """Cliente/Empresa desativado escolhido para proposta nova ou troca (409)."""


# Campos do Cliente que o modal da proposta gerencia. O resto do cadastro
# (obs, whatsapp, inscricoes, contato, grupo...) NUNCA e' tocado por aqui.
_CAMPOS_CLIENTE_TEXTO = ("nome", "cep", "endereco", "complemento", "bairro", "municipio", "estado", "email")


def _numero_do_cliente(valor: Optional[str]) -> Optional[int]:
    """`clientes.numero` e' BigInteger: "S/N" e afins viram nulo no cadastro
    (a copia da proposta guarda o texto que o cadastro aceitou)."""
    texto = (valor or "").strip()
    return int(texto) if texto.isdigit() else None


def _aplicar_destinatario(db: Session, proposta: Proposta, dest: DestinatarioIn) -> None:
    """Grava os dados no cadastro de origem e acerta `cliente`/`empresa` da proposta."""
    if dest.tipo == "cliente":
        cliente = db.get(Cliente, dest.id)
        if cliente is None:
            raise DestinatarioInvalido("cliente nao encontrado")
        trocou = proposta.id is None or proposta.empresa is not None or proposta.cliente != cliente.id
        if trocou and not cliente.ativo:
            raise DestinatarioInativo("cliente desativado")
        for campo in _CAMPOS_CLIENTE_TEXTO:
            setattr(cliente, campo, getattr(dest, campo))
        cliente.numero = _numero_do_cliente(dest.numero)
        cliente.telefones = dest.telefone
        proposta.cliente, proposta.empresa = cliente.id, None
        return

    if dest.tipo == "empresa":
        empresa = db.get(Empresa, dest.id)
        if empresa is None:
            raise DestinatarioInvalido("empresa nao encontrada")
        trocou = proposta.id is None or proposta.empresa != empresa.id
        if trocou and not empresa.ativo:
            raise DestinatarioInativo("empresa desativada")
        for campo in CAMPOS_EMPRESA:
            if campo != "insc_est":          # o modal nao mostra a IE
                setattr(empresa, campo, getattr(dest, campo))
    else:  # nova_empresa
        empresa = criar_empresa(db, EmpresaIn(
            documento=dest.documento, cliente=dest.matriz, nome=dest.nome, cep=dest.cep,
            endereco=dest.endereco, numero=dest.numero, complemento=dest.complemento,
            bairro=dest.bairro, municipio=dest.municipio, estado=dest.estado,
            email=dest.email, telefone=dest.telefone,
        ))
    proposta.empresa, proposta.cliente = empresa.id, empresa.cliente


def _validar_aparelhos(db: Session, cliente_id: Optional[int], ids: list[int]) -> None:
    if not ids:
        return
    if cliente_id is None:
        raise DestinatarioInvalido("proposta sem cliente matriz nao pode ter aparelhos")
    donos = dict(
        db.query(EquipamentoCliente.id, EquipamentoCliente.cliente)
        .filter(EquipamentoCliente.id.in_(ids)).all()
    )
    fora = [i for i in ids if donos.get(i) != cliente_id]
    if fora:
        raise DestinatarioInvalido(f"aparelhos fora da frota do cliente: {fora}")


def _congelar_destinatario(db: Session, proposta: Proposta) -> None:
    """Copia a partir do cadastro JA gravado. Sem cliente nem empresa, mantem o
    que houver (proposta antiga sem vinculo)."""
    db.flush()
    if proposta.empresa is not None:
        empresa = db.get(Empresa, proposta.empresa)
        matriz = db.get(Cliente, empresa.cliente) if empresa.cliente is not None else None
        proposta.destinatario = dados_destinatario(empresa, tipo="empresa", matriz=matriz)
    elif proposta.cliente is not None:
        proposta.destinatario = dados_destinatario(db.get(Cliente, proposta.cliente), tipo="cliente")


def destinatario_atual(proposta: Proposta) -> dict:
    """Copia congelada; proposta anterior as Empresas e ainda nao congelada pelo
    script cai no que o PDF sempre mostrou (cadastro + cliente_override)."""
    return proposta.destinatario or destinatario_legado(proposta.cliente_rel, proposta.cliente_override)
```

Substituir `criar_proposta` inteiro:

```python
def criar_proposta(db: Session, dados: PropostaCreate, vendedor: str, *,
                   vinculo: Optional[tuple[Optional[int], Optional[int]]] = None) -> Proposta:
    """Cria a proposta com número sequencial. Vendedor = quem criou (imutável).

    `dados.destinatario` grava no cadastro e acerta as FKs, tudo na MESMA
    transacao da proposta. `vinculo=(cliente, empresa)` e' o caminho do duplicar:
    repete as FKs da original sem mexer em cadastro.

    Retry anti-corrida: dois requests podem calcular o mesmo `proximo_numero`;
    `numero` e' UNIQUE, entao o segundo commit estoura IntegrityError e tenta de
    novo (até 5x). Cada tentativa refaz tudo, inclusive a Empresa nova, que o
    rollback levou junto.
    """
    payload = dados.model_dump(exclude={"itens", "aparelhos", "vendedor", "destinatario"})
    ultimo_exc: Optional[IntegrityError] = None
    for _ in range(5):
        proposta = Proposta(numero=proximo_numero(db), vendedor=vendedor, **payload)
        if dados.destinatario is not None:
            _aplicar_destinatario(db, proposta, dados.destinatario)
        elif vinculo is not None:
            proposta.cliente, proposta.empresa = vinculo
        _validar_aparelhos(db, proposta.cliente, [a.equipamento_cliente for a in dados.aparelhos or []])
        _aplicar_itens(proposta, dados.itens or [])
        _aplicar_aparelhos(db, proposta, dados.aparelhos or [])
        try:
            # add + flush DENTRO do try: o `numero` repetido estoura ja no flush.
            db.add(proposta)
            _congelar_destinatario(db, proposta)
            db.commit()
            db.refresh(proposta)
            return proposta
        except IntegrityError as exc:
            ultimo_exc = exc
            db.rollback()
    raise ultimo_exc  # esgotou as tentativas
```

Substituir `atualizar_proposta` inteiro:

```python
def atualizar_proposta(db: Session, proposta: Proposta, dados: PropostaUpdate,
                        alterado_por: str) -> Proposta:
    """Versiona o estado ANTERIOR (snapshot + PDF arquivado) e aplica as mudanças.

    A versão só é gravada no MESMO commit da alteração: se o destinatário for
    recusado (422/409), nada fica — nem versão órfã. Gerar o PDF da versão
    continua best-effort: falha aí não impede a atualização.
    """
    versao: Optional[PropostaVersao] = None
    try:
        numero_versao = len(proposta.versoes) + 1
        versao = PropostaVersao(
            proposta=proposta.id,
            numero_versao=numero_versao,
            snapshot=snapshot_proposta(proposta),
            pdf_path=proposta_pdf.arquivar_pdf_versao(db, proposta, numero_versao),
            alterado_por=alterado_por,
        )
    except Exception as e:  # noqa: BLE001 - versionamento nunca deve travar o update
        print(f"[PROPOSTA-VERSAO] erro ao arquivar versao da proposta {proposta.id}: {e}")

    # vendedor e imutavel: sempre o do criador, nunca sobrescrito por update.
    payload = dados.model_dump(exclude_unset=True, exclude={"itens", "aparelhos", "vendedor", "destinatario"})
    for k, v in payload.items():
        if v is None and k in NON_NULLABLE:
            continue
        setattr(proposta, k, v)
    if dados.destinatario is not None:
        _aplicar_destinatario(db, proposta, dados.destinatario)
    if dados.aparelhos is not None:
        _validar_aparelhos(db, proposta.cliente, [a.equipamento_cliente for a in dados.aparelhos])
    elif dados.destinatario is not None:
        _validar_aparelhos(db, proposta.cliente,
                           [a.equipamento_cliente for a in proposta.aparelhos if a.equipamento_cliente])
    if dados.itens is not None:
        _aplicar_itens(proposta, dados.itens)
    if dados.aparelhos is not None:
        _aplicar_aparelhos(db, proposta, dados.aparelhos)
    if versao is not None:
        db.add(versao)
    _congelar_destinatario(db, proposta)
    db.commit()
    db.refresh(proposta)
    return proposta
```

Em `montar_saida`, trocar o bloco `ov = ...` até o fim por:

```python
    dest = destinatario_atual(proposta)
    saida.destinatario = dest
    saida.cliente_nome = dest.get("nome")
    saida.cliente_documento = dest.get("documento")
    return saida
```

Em `snapshot_proposta`, trocar as linhas de `cliente = proposta.cliente_rel` e das chaves `cliente_nome`/`cliente_documento` por:

```python
    dest = destinatario_atual(proposta)
    return {
        "numero": proposta.numero,
        "data": proposta.data.isoformat() if proposta.data else None,
        "cliente_nome": dest.get("nome"),
        "cliente_documento": dest.get("documento"),
        "empresa": proposta.empresa,
        "destinatario": dest,
```

(mantendo o restante do dicionário igual).

- [ ] **Step 5: Rotas**

Em `backend/app/api/propostas.py`:

Imports: `from contextlib import contextmanager`; `from pydantic import ValidationError`; acrescentar `Empresa` ao `from app.models import ...`; `from app.core.empresa import DocumentoInvalido`; `from app.core.empresa_servico import DocumentoDuplicado, MatrizInexistente`.

Helper abaixo de `_content_disposition`:

```python
@contextmanager
def _erros_de_destinatario(db: Session):
    """Traduz as recusas do destinatario em HTTP, desfazendo o que o servico ja
    tinha escrito na sessao (cadastro editado, empresa nova)."""
    try:
        yield
    except (DocumentoInvalido, MatrizInexistente, ps.DestinatarioInvalido) as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except ValidationError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=e.errors()[0]["msg"])
    except (DocumentoDuplicado, ps.DestinatarioInativo) as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
```

`criar`:

```python
    with _erros_de_destinatario(db):
        proposta = ps.criar_proposta(db, dados, vendedor=usuario.nome)
    return ps.montar_saida(db, proposta)
```

`atualizar`:

```python
    proposta = _para_escrita(db, proposta_id)
    with _erros_de_destinatario(db):
        atualizado = ps.atualizar_proposta(db, proposta, dados, alterado_por=usuario.nome)
    return ps.montar_saida(db, atualizado)
```

`duplicar`: no `PropostaCreate(...)`, **remover** as linhas `cliente=original.cliente,` e `cliente_override=original.cliente_override,`; e trocar a chamada por:

```python
    with _erros_de_destinatario(db):
        nova = ps.criar_proposta(db, dados, vendedor=usuario.nome, vinculo=(original.cliente, original.empresa))
    return ps.montar_saida(db, nova)
```

`listar`: trocar o bloco `if q:` por:

```python
    if q:
        qs = q.strip()
        termo = f"%{qs}%"
        filtros = [Cliente.nome.ilike(termo), Empresa.nome.ilike(termo)]
        digitos = re.sub(r"\D", "", qs)
        if digitos and (not qs.isdigit() or len(digitos) >= 11):
            termo_doc = f"%{digitos}%"
            filtros += [Cliente.cgc.ilike(termo_doc), Cliente.cpf.ilike(termo_doc),
                        Empresa.cgc.ilike(termo_doc), Empresa.cpf.ilike(termo_doc)]
        if qs.isdigit():
            filtros.append(Proposta.numero == int(qs))
        query = (
            query.outerjoin(Cliente, Proposta.cliente == Cliente.id)
            .outerjoin(Empresa, Proposta.empresa == Empresa.id)
            .filter(or_(*filtros))
        )
```

- [ ] **Step 6: Ajustar os testes existentes**

- `tests/test_propostas.py`
  - `test_schema_proposta_create_valida`: trocar `cliente=1` por nada (`PropostaCreate(itens=..., aparelhos=...)`), remover `assert payload.cliente == 1`, e trocar `PropostaCreate(cliente=1)` por `PropostaCreate()`.
  - `test_schema_proposta_update_todos_campos_opcionais`: trocar `assert vazio.cliente is None` por `assert vazio.destinatario is None`.
  - Nos `POST` com `"cliente": cli.id` (criar_e_listar, busca_por_documento_formatado, duplicar e o de dois clientes ~l.322): trocar por
    `"destinatario": {"tipo": "cliente", "id": cli.id, "nome": cli.nome, "email": "a@a.com", "telefone": "81999990000"}` — usar o `nome` do próprio cliente para os asserts de `cliente_nome` continuarem valendo.
  - `test_montar_saida_respeita_cliente_override`: continua valendo (fallback legado); se ele cria a proposta com `cliente_override` via model, não precisa mudar.
- `tests/test_caixas_proposta.py::_proposta`: mesma troca de `"cliente": cli.id` pelo bloco `destinatario` com `"nome": "CONCREFER"`.
- Qualquer outro teste que falhe por `cliente_override` na **saída** da API: tirar a asserção (o campo saiu do `PropostaOut`).

- [ ] **Step 7: Rodar e ver passar**

Run: `pytest tests/test_propostas_destinatario.py tests/test_propostas.py tests/test_caixas_proposta.py tests/test_propostas_desabilitar.py tests/test_propostas_faturar.py tests/test_permissao_financeiro_catalogo.py tests/test_publico_proposta.py tests/test_taskhs_proposta_link.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/proposta.py backend/app/core/proposta_servico.py backend/app/api/propostas.py \
  backend/tests/test_propostas_destinatario.py backend/tests/test_propostas.py backend/tests/test_caixas_proposta.py
git commit -m "feat(propostas): destinatario cliente ou empresa gravado no cadastro com copia congelada"
```

---
### Task 7: Busca de destinatário `GET /propostas/destinatarios`

**Files:**
- Modify: `backend/app/schemas/proposta.py`, `backend/app/api/propostas.py`
- Test: `backend/tests/test_propostas_destinatario.py` (acrescentar)

**Interfaces:**
- Produces: `DestinatarioBuscaOut` = `{tipo: "cliente"|"empresa", id, nome, documento, municipio, estado, matriz_id, matriz_nome}`. `GET /propostas/destinatarios?q=` (qualquer interno, `q` com ao menos 2 caracteres) → lista com até 20 Clientes ativos seguidos de até 20 Empresas ativas, cada grupo ordenado por nome.

- [ ] **Step 1: Escrever os testes**

```python
def test_busca_de_destinatario_mistura_clientes_e_empresas_ativos(client_lab, db_session):
    cli = _cliente(db_session, nome="Rumo Matriz")
    _cliente(db_session, nome="Rumo Inativo", cgc="11222333000181", ativo=False)
    db_session.add(Empresa(nome="Rumo Filial PR", cgc=CNPJ_FILIAL, cliente=cli.id, municipio="Curitiba", estado="PR"))
    db_session.commit()
    r = client_lab.get("/propostas/destinatarios", params={"q": "rumo"})
    assert r.status_code == 200
    itens = r.json()
    assert [(i["tipo"], i["nome"]) for i in itens] == [("cliente", "Rumo Matriz"), ("empresa", "Rumo Filial PR")]
    assert itens[1]["matriz_id"] == cli.id and itens[1]["matriz_nome"] == "Rumo Matriz"


def test_busca_de_destinatario_por_documento_com_mascara(client_lab, db_session):
    db_session.add(Empresa(nome="Filial", cgc=CNPJ_FILIAL)); db_session.commit()
    itens = client_lab.get("/propostas/destinatarios", params={"q": "36.312.056/0005-52"}).json()
    assert len(itens) == 1 and itens[0]["documento"] == CNPJ_FILIAL


def test_busca_de_destinatario_sem_resultado(client_lab):
    assert client_lab.get("/propostas/destinatarios", params={"q": "36312056000552"}).json() == []


def test_busca_de_destinatario_exige_termo(client_lab):
    assert client_lab.get("/propostas/destinatarios", params={"q": "a"}).status_code == 422
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_propostas_destinatario.py -q -k busca_de_destinatario`
Expected: FAIL (422 de path param, ou 404).

- [ ] **Step 3: Schema**

No fim de `backend/app/schemas/proposta.py`:

```python
class DestinatarioBuscaOut(BaseModel):
    tipo: Literal["cliente", "empresa"]
    id: int
    nome: Optional[str] = None
    documento: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    matriz_id: Optional[int] = None
    matriz_nome: Optional[str] = None
```

- [ ] **Step 4: Rota**

Em `backend/app/api/propostas.py`, importar `DestinatarioBuscaOut` e declarar **logo depois de `listar` e antes de `criar`** (precisa vir antes de qualquer `/{proposta_id}`):

```python
_LIMITE_BUSCA = 20


@router.get("/destinatarios", response_model=list[DestinatarioBuscaOut])
def buscar_destinatarios(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    """Busca unica do modal: Clientes e Empresas ATIVOS por nome ou documento.
    Lista vazia para um documento completo e' o que faz o modal oferecer
    "Cadastrar empresa"."""
    termo = f"%{q.strip()}%"
    digitos = re.sub(r"\D", "", q)

    def filtro(model):
        filtros = [model.nome.ilike(termo)]
        if digitos:
            filtros += [model.cgc.ilike(f"%{digitos}%"), model.cpf.ilike(f"%{digitos}%")]
        return or_(*filtros)

    clientes = (db.query(Cliente).filter(Cliente.ativo.is_(True), filtro(Cliente))
                .order_by(Cliente.nome).limit(_LIMITE_BUSCA).all())
    empresas = (db.query(Empresa).filter(Empresa.ativo.is_(True), filtro(Empresa))
                .order_by(Empresa.nome).limit(_LIMITE_BUSCA).all())
    return [
        *(DestinatarioBuscaOut(tipo="cliente", id=c.id, nome=c.nome, documento=c.cgc or c.cpf,
                               municipio=c.municipio, estado=c.estado) for c in clientes),
        *(DestinatarioBuscaOut(tipo="empresa", id=e.id, nome=e.nome, documento=e.cgc or e.cpf,
                               municipio=e.municipio, estado=e.estado, matriz_id=e.cliente,
                               matriz_nome=e.matriz_rel.nome if e.matriz_rel else None) for e in empresas),
    ]
```

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_propostas_destinatario.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/proposta.py backend/app/api/propostas.py backend/tests/test_propostas_destinatario.py
git commit -m "feat(propostas): busca unica de destinatario em clientes e empresas"
```

---

### Task 8: PDF lê a cópia congelada

**Files:**
- Modify: `backend/app/core/proposta_pdf.py` (`montar_html`, bloco "Dados do cliente" até o override, ~l.360-418)
- Test: `backend/tests/test_proposta_pdf.py` (acrescentar)

**Interfaces:**
- Consumes: `destinatario_legado`, `linha_endereco` (Task 1). Assinatura de `montar_html(proposta, cliente)` **não muda**.

- [ ] **Step 1: Escrever os testes**

```python
def test_montar_html_usa_a_copia_congelada_e_ignora_o_cadastro_atual():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="NOME NOVO DO CADASTRO", cgc="08857492000148", municipio="Olinda", estado="PE")
    p = Proposta(id=3, numero=101, contato="Maria", destinatario={
        "tipo": "empresa", "id": 9, "nome": "Filial Congelada", "documento": "36312056000552",
        "cep": "29680000", "endereco": "BR 101", "numero": "S/N", "complemento": "KM 196",
        "bairro": "Zona Rural", "municipio": "Joao Neiva", "estado": "ES",
        "email": "f@acme.com", "telefone": "2733330000", "matriz_id": 5, "matriz_nome": "ACME",
    })
    html = proposta_pdf.montar_html(p, cli)
    assert "Filial Congelada" in html
    assert "NOME NOVO DO CADASTRO" not in html
    assert "36.312.056/0005-52" in html
    assert "BR 101, S/N KM 196 - Zona Rural" in html
    assert "Joao Neiva - ES" in html
    assert "2733330000" in html and "f@acme.com" in html


def test_montar_html_contato_legado_do_override_continua_valendo():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta
    cli = Cliente(nome="ACME", cgc="08857492000148")
    p = Proposta(id=4, numero=102, contato="", cliente_override={"contato": "Tatiane"})
    assert "Tatiane" in proposta_pdf.montar_html(p, cli)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_proposta_pdf.py -q -k "copia_congelada or contato_legado"`
Expected: FAIL no primeiro (nome do cadastro aparece).

- [ ] **Step 3: Implementar**

Import no topo de `proposta_pdf.py`: `from app.core.empresa import destinatario_legado, linha_endereco`.

Substituir, em `montar_html`, todo o trecho que começa em `# ── Dados do cliente ──` e termina logo **antes** de `if municipio and estado:` por:

```python
    # ── Dados do destinatario ──
    # A proposta guarda a copia congelada do destinatario (Cliente ou Empresa)
    # de quando foi salva: o PDF nao muda quando o cadastro muda. Proposta
    # anterior as Empresas, ainda nao congelada, cai no cadastro + override —
    # exatamente o que este PDF mostrava antes.
    dest = proposta.destinatario or destinatario_legado(cliente, proposta.cliente_override)
    cliente_display = _esc(dest.get("nome") or "—")
    cliente_documento = _fmt_documento(dest.get("documento"))
    cliente_endereco = _esc(linha_endereco(dest))
    municipio = dest.get("municipio") or ""
    estado = dest.get("estado") or ""
    cliente_email = _esc(dest.get("email") or "")
    cliente_telefone = _esc(dest.get("telefone") or "")
    cliente_cep = _fmt_cep(dest.get("cep"))
    cliente_cidade_estado = ""

    # "Aos cuidados de" e' coluna da proposta. Proposta antiga que gravou o
    # contato dentro do cliente_override (congelado) continua saindo com ele.
    aos_cuidados = (proposta.cliente_override or {}).get("contato") or proposta.contato or ""
```

- [ ] **Step 4: Rodar a suíte do PDF**

Run: `pytest tests/test_proposta_pdf.py tests/test_publico_proposta.py -q`
Expected: PASS — inclusive os testes antigos de override, que passam pelo fallback.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/proposta_pdf.py backend/tests/test_proposta_pdf.py
git commit -m "feat(propostas): pdf usa a copia congelada do destinatario"
```

---

### Task 9: Script `migrar_filiais_propostas`

**Files:**
- Create: `backend/app/scripts/migrar_filiais_propostas.py`
- Test: `backend/tests/test_migrar_filiais_propostas.py`

**Interfaces:**
- Consumes: `destinatario_legado`, `normalizar_documento`, `so_digitos`, `DocumentoInvalido` (Task 1); `Empresa` (Task 2).
- Produces: `planejar(db) -> Plano`; `aplicar(db, plano) -> dict[str, int]` (commita); `main(argv=None)`. `Plano` com `congelar: list[int]`, `criar: dict[str, int]` (documento → id da proposta-fonte), `reaproveitar: dict[str, int]` (documento → id da Empresa), `recusados: dict[str, tuple[int, str]]` (documento → id e nome do Cliente dono), `invalidos: dict[int, str]` (id da proposta → motivo), `ligar: dict[int, str]` (id da proposta → documento).

- [ ] **Step 1: Escrever os testes**

```python
# backend/tests/test_migrar_filiais_propostas.py
from app.models import Cliente, Empresa, Proposta
from app.scripts import migrar_filiais_propostas as mig

MATRIZ = "08857492000148"
FILIAL = "36312056000552"


def _base(db):
    cli = Cliente(nome="ACME", cgc=MATRIZ, endereco="Rua Matriz", municipio="Recife", estado="PE")
    db.add(cli); db.flush()
    ov_filial = {"nome": "ACME Filial", "documento": "36.312.056/0005-52", "endereco": "BR 101",
                 "municipio": "Joao Neiva", "estado": "es", "cep": "29680-000",
                 "email": "f@acme.com", "telefone": "2733330000"}
    p1 = Proposta(numero=1, cliente=cli.id, cliente_override=ov_filial)
    p2 = Proposta(numero=2, cliente=cli.id, cliente_override=dict(ov_filial, telefone="2799990000"))
    p3 = Proposta(numero=3, cliente=cli.id, cliente_override={"nome": "ACME com outro nome"})
    p4 = Proposta(numero=4)
    db.add_all([p1, p2, p3, p4]); db.commit()
    return cli, p1, p2, p3, p4


def test_planejar_nao_grava_nada(db_session):
    _, p1, p2, p3, p4 = _base(db_session)
    plano = mig.planejar(db_session)
    assert sorted(plano.congelar) == sorted([p1.id, p2.id, p3.id, p4.id])
    assert plano.criar == {FILIAL: p1.id}
    assert plano.ligar == {p1.id: FILIAL, p2.id: FILIAL}
    assert db_session.query(Empresa).count() == 0
    assert db_session.get(Proposta, p1.id).destinatario is None


def test_aplicar_cria_uma_empresa_e_liga_as_duas_propostas(db_session):
    cli, p1, p2, p3, p4 = _base(db_session)
    resumo = mig.aplicar(db_session, mig.planejar(db_session))
    emp = db_session.query(Empresa).one()
    assert (emp.nome, emp.cgc, emp.cliente) == ("ACME Filial", FILIAL, cli.id)
    assert (emp.estado, emp.cep) == ("ES", "29680000")
    assert emp.endereco == "BR 101" and emp.bairro is None      # nada herdado da matriz
    db_session.expire_all()
    for p in (db_session.get(Proposta, p1.id), db_session.get(Proposta, p2.id)):
        assert p.empresa == emp.id
        assert p.destinatario["tipo"] == "empresa" and p.destinatario["matriz_nome"] == "ACME"
    # a copia preserva o que o override de cada proposta dizia
    assert db_session.get(Proposta, p2.id).destinatario["telefone"] == "2799990000"
    p3 = db_session.get(Proposta, p3.id)
    assert p3.empresa is None and p3.destinatario["nome"] == "ACME com outro nome"
    assert db_session.get(Proposta, p4.id).destinatario["nome"] is None
    assert resumo["empresas_criadas"] == 1 and resumo["propostas_ligadas"] == 2


def test_documento_de_cliente_e_recusado(db_session):
    cli, p1, *_ = _base(db_session)
    dono = Cliente(nome="Ja E Cliente", cgc=FILIAL); db_session.add(dono); db_session.commit()
    plano = mig.planejar(db_session)
    assert plano.recusados == {FILIAL: (dono.id, "Ja E Cliente")}
    assert plano.ligar == {}
    mig.aplicar(db_session, plano)
    assert db_session.query(Empresa).count() == 0
    assert db_session.get(Proposta, p1.id).destinatario["tipo"] == "cliente"


def test_empresa_existente_e_reaproveitada(db_session):
    cli, p1, p2, *_ = _base(db_session)
    emp = Empresa(nome="Ja Cadastrada", cgc=FILIAL); db_session.add(emp); db_session.commit()
    plano = mig.planejar(db_session)
    assert plano.reaproveitar == {FILIAL: emp.id} and plano.criar == {}
    mig.aplicar(db_session, plano)
    assert db_session.query(Empresa).count() == 1
    assert db_session.get(Proposta, p1.id).empresa == emp.id


def test_documento_invalido_ou_sem_nome_fica_so_congelado(db_session):
    cli = Cliente(nome="ACME", cgc=MATRIZ); db_session.add(cli); db_session.flush()
    ruim = Proposta(numero=9, cliente=cli.id, cliente_override={"nome": "X", "documento": "36312056000559"})
    sem_nome = Proposta(numero=10, cliente=cli.id, cliente_override={"documento": FILIAL})
    db_session.add_all([ruim, sem_nome]); db_session.commit()
    plano = mig.planejar(db_session)
    assert set(plano.invalidos) == {ruim.id, sem_nome.id}
    assert plano.criar == {}


def test_segunda_execucao_nao_faz_nada(db_session):
    _base(db_session)
    mig.aplicar(db_session, mig.planejar(db_session))
    plano = mig.planejar(db_session)
    assert plano.congelar == [] and plano.criar == {} and plano.ligar == {}
    assert db_session.query(Empresa).count() == 1


def test_main_sem_aplicar_so_simula(db_session, monkeypatch, capsys):
    _base(db_session)
    monkeypatch.setattr(mig, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    mig.main([])
    assert "SIMULACAO" in capsys.readouterr().out
    assert db_session.query(Empresa).count() == 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_migrar_filiais_propostas.py -q`
Expected: FAIL com `ImportError`.

- [ ] **Step 3: Implementar**

```python
# backend/app/scripts/migrar_filiais_propostas.py
"""Leva as propostas antigas para o modelo de Empresas (set/2026).

Duas coisas, na mesma rodada:

1. CONGELA a copia do destinatario (`propostas.destinatario`) de toda proposta
   que ainda nao tem, com o que o PDF sempre mostrou: cadastro do cliente com o
   `cliente_override` por cima (`destinatario_legado`).
2. CRIA as filiais escondidas nos overrides: proposta cujo override traz um
   documento diferente do cliente vira destinatario Empresa, com matriz = o
   cliente da proposta. O mesmo documento em varias propostas gera UMA Empresa.

    python -m app.scripts.migrar_filiais_propostas            # so simula
    python -m app.scripts.migrar_filiais_propostas --aplicar  # grava

A Empresa nasce SO com o que o override trazia — nada vem do cadastro da
matriz, para nao botar endereco da matriz na filial.

RECUSA (lista no resumo e deixa a proposta so congelada) quando o documento ja
e' de um Cliente — decidir a mao —, quando o documento e' invalido e quando o
override nao tem nome (`empresas.nome` e' NOT NULL).

Idempotente: proposta congelada nao e' congelada de novo, proposta ligada nao
e' ligada de novo, e o documento que ja virou Empresa e' reaproveitado.
"""
import argparse
from dataclasses import dataclass, field

from app.core.empresa import DocumentoInvalido, destinatario_legado, normalizar_documento, so_digitos
from app.models import Cliente, Empresa, Proposta
from app.models.database import SessionLocal


@dataclass
class Plano:
    congelar: list[int] = field(default_factory=list)
    criar: dict[str, int] = field(default_factory=dict)
    reaproveitar: dict[str, int] = field(default_factory=dict)
    recusados: dict[str, tuple[int, str]] = field(default_factory=dict)
    invalidos: dict[int, str] = field(default_factory=dict)
    ligar: dict[int, str] = field(default_factory=dict)


def _documento_do_override(p: Proposta) -> str:
    return so_digitos((p.cliente_override or {}).get("documento"))


def _eh_filial(p: Proposta) -> bool:
    doc = _documento_do_override(p)
    if not doc or p.empresa is not None:
        return False
    cli = p.cliente_rel
    return cli is None or doc != (cli.cgc or cli.cpf or "")


def planejar(db) -> Plano:
    plano = Plano()
    propostas = db.query(Proposta).order_by(Proposta.id).all()
    plano.congelar = [p.id for p in propostas if p.destinatario is None]

    for p in propostas:
        if not _eh_filial(p):
            continue
        doc = _documento_do_override(p)
        try:
            normalizar_documento(doc)
        except DocumentoInvalido as e:
            plano.invalidos[p.id] = f"documento {doc}: {e}"
            continue
        if not str((p.cliente_override or {}).get("nome") or "").strip():
            plano.invalidos[p.id] = f"documento {doc}: override sem nome"
            continue
        if doc in plano.recusados:
            continue
        dono = db.query(Cliente).filter((Cliente.cgc == doc) | (Cliente.cpf == doc)).first()
        if dono is not None:
            plano.recusados[doc] = (dono.id, dono.nome)
            continue
        existente = db.query(Empresa).filter((Empresa.cgc == doc) | (Empresa.cpf == doc)).first()
        if existente is not None:
            plano.reaproveitar[doc] = existente.id
        elif doc not in plano.criar:
            plano.criar[doc] = p.id
        plano.ligar[p.id] = doc
    return plano


def _texto(v, limite=None):
    s = str(v or "").strip()
    return (s[:limite] if limite else s) or None


def _empresa_do_override(p: Proposta, doc: str) -> Empresa:
    ov = p.cliente_override or {}
    cgc, cpf = normalizar_documento(doc)
    cep = so_digitos(ov.get("cep"))
    return Empresa(
        cliente=p.cliente, nome=_texto(ov.get("nome"), 100), cgc=cgc, cpf=cpf,
        endereco=_texto(ov.get("endereco"), 100), municipio=_texto(ov.get("municipio"), 100),
        estado=(_texto(ov.get("estado"), 2) or "").upper() or None,
        cep=cep if len(cep) == 8 else None,
        email=_texto(ov.get("email"), 100), telefone=_texto(ov.get("telefone"), 50),
    )


def aplicar(db, plano: Plano) -> dict[str, int]:
    ids_empresa = dict(plano.reaproveitar)
    for doc, proposta_id in plano.criar.items():
        empresa = _empresa_do_override(db.get(Proposta, proposta_id), doc)
        db.add(empresa)
        db.flush()
        ids_empresa[doc] = empresa.id

    for proposta_id in plano.congelar:
        p = db.get(Proposta, proposta_id)
        p.destinatario = destinatario_legado(p.cliente_rel, p.cliente_override)

    for proposta_id, doc in plano.ligar.items():
        p = db.get(Proposta, proposta_id)
        copia = destinatario_legado(p.cliente_rel, p.cliente_override)
        matriz = p.cliente_rel
        copia.update({"tipo": "empresa", "id": ids_empresa[doc],
                      "matriz_id": matriz.id if matriz else None,
                      "matriz_nome": matriz.nome if matriz else None})
        # o legado cai no cadastro da matriz para campo vazio; na filial, vazio fica vazio
        ov = p.cliente_override or {}
        for campo in ("endereco", "municipio", "estado", "email", "telefone", "cep"):
            if not str(ov.get(campo) or "").strip():
                copia[campo] = None
        p.empresa = ids_empresa[doc]
        p.destinatario = copia

    db.commit()
    return {
        "empresas_criadas": len(plano.criar),
        "empresas_reaproveitadas": len(plano.reaproveitar),
        "propostas_congeladas": len(plano.congelar),
        "propostas_ligadas": len(plano.ligar),
    }


def _imprimir(plano: Plano) -> None:
    print(f"Propostas a congelar: {len(plano.congelar)}")
    print(f"Empresas a criar: {len(plano.criar)}")
    for doc, pid in plano.criar.items():
        print(f"  + {doc} (a partir da proposta id {pid})")
    print(f"Empresas reaproveitadas: {len(plano.reaproveitar)}")
    for doc, eid in plano.reaproveitar.items():
        print(f"  = {doc} -> empresa {eid}")
    print(f"Propostas a ligar: {len(plano.ligar)}")
    if plano.recusados:
        print("RECUSADOS (documento ja e' de um Cliente — decidir a mao):")
        for doc, (cid, nome) in plano.recusados.items():
            print(f"  ! {doc} -> cliente {cid} {nome}")
    if plano.invalidos:
        print("INVALIDOS (ficam so congelados):")
        for pid, motivo in plano.invalidos.items():
            print(f"  ? proposta id {pid}: {motivo}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aplicar", action="store_true", help="grava (padrao: so simula)")
    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        plano = planejar(db)
        _imprimir(plano)
        if not args.aplicar:
            print("\nSIMULACAO — nada gravado. Rode com --aplicar para gravar.")
            return
        print("\nGravado:", aplicar(db, plano))
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_migrar_filiais_propostas.py -q`
Expected: PASS.

- [ ] **Step 5: Suíte inteira do backend**

Run: `pytest -q`
Expected: só as falhas da baseline (Task 0).

- [ ] **Step 6: Commit**

```bash
git add backend/app/scripts/migrar_filiais_propostas.py backend/tests/test_migrar_filiais_propostas.py
git commit -m "feat(propostas): script que congela as propostas antigas e cria as filiais dos overrides"
```

---
### Task 10: Frontend — permissão, API de Empresas e módulo puro `dadosEmpresa`

**Files:**
- Modify: `frontend/src/auth/roles.ts`
- Create: `frontend/src/app/empresas/api.ts`, `frontend/src/app/empresas/dadosEmpresa.ts`, `frontend/src/app/empresas/dadosEmpresa.test.ts`
- Move: `frontend/src/app/propostas/buscaEndereco.ts` → `frontend/src/app/empresas/buscaEndereco.ts` (e o `.test.ts`)

**Interfaces:**
- Produces:
  - `podeGerenciarEmpresas(user: User | null): boolean`
  - `api.ts`: tipos `Empresa`, `EmpresaPayload`, `EmpresasPage`, `DestinatarioResultado`; objetos `empresasApi` (`listar`, `obter`, `criar`, `atualizar`, `desativar`, `reativar`) e `destinatariosApi.buscar(q)`.
  - `dadosEmpresa.ts`: `CAMPOS_DADOS`, `CampoDados`, `DadosEmpresa`, `ROTULOS_DADOS`, `UFS`, `OBRIGATORIOS_PROPOSTA`, `dadosVazios(documento?)`, `dadosDeCliente(c, opcoes?)`, `dadosDeEmpresa(e, opcoes?)`, `sugestoesDeCliente(c)`, `sugestoesDeEmpresa(e)`, `camposFaltando(d, obrigatorios)`.
  - `buscaEndereco.ts`: `buscaApi`, `ResultadoCep`, `ResultadoCnpj`, `aplicarResultadoCep(d, r)`, `aplicarResultadoCnpj(d, r)` (agora sobre `DadosEmpresa`, retornando `{ dados, preenchidos }`), `mensagemErroBusca`.

- [ ] **Step 1: Permissão**

Em `frontend/src/auth/roles.ts`, depois de `podeGerenciarPropostas`:

```ts
// Espelha `_escrever` de backend/app/api/empresas.py. Hoje e' o mesmo trio de
// propostas (o modal da proposta cria e edita Empresa), mas com nome proprio
// para as duas regras poderem divergir.
export function podeGerenciarEmpresas(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL || user?.funcao === FUNCAO_FINANCEIRO
}
```

- [ ] **Step 2: API**

```ts
// frontend/src/app/empresas/api.ts
import { apiJson } from '../../lib/api'

export interface Empresa {
  id: number
  cliente: number | null
  matriz_nome: string | null
  nome: string
  cgc: string | null
  cpf: string | null
  cep: string | null
  endereco: string | null
  numero: string | null
  complemento: string | null
  bairro: string | null
  municipio: string | null
  estado: string | null
  email: string | null
  telefone: string | null
  insc_est: string | null
  ativo: boolean
  created_at: string | null
  updated_at: string | null
}

export interface EmpresaPayload {
  documento: string
  cliente: number | null
  nome: string
  cep: string | null
  endereco: string | null
  numero: string | null
  complemento: string | null
  bairro: string | null
  municipio: string | null
  estado: string | null
  email: string | null
  telefone: string | null
  insc_est: string | null
}

export interface EmpresasPage {
  items: Empresa[]
  total: number
}

export interface ListarEmpresasParams {
  q?: string
  cliente?: number
  ativo?: boolean
  offset?: number
  limit?: number
}

export interface DestinatarioResultado {
  tipo: 'cliente' | 'empresa'
  id: number
  nome: string | null
  documento: string | null
  municipio: string | null
  estado: string | null
  matriz_id: number | null
  matriz_nome: string | null
}

export const empresasApi = {
  listar: (params: ListarEmpresasParams = {}): Promise<EmpresasPage> => {
    const sp = new URLSearchParams()
    if (params.q) sp.set('q', params.q)
    if (params.cliente != null) sp.set('cliente', String(params.cliente))
    if (params.ativo != null) sp.set('ativo', String(params.ativo))
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<EmpresasPage>(`/empresas?${sp.toString()}`)
  },
  obter: (id: number) => apiJson<Empresa>(`/empresas/${id}`),
  criar: (payload: EmpresaPayload) => apiJson<Empresa>('/empresas', { method: 'POST', body: JSON.stringify(payload) }),
  atualizar: (id: number, payload: EmpresaPayload) =>
    apiJson<Empresa>(`/empresas/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  desativar: (id: number) => apiJson<Empresa>(`/empresas/${id}/desativar`, { method: 'POST' }),
  reativar: (id: number) => apiJson<Empresa>(`/empresas/${id}/reativar`, { method: 'POST' }),
}

export const destinatariosApi = {
  buscar: (q: string) =>
    apiJson<DestinatarioResultado[]>(`/propostas/destinatarios?q=${encodeURIComponent(q)}`),
}
```

- [ ] **Step 3: Testes do módulo puro**

```ts
// frontend/src/app/empresas/dadosEmpresa.test.ts
import { describe, it, expect } from 'vitest'
import {
  camposFaltando, dadosDeCliente, dadosDeEmpresa, dadosVazios, OBRIGATORIOS_PROPOSTA,
  sugestoesDeCliente, sugestoesDeEmpresa,
} from './dadosEmpresa'
import type { Cliente } from '../clientes/api'
import type { Empresa } from './api'

const CLIENTE = {
  id: 5, grupo: null, nome: 'ACME', cgc: '08857492000148', cpf: null, endereco: 'Rua X', numero: 10,
  complemento: null, bairro: 'Centro', municipio: 'Recife', estado: 'PE', cep: '50000000', contato: null,
  email: 'a@acme.com', telefones: null, celular: '81999990000', whatsapp: null, whatsapp1: null, whatsapp2: null,
  insc_mun: null, insc_est: null, datcad: null, obs: null, ativo: true,
} as Cliente

const EMPRESA: Empresa = {
  id: 9, cliente: 5, matriz_nome: 'ACME', nome: 'Filial', cgc: '36312056000552', cpf: null, cep: '29680000',
  endereco: 'BR 101', numero: 'S/N', complemento: null, bairro: 'Zona Rural', municipio: 'Joao Neiva',
  estado: 'ES', email: 'f@acme.com', telefone: '2733330000', insc_est: null, ativo: true,
  created_at: null, updated_at: null,
}

describe('dadosEmpresa', () => {
  it('dados do cliente abrem com e-mail e telefone vazios', () => {
    const d = dadosDeCliente(CLIENTE)
    expect(d).toMatchObject({ nome: 'ACME', documento: '08857492000148', numero: '10', bairro: 'Centro' })
    expect(d.email).toBe('')
    expect(d.telefone).toBe('')
  })

  it('com comContato, e-mail e telefone vem do cadastro', () => {
    expect(dadosDeEmpresa(EMPRESA, { comContato: true })).toMatchObject({ email: 'f@acme.com', telefone: '2733330000' })
  })

  it('sugestao de telefone do cliente prefere telefones e cai no celular', () => {
    expect(sugestoesDeCliente(CLIENTE)).toEqual({ email: 'a@acme.com', telefone: '81999990000' })
    expect(sugestoesDeCliente({ ...CLIENTE, telefones: '8130001111' }).telefone).toBe('8130001111')
    expect(sugestoesDeEmpresa(EMPRESA)).toEqual({ email: 'f@acme.com', telefone: '2733330000' })
  })

  it('camposFaltando ignora pontuacao em documento e cep', () => {
    const d = { ...dadosVazios('...'), nome: 'X', cep: '-' }
    expect(camposFaltando(d, OBRIGATORIOS_PROPOSTA)).toEqual(
      ['documento', 'cep', 'endereco', 'municipio', 'estado', 'telefone', 'email'],
    )
  })
})
```

- [ ] **Step 4: Rodar e ver falhar**

Run (em `frontend/`): `npx vitest run src/app/empresas/dadosEmpresa.test.ts`
Expected: FAIL (módulo inexistente).

- [ ] **Step 5: Implementar `dadosEmpresa.ts`**

```ts
// frontend/src/app/empresas/dadosEmpresa.ts
// Dados cadastrais de um destinatario (Cliente ou Empresa) como aparecem no
// formulario compartilhado. Fonte unica dos campos, rotulos e obrigatorios —
// usada pela pagina Empresas e pelo modal da proposta.

import { soDigitos } from '../../lib/documento'
import type { Cliente } from '../clientes/api'
import type { Empresa } from './api'

export const CAMPOS_DADOS = [
  'nome', 'documento', 'cep', 'endereco', 'numero', 'complemento', 'bairro',
  'municipio', 'estado', 'telefone', 'email',
] as const
export type CampoDados = (typeof CAMPOS_DADOS)[number]
export type DadosEmpresa = Record<CampoDados, string>

export const ROTULOS_DADOS: Record<CampoDados, string> = {
  nome: 'Razão social / Nome',
  documento: 'CNPJ / CPF',
  cep: 'CEP',
  endereco: 'Endereço',
  numero: 'Número',
  complemento: 'Complemento',
  bairro: 'Bairro',
  municipio: 'Município',
  estado: 'Estado (UF)',
  telefone: 'Telefone',
  email: 'E-mail',
}

export const UFS = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG',
  'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
]

/** Obrigatorios na proposta. "Aos cuidados de" tambem e', mas mora na proposta. */
export const OBRIGATORIOS_PROPOSTA: readonly CampoDados[] = [
  'nome', 'documento', 'cep', 'endereco', 'municipio', 'estado', 'telefone', 'email',
]

const SO_DIGITOS = new Set<CampoDados>(['documento', 'cep'])

export function dadosVazios(documento = ''): DadosEmpresa {
  const d = Object.fromEntries(CAMPOS_DADOS.map((c) => [c, ''])) as DadosEmpresa
  d.documento = documento
  return d
}

interface Opcoes {
  /** Traz e-mail e telefone do cadastro. Na proposta eles abrem VAZIOS de
   *  proposito: vindo prontos, ninguem conferia e a proposta saia com o contato
   *  velho (pedido do comercial, commit 706fc68). */
  comContato?: boolean
}

const txt = (v: string | number | null | undefined) => (v == null ? '' : String(v))

export function sugestoesDeCliente(c: Cliente): { email: string; telefone: string } {
  return { email: txt(c.email), telefone: txt(c.telefones || c.celular || c.whatsapp) }
}

export function sugestoesDeEmpresa(e: Empresa): { email: string; telefone: string } {
  return { email: txt(e.email), telefone: txt(e.telefone) }
}

export function dadosDeCliente(c: Cliente, opcoes: Opcoes = {}): DadosEmpresa {
  const s = sugestoesDeCliente(c)
  return {
    nome: txt(c.nome), documento: soDigitos(c.cgc || c.cpf), cep: soDigitos(c.cep),
    endereco: txt(c.endereco), numero: txt(c.numero), complemento: txt(c.complemento),
    bairro: txt(c.bairro), municipio: txt(c.municipio), estado: txt(c.estado),
    email: opcoes.comContato ? s.email : '', telefone: opcoes.comContato ? s.telefone : '',
  }
}

export function dadosDeEmpresa(e: Empresa, opcoes: Opcoes = {}): DadosEmpresa {
  const s = sugestoesDeEmpresa(e)
  return {
    nome: e.nome, documento: soDigitos(e.cgc || e.cpf), cep: soDigitos(e.cep),
    endereco: txt(e.endereco), numero: txt(e.numero), complemento: txt(e.complemento),
    bairro: txt(e.bairro), municipio: txt(e.municipio), estado: txt(e.estado),
    email: opcoes.comContato ? s.email : '', telefone: opcoes.comContato ? s.telefone : '',
  }
}

export function camposFaltando(d: DadosEmpresa, obrigatorios: readonly CampoDados[]): CampoDados[] {
  return obrigatorios.filter((c) => (SO_DIGITOS.has(c) ? !soDigitos(d[c]) : d[c].trim() === ''))
}
```

- [ ] **Step 6: Mover e retipar `buscaEndereco`**

```bash
git mv frontend/src/app/propostas/buscaEndereco.ts frontend/src/app/empresas/buscaEndereco.ts
git mv frontend/src/app/propostas/buscaEndereco.test.ts frontend/src/app/empresas/buscaEndereco.test.ts
```

Novo conteúdo de `frontend/src/app/empresas/buscaEndereco.ts` (o `mensagemErroBusca` fica igual ao atual — copie a função inteira, com o comentário do 429):

```ts
// Busca de dados publicos (CEP/CNPJ) para preencher o formulario de dados da
// empresa. A regra de QUAL campo cada busca preenche mora aqui, pura e testavel.

import { apiJson, ApiError } from '../../lib/api'
import type { CampoDados, DadosEmpresa } from './dadosEmpresa'

export interface ResultadoCep {
  cep: string
  endereco: string
  bairro: string
  municipio: string
  estado: string
}

export interface ResultadoCnpj extends ResultadoCep {
  documento: string
  nome: string
  numero: string
  complemento: string
  situacao: string
}

export const buscaApi = {
  cep: (cep: string) => apiJson<ResultadoCep>(`/integracoes/cep/${encodeURIComponent(cep)}`),
  cnpj: (cnpj: string) => apiJson<ResultadoCnpj>(`/integracoes/cnpj/${encodeURIComponent(cnpj)}`),
}

export interface Preenchimento {
  dados: DadosEmpresa
  preenchidos: CampoDados[]
}

/** Campo vazio na resposta nao apaga o que ja estava preenchido. */
function aplicar(dados: DadosEmpresa, valores: Partial<DadosEmpresa>): Preenchimento {
  const novo = { ...dados }
  const preenchidos: CampoDados[] = []
  for (const [campo, valor] of Object.entries(valores) as [CampoDados, string | undefined][]) {
    if (valor == null || valor.trim() === '') continue
    novo[campo] = valor
    preenchidos.push(campo)
  }
  return { dados: novo, preenchidos }
}

/** O CEP chega no nivel da rua — o numero continua sendo digitado a mao. */
export function aplicarResultadoCep(dados: DadosEmpresa, r: ResultadoCep): Preenchimento {
  return aplicar(dados, { cep: r.cep, endereco: r.endereco, bairro: r.bairro, municipio: r.municipio, estado: r.estado })
}

/**
 * Telefone e e-mail ficam de fora de proposito: na Receita costumam estar
 * desatualizados, e sao justamente os que a Health Safety tem bons no cadastro.
 */
export function aplicarResultadoCnpj(dados: DadosEmpresa, r: ResultadoCnpj): Preenchimento {
  return aplicar(dados, {
    nome: r.nome, cep: r.cep, endereco: r.endereco, numero: r.numero, complemento: r.complemento,
    bairro: r.bairro, municipio: r.municipio, estado: r.estado,
  })
}

// mensagemErroBusca: copiar sem mudanca da versao anterior deste arquivo.
```

Em `buscaEndereco.test.ts`: trocar os rascunhos parciais por `{ ...dadosVazios(), ...parcial }` (import de `./dadosEmpresa`), o nome da chave de retorno `draft` por `dados`, e acrescentar nos resultados de CEP/CNPJ os campos `bairro`, `numero`, `complemento` com as asserções de que são preenchidos.

- [ ] **Step 7: Rodar**

Run: `npx vitest run src/app/empresas`
Expected: PASS. (`PropostaModal.tsx` ainda importa o caminho antigo — o `tsc` fica quebrado até a Task 14; **não** rode o build aqui.)

- [ ] **Step 8: Commit**

```bash
git add frontend/src/auth/roles.ts frontend/src/app/empresas/api.ts frontend/src/app/empresas/dadosEmpresa.ts \
  frontend/src/app/empresas/dadosEmpresa.test.ts frontend/src/app/empresas/buscaEndereco.ts \
  frontend/src/app/empresas/buscaEndereco.test.ts frontend/src/app/propostas/buscaEndereco.ts frontend/src/app/propostas/buscaEndereco.test.ts
git commit -m "feat(empresas): api e dados compartilhados do formulario de empresa"
```

---

### Task 11: Componente `DadosEmpresaForm`

**Files:**
- Create: `frontend/src/app/empresas/DadosEmpresaForm.tsx`, `frontend/src/app/empresas/DadosEmpresaForm.test.tsx`

**Interfaces:**
- Consumes: `DadosEmpresa`, `CampoDados`, `ROTULOS_DADOS`, `UFS`, `camposFaltando` (Task 10); `buscaApi`, `aplicarResultadoCep`, `aplicarResultadoCnpj`, `mensagemErroBusca` (Task 10).
- Produces: `DadosEmpresaForm` com props

```ts
interface DadosEmpresaFormProps {
  dados: DadosEmpresa
  onChange: (dados: DadosEmpresa) => void
  documentoTravado?: boolean
  somenteLeitura?: boolean
  sugestoes?: { email?: string; telefone?: string }
  obrigatorios?: readonly CampoDados[]
  destacarFaltando?: boolean
  idPrefixo?: string          // padrao 'de' -> ids 'de-nome', 'de-documento', ...
  children?: ReactNode        // campos extras no fim da grade
}
```

- [ ] **Step 1: Escrever os testes**

```tsx
// frontend/src/app/empresas/DadosEmpresaForm.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useState } from 'react'

const buscarCep = vi.fn()
const buscarCnpj = vi.fn()
vi.mock('./buscaEndereco', async (orig) => {
  const real = await orig<typeof import('./buscaEndereco')>()
  return { ...real, buscaApi: { cep: (...a: unknown[]) => buscarCep(...a), cnpj: (...a: unknown[]) => buscarCnpj(...a) } }
})

import { DadosEmpresaForm } from './DadosEmpresaForm'
import { dadosVazios, type DadosEmpresa } from './dadosEmpresa'

function Harness(props: Partial<React.ComponentProps<typeof DadosEmpresaForm>> & { inicial?: Partial<DadosEmpresa> }) {
  const [dados, setDados] = useState<DadosEmpresa>({ ...dadosVazios(), ...props.inicial })
  return (
    <>
      <DadosEmpresaForm {...props} dados={dados} onChange={setDados} />
      <output data-testid="estado">{JSON.stringify(dados)}</output>
    </>
  )
}
const estado = () => JSON.parse(screen.getByTestId('estado').textContent ?? '{}') as DadosEmpresa

describe('DadosEmpresaForm', () => {
  beforeEach(() => { buscarCep.mockReset(); buscarCnpj.mockReset() })

  it('edita os campos', () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText(/Bairro/), { target: { value: 'Centro' } })
    expect(estado().bairro).toBe('Centro')
  })

  it('documento travado fica somente leitura', () => {
    render(<Harness documentoTravado inicial={{ documento: '08857492000148' }} />)
    const doc = screen.getByLabelText(/CNPJ \/ CPF/) as HTMLInputElement
    expect(doc.readOnly).toBe(true)
    expect(doc.value).toBe('08.857.492/0001-48')
  })

  it('sugestao de e-mail preenche com um clique', () => {
    render(<Harness sugestoes={{ email: 'a@acme.com' }} />)
    fireEvent.click(screen.getByRole('button', { name: /Usar do cadastro: a@acme.com/ }))
    expect(estado().email).toBe('a@acme.com')
  })

  it('sugestao some quando o campo ja tem o mesmo valor', () => {
    render(<Harness sugestoes={{ telefone: '8130001111' }} inicial={{ telefone: '8130001111' }} />)
    expect(screen.queryByRole('button', { name: /Usar do cadastro/ })).toBeNull()
  })

  it('lupa do CNPJ preenche numero e bairro e permite desfazer', async () => {
    buscarCnpj.mockResolvedValue({
      documento: '36312056000552', nome: 'CBF', cep: '29680000', endereco: 'BR 101', numero: 'S/N',
      complemento: 'KM 196', bairro: 'Zona Rural', municipio: 'Joao Neiva', estado: 'ES', situacao: 'ATIVA',
    })
    render(<Harness inicial={{ documento: '36312056000552' }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Buscar dados pelo CNPJ' }))
    await waitFor(() => expect(estado().bairro).toBe('Zona Rural'))
    expect(estado().numero).toBe('S/N')
    fireEvent.click(screen.getByRole('button', { name: 'Desfazer' }))
    expect(estado().bairro).toBe('')
  })

  it('somente leitura desabilita campos e lupas', () => {
    render(<Harness somenteLeitura />)
    expect((screen.getByLabelText(/Razão social/) as HTMLInputElement).disabled).toBe(true)
    expect(screen.queryByRole('button', { name: 'Buscar dados pelo CNPJ' })).toBeNull()
  })

  it('destaca obrigatorio vazio', () => {
    render(<Harness obrigatorios={['nome']} destacarFaltando />)
    expect(screen.getByLabelText(/Razão social \/ Nome \*/).className).toContain('border-danger')
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run src/app/empresas/DadosEmpresaForm.test.tsx`
Expected: FAIL (módulo inexistente).

- [ ] **Step 3: Implementar**

```tsx
// frontend/src/app/empresas/DadosEmpresaForm.tsx
import { useState, type ReactNode } from 'react'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { IconSearch } from '../../components/ui/icons'
import { formatarDocumento, mascararCEP, soDigitos } from '../../lib/documento'
import { cn } from '../../lib/utils'
import { camposFaltando, ROTULOS_DADOS, UFS, type CampoDados, type DadosEmpresa } from './dadosEmpresa'
import { aplicarResultadoCep, aplicarResultadoCnpj, buscaApi, mensagemErroBusca } from './buscaEndereco'

function ComLupa({ aoBuscar, carregando, desabilitado, rotulo, children }: {
  aoBuscar: () => void
  /** Spinner nesta lupa especifica — so a que de fato esta buscando. */
  carregando: boolean
  /** Vale para as duas lupas enquanto qualquer busca estiver em andamento: uma
   *  segunda busca dispararia com os dados ja desatualizados pela primeira. */
  desabilitado: boolean
  rotulo: string
  children: ReactNode
}) {
  return (
    <div className="flex items-end gap-2">
      <div className="flex-1 min-w-0">{children}</div>
      <button
        type="button" onClick={aoBuscar} disabled={desabilitado} aria-label={rotulo} title={rotulo}
        className="mb-0.5 shrink-0 rounded-lg border border-border bg-background-elevated p-2.5 text-slate-400 hover:text-primary hover:border-primary/40 disabled:opacity-50 transition-colors"
      >
        {carregando ? <Spinner className="w-4 h-4" /> : <IconSearch className="w-4 h-4" />}
      </button>
    </div>
  )
}

export interface DadosEmpresaFormProps {
  dados: DadosEmpresa
  onChange: (dados: DadosEmpresa) => void
  documentoTravado?: boolean
  somenteLeitura?: boolean
  sugestoes?: { email?: string; telefone?: string }
  obrigatorios?: readonly CampoDados[]
  destacarFaltando?: boolean
  idPrefixo?: string
  children?: ReactNode
}

export function DadosEmpresaForm({
  dados, onChange, documentoTravado, somenteLeitura, sugestoes, obrigatorios = [],
  destacarFaltando, idPrefixo = 'de', children,
}: DadosEmpresaFormProps) {
  const [buscando, setBuscando] = useState<'cep' | 'cnpj' | null>(null)
  const [erroBusca, setErroBusca] = useState('')
  const [resultado, setResultado] = useState<{ origem: 'CEP' | 'CNPJ'; campos: string[]; situacao?: string } | null>(null)
  const [anterior, setAnterior] = useState<DadosEmpresa | null>(null)

  const faltando = destacarFaltando ? camposFaltando(dados, obrigatorios) : []
  const id = (c: CampoDados) => `${idPrefixo}-${c}`
  const rotulo = (c: CampoDados) => (obrigatorios.includes(c) ? `${ROTULOS_DADOS[c]} *` : ROTULOS_DADOS[c])
  const classe = (c: CampoDados, extra?: string) => cn(extra, faltando.includes(c) && 'border-danger')
  const definir = (c: CampoDados, v: string) => onChange({ ...dados, [c]: v })

  async function buscar(tipo: 'cep' | 'cnpj') {
    if (buscando) return
    setErroBusca('')
    setBuscando(tipo)
    const antes = dados
    try {
      if (tipo === 'cnpj') {
        const r = await buscaApi.cnpj(soDigitos(dados.documento))
        const { dados: novos, preenchidos } = aplicarResultadoCnpj(dados, r)
        onChange(novos)
        setResultado({ origem: 'CNPJ', campos: preenchidos.map((c) => ROTULOS_DADOS[c]), situacao: r.situacao || undefined })
      } else {
        const { dados: novos, preenchidos } = aplicarResultadoCep(dados, await buscaApi.cep(soDigitos(dados.cep)))
        onChange(novos)
        setResultado({ origem: 'CEP', campos: preenchidos.map((c) => ROTULOS_DADOS[c]) })
      }
      setAnterior(antes)
    } catch (e) {
      setResultado(null)
      setErroBusca(mensagemErroBusca(e, tipo === 'cnpj' ? 'CNPJ' : 'CEP'))
    } finally {
      setBuscando(null)
    }
  }

  function desfazer() {
    if (anterior) onChange(anterior)
    setAnterior(null)
    setResultado(null)
  }

  function campoTexto(c: CampoDados, extra?: string) {
    return (
      <Input id={id(c)} label={rotulo(c)} value={dados[c]} disabled={somenteLeitura}
        onChange={(e) => definir(c, e.target.value)} className={classe(c, extra)} />
    )
  }

  function campoContato(c: 'email' | 'telefone') {
    const sugestao = sugestoes?.[c]
    return (
      <div>
        {campoTexto(c)}
        {!somenteLeitura && sugestao && sugestao !== dados[c] && (
          <button type="button" onClick={() => definir(c, sugestao)} className="mt-1 text-xs font-semibold text-primary hover:underline">
            Usar do cadastro: {sugestao}
          </button>
        )}
      </div>
    )
  }

  const documento = (
    <Input id={id('documento')} label={rotulo('documento')} value={formatarDocumento(dados.documento)}
      readOnly={documentoTravado} disabled={somenteLeitura}
      onChange={(e) => definir('documento', soDigitos(e.target.value))}
      className={classe('documento', documentoTravado ? 'opacity-70' : undefined)} />
  )
  const cep = (
    <Input id={id('cep')} label={rotulo('cep')} value={mascararCEP(dados.cep)} disabled={somenteLeitura}
      onChange={(e) => definir('cep', soDigitos(e.target.value))} className={classe('cep')} />
  )

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">{campoTexto('nome')}</div>
        {somenteLeitura ? documento : (
          <ComLupa aoBuscar={() => buscar('cnpj')} carregando={buscando === 'cnpj'} desabilitado={buscando !== null} rotulo="Buscar dados pelo CNPJ">
            {documento}
          </ComLupa>
        )}
        {somenteLeitura ? cep : (
          <ComLupa aoBuscar={() => buscar('cep')} carregando={buscando === 'cep'} desabilitado={buscando !== null} rotulo="Buscar endereço pelo CEP">
            {cep}
          </ComLupa>
        )}
        <div className="sm:col-span-2">{campoTexto('endereco')}</div>
        {campoTexto('numero')}
        {campoTexto('complemento')}
        {campoTexto('bairro')}
        {campoTexto('municipio')}
        <Select id={id('estado')} label={rotulo('estado')} value={dados.estado} disabled={somenteLeitura}
          onChange={(e) => definir('estado', e.target.value)} className={classe('estado')}>
          <option value="">—</option>
          {UFS.map((uf) => <option key={uf} value={uf}>{uf}</option>)}
        </Select>
        {campoContato('telefone')}
        <div className="sm:col-span-2">{campoContato('email')}</div>
        {children}
      </div>
      {erroBusca && <p className="text-xs font-medium text-danger">{erroBusca}</p>}
      {resultado && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span className="text-slate-400">Preenchido pelo {resultado.origem}: {resultado.campos.join(', ')}.</span>
          {resultado.situacao && (
            <span className={resultado.situacao === 'ATIVA' ? 'text-slate-500' : 'font-semibold text-warning'}>
              Situação na Receita: {resultado.situacao}
            </span>
          )}
          <button type="button" onClick={desfazer} className="font-semibold text-primary hover:underline">Desfazer</button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npx vitest run src/app/empresas/DadosEmpresaForm.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/empresas/DadosEmpresaForm.tsx frontend/src/app/empresas/DadosEmpresaForm.test.tsx
git commit -m "feat(empresas): formulario compartilhado de dados da empresa"
```

---
### Task 12: Página Empresas, modal de cadastro e seletor de matriz

**Files:**
- Create: `frontend/src/app/empresas/MatrizSelect.tsx`, `frontend/src/app/empresas/EmpresaModal.tsx`, `frontend/src/app/empresas/EmpresasPage.tsx`, `frontend/src/app/empresas/EmpresasPage.test.tsx`
- Modify: `frontend/src/app/routes.tsx`, `frontend/src/layout/Sidebar.tsx`

**Interfaces:**
- Consumes: `empresasApi`, `Empresa`, `EmpresaPayload` (Task 10); `DadosEmpresaForm` (Task 11); `dadosDeEmpresa`, `dadosVazios`, `camposFaltando`, `DadosEmpresa` (Task 10); `clientesApi`, `ClienteListItem`; `podeGerenciarEmpresas`.
- Produces:
  - `MatrizSelect({ valor, onChange, disabled? })` com `valor: { id: number; nome: string | null } | null` e `onChange(v: { id: number; nome: string | null } | null)`.
  - `EmpresaModal({ empresa, onClose, onSalvo })` — `empresa: Empresa | null` (null = nova); `onSalvo(e: Empresa)`.
  - `EmpresasPage` em `/app/empresas`.

- [ ] **Step 1: Escrever os testes**

```tsx
// frontend/src/app/empresas/EmpresasPage.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

let mockUser = { id: 1, nome: 'Com', email: 'c@c.com', funcao_id: 1, funcao: 'Comercial Pós-Vendas' }
vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

import { EmpresasPage } from './EmpresasPage'
import { empresasApi, type Empresa } from './api'
import { clientesApi } from '../clientes/api'
import { ApiError } from '../../lib/api'

const EMPRESA: Empresa = {
  id: 9, cliente: 5, matriz_nome: 'ACME', nome: 'Filial Norte', cgc: '36312056000552', cpf: null, cep: '29680000',
  endereco: 'BR 101', numero: 'S/N', complemento: null, bairro: null, municipio: 'Joao Neiva', estado: 'ES',
  email: 'f@acme.com', telefone: '2733330000', insc_est: null, ativo: true, created_at: null, updated_at: null,
}

const renderPagina = () => render(<MemoryRouter><EmpresasPage /></MemoryRouter>)

describe('EmpresasPage', () => {
  beforeEach(() => {
    mockUser = { id: 1, nome: 'Com', email: 'c@c.com', funcao_id: 1, funcao: 'Comercial Pós-Vendas' }
    vi.restoreAllMocks()
    vi.spyOn(empresasApi, 'listar').mockResolvedValue({ items: [EMPRESA], total: 1 })
    vi.spyOn(clientesApi, 'listar').mockResolvedValue({ items: [], total: 0 })
  })

  it('lista empresas com a matriz', async () => {
    renderPagina()
    expect(await screen.findByText('Filial Norte')).toBeInTheDocument()
    expect(screen.getByText('ACME')).toBeInTheDocument()
    expect(screen.getByText('36.312.056/0005-52')).toBeInTheDocument()
  })

  it('cria empresa pelo modal', async () => {
    const criar = vi.spyOn(empresasApi, 'criar').mockResolvedValue({ ...EMPRESA, id: 10 })
    renderPagina()
    await screen.findByText('Filial Norte')
    fireEvent.click(screen.getByRole('button', { name: 'Nova empresa' }))
    fireEvent.change(screen.getByLabelText(/Razão social/), { target: { value: 'Filial Sul' } })
    fireEvent.change(screen.getByLabelText(/CNPJ \/ CPF/), { target: { value: '11.222.333/0001-81' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    await waitFor(() => expect(criar).toHaveBeenCalledWith(expect.objectContaining({
      nome: 'Filial Sul', documento: '11222333000181', cliente: null, email: null,
    })))
  })

  it('mostra o 409 de documento duplicado', async () => {
    vi.spyOn(empresasApi, 'criar').mockRejectedValue(new ApiError(409, 'Documento já cadastrado como Cliente: ACME'))
    renderPagina()
    await screen.findByText('Filial Norte')
    fireEvent.click(screen.getByRole('button', { name: 'Nova empresa' }))
    fireEvent.change(screen.getByLabelText(/Razão social/), { target: { value: 'X' } })
    fireEvent.change(screen.getByLabelText(/CNPJ \/ CPF/), { target: { value: '08857492000148' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Documento já cadastrado como Cliente: ACME')).toBeInTheDocument()
  })

  it('quem nao gerencia so visualiza', async () => {
    mockUser = { ...mockUser, funcao: 'Laboratório' }
    renderPagina()
    await screen.findByText('Filial Norte')
    expect(screen.queryByRole('button', { name: 'Nova empresa' })).toBeNull()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run src/app/empresas/EmpresasPage.test.tsx`
Expected: FAIL (módulo inexistente).

- [ ] **Step 3: `MatrizSelect`**

```tsx
// frontend/src/app/empresas/MatrizSelect.tsx
import { useEffect, useState } from 'react'
import { IconButton } from '../../components/ui/IconButton'
import { IconX } from '../../components/ui/icons'
import { formatarDocumento } from '../../lib/documento'
import { clientesApi, type ClienteListItem } from '../clientes/api'

export interface MatrizValor { id: number; nome: string | null }

const inputClass = 'w-full px-3 py-2.5 text-sm rounded-lg border border-border bg-background-elevated text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-colors'

/** Cliente matriz da Empresa (opcional): de onde vem a frota da proposta. */
export function MatrizSelect({ valor, onChange, disabled }: {
  valor: MatrizValor | null
  onChange: (v: MatrizValor | null) => void
  disabled?: boolean
}) {
  const [termo, setTermo] = useState('')
  const [resultados, setResultados] = useState<ClienteListItem[]>([])

  useEffect(() => {
    if (valor || termo.trim().length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResultados([])
      return
    }
    let vivo = true
    clientesApi.listar({ q: termo.trim(), limit: 10 })
      .then((r) => { if (vivo) setResultados(r.items) })
      .catch(() => { if (vivo) setResultados([]) })
    return () => { vivo = false }
  }, [termo, valor])

  return (
    <div className="sm:col-span-2">
      <label htmlFor="matriz-busca" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">
        Cliente matriz (opcional)
      </label>
      {valor ? (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-background-elevated px-3 py-2">
          <span className="truncate text-sm text-slate-200">{valor.nome ?? `Cliente #${valor.id}`}</span>
          {!disabled && (
            <IconButton label="Remover matriz" tone="excluir" onClick={() => onChange(null)}><IconX className="w-4 h-4" /></IconButton>
          )}
        </div>
      ) : (
        <>
          <input id="matriz-busca" value={termo} disabled={disabled} onChange={(e) => setTermo(e.target.value)}
            placeholder="Buscar cliente por nome ou CNPJ" className={inputClass} />
          {resultados.length > 0 && (
            <ul className="mt-1.5 divide-y divide-border rounded-lg border border-border max-h-48 overflow-y-auto">
              {resultados.map((c) => (
                <li key={c.id}>
                  <button type="button" onClick={() => { onChange({ id: c.id, nome: c.nome }); setTermo('') }}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-background-elevated">
                    <span className="block font-semibold text-slate-200">{c.nome ?? `Cliente #${c.id}`}</span>
                    {(c.cgc || c.cpf) && <span className="block text-xs text-slate-500">{formatarDocumento(c.cgc || c.cpf)}</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 4: `EmpresaModal`**

```tsx
// frontend/src/app/empresas/EmpresaModal.tsx
import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { soDigitos } from '../../lib/documento'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarEmpresas } from '../../auth/roles'
import { empresasApi, type Empresa, type EmpresaPayload } from './api'
import { camposFaltando, dadosDeEmpresa, dadosVazios, type DadosEmpresa } from './dadosEmpresa'
import { DadosEmpresaForm } from './DadosEmpresaForm'
import { MatrizSelect, type MatrizValor } from './MatrizSelect'

const OBRIGATORIOS = ['nome', 'documento'] as const
const nulo = (v: string) => (v.trim() === '' ? null : v.trim())

export function montarPayloadEmpresa(dados: DadosEmpresa, matriz: MatrizValor | null, inscEst: string): EmpresaPayload {
  return {
    documento: soDigitos(dados.documento), cliente: matriz?.id ?? null, nome: dados.nome.trim(),
    cep: nulo(soDigitos(dados.cep)), endereco: nulo(dados.endereco), numero: nulo(dados.numero),
    complemento: nulo(dados.complemento), bairro: nulo(dados.bairro), municipio: nulo(dados.municipio),
    estado: nulo(dados.estado), email: nulo(dados.email), telefone: nulo(dados.telefone), insc_est: nulo(inscEst),
  }
}

export function EmpresaModal({ empresa, onClose, onSalvo }: {
  empresa: Empresa | null
  onClose: () => void
  onSalvo: (e: Empresa) => void
}) {
  const { user } = useAuth()
  const podeEditar = podeGerenciarEmpresas(user)
  const [dados, setDados] = useState<DadosEmpresa>(() => (empresa ? dadosDeEmpresa(empresa, { comContato: true }) : dadosVazios()))
  const [matriz, setMatriz] = useState<MatrizValor | null>(
    empresa?.cliente != null ? { id: empresa.cliente, nome: empresa.matriz_nome } : null,
  )
  const [inscEst, setInscEst] = useState(empresa?.insc_est ?? '')
  const [tentou, setTentou] = useState(false)
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  async function salvar(e: FormEvent) {
    e.preventDefault()
    setTentou(true)
    if (camposFaltando(dados, OBRIGATORIOS).length) {
      setErro('Preencha razão social e CNPJ/CPF.')
      return
    }
    setErro('')
    setSalvando(true)
    try {
      const payload = montarPayloadEmpresa(dados, matriz, inscEst)
      const salva = empresa ? await empresasApi.atualizar(empresa.id, payload) : await empresasApi.criar(payload)
      onSalvo(salva)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar a empresa')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Modal open onClose={onClose} title={empresa ? `Empresa: ${empresa.nome}` : 'Nova empresa'} size="3xl" closeOnBackdrop={false}
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose} disabled={salvando}>{podeEditar ? 'Cancelar' : 'Fechar'}</Button>
          {podeEditar && <Button type="submit" form="form-empresa" disabled={salvando}>{salvando ? 'Salvando…' : 'Salvar'}</Button>}
        </>
      }
    >
      <form id="form-empresa" onSubmit={salvar} className="space-y-4">
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
        <DadosEmpresaForm dados={dados} onChange={setDados} somenteLeitura={!podeEditar}
          obrigatorios={OBRIGATORIOS} destacarFaltando={tentou} idPrefixo="emp">
          <Input id="emp-insc-est" label="Inscrição estadual" value={inscEst} disabled={!podeEditar}
            onChange={(e) => setInscEst(e.target.value)} />
          <MatrizSelect valor={matriz} onChange={setMatriz} disabled={!podeEditar} />
        </DadosEmpresaForm>
      </form>
    </Modal>
  )
}
```

- [ ] **Step 5: `EmpresasPage`**

```tsx
// frontend/src/app/empresas/EmpresasPage.tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { SearchBar } from '../../components/ui/SearchBar'
import { PaginationOffset } from '../../components/ui/Pagination'
import { PageContainer } from '../../components/ui/Page'
import { IconButton, IconButtonGroup } from '../../components/ui/IconButton'
import { IconBan, IconPencil, IconRestore } from '../../components/ui/icons'
import { ApiError } from '../../lib/api'
import { formatarDocumento } from '../../lib/documento'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarEmpresas } from '../../auth/roles'
import { empresasApi, type Empresa } from './api'
import { EmpresaModal } from './EmpresaModal'

const LIMITE = 25

export function EmpresasPage() {
  const { user } = useAuth()
  const podeEditar = podeGerenciarEmpresas(user)
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<Empresa[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')
  const [recarga, setRecarga] = useState(0)
  const [modal, setModal] = useState<{ empresa: Empresa | null } | null>(null)

  useEffect(() => {
    let vivo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    empresasApi.listar({ q: busca || undefined, offset, limit: LIMITE })
      .then((p) => { if (vivo) { setItens(p.items); setTotal(p.total) } })
      .catch((e) => { if (vivo) { setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) } })
    return () => { vivo = false }
  }, [busca, offset, recarga])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(termo.trim())
  }

  async function alternarAtivo(emp: Empresa) {
    try {
      await (emp.ativo ? empresasApi.desativar(emp.id) : empresasApi.reativar(emp.id))
      setRecarga((n) => n + 1)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao alterar a empresa')
    }
  }

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Empresas</h1>
        {podeEditar && <Button onClick={() => setModal({ empresa: null })}>Nova empresa</Button>}
      </div>
      <p className="text-sm text-slate-500">Filiais com os dados cadastrais. Os aparelhos das propostas vêm do cliente matriz.</p>
      <SearchBar value={termo} onChange={setTermo} onSubmit={onBuscar} placeholder="Buscar por nome, CNPJ, CPF ou município" />
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma empresa encontrada.</p>
      ) : (
        <Table
          head={<><TH>Nome</TH><TH>CNPJ / CPF</TH><TH>Matriz</TH><TH>Município/UF</TH><TH>Ativo</TH><TH>Ações</TH></>}
          footer={<PaginationOffset offset={offset} limit={LIMITE} total={total} onOffsetChange={setOffset} itemLabel="empresas" />}
        >
          {itens.map((emp) => (
            <tr key={emp.id} className="hover:bg-background-elevated transition-colors">
              <TD>{emp.nome}</TD>
              <TD>{formatarDocumento(emp.cgc || emp.cpf) || '—'}</TD>
              <TD>
                {emp.cliente != null
                  ? <Link to={`/app/clientes/${emp.cliente}`} className="text-primary hover:underline">{emp.matriz_nome ?? `Cliente #${emp.cliente}`}</Link>
                  : '—'}
              </TD>
              <TD>{[emp.municipio, emp.estado].filter(Boolean).join(' / ') || '—'}</TD>
              <TD><Badge tone={emp.ativo ? 'primary' : 'neutral'}>{emp.ativo ? 'Ativa' : 'Inativa'}</Badge></TD>
              <TD>
                <IconButtonGroup>
                  <IconButton label={podeEditar ? 'Editar' : 'Ver'} tone={podeEditar ? 'editar' : 'ver'} onClick={() => setModal({ empresa: emp })}>
                    <IconPencil className="w-4 h-4" />
                  </IconButton>
                  {podeEditar && (
                    <IconButton label={emp.ativo ? 'Desativar' : 'Reativar'} tone={emp.ativo ? 'excluir' : 'ok'} onClick={() => void alternarAtivo(emp)}>
                      {emp.ativo ? <IconBan className="w-4 h-4" /> : <IconRestore className="w-4 h-4" />}
                    </IconButton>
                  )}
                </IconButtonGroup>
              </TD>
            </tr>
          ))}
        </Table>
      )}
      {modal && (
        <EmpresaModal empresa={modal.empresa} onClose={() => setModal(null)}
          onSalvo={() => { setModal(null); setRecarga((n) => n + 1) }} />
      )}
    </PageContainer>
  )
}
```

- [ ] **Step 6: Rota e menu**

`frontend/src/app/routes.tsx`: importar `import { EmpresasPage } from './empresas/EmpresasPage'` e, logo depois da rota `clientes/:id` (fechamento do `</Route>`), acrescentar:

```tsx
        <Route path="empresas" element={<EmpresasPage />} />
```

`frontend/src/layout/Sidebar.tsx`: em `NAV_ITEMS`, logo depois do item `Clientes`:

```tsx
  { label: 'Empresas', icon: <IconClientes />, to: '/app/empresas' },
```

- [ ] **Step 7: Rodar e ver passar**

Run: `npx vitest run src/app/empresas`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/empresas/MatrizSelect.tsx frontend/src/app/empresas/EmpresaModal.tsx \
  frontend/src/app/empresas/EmpresasPage.tsx frontend/src/app/empresas/EmpresasPage.test.tsx \
  frontend/src/app/routes.tsx frontend/src/layout/Sidebar.tsx
git commit -m "feat(empresas): pagina de empresas com cadastro e matriz"
```

---

### Task 13: Bloco "Empresas vinculadas" na tela do Cliente

**Files:**
- Create: `frontend/src/app/clientes/EmpresasVinculadasSection.tsx`, `frontend/src/app/clientes/EmpresasVinculadasSection.test.tsx`
- Modify: `frontend/src/app/clientes/ClienteDadosTab.tsx` (dentro de `<DetailAside>`)

**Interfaces:**
- Consumes: `empresasApi.listar({ cliente })` (Task 10).
- Produces: `EmpresasVinculadasSection({ clienteId }: { clienteId: number })` — some (renderiza `null`) quando não há empresa.

- [ ] **Step 1: Escrever os testes**

```tsx
// frontend/src/app/clientes/EmpresasVinculadasSection.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { EmpresasVinculadasSection } from './EmpresasVinculadasSection'
import { empresasApi, type Empresa } from '../empresas/api'

const EMPRESA = {
  id: 9, cliente: 5, matriz_nome: 'ACME', nome: 'Filial Norte', cgc: '36312056000552', cpf: null,
  municipio: 'Joao Neiva', estado: 'ES', ativo: true,
} as Empresa

describe('EmpresasVinculadasSection', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('lista as filiais do cliente', async () => {
    const listar = vi.spyOn(empresasApi, 'listar').mockResolvedValue({ items: [EMPRESA], total: 1 })
    render(<MemoryRouter><EmpresasVinculadasSection clienteId={5} /></MemoryRouter>)
    expect(await screen.findByText('Filial Norte')).toBeInTheDocument()
    expect(listar).toHaveBeenCalledWith({ cliente: 5, limit: 100 })
  })

  it('some quando nao ha filial', async () => {
    const listar = vi.spyOn(empresasApi, 'listar').mockResolvedValue({ items: [], total: 0 })
    const { container } = render(<MemoryRouter><EmpresasVinculadasSection clienteId={5} /></MemoryRouter>)
    await waitFor(() => expect(listar).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run src/app/clientes/EmpresasVinculadasSection.test.tsx`
Expected: FAIL (módulo inexistente).

- [ ] **Step 3: Implementar**

Antes, abrir `frontend/src/app/clientes/FuncionariosSection.tsx` e copiar dele o **container e o título** da seção (mesmas classes), para o bloco ficar igual aos vizinhos do aside. O conteúdo:

```tsx
// frontend/src/app/clientes/EmpresasVinculadasSection.tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatarDocumento } from '../../lib/documento'
import { empresasApi, type Empresa } from '../empresas/api'

/** Filiais cujo cliente matriz e' este. Sem nenhuma, o bloco nao aparece. */
export function EmpresasVinculadasSection({ clienteId }: { clienteId: number }) {
  const [empresas, setEmpresas] = useState<Empresa[]>([])

  useEffect(() => {
    let vivo = true
    empresasApi.listar({ cliente: clienteId, limit: 100 })
      .then((p) => { if (vivo) setEmpresas(p.items) })
      .catch(() => { if (vivo) setEmpresas([]) })
    return () => { vivo = false }
  }, [clienteId])

  if (empresas.length === 0) return null

  return (
    <section className="rounded-2xl border border-border bg-background-surface p-5 space-y-3">
      <h2 className="text-sm font-bold text-slate-200">Empresas vinculadas</h2>
      <ul className="divide-y divide-border">
        {empresas.map((e) => (
          <li key={e.id} className="py-2">
            <Link to="/app/empresas" className="block text-sm font-semibold text-primary hover:underline">{e.nome}</Link>
            <span className="block text-xs text-slate-500">
              {formatarDocumento(e.cgc || e.cpf)}{e.municipio ? ` · ${e.municipio}/${e.estado ?? ''}` : ''}{e.ativo ? '' : ' · inativa'}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
```

(Se as classes de `<section>`/`<h2>` de `FuncionariosSection` forem outras, use as de lá.)

Em `ClienteDadosTab.tsx`: importar e colocar, dentro de `<DetailAside>`, logo antes de `<FuncionariosSection .../>`:

```tsx
          <EmpresasVinculadasSection clienteId={cliente.id} />
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npx vitest run src/app/clientes`
Expected: PASS. Se testes existentes de `ClienteDadosTab`/`ClienteLayout` passarem a chamar a rede, mockar `empresasApi.listar` neles com `vi.spyOn(empresasApi, 'listar').mockResolvedValue({ items: [], total: 0 })`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/clientes/EmpresasVinculadasSection.tsx frontend/src/app/clientes/EmpresasVinculadasSection.test.tsx frontend/src/app/clientes/ClienteDadosTab.tsx
git commit -m "feat(clientes): bloco de empresas vinculadas na tela do cliente"
```

---
### Task 14: Tipos da proposta, módulo puro `destinatario` e validação

**Files:**
- Modify: `frontend/src/app/propostas/api.ts`, `frontend/src/app/propostas/validacao.ts`, `frontend/src/app/propostas/validacao.test.ts`, `frontend/src/app/propostas/api.test.ts`
- Create: `frontend/src/app/propostas/destinatario.ts`, `frontend/src/app/propostas/destinatario.test.ts`

**Interfaces:**
- Consumes: `Cliente`, `ClienteListItem`; `Empresa`; `DadosEmpresa`, `camposFaltando`, `OBRIGATORIOS_PROPOSTA`, `ROTULOS_DADOS` (Task 10).
- Produces:
  - `api.ts`: `DestinatarioIn`, `DestinatarioCopia`; `PropostaBase` **sem** `cliente`/`cliente_override`; `PropostaCreate.destinatario?: DestinatarioIn | null`; `Proposta` com `cliente: number | null`, `empresa: number | null`, `destinatario: DestinatarioCopia | null`.
  - `destinatario.ts`: `type Selecao`, `clienteDaFrota(s: Selecao | null): number | null`, `montarDestinatario(s: Selecao, d: DadosEmpresa): DestinatarioIn`, `descreverSelecao(s: Selecao): string`.
  - `validacao.ts`: `validarProposta({ selecao, dados, contato, outrosItens, carregando }): string | null`, `camposObrigatoriosFaltando(dados, contato): string[]` (rótulos), `htmlTemTexto` (sem mudança).

- [ ] **Step 1: Tipos em `api.ts`**

Em `frontend/src/app/propostas/api.ts`:
- Remover `cliente` e `cliente_override` de `PropostaBase`.
- Acrescentar antes de `PropostaBase`:

```ts
/** O que o modal manda: o servidor grava no cadastro e monta a copia. */
export interface DestinatarioIn {
  tipo: 'cliente' | 'empresa' | 'nova_empresa'
  id: number | null
  matriz: number | null
  nome: string
  documento: string | null
  cep: string | null
  endereco: string | null
  numero: string | null
  complemento: string | null
  bairro: string | null
  municipio: string | null
  estado: string | null
  email: string
  telefone: string
}

/** Copia congelada devolvida pela API (`propostas.destinatario`). */
export interface DestinatarioCopia {
  tipo: 'cliente' | 'empresa'
  id: number | null
  nome: string | null
  documento: string | null
  cep: string | null
  endereco: string | null
  numero: string | null
  complemento: string | null
  bairro: string | null
  municipio: string | null
  estado: string | null
  email: string | null
  telefone: string | null
  matriz_id?: number | null
  matriz_nome?: string | null
}
```

- Em `PropostaCreate`: `destinatario?: DestinatarioIn | null`.
- Em `Proposta` (o tipo de saída): acrescentar `cliente: number | null`, `empresa: number | null`, `destinatario: DestinatarioCopia | null`.
- `api.test.ts`: na fixture, trocar `cliente_override: null` por `empresa: null, destinatario: null` (manter `cliente`).

- [ ] **Step 2: Testes de `destinatario.ts` e da validação**

```ts
// frontend/src/app/propostas/destinatario.test.ts
import { describe, it, expect } from 'vitest'
import { clienteDaFrota, descreverSelecao, montarDestinatario, type Selecao } from './destinatario'
import { dadosVazios } from '../empresas/dadosEmpresa'
import type { Cliente } from '../clientes/api'
import type { Empresa } from '../empresas/api'

const CLIENTE = { id: 5, nome: 'ACME' } as Cliente
const EMPRESA = { id: 9, nome: 'Filial', cliente: 5, matriz_nome: 'ACME' } as Empresa
const EMPRESA_SOLTA = { ...EMPRESA, cliente: null, matriz_nome: null } as Empresa

const DADOS = {
  ...dadosVazios('36.312.056/0005-52'), nome: ' Filial ', cep: '29680-000', endereco: 'BR 101',
  numero: 'S/N', municipio: 'Joao Neiva', estado: 'ES', email: 'f@acme.com', telefone: '2733330000',
}

describe('destinatario', () => {
  it('cliente da frota por tipo', () => {
    expect(clienteDaFrota(null)).toBeNull()
    expect(clienteDaFrota({ tipo: 'cliente', cliente: CLIENTE })).toBe(5)
    expect(clienteDaFrota({ tipo: 'empresa', empresa: EMPRESA })).toBe(5)
    expect(clienteDaFrota({ tipo: 'empresa', empresa: EMPRESA_SOLTA })).toBeNull()
    expect(clienteDaFrota({ tipo: 'nova_empresa', matriz: { id: 7, nome: 'M' } })).toBe(7)
    expect(clienteDaFrota({ tipo: 'nova_empresa', matriz: null })).toBeNull()
  })

  it('payload de cliente nao leva documento', () => {
    const p = montarDestinatario({ tipo: 'cliente', cliente: CLIENTE }, DADOS)
    expect(p).toMatchObject({ tipo: 'cliente', id: 5, matriz: null, documento: null, nome: 'Filial', cep: '29680000', bairro: null })
  })

  it('payload de nova empresa leva documento em digitos e a matriz', () => {
    const s: Selecao = { tipo: 'nova_empresa', matriz: { id: 7, nome: 'M' } }
    expect(montarDestinatario(s, DADOS)).toMatchObject({ tipo: 'nova_empresa', id: null, matriz: 7, documento: '36312056000552' })
  })

  it('descricao', () => {
    expect(descreverSelecao({ tipo: 'empresa', empresa: EMPRESA })).toBe('Empresa · matriz ACME')
    expect(descreverSelecao({ tipo: 'empresa', empresa: EMPRESA_SOLTA })).toBe('Empresa · sem matriz')
    expect(descreverSelecao({ tipo: 'cliente', cliente: CLIENTE })).toBe('Cliente')
    expect(descreverSelecao({ tipo: 'nova_empresa', matriz: null })).toBe('Nova empresa · sem matriz')
  })
})
```

Substituir **inteiro** `frontend/src/app/propostas/validacao.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { htmlTemTexto, validarProposta, camposObrigatoriosFaltando } from './validacao'
import { dadosVazios } from '../empresas/dadosEmpresa'
import type { Cliente } from '../clientes/api'

const COMPLETO = {
  ...dadosVazios('08857492000148'), nome: 'ACME', cep: '50000000', endereco: 'Rua X',
  municipio: 'Recife', estado: 'PE', email: 'a@a.com', telefone: '81999990000',
}
const SELECAO = { tipo: 'cliente' as const, cliente: { id: 5 } as Cliente }

describe('validacao', () => {
  it('htmlTemTexto ignora markup vazio do editor', () => {
    expect(htmlTemTexto('<p><br></p>')).toBe(false)
    expect(htmlTemTexto('<p>&nbsp;</p>')).toBe(false)
    expect(htmlTemTexto('<p>ok</p>')).toBe(true)
  })

  it('exige destinatario', () => {
    expect(validarProposta({ selecao: null, dados: COMPLETO, contato: 'Maria', outrosItens: '<p>x</p>' }))
      .toBe('Escolha o destinatário antes de salvar a proposta.')
  })

  it('espera o carregamento', () => {
    expect(validarProposta({ selecao: SELECAO, dados: COMPLETO, contato: 'Maria', outrosItens: '<p>x</p>', carregando: true }))
      .toBe('Aguarde o carregamento dos dados do destinatário.')
  })

  it('lista os obrigatorios faltando, incluindo o contato', () => {
    const dados = { ...COMPLETO, email: '', telefone: ' ' }
    expect(camposObrigatoriosFaltando(dados, '')).toEqual(['Telefone', 'E-mail', 'Contato (aos cuidados de)'])
    expect(validarProposta({ selecao: SELECAO, dados, contato: '', outrosItens: '<p>x</p>' }))
      .toBe('Preencha os campos obrigatórios: Telefone, E-mail, Contato (aos cuidados de).')
  })

  it('exige outros itens', () => {
    expect(validarProposta({ selecao: SELECAO, dados: COMPLETO, contato: 'Maria', outrosItens: '<p><br></p>' }))
      .toBe('Preencha "Outros Itens ou Serviços" — use o botao Aplicar modelo.')
  })

  it('ok', () => {
    expect(validarProposta({ selecao: SELECAO, dados: COMPLETO, contato: 'Maria', outrosItens: '<p>x</p>' })).toBeNull()
  })
})
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `npx vitest run src/app/propostas/destinatario.test.ts src/app/propostas/validacao.test.ts`
Expected: FAIL.

- [ ] **Step 4: Implementar `destinatario.ts`**

```ts
// frontend/src/app/propostas/destinatario.ts
// Destinatario da proposta: um Cliente (matriz, dono da frota), uma Empresa
// (filial, frota da matriz) ou uma Empresa ainda nao cadastrada, que nasce no
// servidor junto com a proposta.

import { soDigitos } from '../../lib/documento'
import type { Cliente } from '../clientes/api'
import type { Empresa } from '../empresas/api'
import type { DadosEmpresa } from '../empresas/dadosEmpresa'
import type { MatrizValor } from '../empresas/MatrizSelect'
import type { DestinatarioIn } from './api'

export type Selecao =
  | { tipo: 'cliente'; cliente: Cliente }
  | { tipo: 'empresa'; empresa: Empresa }
  | { tipo: 'nova_empresa'; matriz: MatrizValor | null }

/** De qual cliente sai a frota (aparelhos) da proposta. */
export function clienteDaFrota(s: Selecao | null): number | null {
  if (!s) return null
  if (s.tipo === 'cliente') return s.cliente.id
  if (s.tipo === 'empresa') return s.empresa.cliente
  return s.matriz?.id ?? null
}

export function descreverSelecao(s: Selecao): string {
  if (s.tipo === 'cliente') return 'Cliente'
  const matriz = s.tipo === 'empresa' ? s.empresa.matriz_nome : s.matriz?.nome
  const temMatriz = s.tipo === 'empresa' ? s.empresa.cliente != null : s.matriz != null
  const rotulo = s.tipo === 'empresa' ? 'Empresa' : 'Nova empresa'
  return `${rotulo} · ${temMatriz ? `matriz ${matriz ?? ''}`.trim() : 'sem matriz'}`
}

const nulo = (v: string) => (v.trim() === '' ? null : v.trim())

export function montarDestinatario(s: Selecao, d: DadosEmpresa): DestinatarioIn {
  return {
    tipo: s.tipo,
    id: s.tipo === 'cliente' ? s.cliente.id : s.tipo === 'empresa' ? s.empresa.id : null,
    matriz: s.tipo === 'nova_empresa' ? (s.matriz?.id ?? null) : null,
    // Documento de cadastro existente nao muda pela proposta (o servidor ignora).
    documento: s.tipo === 'nova_empresa' ? soDigitos(d.documento) : null,
    nome: d.nome.trim(),
    cep: nulo(soDigitos(d.cep)),
    endereco: nulo(d.endereco),
    numero: nulo(d.numero),
    complemento: nulo(d.complemento),
    bairro: nulo(d.bairro),
    municipio: nulo(d.municipio),
    estado: nulo(d.estado),
    email: d.email.trim(),
    telefone: d.telefone.trim(),
  }
}
```

- [ ] **Step 5: Reescrever `validacao.ts`**

```ts
// Regras minimas para uma proposta sair do modal. Existem porque o backend
// aceita quase tudo opcional e o submit implicito do browser (Enter) chegou a
// criar propostas em branco — ver PropostaModal.

import { camposFaltando, OBRIGATORIOS_PROPOSTA, ROTULOS_DADOS, type DadosEmpresa } from '../empresas/dadosEmpresa'
import type { Selecao } from './destinatario'

/**
 * O editor rico (Quill) nunca devolve string vazia depois de tocado: sobra
 * `<p><br></p>`, `&nbsp;` e afins. Aqui interessa se ha TEXTO, nao markup.
 */
export function htmlTemTexto(html?: string | null): boolean {
  if (!html) return false
  return html.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/gi, ' ').trim() !== ''
}

export const ROTULO_CONTATO = 'Contato (aos cuidados de)'

/**
 * Rotulos dos obrigatorios vazios, na ordem do formulario. E-mail, telefone e
 * "aos cuidados de" nascem vazios de proposito e so sao conferidos porque estao
 * aqui — herdados do cadastro, ninguem olhava (pedido do comercial).
 */
export function camposObrigatoriosFaltando(dados: DadosEmpresa, contato: string): string[] {
  const faltando = camposFaltando(dados, OBRIGATORIOS_PROPOSTA).map((c) => ROTULOS_DADOS[c])
  if (contato.trim() === '') faltando.push(ROTULO_CONTATO)
  return faltando
}

export interface PropostaValidavel {
  selecao: Selecao | null
  dados: DadosEmpresa
  contato: string
  outrosItens?: string | null
  /** Dados do destinatario ainda carregando — nao da para julgar os campos. */
  carregando?: boolean
}

/** Devolve a mensagem do primeiro problema encontrado, ou null se estiver ok. */
export function validarProposta(p: PropostaValidavel): string | null {
  if (p.selecao == null) return 'Escolha o destinatário antes de salvar a proposta.'
  if (p.carregando) return 'Aguarde o carregamento dos dados do destinatário.'
  const faltando = camposObrigatoriosFaltando(p.dados, p.contato)
  if (faltando.length) return `Preencha os campos obrigatórios: ${faltando.join(', ')}.`
  if (!htmlTemTexto(p.outrosItens)) return 'Preencha "Outros Itens ou Serviços" — use o botao Aplicar modelo.'
  return null
}
```

> A ordem de `OBRIGATORIOS_PROPOSTA` (Task 10) é `nome, documento, cep, endereco, municipio, estado, telefone, email` — por isso o teste espera `Telefone, E-mail`.

- [ ] **Step 6: Rodar e ver passar**

Run: `npx vitest run src/app/propostas/destinatario.test.ts src/app/propostas/validacao.test.ts src/app/propostas/api.test.ts`
Expected: PASS. (`PropostaModal.tsx`/`PropostasPage.tsx` seguem quebrados no `tsc` até as Tasks 16–17.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/propostas/api.ts frontend/src/app/propostas/api.test.ts frontend/src/app/propostas/destinatario.ts \
  frontend/src/app/propostas/destinatario.test.ts frontend/src/app/propostas/validacao.ts frontend/src/app/propostas/validacao.test.ts
git commit -m "feat(propostas): tipos e regras do destinatario no frontend"
```

---

### Task 15: Componente `DestinatarioBusca`

**Files:**
- Create: `frontend/src/app/propostas/DestinatarioBusca.tsx`, `frontend/src/app/propostas/DestinatarioBusca.test.tsx`

**Interfaces:**
- Consumes: `destinatariosApi.buscar`, `DestinatarioResultado` (Task 10).
- Produces: `DestinatarioBusca({ onEscolher, onCadastrarEmpresa })` com `onEscolher(r: DestinatarioResultado)` e `onCadastrarEmpresa(documento: string)` (só dígitos).

- [ ] **Step 1: Escrever os testes**

```tsx
// frontend/src/app/propostas/DestinatarioBusca.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const buscar = vi.fn()
vi.mock('../empresas/api', () => ({ destinatariosApi: { buscar: (...a: unknown[]) => buscar(...a) } }))

import { DestinatarioBusca } from './DestinatarioBusca'

const CLIENTE = { tipo: 'cliente', id: 5, nome: 'Rumo Matriz', documento: '08857492000148', municipio: 'Recife', estado: 'PE', matriz_id: null, matriz_nome: null }
const EMPRESA = { tipo: 'empresa', id: 9, nome: 'Rumo Filial', documento: '36312056000552', municipio: 'Curitiba', estado: 'PR', matriz_id: 5, matriz_nome: 'Rumo Matriz' }

describe('DestinatarioBusca', () => {
  beforeEach(() => buscar.mockReset())

  it('marca cada resultado como Cliente ou Empresa e escolhe', async () => {
    buscar.mockResolvedValue([CLIENTE, EMPRESA])
    const onEscolher = vi.fn()
    render(<DestinatarioBusca onEscolher={onEscolher} onCadastrarEmpresa={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(/Buscar cliente ou empresa/), { target: { value: 'rumo' } })
    expect(await screen.findByText('Empresa · matriz Rumo Matriz')).toBeInTheDocument()
    expect(screen.getByText('Cliente')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Rumo Filial/ }))
    expect(onEscolher).toHaveBeenCalledWith(EMPRESA)
  })

  it('documento completo sem resultado oferece cadastrar empresa', async () => {
    buscar.mockResolvedValue([])
    const onCadastrar = vi.fn()
    render(<DestinatarioBusca onEscolher={vi.fn()} onCadastrarEmpresa={onCadastrar} />)
    fireEvent.change(screen.getByPlaceholderText(/Buscar cliente ou empresa/), { target: { value: '36.312.056/0005-52' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Cadastrar empresa com este documento' }))
    expect(onCadastrar).toHaveBeenCalledWith('36312056000552')
  })

  it('nome sem resultado nao oferece cadastro', async () => {
    buscar.mockResolvedValue([])
    render(<DestinatarioBusca onEscolher={vi.fn()} onCadastrarEmpresa={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(/Buscar cliente ou empresa/), { target: { value: 'inexistente' } })
    await waitFor(() => expect(buscar).toHaveBeenCalled())
    expect(await screen.findByText('Nenhum cliente ou empresa encontrado.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Cadastrar empresa/ })).toBeNull()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run src/app/propostas/DestinatarioBusca.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implementar**

```tsx
// frontend/src/app/propostas/DestinatarioBusca.tsx
import { useEffect, useState } from 'react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { IconSearch } from '../../components/ui/icons'
import { formatarDocumento, soDigitos } from '../../lib/documento'
import { destinatariosApi, type DestinatarioResultado } from '../empresas/api'

const inputClass = 'w-full pl-9 px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-transparent transition-colors'

/** Termo que e' um documento completo digitado (so digitos e pontuacao). */
function documentoCompleto(termo: string): string | null {
  if (!/^[\d.\-/\s]+$/.test(termo)) return null
  const d = soDigitos(termo)
  return d.length === 11 || d.length === 14 ? d : null
}

export function DestinatarioBusca({ onEscolher, onCadastrarEmpresa }: {
  onEscolher: (r: DestinatarioResultado) => void
  onCadastrarEmpresa: (documento: string) => void
}) {
  const [termo, setTermo] = useState('')
  const [resultados, setResultados] = useState<DestinatarioResultado[] | null>(null)
  const [buscando, setBuscando] = useState(false)

  useEffect(() => {
    const q = termo.trim()
    if (q.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResultados(null)
      return
    }
    let vivo = true
    setBuscando(true)
    destinatariosApi.buscar(q)
      .then((r) => { if (vivo) setResultados(r) })
      .catch(() => { if (vivo) setResultados([]) })
      .finally(() => { if (vivo) setBuscando(false) })
    return () => { vivo = false }
  }, [termo])

  const documento = documentoCompleto(termo)

  return (
    <div className="relative">
      <span className="absolute left-3 top-2.5 text-slate-500 pointer-events-none"><IconSearch className="w-4 h-4" /></span>
      <input value={termo} onChange={(e) => setTermo(e.target.value)} className={inputClass}
        placeholder="Buscar cliente ou empresa por nome, CNPJ ou CPF" />
      {buscando && <p className="mt-1 text-xs text-slate-500">Buscando…</p>}
      {!buscando && resultados && resultados.length > 0 && (
        <ul className="mt-1.5 divide-y divide-border rounded-lg border border-border overflow-hidden max-h-60 overflow-y-auto">
          {resultados.map((r) => (
            <li key={`${r.tipo}-${r.id}`}>
              <button type="button" onClick={() => onEscolher(r)}
                className="w-full text-left px-3 py-2.5 text-sm hover:bg-background-elevated transition-colors">
                <span className="flex items-center gap-2">
                  <span className="font-semibold text-slate-200">{r.nome ?? `#${r.id}`}</span>
                  <Badge tone={r.tipo === 'cliente' ? 'primary' : 'info'}>
                    {r.tipo === 'cliente' ? 'Cliente' : r.matriz_nome ? `Empresa · matriz ${r.matriz_nome}` : 'Empresa · sem matriz'}
                  </Badge>
                </span>
                <span className="block text-xs text-slate-500">
                  {formatarDocumento(r.documento)}{r.municipio ? ` · ${r.municipio}/${r.estado ?? ''}` : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {!buscando && resultados && resultados.length === 0 && (
        <div className="mt-1.5 flex flex-wrap items-center gap-3">
          <p className="text-xs text-slate-500">Nenhum cliente ou empresa encontrado.</p>
          {documento && (
            <Button type="button" variant="secondary" onClick={() => onCadastrarEmpresa(documento)}>
              Cadastrar empresa com este documento
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npx vitest run src/app/propostas/DestinatarioBusca.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/propostas/DestinatarioBusca.tsx frontend/src/app/propostas/DestinatarioBusca.test.tsx
git commit -m "feat(propostas): busca unica de destinatario com cadastro de empresa"
```

---
### Task 16: Modal da proposta com destinatário

**Files:**
- Modify: `frontend/src/app/propostas/PropostaModal.tsx`, `frontend/src/app/propostas/PropostaModal.test.tsx`

**Interfaces:**
- Consumes: `DestinatarioBusca` (Task 15); `DadosEmpresaForm` (Task 11); `MatrizSelect`, `MatrizValor` (Task 12); `Selecao`, `clienteDaFrota`, `montarDestinatario`, `descreverSelecao` (Task 14); `validarProposta`, `camposObrigatoriosFaltando`, `ROTULO_CONTATO` (Task 14); `dadosDeCliente`, `dadosDeEmpresa`, `dadosVazios`, `sugestoesDeCliente`, `sugestoesDeEmpresa`, `OBRIGATORIOS_PROPOSTA`, `DadosEmpresa` (Task 10); `empresasApi`, `destinatariosApi`, `DestinatarioResultado` (Task 10).
- Produces: nada novo para outras tasks; o modal passa a enviar `destinatario` e deixa de enviar `cliente`/`cliente_override`.

Esta task **substitui trechos** de `PropostaModal.tsx`. As outras seções do modal (introdução, lista de aparelhos, itens, condições, observações, assinatura) ficam como estão, trocando apenas `form.cliente != null` por `frotaClienteId != null` onde aparecer.

- [ ] **Step 1: Reescrever os testes do modal que tocam o cliente**

Em `frontend/src/app/propostas/PropostaModal.test.tsx`:

1. **Mocks**: remover o mock de `./buscaEndereco` (as lupas agora são testadas em `DadosEmpresaForm.test.tsx`). Acrescentar:

```tsx
const destinatariosBuscar = vi.fn()
const empresasObter = vi.fn()
vi.mock('../empresas/api', () => ({
  destinatariosApi: { buscar: (...a: unknown[]) => destinatariosBuscar(...a) },
  empresasApi: { obter: (...a: unknown[]) => empresasObter(...a) },
}))
```

2. **Fixtures**: em `PROPOSTA_BASE`, trocar `cliente_override: null` por `empresa: null, destinatario: null`. Acrescentar:

```tsx
const RESULTADO_CLIENTE = { tipo: 'cliente', id: 5, nome: 'Cliente Teste', documento: '36312056000552', municipio: 'Recife', estado: 'PE', matriz_id: null, matriz_nome: null }
const EMPRESA = {
  id: 9, cliente: 5, matriz_nome: 'Cliente Teste', nome: 'Filial Norte', cgc: '11222333000181', cpf: null,
  cep: '29680000', endereco: 'BR 101', numero: 'S/N', complemento: null, bairro: 'Zona Rural',
  municipio: 'Joao Neiva', estado: 'ES', email: 'filial@teste.com', telefone: '2733330000', insc_est: null,
  ativo: true, created_at: null, updated_at: null,
}
const RESULTADO_EMPRESA = { tipo: 'empresa', id: 9, nome: 'Filial Norte', documento: '11222333000181', municipio: 'Joao Neiva', estado: 'ES', matriz_id: 5, matriz_nome: 'Cliente Teste' }
```

3. **`beforeEach`**: acrescentar `destinatariosBuscar.mockResolvedValue([RESULTADO_CLIENTE])` e `empresasObter.mockResolvedValue(EMPRESA)`.

4. **Helper** `selecionarCliente` passa a ser:

```tsx
const BUSCA = /Buscar cliente ou empresa/

async function selecionarCliente() {
  fireEvent.change(screen.getByPlaceholderText(BUSCA), { target: { value: 'Cliente' } })
  fireEvent.click(await screen.findByRole('button', { name: /Cliente Teste/ }))
  await screen.findByLabelText('Bafômetro X')
}
```

e todo `screen.getByPlaceholderText('Buscar cliente por nome, CNPJ ou CPF')` do arquivo vira `screen.getByPlaceholderText(BUSCA)`; todo `findByText('Cliente Teste')` usado para **escolher** o resultado vira `findByRole('button', { name: /Cliente Teste/ })`.

5. **Apagar** os testes que só existem por causa do override (o comportamento sumiu):
   - no `describe('PropostaModal')`: `REPRO proposta 99...`, `reabrir uma proposta com override...`, `campo herdado do cadastro fica marcado...`, `override de documento nasce mascarado...`, `nao mexer em campo nenhum nao grava override`, `proposta antiga com override redundante...`, `cliente sem CNPJ/CPF no cadastro bloqueia...` (o documento do cliente agora é travado);
   - o `describe('PropostaModal — painel do cliente sempre visivel')` inteiro;
   - o `describe('PropostaModal — busca de CEP e CNPJ')` inteiro.

6. **Ajustar** `ao editar uma proposta existente, o campo Introdução vem pré-preenchido`: a fixture já tem `cliente: 5`; garantir `clientesObter` resolvido (já está no `beforeEach`).

7. **Acrescentar** um `describe` novo:

```tsx
describe('PropostaModal — destinatario', () => {
  it('cliente escolhido abre os dados preenchidos, documento travado e e-mail vazio com sugestao', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    expect((screen.getByLabelText(/Razão social/) as HTMLInputElement).value).toBe('Cliente Teste')
    expect((screen.getByLabelText(/CNPJ \/ CPF/) as HTMLInputElement).readOnly).toBe(true)
    expect((screen.getByLabelText('E-mail *') as HTMLInputElement).value).toBe('')
    expect(screen.getByRole('button', { name: 'Usar do cadastro: cliente@teste.com' })).toBeInTheDocument()
    expect(screen.getByText(/atualizam o cadastro de Cliente Teste/)).toBeInTheDocument()
  })

  it('salvar envia o destinatario cliente e nao envia cliente nem override', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    fireEvent.change(screen.getByLabelText(/Bairro/), { target: { value: 'Boa Vista' } })
    preencherObrigatorios()
    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))
    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    const payload = propostasCriar.mock.calls[0][0]
    expect(payload.destinatario).toMatchObject({
      tipo: 'cliente', id: 5, documento: null, bairro: 'Boa Vista', email: 'cliente@teste.com', telefone: '8130001111',
    })
    expect(payload).not.toHaveProperty('cliente')
    expect(payload).not.toHaveProperty('cliente_override')
    expect(payload.contato).toBe('Joana')
  })

  it('empresa escolhida carrega a frota da matriz', async () => {
    destinatariosBuscar.mockResolvedValue([RESULTADO_EMPRESA])
    render(<PropostaModal onClose={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(BUSCA), { target: { value: 'Filial' } })
    fireEvent.click(await screen.findByRole('button', { name: /Filial Norte/ }))
    await screen.findByLabelText('Bafômetro X')
    expect(frotaDoClienteMock).toHaveBeenCalledWith(5)
    expect(screen.getByText('Empresa · matriz Cliente Teste')).toBeInTheDocument()
  })

  it('documento sem resultado cadastra empresa nova com a matriz escolhida', async () => {
    destinatariosBuscar.mockResolvedValue([])
    render(<PropostaModal onClose={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(BUSCA), { target: { value: '11.222.333/0001-81' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Cadastrar empresa com este documento' }))
    expect((screen.getByLabelText(/CNPJ \/ CPF/) as HTMLInputElement).readOnly).toBe(false)
    expect(screen.queryByLabelText('Bafômetro X')).toBeNull()        // sem matriz, sem frota
    fireEvent.change(screen.getByLabelText(/Razão social/), { target: { value: 'Filial Nova' } })
    fireEvent.change(screen.getByLabelText(/^CEP/), { target: { value: '29680000' } })
    fireEvent.change(screen.getByLabelText(/Endereço \*/), { target: { value: 'BR 101' } })
    fireEvent.change(screen.getByLabelText(/Município/), { target: { value: 'Joao Neiva' } })
    fireEvent.change(screen.getByLabelText(/Estado/), { target: { value: 'ES' } })
    preencherObrigatorios()
    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))
    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    expect(propostasCriar.mock.calls[0][0].destinatario).toMatchObject({
      tipo: 'nova_empresa', id: null, matriz: null, documento: '11222333000181', nome: 'Filial Nova',
    })
  })

  it('409 ao cadastrar empresa oferece usar o cadastro existente', async () => {
    destinatariosBuscar.mockResolvedValueOnce([]).mockResolvedValue([RESULTADO_EMPRESA])
    propostasCriar.mockRejectedValueOnce(new ApiError(409, 'Documento já cadastrado como Empresa: Filial Norte'))
    render(<PropostaModal onClose={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(BUSCA), { target: { value: '11222333000181' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Cadastrar empresa com este documento' }))
    fireEvent.change(screen.getByLabelText(/Razão social/), { target: { value: 'X' } })
    fireEvent.change(screen.getByLabelText(/^CEP/), { target: { value: '29680000' } })
    fireEvent.change(screen.getByLabelText(/Endereço \*/), { target: { value: 'BR 101' } })
    fireEvent.change(screen.getByLabelText(/Município/), { target: { value: 'Joao Neiva' } })
    fireEvent.change(screen.getByLabelText(/Estado/), { target: { value: 'ES' } })
    preencherObrigatorios('filial@teste.com')
    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))
    fireEvent.click(await screen.findByRole('button', { name: 'Usar este cadastro' }))
    await waitFor(() => expect(empresasObter).toHaveBeenCalledWith(9))
    expect((await screen.findByLabelText(/Razão social/) as HTMLInputElement).value).toBe('Filial Norte')
    expect((screen.getByLabelText('E-mail *') as HTMLInputElement).value).toBe('filial@teste.com')   // o digitado fica
  })

  it('trocar destinatario limpa selecao e aparelhos', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    fireEvent.click(screen.getByLabelText('Bafômetro X'))
    fireEvent.click(screen.getByRole('button', { name: 'Trocar destinatário' }))
    expect(screen.getByPlaceholderText(BUSCA)).toBeInTheDocument()
    expect(screen.queryByLabelText('Bafômetro X')).toBeNull()
  })

  it('editar proposta de empresa carrega a empresa atual', async () => {
    propostasObter.mockResolvedValue({ ...PROPOSTA_BASE, empresa: 9, cliente: 5 })
    render(<PropostaModal propostaId={900} onClose={vi.fn()} />)
    expect((await screen.findByLabelText(/Razão social/) as HTMLInputElement).value).toBe('Filial Norte')
    expect(empresasObter).toHaveBeenCalledWith(9)
    expect(clientesObter).not.toHaveBeenCalled()
  })

  it('submeter sem destinatario nao cria proposta', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))
    expect(await screen.findByText('Escolha o destinatário antes de salvar a proposta.')).toBeInTheDocument()
    expect(propostasCriar).not.toHaveBeenCalled()
  })
})
```

> O teste antigo `submeter sem cliente nao cria proposta e mostra erro` é substituído pelo último acima — apague o antigo.

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run src/app/propostas/PropostaModal.test.tsx`
Expected: FAIL (placeholder novo inexistente etc.).

- [ ] **Step 3: Imports e constantes**

No topo de `PropostaModal.tsx`:
- Remover os imports de `Select`, `mascararCEP`, `clientesApi`'s `ClienteListItem`, `camposObrigatoriosFaltando`/`CAMPOS_OBRIGATORIOS` antigos, todo o bloco de `./clienteOverride` e todo o bloco de `./buscaEndereco`.
- Remover as constantes `UFS` e o componente `ComLupa` (foram para `DadosEmpresaForm`).
- Acrescentar:

```tsx
import { clientesApi, type Cliente } from '../clientes/api'
import { empresasApi, destinatariosApi, type DestinatarioResultado, type Empresa } from '../empresas/api'
import {
  dadosDeCliente, dadosDeEmpresa, dadosVazios, OBRIGATORIOS_PROPOSTA, sugestoesDeCliente, sugestoesDeEmpresa,
  type DadosEmpresa,
} from '../empresas/dadosEmpresa'
import { DadosEmpresaForm } from '../empresas/DadosEmpresaForm'
import { MatrizSelect } from '../empresas/MatrizSelect'
import { DestinatarioBusca } from './DestinatarioBusca'
import { clienteDaFrota, descreverSelecao, montarDestinatario, type Selecao } from './destinatario'
import { camposObrigatoriosFaltando, htmlTemTexto, ROTULO_CONTATO, validarProposta } from './validacao'
```

- Em `EMPTY_FORM`: remover `cliente: null,` e `cliente_override: null,`.

- [ ] **Step 4: Estado**

Substituir os blocos `// ─── Cliente ───` e `// ─── Dados do cliente nesta proposta ───` (da declaração de `clienteSelecionado` até `draftAnterior`, mantendo o bloco de Frota/Aparelhos entre eles) por:

```tsx
  // ─── Destinatario ─────────────────────────────────────────────────────
  // Os dados editados aqui ATUALIZAM o cadastro de origem (Cliente/Empresa) ao
  // salvar — nao existe mais "dados so nesta proposta". A proposta guarda uma
  // copia congelada, montada pelo servidor.
  const [selecao, setSelecao] = useState<Selecao | null>(null)
  const [dados, setDados] = useState<DadosEmpresa>(dadosVazios())
  const [carregandoDestinatario, setCarregandoDestinatario] = useState(false)
  /** Ultimo Cliente escolhido: vira a matriz sugerida de uma empresa nova. */
  const [ultimoCliente, setUltimoCliente] = useState<Cliente | null>(null)
  /** Cadastro existente com o documento recusado (409) — oferece "Usar este cadastro". */
  const [conflito, setConflito] = useState<DestinatarioResultado | null>(null)
  // Marca em vermelho os obrigatorios em branco, mas so depois da primeira
  // tentativa de salvar: campo vazio ainda nao visitado nao e' erro.
  const [tentouSalvar, setTentouSalvar] = useState(false)
  const frotaClienteId = clienteDaFrota(selecao)
  const frotaAnteriorRef = useRef<number | null | undefined>(undefined)
```

(Remover `clienteAnteriorRef`.)

- [ ] **Step 5: Carregar destinatário de proposta existente e da duplicação**

Acrescentar, antes do efeito "Carrega proposta existente":

```tsx
  // ─── Destinatario de proposta ja salva (edicao/duplicacao) ────────────
  // Abre com o cadastro ATUAL, nao com a copia congelada: salvar refaz a copia.
  async function carregarDestinatario(p: { empresa: number | null; cliente: number | null }) {
    if (p.empresa == null && p.cliente == null) return
    setCarregandoDestinatario(true)
    try {
      if (p.empresa != null) {
        const empresa = await empresasApi.obter(p.empresa)
        setSelecao({ tipo: 'empresa', empresa })
        setDados(dadosDeEmpresa(empresa))
      } else if (p.cliente != null) {
        const cliente = await clientesApi.obter(p.cliente)
        setSelecao({ tipo: 'cliente', cliente })
        setUltimoCliente(cliente)
        setDados(dadosDeCliente(cliente))
      }
    } catch {
      setErro('Falha ao carregar os dados do destinatário')
    } finally {
      setCarregandoDestinatario(false)
    }
  }
```

Nos **dois** efeitos de carga (edição e duplicação), dentro do `.then((p) => { ... })`:
- no `setForm({...})`: remover `cliente: p.cliente,` e `cliente_override: p.cliente_override ?? null,`; trocar `contato: p.contato || String(p.cliente_override?.contato ?? '')` por `contato: p.contato ?? ''`;
- depois de `setEditorKey(...)`, acrescentar `void carregarDestinatario(p)`.

> A proposta antiga com o contato dentro do override perde o pré-preenchimento do "aos cuidados de" no modal; o PDF continua lendo o legado (Task 8). O campo é obrigatório, então quem reabrir digita de novo.

- [ ] **Step 6: Frota pelo cliente da frota**

**Apagar** o efeito "Busca de cliente" inteiro. Substituir o efeito "Carrega dados completos do cliente + frota ao trocar `form.cliente`" por:

```tsx
  // ─── Frota do cliente matriz ──────────────────────────────────────────
  // Muda com o destinatario: Cliente -> a propria frota; Empresa -> a da matriz.
  // Na primeira carga (edicao) os aparelhos salvos sao mantidos; numa troca de
  // verdade eles sao limpos, porque eram de outra frota.
  useEffect(() => {
    const anterior = frotaAnteriorRef.current
    frotaAnteriorRef.current = frotaClienteId
    if (anterior !== undefined && anterior !== null && anterior !== frotaClienteId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAparelhosSelecionados([])
      setBuscaAparelho('')
    }
    if (frotaClienteId == null) {
      setFrota(null)
      return
    }
    let vivo = true
    setCarregandoFrota(true)
    frotaDoCliente(frotaClienteId)
      .catch(() => [])
      .then((itensFrota) => { if (vivo) { setFrota(itensFrota); setCarregandoFrota(false) } })
    return () => { vivo = false }
  }, [frotaClienteId])
```

- [ ] **Step 7: Handlers**

Substituir o bloco `// ─── Cliente handlers ───` e todo o `// ─── Painel do cliente ───` (de `selecionarCliente` até `restaurarOverride`) por:

```tsx
  // ─── Destinatario handlers ────────────────────────────────────────────
  async function escolherDestinatario(r: DestinatarioResultado, manterContato?: { email: string; telefone: string }) {
    setConflito(null)
    setTentouSalvar(false)
    setCarregandoDestinatario(true)
    try {
      if (r.tipo === 'cliente') {
        const cliente = await clientesApi.obter(r.id)
        setSelecao({ tipo: 'cliente', cliente })
        setUltimoCliente(cliente)
        setDados({ ...dadosDeCliente(cliente), ...manterContato })
      } else {
        const empresa: Empresa = await empresasApi.obter(r.id)
        setSelecao({ tipo: 'empresa', empresa })
        setDados({ ...dadosDeEmpresa(empresa), ...manterContato })
      }
    } catch {
      setErro('Falha ao carregar os dados do destinatário')
    } finally {
      setCarregandoDestinatario(false)
    }
  }

  function cadastrarEmpresa(documento: string) {
    setConflito(null)
    setTentouSalvar(false)
    setSelecao({ tipo: 'nova_empresa', matriz: ultimoCliente ? { id: ultimoCliente.id, nome: ultimoCliente.nome } : null })
    setDados(dadosVazios(documento))
  }

  function trocarDestinatario() {
    setSelecao(null)
    setDados(dadosVazios())
    setConflito(null)
    setTentouSalvar(false)
  }

  const sugestoes = selecao?.tipo === 'cliente'
    ? sugestoesDeCliente(selecao.cliente)
    : selecao?.tipo === 'empresa' ? sugestoesDeEmpresa(selecao.empresa) : undefined
  const nomeDoCadastro = selecao?.tipo === 'cliente'
    ? selecao.cliente.nome
    : selecao?.tipo === 'empresa' ? selecao.empresa.nome : null
  const faltandoContato = tentouSalvar && camposObrigatoriosFaltando(dados, form.contato ?? '').includes(ROTULO_CONTATO)
```

(Remova do arquivo o que ficar sem uso: `overrideAtual`, `camposEditados`, `rascunhoConferido`, `obrigatoriosFaltando`, `rotuloCampo`, `herdadoDoCadastro`, `classeOverride`, `definirOverride`, `limparBusca`, `buscarPorCnpj`, `buscarPorCep`, `desfazerBusca`, `restaurarOverride` — o `npm run lint` aponta o que sobrar.)

- [ ] **Step 8: Submit**

Em `submeter`, trocar a chamada de validação por:

```tsx
    const problema = validarProposta({
      selecao,
      dados,
      contato: form.contato ?? '',
      outrosItens: form.outros_itens,
      carregando: carregandoDestinatario,
    })
```

No `payload`, remover `cliente_override: overrideAtual,` e acrescentar `destinatario: selecao ? montarDestinatario(selecao, dados) : null,`. O `...form` já não tem `cliente`.

Trocar o `catch` por:

```tsx
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar a proposta')
      // Documento de empresa nova ja existe: acha o cadastro para oferecer usa-lo.
      if (err instanceof ApiError && err.status === 409 && selecao?.tipo === 'nova_empresa') {
        const doc = soDigitos(dados.documento)
        const achados = await destinatariosApi.buscar(doc).catch(() => [])
        setConflito(achados.find((r) => soDigitos(r.documento) === doc) ?? null)
      }
    } finally {
```

- [ ] **Step 9: JSX da seção**

Substituir a `<Secao titulo="Cliente" ...>` do começo até **antes** do `<label ...>` do checkbox "Endereço de entrega diferente" por:

```tsx
          {/* ── Destinatário ── */}
          <Secao titulo="Destinatário" icon={<IconClientes className="w-3.5 h-3.5" />} primeira>
            {selecao == null ? (
              <DestinatarioBusca onEscolher={(r) => void escolherDestinatario(r)} onCadastrarEmpresa={cadastrarEmpresa} />
            ) : (
              <div className="space-y-3 rounded-lg border border-border bg-background-elevated/40 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-slate-100">{nomeDoCadastro ?? (dados.nome || 'Nova empresa')}</p>
                    <Badge tone={selecao.tipo === 'cliente' ? 'primary' : 'info'}>{descreverSelecao(selecao)}</Badge>
                  </div>
                  <Button type="button" variant="ghost" onClick={trocarDestinatario}>Trocar destinatário</Button>
                </div>
                <p className="text-xs text-slate-500">
                  {selecao.tipo === 'nova_empresa'
                    ? `Ao salvar a proposta, a empresa ${dados.nome || 'nova'} é cadastrada com estes dados.`
                    : `Alterações nestes dados atualizam o cadastro de ${nomeDoCadastro ?? ''}.`}
                  {' '}E-mail, telefone e contato são sempre conferidos a cada proposta.
                </p>
                {carregandoDestinatario ? (
                  <div className="flex justify-center py-6"><Spinner className="w-6 h-6" /></div>
                ) : (
                  <DadosEmpresaForm
                    dados={dados}
                    onChange={setDados}
                    documentoTravado={selecao.tipo !== 'nova_empresa'}
                    sugestoes={sugestoes}
                    obrigatorios={OBRIGATORIOS_PROPOSTA}
                    destacarFaltando={tentouSalvar}
                    idPrefixo="dest"
                  >
                    {selecao.tipo === 'nova_empresa' && (
                      <MatrizSelect valor={selecao.matriz} onChange={(matriz) => setSelecao({ tipo: 'nova_empresa', matriz })} />
                    )}
                    {/* "Aos cuidados de" e' coluna da PROPOSTA, nao do cadastro. */}
                    <div className="sm:col-span-2">
                      <Input
                        id="dest-contato"
                        label={`${ROTULO_CONTATO} *`}
                        value={form.contato ?? ''}
                        onChange={(e) => setField('contato', e.target.value)}
                        className={cn(faltandoContato && 'border-danger')}
                        placeholder="Nome do contato no cliente"
                      />
                    </div>
                  </DadosEmpresaForm>
                )}
                {conflito && (
                  <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warning/40 bg-warning/5 px-3 py-2 text-xs">
                    <span className="text-slate-300">
                      Este documento já é {conflito.tipo === 'cliente' ? 'do cliente' : 'da empresa'} <strong>{conflito.nome}</strong>.
                    </span>
                    <Button type="button" variant="secondary"
                      onClick={() => void escolherDestinatario(conflito, { email: dados.email, telefone: dados.telefone })}>
                      Usar este cadastro
                    </Button>
                  </div>
                )}
              </div>
            )}
```

(O checkbox de endereço de entrega e o fechamento `</Secao>` continuam como estão.)

Na seção de aparelhos, trocar `{form.cliente != null && (` por `{frotaClienteId != null && (`.

- [ ] **Step 10: Rodar os testes do modal**

Run: `npx vitest run src/app/propostas/PropostaModal.test.tsx`
Expected: PASS.

- [ ] **Step 11: Lint e tipos do módulo**

Run: `npm run lint && npx tsc -b --noEmit`
Expected: sem erros em `PropostaModal.tsx`. Erros restantes só em `PropostasPage.tsx` (resolvidos na Task 17).

- [ ] **Step 12: Commit**

```bash
git add frontend/src/app/propostas/PropostaModal.tsx frontend/src/app/propostas/PropostaModal.test.tsx
git commit -m "feat(propostas): modal escolhe cliente ou empresa e grava os dados no cadastro"
```

---
### Task 17: Listagem de propostas sem override

**Files:**
- Modify: `frontend/src/app/propostas/PropostasPage.tsx`, `frontend/src/app/propostas/PropostasPage.test.tsx`
- Delete: `frontend/src/app/propostas/clienteOverride.ts`, `frontend/src/app/propostas/clienteOverride.test.ts`, `frontend/src/app/propostas/OverrideDetalhe.tsx`

**Interfaces:**
- Consumes: `Proposta.empresa` (Task 14).

- [ ] **Step 1: Ajustar os testes**

Em `PropostasPage.test.tsx`:
- Na fixture `PROPOSTA`, trocar `cliente_override: null` por `empresa: null, destinatario: null`.
- Apagar os três testes do selo de override: `proposta sem dados editados nao mostra o selo`, `selo "Dados editados" abre o comparativo cadastro x proposta` e `override que repete o cadastro aparece marcado como igual`. Se o mock de `../clientes/api` (`clientesObter`) ficar sem uso, remover.
- Acrescentar, no mesmo `describe` onde estavam:

```tsx
  it('proposta de empresa mostra o selo Filial', async () => {
    listar.mockResolvedValue({
      items: [{ ...PROPOSTA, empresa: 9, cliente_nome: 'Filial Norte' }],
      total: 1, page: 1, page_size: 25, total_pages: 1,
    })
    render(<PropostasPage />)
    await screen.findByText('#42')
    expect(screen.getByText('Filial Norte')).toBeInTheDocument()
    expect(screen.getByText('Filial')).toBeInTheDocument()
  })

  it('proposta de cliente nao mostra o selo Filial', async () => {
    render(<PropostasPage />)
    await screen.findByText('#42')
    expect(screen.queryByText('Filial')).not.toBeInTheDocument()
  })
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run src/app/propostas/PropostasPage.test.tsx`
Expected: FAIL (selo inexistente).

- [ ] **Step 3: Implementar**

Em `PropostasPage.tsx`:
- Remover os imports de `OverrideDetalheModal` e `temOverride`, o estado `overrideDe`/`setOverrideDe` e o bloco `{overrideDe && (<OverrideDetalheModal ... />)}`.
- Na célula do cliente, trocar o `<button>` "Dados editados" por:

```tsx
                  {p.empresa != null && <span className="mt-1 inline-block"><Badge tone="info">Filial</Badge></span>}
```

- Se `IconPencil` ficar sem uso, remover do import.

Apagar os arquivos:

```bash
git rm frontend/src/app/propostas/clienteOverride.ts frontend/src/app/propostas/clienteOverride.test.ts frontend/src/app/propostas/OverrideDetalhe.tsx
```

- [ ] **Step 4: Verificação completa do frontend**

Run (em `frontend/`): `npm run lint && npx tsc -b --noEmit && npm run build && npm test`
Expected: lint/tsc/build limpos; testes só com as falhas da baseline (Task 0). Qualquer referência restante a `cliente_override`, `clienteOverride` ou `propostas/buscaEndereco` aparece aqui — corrigir.

Conferência final de sobras:

```bash
grep -rn "cliente_override\|clienteOverride\|OverrideDetalhe\|propostas/buscaEndereco" src || echo "limpo"
```
Expected: `limpo`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/propostas/PropostasPage.tsx frontend/src/app/propostas/PropostasPage.test.tsx
git commit -m "refactor(propostas): remove o override da listagem e marca proposta de filial"
```

---

### Task 18: Documentação, changelog e verificação final

**Files:**
- Create: `docs/operacao-empresas-migracao.md`
- Modify: `CLAUDE.md`, `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Doc de operação**

```markdown
# Operação: Empresas e migração das propostas antigas

Entrega v1.53.0 (set/2026). A proposta passa a ter como destinatário um Cliente ou uma
Empresa (filial), e os dados editados no modal gravam no cadastro. Cada proposta guarda uma
cópia congelada (`propostas.destinatario`); `cliente_override` fica congelado.

## Ordem em produção

1. **Deploy** da branch já na `main`.
2. **Migração** `0030_empresas` (só DDL): `alembic upgrade head`. Cria `empresas` e as colunas
   `propostas.empresa` e `propostas.destinatario`. Não mexe em dado nenhum.
   Até o passo 4, proposta antiga sem cópia é exibida exatamente como antes (cadastro +
   override), então não há janela de PDF quebrado.
3. **Simular** a migração das propostas:
   `python -m app.scripts.migrar_filiais_propostas`
   Esperado na base de 15/09/2026: ~258 propostas a congelar, ~14 empresas a criar, 15
   propostas a ligar. Conferir a lista de **RECUSADOS** (documento que já é de um Cliente —
   decidir à mão se aquela proposta deveria apontar para o cliente) e de **INVALIDOS**
   (documento com dígito errado ou override sem nome — ficam só congeladas).
4. **Gravar**: `python -m app.scripts.migrar_filiais_propostas --aplicar`. Idempotente.

## Voltar a versão (downgrade)

`alembic downgrade 0029_notas_fiscais` apaga `empresas` e as duas colunas novas. Proposta
criada ou salva **depois** da 0030 não tem override: sem a cópia, o PDF dela volta a sair só
com o cadastro do cliente (e a de filial sai com os dados da matriz). Antes de voltar, liste
essas propostas (`updated_at` depois do deploy) e avise o comercial.

## Regras que não estão óbvias no código

- Documento é único **somando** clientes e empresas. Do lado do cadastro de Clientes a trava
  só olha Empresas: duplicata antiga entre clientes não pode travar edição.
- `unificar_clientes` reaponta `empresas.cliente` junto com as outras FKs de `clientes`.
- Telefone editado pela proposta grava em `clientes.telefones`; celular e WhatsApp não mudam.
- `clientes.numero` é inteiro: "S/N" digitado na proposta vira nulo no cliente (a Empresa
  guarda o texto).
```

- [ ] **Step 2: `CLAUDE.md`**

Na seção de comandos do backend, depois da linha de `renumerar_patrimonios`:

```
python -m app.scripts.migrar_filiais_propostas                     # SIMULA: congela propostas antigas e cria filiais (--aplicar grava)
```

Na seção "Arquitetura", logo depois de "Exportação para Excel", acrescentar:

```markdown
### Empresas e destinatário da proposta
**Empresa** é uma filial: só dados cadastrais, com matriz **opcional** em `empresas.cliente` — os aparelhos da proposta vêm da frota da matriz. A proposta tem como destinatário um Cliente (`propostas.cliente`) **ou** uma Empresa (`propostas.empresa`, e aí `cliente` é a matriz dela).

- **Não existe mais "dados só nesta proposta".** O modal manda um bloco `destinatario` e o servidor, na mesma transação, grava no cadastro de origem (ou cria a Empresa), acerta as FKs, valida os aparelhos contra a frota e congela a cópia. Núcleo puro em [app/core/empresa.py](backend/app/core/empresa.py).
- ⚠️ **`propostas.destinatario` é a cópia congelada e só o servidor escreve.** O PDF lê dela; proposta antiga ainda sem cópia cai em `destinatario_legado` (cadastro + override), que reproduz o PDF de antes.
- ⚠️ **`propostas.cliente_override` está CONGELADA**, como as colunas legadas de nota fiscal: nenhum caminho novo escreve nela.
- **Documento único somando `clientes` e `empresas`** (`checar_documento_livre`); do lado de Clientes a trava só olha Empresas.
- **Documento de cadastro existente não muda pela proposta** — o servidor ignora; corrige-se na página de Clientes/Empresas.
- Procedimento de produção em [docs/operacao-empresas-migracao.md](docs/operacao-empresas-migracao.md).
```

No trecho do `unificar_clientes` que fala em **13 colunas**, trocar para **14 colunas**. Na seção "Migrações Alembic", trocar `(0001–0029)` por `(0001–0030)` e acrescentar "e as empresas (filiais) com o destinatário da proposta (`0030`)".

- [ ] **Step 3: Changelog**

Em `frontend/src/app/changelog/data.ts`, nova primeira entrada de `CHANGELOG`:

```ts
  {
    versao: '1.53.0',
    data: 'DD/MM/2026', // data do merge
    itens: [
      { tipo: 'novidade', texto: 'Nova página Empresas, para cadastrar filiais: os dados da empresa e, se houver, o cliente matriz de onde vêm os aparelhos. A tela do cliente mostra as empresas vinculadas a ele.' },
      { tipo: 'novidade', texto: 'Na proposta, o destinatário pode ser um cliente ou uma empresa, numa busca só por nome, CNPJ ou CPF. Digitando um documento que ainda não existe, dá para cadastrar a empresa ali mesmo, sem sair da proposta.' },
      { tipo: 'melhoria', texto: 'Os dados da empresa editados na proposta agora ficam salvos no cadastro do cliente ou da empresa, e aparecem prontos na próxima proposta. O antigo "dados editados só nesta proposta" deixa de existir. Propostas já feitas continuam saindo com os dados da época.' },
      { tipo: 'melhoria', texto: 'As buscas por CEP e CNPJ passam a preencher número, complemento e bairro em campos separados.' },
    ],
  },
```

(Substituir `DD/MM/2026` pela data real do fechamento da release.)

- [ ] **Step 4: Verificação final**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -15
cd ../frontend && npm run lint && npx tsc -b --noEmit && npm run build && npm test 2>&1 | tail -15
```
Expected: backend e frontend só com as falhas da baseline da Task 0.

- [ ] **Step 5: Commits**

```bash
git add docs/operacao-empresas-migracao.md CLAUDE.md
git commit -m "docs: empresas, destinatario da proposta e operacao da migracao"
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.53.0 — empresas e destinatario da proposta sem override"
```

Merge na `main` e push **só quando o Erick pedir**, no formato `merge: empresas e destinatario da proposta (v1.53.0) — ...`, conferindo o remoto antes (`git fetch`).
