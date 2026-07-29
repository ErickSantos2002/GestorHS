# Campo CEP na proposta + busca por CEP e CNPJ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar o campo CEP aos dados do cliente na proposta e duas lupas (CEP e CNPJ) que consultam APIs públicas pelo backend e preenchem os campos automaticamente.

**Architecture:** O backend ganha dois endpoints GET autenticados (`/integracoes/cep/{cep}` e `/integracoes/cnpj/{cnpj}`) com a mesma separação já usada na integração do TaskHS: `core/enderecos.py` puro (validação, capitalização, mapeamento do JSON de cada provedor) e `integrations/enderecos_client.py` com o I/O `httpx` e o fallback BrasilAPI → ViaCEP. No frontend, `cep` entra na lista canônica de campos do override e a lógica de "qual campo cada busca preenche" fica pura em `buscaEndereco.ts`, deixando o `PropostaModal` só com a orquestração de UI.

**Tech Stack:** Backend Python 3.12 · FastAPI · httpx (já é dependência) · pytest com SQLite in-memory. Frontend React 19 · TS · Vitest + Testing Library.

## Global Constraints

- Spec de referência: `docs/superpowers/specs/2026-07-29-cep-cnpj-lookup-proposta-design.md`.
- Branch: `feat/cep-cnpj-proposta`. **Nunca use `git add -A`** — outro agente pode estar no mesmo repo; sempre liste os arquivos no `git add`.
- Commits em **português sem acentos** (ASCII), Conventional Commits, **assunto de uma linha só**, sem corpo e **sem trailer de co-autor**.
- Idioma do domínio é PT-BR: nomes de funções, variáveis e mensagens em português.
- **Nenhum teste pode tocar a internet.** Todo acesso HTTP é monkeypatched.
- **Sem migração Alembic** — `cliente_override` é JSON e `Cliente.cep` já existe.
- Verificação do frontend antes de commitar: `npm run lint && npx tsc -b --noEmit`.
- Backend: rodar `pytest -q` a partir de `backend/` com a venv ativa (`source .venv/bin/activate`).
- Formato de saída dos endpoints, fixo (não inventar campos): CEP → `{cep, endereco, municipio, estado}`; CNPJ → `{documento, nome, endereco, municipio, estado, cep, situacao}`.

---

### Task 1: `core/enderecos.py` — validação, capitalização e mapeadores puros

**Files:**
- Create: `backend/app/core/enderecos.py`
- Test: `backend/tests/test_enderecos.py`

**Interfaces:**
- Consumes: nada.
- Produces: `DocumentoInvalido`, `NaoEncontrado`, `ProvedorIndisponivel` (exceções); `so_digitos(v: str | None) -> str`; `validar_cep(cep: str) -> str`; `validar_cnpj(cnpj: str) -> str`; `capitalizar(texto: str | None) -> str`; `mapear_brasilapi_cep(dados: dict) -> dict`; `mapear_viacep(dados: dict) -> dict`; `mapear_brasilapi_cnpj(dados: dict) -> dict`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_enderecos.py`:

```python
import pytest

from app.core import enderecos


def test_validar_cep_aceita_com_e_sem_mascara():
    assert enderecos.validar_cep("50030-230") == "50030230"
    assert enderecos.validar_cep("50030230") == "50030230"


def test_validar_cep_rejeita_tamanho_errado():
    with pytest.raises(enderecos.DocumentoInvalido):
        enderecos.validar_cep("5003023")
    with pytest.raises(enderecos.DocumentoInvalido):
        enderecos.validar_cep("")


def test_validar_cnpj_aceita_com_e_sem_mascara():
    assert enderecos.validar_cnpj("36.312.056/0005-52") == "36312056000552"


def test_validar_cnpj_rejeita_tamanho_errado():
    with pytest.raises(enderecos.DocumentoInvalido):
        enderecos.validar_cnpj("36312056")


def test_capitalizar_texto_da_receita():
    assert enderecos.capitalizar("JOAO NEIVA") == "Joao Neiva"
    assert enderecos.capitalizar("ZONA RURAL") == "Zona Rural"


def test_capitalizar_deixa_conectivos_minusculos_menos_no_inicio():
    assert enderecos.capitalizar("CAIS DO APOLO") == "Cais do Apolo"
    assert enderecos.capitalizar("AVENIDA DAS AMERICAS") == "Avenida das Americas"


def test_capitalizar_preserva_siglas_e_tokens_com_digito():
    assert enderecos.capitalizar("BR 101") == "BR 101"
    assert enderecos.capitalizar("KM 196,5") == "KM 196,5"
    assert enderecos.capitalizar("CBF INDUSTRIA DE GUSA S/A") == "CBF Industria de Gusa S/A"


def test_capitalizar_e_idempotente_e_trata_vazio():
    assert enderecos.capitalizar("Cais do Apolo") == "Cais do Apolo"
    assert enderecos.capitalizar("") == ""
    assert enderecos.capitalizar(None) == ""


def test_mapear_brasilapi_cep():
    dados = {"cep": "50030230", "state": "PE", "city": "RECIFE",
             "neighborhood": "Recife", "street": "CAIS DO APOLO", "service": "open-cep"}
    assert enderecos.mapear_brasilapi_cep(dados) == {
        "cep": "50030230", "endereco": "Cais do Apolo", "municipio": "Recife", "estado": "PE",
    }


def test_mapear_viacep():
    dados = {"cep": "50030-230", "logradouro": "Cais do Apolo", "bairro": "Recife",
             "localidade": "Recife", "uf": "pe"}
    assert enderecos.mapear_viacep(dados) == {
        "cep": "50030230", "endereco": "Cais do Apolo", "municipio": "Recife", "estado": "PE",
    }


def test_mapear_viacep_com_erro_vira_nao_encontrado():
    with pytest.raises(enderecos.NaoEncontrado):
        enderecos.mapear_viacep({"erro": True})
    with pytest.raises(enderecos.NaoEncontrado):
        enderecos.mapear_viacep({"erro": "true"})


def test_mapear_brasilapi_cnpj_monta_endereco_completo():
    dados = {
        "cnpj": "36312056000552", "razao_social": "CBF INDUSTRIA DE GUSA S/A",
        "logradouro": "BR 101", "numero": "S/N", "complemento": "KM 196,5",
        "bairro": "ZONA RURAL", "municipio": "JOAO NEIVA", "uf": "ES", "cep": "29680000",
        "descricao_situacao_cadastral": "ATIVA",
    }
    assert enderecos.mapear_brasilapi_cnpj(dados) == {
        "documento": "36312056000552",
        "nome": "CBF Industria de Gusa S/A",
        "endereco": "BR 101, S/N KM 196,5",
        "municipio": "Joao Neiva",
        "estado": "ES",
        "cep": "29680000",
        "situacao": "ATIVA",
    }


def test_mapear_brasilapi_cnpj_sem_numero_nem_complemento():
    dados = {"cnpj": "36312056000552", "razao_social": "ACME LTDA",
             "logradouro": "RUA X", "numero": "", "complemento": None,
             "municipio": "RECIFE", "uf": "PE", "cep": "50030230",
             "descricao_situacao_cadastral": "ATIVA"}
    r = enderecos.mapear_brasilapi_cnpj(dados)
    assert r["endereco"] == "Rua X"
    assert r["nome"] == "Acme Ltda"


def test_mapear_brasilapi_cnpj_campos_ausentes_viram_string_vazia():
    r = enderecos.mapear_brasilapi_cnpj({"cnpj": "36312056000552"})
    assert r == {"documento": "36312056000552", "nome": "", "endereco": "",
                 "municipio": "", "estado": "", "cep": "", "situacao": ""}
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_enderecos.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core.enderecos'`

- [ ] **Step 3: Implementar**

Criar `backend/app/core/enderecos.py`:

```python
"""Consulta de CEP/CNPJ em APIs publicas: validacao de formato, normalizacao de
texto e mapeamento do JSON de cada provedor para o formato unico do GestorHS.

Puro, sem I/O — as chamadas HTTP vivem em app/integrations/enderecos_client.py.
"""
import re

# Conectivos que ficam minusculos no meio do nome ("Cais do Apolo").
_CONECTIVOS = {"de", "da", "do", "das", "dos", "e"}


class DocumentoInvalido(ValueError):
    """CEP/CNPJ fora do formato esperado. Checado ANTES de sair para a rede."""


class NaoEncontrado(Exception):
    """O provedor respondeu, mas nao conhece esse CEP/CNPJ."""


class ProvedorIndisponivel(Exception):
    """Falha de rede ou erro do provedor."""


def so_digitos(v) -> str:
    return re.sub(r"\D", "", str(v or ""))


def validar_cep(cep: str) -> str:
    d = so_digitos(cep)
    if len(d) != 8:
        raise DocumentoInvalido("CEP deve ter 8 digitos")
    return d


def validar_cnpj(cnpj: str) -> str:
    d = so_digitos(cnpj)
    if len(d) != 14:
        raise DocumentoInvalido("CNPJ deve ter 14 digitos")
    return d


def capitalizar(texto) -> str:
    """Converte o CAIXA ALTA da Receita para forma capitalizada.

    Preserva o que nao deve ser mexido: tokens com digito ("101", "196,5") e
    siglas de ate 3 caracteres em maiuscula ("BR", "KM", "CBF", "S/A").
    Conectivos ficam minusculos, exceto na primeira palavra.

    NAO restaura acentuacao — a fonte ja veio sem ela ("JOAO" -> "Joao").
    """
    if not texto:
        return ""
    saida = []
    for i, token in enumerate(str(texto).split()):
        if any(c.isdigit() for c in token):
            saida.append(token)
        elif i > 0 and token.lower() in _CONECTIVOS:
            saida.append(token.lower())
        elif len(token) <= 3 and token.isupper():
            saida.append(token)
        else:
            saida.append(token.capitalize())
    return " ".join(saida)


def mapear_brasilapi_cep(dados: dict) -> dict:
    return {
        "cep": so_digitos(dados.get("cep")),
        "endereco": capitalizar(dados.get("street")),
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
        "municipio": capitalizar(dados.get("localidade")),
        "estado": str(dados.get("uf") or "").upper(),
    }


def mapear_brasilapi_cnpj(dados: dict) -> dict:
    endereco = capitalizar(dados.get("logradouro"))
    numero = str(dados.get("numero") or "").strip()
    complemento = capitalizar(dados.get("complemento"))
    if numero:
        endereco = f"{endereco}, {numero}" if endereco else numero
    if complemento:
        endereco = f"{endereco} {complemento}".strip()
    return {
        "documento": so_digitos(dados.get("cnpj")),
        "nome": capitalizar(dados.get("razao_social")),
        "endereco": endereco,
        "municipio": capitalizar(dados.get("municipio")),
        "estado": str(dados.get("uf") or "").upper(),
        "cep": so_digitos(dados.get("cep")),
        "situacao": str(dados.get("descricao_situacao_cadastral") or "").upper(),
    }
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_enderecos.py -q`
Expected: PASS (14 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/enderecos.py backend/tests/test_enderecos.py
git commit -m "feat(enderecos): validacao, capitalizacao e mapeadores de CEP e CNPJ"
```

---

### Task 2: `integrations/enderecos_client.py` — httpx com fallback BrasilAPI → ViaCEP

**Files:**
- Create: `backend/app/integrations/enderecos_client.py`
- Test: `backend/tests/test_enderecos_client.py`

**Interfaces:**
- Consumes: de `app.core.enderecos` — `validar_cep`, `validar_cnpj`, `mapear_brasilapi_cep`, `mapear_viacep`, `mapear_brasilapi_cnpj`, `NaoEncontrado`, `ProvedorIndisponivel`, `DocumentoInvalido`.
- Produces: `buscar_cep(cep: str) -> dict`; `buscar_cnpj(cnpj: str) -> dict`. Ambas levantam `DocumentoInvalido`, `NaoEncontrado` ou `ProvedorIndisponivel`. Constantes `URL_BRASILAPI_CEP`, `URL_VIACEP`, `URL_BRASILAPI_CNPJ`, `TIMEOUT`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_enderecos_client.py`:

```python
"""Nenhum teste aqui toca a internet: httpx.get e' sempre monkeypatched."""
import httpx
import pytest

from app.core import enderecos
from app.integrations import enderecos_client


class RespostaFake:
    def __init__(self, status_code=200, dados=None):
        self.status_code = status_code
        self._dados = dados if dados is not None else {}

    def json(self):
        return self._dados


def _fingir(monkeypatch, roteador):
    """roteador: callable(url) -> RespostaFake, ou levanta para simular rede fora."""
    chamadas = []

    def _get(url, timeout=None):
        chamadas.append(url)
        return roteador(url)

    monkeypatch.setattr(enderecos_client.httpx, "get", _get)
    return chamadas


CEP_BRASILAPI = {"cep": "50030230", "state": "PE", "city": "RECIFE", "street": "CAIS DO APOLO"}
CEP_VIACEP = {"cep": "50030-230", "logradouro": "Cais do Apolo", "localidade": "Recife", "uf": "PE"}
ESPERADO_CEP = {"cep": "50030230", "endereco": "Cais do Apolo", "municipio": "Recife", "estado": "PE"}


def test_buscar_cep_usa_brasilapi_e_nao_chama_o_fallback(monkeypatch):
    chamadas = _fingir(monkeypatch, lambda url: RespostaFake(200, CEP_BRASILAPI))
    assert enderecos_client.buscar_cep("50030-230") == ESPERADO_CEP
    assert len(chamadas) == 1
    assert "brasilapi" in chamadas[0]


def test_buscar_cep_cai_no_viacep_quando_brasilapi_da_erro(monkeypatch):
    def roteador(url):
        if "brasilapi" in url:
            raise httpx.ConnectError("sem rede")
        return RespostaFake(200, CEP_VIACEP)

    chamadas = _fingir(monkeypatch, roteador)
    assert enderecos_client.buscar_cep("50030230") == ESPERADO_CEP
    assert len(chamadas) == 2
    assert "viacep" in chamadas[1]


def test_buscar_cep_cai_no_viacep_quando_brasilapi_da_404(monkeypatch):
    def roteador(url):
        return RespostaFake(404) if "brasilapi" in url else RespostaFake(200, CEP_VIACEP)

    chamadas = _fingir(monkeypatch, roteador)
    assert enderecos_client.buscar_cep("50030230") == ESPERADO_CEP
    assert len(chamadas) == 2


def test_buscar_cep_inexistente_nos_dois_levanta_nao_encontrado(monkeypatch):
    def roteador(url):
        return RespostaFake(404) if "brasilapi" in url else RespostaFake(200, {"erro": True})

    _fingir(monkeypatch, roteador)
    with pytest.raises(enderecos.NaoEncontrado):
        enderecos_client.buscar_cep("00000000")


def test_buscar_cep_com_os_dois_provedores_fora_levanta_indisponivel(monkeypatch):
    def roteador(url):
        raise httpx.ConnectError("sem rede")

    _fingir(monkeypatch, roteador)
    with pytest.raises(enderecos.ProvedorIndisponivel):
        enderecos_client.buscar_cep("50030230")


def test_buscar_cep_invalido_nao_sai_para_a_rede(monkeypatch):
    chamadas = _fingir(monkeypatch, lambda url: RespostaFake(200, CEP_BRASILAPI))
    with pytest.raises(enderecos.DocumentoInvalido):
        enderecos_client.buscar_cep("123")
    assert chamadas == []


def test_buscar_cnpj_mapeia_a_resposta(monkeypatch):
    dados = {"cnpj": "36312056000552", "razao_social": "ACME LTDA", "logradouro": "RUA X",
             "numero": "10", "municipio": "RECIFE", "uf": "PE", "cep": "50030230",
             "descricao_situacao_cadastral": "ATIVA"}
    chamadas = _fingir(monkeypatch, lambda url: RespostaFake(200, dados))
    r = enderecos_client.buscar_cnpj("36.312.056/0005-52")
    assert r["nome"] == "Acme Ltda"
    assert r["endereco"] == "Rua X, 10"
    assert r["situacao"] == "ATIVA"
    assert len(chamadas) == 1


def test_buscar_cnpj_404_levanta_nao_encontrado_sem_fallback(monkeypatch):
    chamadas = _fingir(monkeypatch, lambda url: RespostaFake(404))
    with pytest.raises(enderecos.NaoEncontrado):
        enderecos_client.buscar_cnpj("00000000000000")
    assert len(chamadas) == 1


def test_buscar_cnpj_erro_de_rede_levanta_indisponivel(monkeypatch):
    def roteador(url):
        raise httpx.ConnectError("sem rede")

    _fingir(monkeypatch, roteador)
    with pytest.raises(enderecos.ProvedorIndisponivel):
        enderecos_client.buscar_cnpj("36312056000552")


def test_buscar_cnpj_invalido_nao_sai_para_a_rede(monkeypatch):
    chamadas = _fingir(monkeypatch, lambda url: RespostaFake(200, {}))
    with pytest.raises(enderecos.DocumentoInvalido):
        enderecos_client.buscar_cnpj("123")
    assert chamadas == []
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_enderecos_client.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.integrations.enderecos_client'`

- [ ] **Step 3: Implementar**

Criar `backend/app/integrations/enderecos_client.py`:

```python
"""I/O das consultas de CEP/CNPJ em APIs publicas.

Sincrono e com erro que sobe, de proposito: o usuario esta esperando o resultado
na tela. Difere do taskhs_client, que e' best-effort e engole tudo.
"""
import logging

import httpx

from app.core import enderecos

logger = logging.getLogger(__name__)

TIMEOUT = 5
URL_BRASILAPI_CEP = "https://brasilapi.com.br/api/cep/v2/{cep}"
URL_VIACEP = "https://viacep.com.br/ws/{cep}/json/"
URL_BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"


def _get_json(url: str):
    """GET que devolve o JSON, None em 404 e levanta ProvedorIndisponivel no resto."""
    try:
        resp = httpx.get(url, timeout=TIMEOUT)
    except Exception as e:
        raise enderecos.ProvedorIndisponivel(str(e)) from e
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise enderecos.ProvedorIndisponivel(f"HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError as e:
        raise enderecos.ProvedorIndisponivel("resposta nao e JSON") from e


def buscar_cep(cep: str) -> dict:
    """BrasilAPI primeiro, ViaCEP como fallback — tanto para falha quanto para 404,
    porque a BrasilAPI agrega provedores que caem individualmente."""
    digitos = enderecos.validar_cep(cep)
    try:
        dados = _get_json(URL_BRASILAPI_CEP.format(cep=digitos))
        if dados is not None:
            return enderecos.mapear_brasilapi_cep(dados)
    except enderecos.ProvedorIndisponivel:
        logger.warning("BrasilAPI CEP indisponivel; tentando ViaCEP")
    dados = _get_json(URL_VIACEP.format(cep=digitos))
    if dados is None:
        raise enderecos.NaoEncontrado("CEP nao encontrado")
    return enderecos.mapear_viacep(dados)


def buscar_cnpj(cnpj: str) -> dict:
    """Sem fallback: a ReceitaWS limita a 3 req/min e daria mais erro do que ajuda."""
    digitos = enderecos.validar_cnpj(cnpj)
    dados = _get_json(URL_BRASILAPI_CNPJ.format(cnpj=digitos))
    if dados is None:
        raise enderecos.NaoEncontrado("CNPJ nao encontrado")
    return enderecos.mapear_brasilapi_cnpj(dados)
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_enderecos_client.py -q`
Expected: PASS (10 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrations/enderecos_client.py backend/tests/test_enderecos_client.py
git commit -m "feat(enderecos): cliente httpx com fallback brasilapi para viacep"
```

---

### Task 3: Endpoints `/integracoes/cep` e `/integracoes/cnpj`

**Files:**
- Create: `backend/app/api/integracoes_externas.py`
- Modify: `backend/app/main.py` (linha de import do `app.api` e a lista de `include_router`)
- Test: `backend/tests/test_integracoes_externas.py`

**Interfaces:**
- Consumes: `app.integrations.enderecos_client.buscar_cep` / `buscar_cnpj`; exceções de `app.core.enderecos`; `app.api.deps.get_current_usuario`.
- Produces: rotas `GET /integracoes/cep/{cep}` e `GET /integracoes/cnpj/{cnpj}`, ambas exigindo usuário interno. Objeto `router` (APIRouter com `prefix="/integracoes"`).

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_integracoes_externas.py`:

```python
import pytest

from app.core import enderecos

RESULTADO_CEP = {"cep": "50030230", "endereco": "Cais do Apolo",
                 "municipio": "Recife", "estado": "PE"}
RESULTADO_CNPJ = {"documento": "36312056000552", "nome": "Acme Ltda",
                  "endereco": "Rua X, 10", "municipio": "Recife", "estado": "PE",
                  "cep": "50030230", "situacao": "ATIVA"}


@pytest.fixture()
def fingir_busca(monkeypatch):
    """Troca as funcoes de I/O por fakes — o endpoint nunca sai para a rede."""
    import app.api.integracoes_externas as mod

    def _aplicar(*, cep=None, cnpj=None):
        if cep is not None:
            monkeypatch.setattr(mod.enderecos_client, "buscar_cep", cep)
        if cnpj is not None:
            monkeypatch.setattr(mod.enderecos_client, "buscar_cnpj", cnpj)

    return _aplicar


def test_consultar_cep_devolve_o_mapeamento(client_admin, fingir_busca):
    fingir_busca(cep=lambda v: RESULTADO_CEP)
    r = client_admin.get("/integracoes/cep/50030-230")
    assert r.status_code == 200
    assert r.json() == RESULTADO_CEP


def test_consultar_cnpj_devolve_o_mapeamento(client_admin, fingir_busca):
    fingir_busca(cnpj=lambda v: RESULTADO_CNPJ)
    r = client_admin.get("/integracoes/cnpj/36312056000552")
    assert r.status_code == 200
    assert r.json() == RESULTADO_CNPJ


def test_cep_invalido_vira_400(client_admin, fingir_busca):
    def _erro(v):
        raise enderecos.DocumentoInvalido("CEP deve ter 8 digitos")

    fingir_busca(cep=_erro)
    assert client_admin.get("/integracoes/cep/123").status_code == 400


def test_cep_inexistente_vira_404(client_admin, fingir_busca):
    def _erro(v):
        raise enderecos.NaoEncontrado("CEP nao encontrado")

    fingir_busca(cep=_erro)
    assert client_admin.get("/integracoes/cep/00000000").status_code == 404


def test_provedor_fora_vira_502(client_admin, fingir_busca):
    def _erro(v):
        raise enderecos.ProvedorIndisponivel("sem rede")

    fingir_busca(cnpj=_erro)
    r = client_admin.get("/integracoes/cnpj/36312056000552")
    assert r.status_code == 502
    assert "indispon" in r.json()["detail"]


def test_exige_autenticacao(client):
    assert client.get("/integracoes/cep/50030230").status_code == 401
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_integracoes_externas.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.integracoes_externas'`

- [ ] **Step 3: Criar o router**

Criar `backend/app/api/integracoes_externas.py`:

```python
"""Consultas a APIs publicas (CEP/CNPJ) usadas para preencher dados na proposta.

So para usuario interno — nao e' exposto ao portal do cliente. O valor do path
e' validado como digitos antes de compor a URL do provedor.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_usuario
from app.core import enderecos
from app.integrations import enderecos_client
from app.models import Usuario

router = APIRouter(prefix="/integracoes", tags=["integracoes"])


def _executar(fn, valor: str) -> dict:
    try:
        return fn(valor)
    except enderecos.DocumentoInvalido as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except enderecos.NaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except enderecos.ProvedorIndisponivel as e:
        raise HTTPException(status_code=502, detail="servico de consulta indisponivel") from e


@router.get("/cep/{cep}")
def consultar_cep(cep: str, _: Usuario = Depends(get_current_usuario)):
    return _executar(enderecos_client.buscar_cep, cep)


@router.get("/cnpj/{cnpj}")
def consultar_cnpj(cnpj: str, _: Usuario = Depends(get_current_usuario)):
    return _executar(enderecos_client.buscar_cnpj, cnpj)
```

- [ ] **Step 4: Registrar o router no `main.py`**

Em `backend/app/main.py`, adicionar `integracoes_externas` ao final da lista de nomes importados de `app.api` (a linha longa de `from app.api import ...`), e acrescentar a linha de registro logo depois de `app.include_router(logs_integracao.router)`:

```python
app.include_router(integracoes_externas.router)
```

- [ ] **Step 5: Rodar o teste e confirmar que passa**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_integracoes_externas.py -q`
Expected: PASS (6 testes)

- [ ] **Step 6: Rodar a suíte inteira do backend**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: PASS — nenhuma regressão. Anote o total de testes.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/integracoes_externas.py backend/app/main.py backend/tests/test_integracoes_externas.py
git commit -m "feat(integracoes): endpoints de consulta de CEP e CNPJ"
```

---

### Task 4: CEP no bloco de endereço do cliente no PDF

**Files:**
- Modify: `backend/app/core/proposta_pdf.py` (helper novo perto de `_fmt_documento:89`; bloco de dados do cliente `:355-400`)
- Test: `backend/tests/test_proposta_pdf.py`

**Interfaces:**
- Consumes: nada das tasks anteriores.
- Produces: helper `_fmt_cep(v) -> str` (privado do módulo) e a chave `cep` reconhecida em `cliente_override`.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar ao fim de `backend/tests/test_proposta_pdf.py`:

```python
def test_montar_html_mostra_cep_do_cadastro_na_linha_de_cidade():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", cgc="08857492000148", municipio="Recife",
                  estado="PE", cep="50030230")
    p = Proposta(id=1, numero=101)

    html = proposta_pdf.montar_html(p, cli)

    assert "Recife - PE — CEP: 50030-230" in html


def test_montar_html_usa_o_cep_do_override_quando_houver():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", municipio="Recife", estado="PE", cep="50030230")
    p = Proposta(id=2, numero=102, cliente_override={"cep": "01310100"})

    html = proposta_pdf.montar_html(p, cli)

    assert "CEP: 01310-100" in html
    assert "50030-230" not in html


def test_montar_html_sem_cep_nenhum_nao_emite_a_parte_de_cep():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", municipio="Recife", estado="PE", cep=None)
    p = Proposta(id=3, numero=103)

    html = proposta_pdf.montar_html(p, cli)

    assert "CEP:" not in html
    assert "Recife - PE" in html
```

**Nota:** `montar_html(proposta, cliente)` recebe os **objetos**, não `(db, id)` —
é assim que os testes já existentes neste arquivo funcionam, sem tocar o banco.
`Proposta(id=..., numero=...)` sem `cliente` é suficiente porque o cliente entra
como segundo argumento.

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_proposta_pdf.py -q -k cep`
Expected: FAIL — o CEP não aparece no HTML.

- [ ] **Step 3: Implementar o helper**

Em `backend/app/core/proposta_pdf.py`, logo depois de `_fmt_documento`:

```python
def _fmt_cep(v) -> str:
    """Formata CEP de 8 dígitos; mantém o original se não bater."""
    digitos = re.sub(r"\D", "", str(v or ""))
    return f"{digitos[:5]}-{digitos[5:]}" if len(digitos) == 8 else digitos
```

- [ ] **Step 4: Ler o CEP do cadastro e do override**

No bloco "Dados do cliente", declarar a variável junto das outras (perto de `cliente_cidade_estado = ""`):

```python
    cliente_cep = ""
```

Dentro do `if cliente:`, junto de `cliente_email = ...`:

```python
        cliente_cep = _fmt_cep(cliente.cep)
```

No bloco de override, junto dos demais `if ov.get(...)`:

```python
    if ov.get("cep"):
        cliente_cep = _fmt_cep(ov["cep"])
```

- [ ] **Step 5: Compor a linha de cidade/UF com o CEP**

Logo **depois** do bloco de override (antes de `aos_cuidados_esc = ...`), acrescentar:

```python
    # CEP entra na linha de cidade/UF — mesma convencao que o bloco de Entrega
    # deste PDF ja usa ("Municipio/UF — CEP: NNNNN-NNN").
    if cliente_cep:
        cliente_cidade_estado = (
            f"{cliente_cidade_estado} — CEP: {cliente_cep}"
            if cliente_cidade_estado else f"CEP: {cliente_cep}"
        )
```

- [ ] **Step 6: Rodar os testes e confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_proposta_pdf.py -q`
Expected: PASS — os três novos e todos os antigos.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/proposta_pdf.py backend/tests/test_proposta_pdf.py
git commit -m "feat(proposta): imprimir CEP do cliente no bloco de endereco do PDF"
```

---

### Task 5: `cep` como campo do override no frontend + máscara

**Files:**
- Modify: `frontend/src/lib/documento.ts`
- Modify: `frontend/src/app/propostas/clienteOverride.ts`
- Test: `frontend/src/lib/documento.test.ts`, `frontend/src/app/propostas/clienteOverride.test.ts`

**Interfaces:**
- Consumes: `soDigitos` de `lib/documento`; `Cliente` de `app/clientes/api`.
- Produces: `mascararCEP(v: string | null | undefined) -> string` em `lib/documento.ts`. Em `clienteOverride.ts`: `'cep'` dentro de `CAMPOS_OVERRIDE` (entre `'estado'` e `'email'`), `ROTULOS_OVERRIDE.cep === 'CEP'`, `valorDoCadastro('cep', cliente)`, e a nova `mesmoValorDoCadastro(campo: CampoOverride, valor: string, cliente?: Cliente | null) -> boolean`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `frontend/src/lib/documento.test.ts`:

```ts
import { mascararCEP } from './documento'

describe('mascararCEP', () => {
  it('mascara progressivamente e capa em 8 digitos', () => {
    expect(mascararCEP('50030')).toBe('50030')
    expect(mascararCEP('50030230')).toBe('50030-230')
    expect(mascararCEP('500302309999')).toBe('50030-230')
  })

  it('ignora o que nao e digito e trata vazio', () => {
    expect(mascararCEP('50030-230')).toBe('50030-230')
    expect(mascararCEP('')).toBe('')
    expect(mascararCEP(null)).toBe('')
  })
})
```

**Nota:** o arquivo já tem imports de `./documento` no topo — some `mascararCEP` ao import existente em vez de criar um segundo import.

Acrescentar a `frontend/src/app/propostas/clienteOverride.test.ts`:

```ts
import { mesmoValorDoCadastro } from './clienteOverride'

describe('cep como campo do override', () => {
  it('valorDoCadastro le o CEP do cliente sem mascara', () => {
    expect(valorDoCadastro('cep', { ...CLIENTE, cep: '50030-230' })).toBe('50030230')
    expect(valorDoCadastro('cep', { ...CLIENTE, cep: null })).toBe('')
  })

  it('camposAlterados formata o CEP dos dois lados', () => {
    const [c] = camposAlterados({ cep: '01310100' }, { ...CLIENTE, cep: '50030230' })
    expect(c.rotulo).toBe('CEP')
    expect(c.cadastro).toBe('50030-230')
    expect(c.proposta).toBe('01310-100')
    expect(c.mudou).toBe(true)
  })

  it('CEP com e sem mascara conta como igual ao cadastro', () => {
    const [c] = camposAlterados({ cep: '50030-230' }, { ...CLIENTE, cep: '50030230' })
    expect(c.mudou).toBe(false)
  })
})

describe('mesmoValorDoCadastro', () => {
  it('compara ignorando mascara em documento e cep', () => {
    expect(mesmoValorDoCadastro('documento', '36.312.056/0005-52', CLIENTE)).toBe(true)
    expect(mesmoValorDoCadastro('cep', '50030-230', { ...CLIENTE, cep: '50030230' })).toBe(true)
  })

  it('compara ignorando espacos em volta nos campos de texto', () => {
    expect(mesmoValorDoCadastro('nome', '  Cliente Teste  ', CLIENTE)).toBe(true)
    expect(mesmoValorDoCadastro('nome', 'Outro Nome', CLIENTE)).toBe(false)
  })

  it('sem cliente carregado nada e igual ao cadastro', () => {
    expect(mesmoValorDoCadastro('nome', 'Cliente Teste', null)).toBe(false)
  })
})
```

**Nota:** `CLIENTE`, `valorDoCadastro` e `camposAlterados` já existem no arquivo — reaproveite, e some `mesmoValorDoCadastro` ao import existente. Cada teste acima já passa o `cep` que precisa via spread, então a constante `CLIENTE` (que tem `cep: null`) não muda.

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd frontend && npx vitest run src/lib/documento.test.ts src/app/propostas/clienteOverride.test.ts`
Expected: FAIL — `mascararCEP` e `mesmoValorDoCadastro` não existem.

- [ ] **Step 3: Implementar `mascararCEP`**

Em `frontend/src/lib/documento.ts`, depois de `mascararCPF`:

```ts
/** Mascara progressiva de CEP para input (capa em 8 digitos). */
export function mascararCEP(v: string | null | undefined): string {
  const d = soDigitos(v).slice(0, 8)
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d
}
```

- [ ] **Step 4: Somar `cep` ao módulo de override**

Em `frontend/src/app/propostas/clienteOverride.ts`:

1. Importar `mascararCEP` junto de `formatarDocumento, soDigitos`.
2. Em `CAMPOS_OVERRIDE`, inserir `'cep'` **entre `'estado'` e `'email'`**:

```ts
export const CAMPOS_OVERRIDE = ['nome', 'documento', 'endereco', 'municipio', 'estado', 'cep', 'email', 'telefone', 'contato'] as const
```

3. Em `ROTULOS_OVERRIDE`, acrescentar `cep: 'CEP',` depois de `estado`.
4. Em `valorDoCadastro`, acrescentar o caso antes de `case 'email'`:

```ts
    case 'cep': return soDigitos(cliente.cep)
```

5. Trocar as duas funções locais de `camposAlterados` por helpers de módulo, para
   `mesmoValorDoCadastro` reusar exatamente a mesma regra (documento e CEP
   comparam só dígitos; o resto compara texto sem espaços nas pontas):

```ts
// Campos guardados como digitos puros — mascara e' so apresentacao.
const CAMPOS_DIGITOS = new Set<CampoOverride>(['documento', 'cep'])

function normalizarCampo(campo: CampoOverride, v: string): string {
  return CAMPOS_DIGITOS.has(campo) ? soDigitos(v) : v.trim()
}

function exibirCampo(campo: CampoOverride, v: string): string {
  if (campo === 'documento') return formatarDocumento(v)
  if (campo === 'cep') return mascararCEP(v)
  return v
}

/** true quando o valor digitado equivale ao que ja esta no cadastro. */
export function mesmoValorDoCadastro(campo: CampoOverride, valor: string, cliente?: Cliente | null): boolean {
  return normalizarCampo(campo, valor) === normalizarCampo(campo, valorDoCadastro(campo, cliente))
}
```

6. Dentro de `camposAlterados`, apagar as constantes locais `exibir` e
   `normalizar` e usar `exibirCampo`/`normalizarCampo`.

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `cd frontend && npx vitest run src/lib/documento.test.ts src/app/propostas/clienteOverride.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/documento.ts frontend/src/lib/documento.test.ts frontend/src/app/propostas/clienteOverride.ts frontend/src/app/propostas/clienteOverride.test.ts
git commit -m "feat(propostas): cep como campo do override e mascara de CEP"
```

---

### Task 6: Override grava só o que diverge do cadastro

**Files:**
- Modify: `frontend/src/app/propostas/PropostaModal.tsx` (função `salvarOverride`)
- Test: `frontend/src/app/propostas/PropostaModal.test.tsx`

**Interfaces:**
- Consumes: `mesmoValorDoCadastro` da Task 5.
- Produces: nenhuma API nova — muda o conteúdo gravado em `cliente_override`.

- [ ] **Step 1: Escrever o teste que falha**

Em `frontend/src/app/propostas/PropostaModal.test.tsx`, **substituir** o teste
`'override aplicado sem mudar nada avisa que os dados so foram fixados'` por:

```ts
  it('aplicar override sem mudar nada nao grava override', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()

    fireEvent.click(screen.getByLabelText('Editar dados nesta proposta'))
    fireEvent.click(screen.getByText('Aplicar'))

    // nada divergiu do cadastro: a proposta nao pode ficar marcada como editada
    expect(screen.queryByText(/Editados só nesta proposta/)).not.toBeInTheDocument()

    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))
    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    expect(propostasCriar.mock.calls[0][0].cliente_override).toBeNull()
  })
```

E no teste `'override de documento nasce mascarado com o CNPJ do cadastro e guarda so digitos'`,
acrescentar depois do `expect(payload.cliente_override.documento).toBe('12345678909')`:

```ts
    // so o campo que divergiu entra no override
    expect(Object.keys(payload.cliente_override)).toEqual(['documento'])
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd frontend && npx vitest run src/app/propostas/PropostaModal.test.tsx`
Expected: FAIL — hoje `salvarOverride` grava os 8 campos.

- [ ] **Step 3: Implementar**

Em `PropostaModal.tsx`, somar `mesmoValorDoCadastro` ao import de `./clienteOverride` e trocar `salvarOverride` por:

```tsx
  function salvarOverride() {
    const limpo: Record<string, string> = {}
    CAMPOS_OVERRIDE.forEach((k) => {
      const v = overrideDraft[k]
      if (v == null || v.trim() === '') return
      // Campo identico ao cadastro nao vira override: o painel abre
      // pre-preenchido, entao gravar tudo marcaria a proposta como
      // "Dados editados" sem nada divergir de fato.
      if (mesmoValorDoCadastro(k, v, clienteSelecionado)) return
      limpo[k] = v.trim()
    })
    setField('cliente_override', Object.keys(limpo).length ? limpo : null)
    setMostrarOverride(false)
  }
```

- [ ] **Step 4: Remover o aviso que ficou sem uso**

O ramo `'Dados do cliente fixados nesta proposta — hoje iguais ao cadastro.'`
não é mais alcançável (override sem divergência agora vira `null`). Trocar o
bloco do aviso por:

```tsx
            {temOverride && (
              <p className="text-xs font-medium text-warning">
                Editados só nesta proposta: {camposEditados.filter((c) => c.mudou).map((c) => c.rotulo).join(', ')}.
              </p>
            )}
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `cd frontend && npx vitest run src/app/propostas/`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/propostas/PropostaModal.tsx frontend/src/app/propostas/PropostaModal.test.tsx
git commit -m "fix(propostas): gravar no override so os campos que divergem do cadastro"
```

---

### Task 7: `buscaEndereco.ts` — cliente de API e regra de preenchimento

**Files:**
- Create: `frontend/src/app/propostas/buscaEndereco.ts`
- Test: `frontend/src/app/propostas/buscaEndereco.test.ts`

**Interfaces:**
- Consumes: `apiJson` e `ApiError` de `lib/api`; `CampoOverride` de `./clienteOverride`.
- Produces: `ResultadoCep`, `ResultadoCnpj`, `DraftOverride`, `Preenchimento`; `buscaApi.cep(cep: string): Promise<ResultadoCep>`; `buscaApi.cnpj(cnpj: string): Promise<ResultadoCnpj>`; `aplicarResultadoCep(draft, r): Preenchimento`; `aplicarResultadoCnpj(draft, r): Preenchimento`; `mensagemErroBusca(e: unknown, tipo: 'CEP' | 'CNPJ'): string`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `frontend/src/app/propostas/buscaEndereco.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { ApiError } from '../../lib/api'
import { aplicarResultadoCep, aplicarResultadoCnpj, mensagemErroBusca } from './buscaEndereco'

const CEP = { cep: '50030230', endereco: 'Cais do Apolo', municipio: 'Recife', estado: 'PE' }
const CNPJ = {
  documento: '36312056000552', nome: 'Acme Ltda', endereco: 'Rua X, 10',
  municipio: 'Recife', estado: 'PE', cep: '50030230', situacao: 'ATIVA',
}

describe('aplicarResultadoCep', () => {
  it('preenche endereco, municipio e estado', () => {
    const { draft, preenchidos } = aplicarResultadoCep({}, CEP)
    expect(draft).toEqual({ endereco: 'Cais do Apolo', municipio: 'Recife', estado: 'PE' })
    expect(preenchidos).toEqual(['endereco', 'municipio', 'estado'])
  })

  it('nao toca em nome, documento, telefone, email nem contato', () => {
    const antes = { nome: 'Filial', documento: '111', telefone: '81999', email: 'a@b.c', contato: 'Ana' }
    const { draft } = aplicarResultadoCep(antes, CEP)
    expect(draft.nome).toBe('Filial')
    expect(draft.documento).toBe('111')
    expect(draft.telefone).toBe('81999')
    expect(draft.email).toBe('a@b.c')
    expect(draft.contato).toBe('Ana')
  })

  it('sobrescreve valor ja preenchido', () => {
    const { draft } = aplicarResultadoCep({ municipio: 'Olinda' }, CEP)
    expect(draft.municipio).toBe('Recife')
  })

  it('campo vazio na resposta nao apaga o que ja existe', () => {
    const { draft, preenchidos } = aplicarResultadoCep({ municipio: 'Olinda' }, { ...CEP, municipio: '' })
    expect(draft.municipio).toBe('Olinda')
    expect(preenchidos).not.toContain('municipio')
  })
})

describe('aplicarResultadoCnpj', () => {
  it('preenche razao social, endereco, municipio, estado e cep', () => {
    const { draft, preenchidos } = aplicarResultadoCnpj({}, CNPJ)
    expect(draft).toEqual({
      nome: 'Acme Ltda', endereco: 'Rua X, 10', municipio: 'Recife', estado: 'PE', cep: '50030230',
    })
    expect(preenchidos).toEqual(['nome', 'endereco', 'municipio', 'estado', 'cep'])
  })

  it('nao sobrescreve telefone, email nem contato (dados da Receita sao velhos)', () => {
    const antes = { telefone: '8130001111', email: 'bom@cliente.com', contato: 'Ana' }
    const { draft } = aplicarResultadoCnpj(antes, CNPJ)
    expect(draft.telefone).toBe('8130001111')
    expect(draft.email).toBe('bom@cliente.com')
    expect(draft.contato).toBe('Ana')
  })

  it('nao altera o draft original (funcao pura)', () => {
    const antes = { municipio: 'Olinda' }
    aplicarResultadoCnpj(antes, CNPJ)
    expect(antes.municipio).toBe('Olinda')
  })
})

describe('mensagemErroBusca', () => {
  it('traduz os status conhecidos', () => {
    expect(mensagemErroBusca(new ApiError(404, 'x'), 'CNPJ')).toMatch(/não encontrado/i)
    expect(mensagemErroBusca(new ApiError(400, 'x'), 'CEP')).toMatch(/inválido/i)
    expect(mensagemErroBusca(new ApiError(502, 'x'), 'CEP')).toMatch(/indisponível/i)
  })

  it('erro desconhecido vira mensagem generica com o tipo', () => {
    expect(mensagemErroBusca(new Error('boom'), 'CEP')).toMatch(/Falha ao consultar o CEP/)
  })
})
```

**Nota:** `ApiError` é `constructor(status: number, message: string)` — confirmado em `frontend/src/lib/api.ts:22-29`.

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `cd frontend && npx vitest run src/app/propostas/buscaEndereco.test.ts`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Implementar**

Criar `frontend/src/app/propostas/buscaEndereco.ts`:

```ts
// Busca de dados publicos (CEP/CNPJ) para preencher o override da proposta.
// A regra de QUAL campo cada busca preenche mora aqui, pura e testavel; o
// PropostaModal so orquestra a UI.

import { apiJson, ApiError } from '../../lib/api'
import type { CampoOverride } from './clienteOverride'

export interface ResultadoCep {
  cep: string
  endereco: string
  municipio: string
  estado: string
}

export interface ResultadoCnpj extends ResultadoCep {
  documento: string
  nome: string
  situacao: string
}

export const buscaApi = {
  cep: (cep: string) => apiJson<ResultadoCep>(`/integracoes/cep/${encodeURIComponent(cep)}`),
  cnpj: (cnpj: string) => apiJson<ResultadoCnpj>(`/integracoes/cnpj/${encodeURIComponent(cnpj)}`),
}

export type DraftOverride = Partial<Record<CampoOverride, string>>

export interface Preenchimento {
  draft: DraftOverride
  preenchidos: CampoOverride[]
}

/** Campo vazio na resposta nao apaga o que ja estava preenchido. */
function aplicar(draft: DraftOverride, valores: DraftOverride): Preenchimento {
  const novo = { ...draft }
  const preenchidos: CampoOverride[] = []
  for (const [campo, valor] of Object.entries(valores) as [CampoOverride, string | undefined][]) {
    if (valor == null || valor.trim() === '') continue
    novo[campo] = valor
    preenchidos.push(campo)
  }
  return { draft: novo, preenchidos }
}

/** O CEP chega no nivel da rua — o numero continua sendo digitado a mao. */
export function aplicarResultadoCep(draft: DraftOverride, r: ResultadoCep): Preenchimento {
  return aplicar(draft, { endereco: r.endereco, municipio: r.municipio, estado: r.estado })
}

/**
 * O CNPJ traz endereco completo (logradouro + numero + complemento).
 * Telefone e e-mail ficam de fora de proposito: na Receita costumam estar
 * desatualizados, e sao justamente os que a Health Safety tem bons no cadastro.
 */
export function aplicarResultadoCnpj(draft: DraftOverride, r: ResultadoCnpj): Preenchimento {
  return aplicar(draft, {
    nome: r.nome, endereco: r.endereco, municipio: r.municipio, estado: r.estado, cep: r.cep,
  })
}

export function mensagemErroBusca(e: unknown, tipo: 'CEP' | 'CNPJ'): string {
  if (e instanceof ApiError) {
    if (e.status === 404) return `${tipo} não encontrado.`
    if (e.status === 400) return `${tipo} inválido.`
    if (e.status === 502) return 'Serviço de consulta indisponível. Tente de novo em instantes.'
  }
  return `Falha ao consultar o ${tipo}.`
}
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `cd frontend && npx vitest run src/app/propostas/buscaEndereco.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/propostas/buscaEndereco.ts frontend/src/app/propostas/buscaEndereco.test.ts
git commit -m "feat(propostas): modulo de busca de CEP e CNPJ com regra de preenchimento"
```

---

### Task 8: Campo CEP e as duas lupas no painel de override

**Files:**
- Modify: `frontend/src/app/propostas/PropostaModal.tsx`
- Test: `frontend/src/app/propostas/PropostaModal.test.tsx`

**Interfaces:**
- Consumes: `buscaApi`, `aplicarResultadoCep`, `aplicarResultadoCnpj`, `mensagemErroBusca`, `DraftOverride` (Task 7); `mascararCEP` e `soDigitos` de `lib/documento`; `ROTULOS_OVERRIDE` de `./clienteOverride`.
- Produces: UI. Botões com `aria-label` **exatos** (usados pelos testes): `"Buscar dados pelo CNPJ"` e `"Buscar endereço pelo CEP"`. Campo com `label="CEP"` e `id="ov-cep"`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar em `frontend/src/app/propostas/PropostaModal.test.tsx`.

Primeiro, no bloco de mocks do topo (junto dos outros `vi.mock`), acrescentar:

```ts
const buscarCep = vi.fn()
const buscarCnpj = vi.fn()
vi.mock('./buscaEndereco', async (orig) => {
  const real = await orig<typeof import('./buscaEndereco')>()
  return { ...real, buscaApi: { cep: (...a: unknown[]) => buscarCep(...a), cnpj: (...a: unknown[]) => buscarCnpj(...a) } }
})
```

Depois, os testes:

```ts
describe('PropostaModal — busca de CEP e CNPJ', () => {
  const RESULTADO_CNPJ = {
    documento: '36312056000552', nome: 'Acme Industria Ltda', endereco: 'Rua Nova, 10',
    municipio: 'Olinda', estado: 'PE', cep: '53000000', situacao: 'ATIVA',
  }
  const RESULTADO_CEP = {
    cep: '53000000', endereco: 'Rua Nova', municipio: 'Olinda', estado: 'PE',
  }

  async function abrirOverride() {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    fireEvent.click(screen.getByLabelText('Editar dados nesta proposta'))
  }

  it('lupa do CNPJ preenche razao social, endereco, municipio, estado e CEP', async () => {
    buscarCnpj.mockResolvedValue(RESULTADO_CNPJ)
    await abrirOverride()

    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))

    await waitFor(() => expect(buscarCnpj).toHaveBeenCalledWith('36312056000552'))
    expect((screen.getByLabelText('Razão social / Nome') as HTMLInputElement).value).toBe('Acme Industria Ltda')
    expect((screen.getByLabelText('Endereço') as HTMLInputElement).value).toBe('Rua Nova, 10')
    expect((screen.getByLabelText('Município') as HTMLInputElement).value).toBe('Olinda')
    expect((screen.getByLabelText('CEP') as HTMLInputElement).value).toBe('53000-000')
  })

  it('lupa do CNPJ nao altera telefone nem e-mail', async () => {
    buscarCnpj.mockResolvedValue(RESULTADO_CNPJ)
    await abrirOverride()
    const email = screen.getByLabelText('E-mail') as HTMLInputElement
    const antes = email.value

    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))
    await waitFor(() => expect(buscarCnpj).toHaveBeenCalled())

    expect(email.value).toBe(antes)
  })

  it('mostra os campos preenchidos e a situacao cadastral', async () => {
    buscarCnpj.mockResolvedValue(RESULTADO_CNPJ)
    await abrirOverride()

    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))

    expect(await screen.findByText(/Preenchido pelo CNPJ:/)).toBeInTheDocument()
    expect(screen.getByText(/Situação na Receita: ATIVA/)).toBeInTheDocument()
  })

  it('Desfazer restaura os valores anteriores a busca', async () => {
    buscarCnpj.mockResolvedValue(RESULTADO_CNPJ)
    await abrirOverride()
    const nome = screen.getByLabelText('Razão social / Nome') as HTMLInputElement
    const antes = nome.value

    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))
    await waitFor(() => expect(nome.value).toBe('Acme Industria Ltda'))

    fireEvent.click(screen.getByText('Desfazer'))

    expect(nome.value).toBe(antes)
    expect(screen.queryByText(/Preenchido pelo CNPJ:/)).not.toBeInTheDocument()
  })

  it('o painel abre com o CEP do cadastro ja preenchido', async () => {
    clientesObter.mockResolvedValue({ ...CLIENTE_COMPLETO, cep: '50030230' })
    await abrirOverride()
    expect((screen.getByLabelText('CEP') as HTMLInputElement).value).toBe('50030-230')
  })

  it('lupa do CEP preenche endereco, municipio e estado sem tocar no nome', async () => {
    buscarCep.mockResolvedValue(RESULTADO_CEP)
    await abrirOverride()
    const nome = screen.getByLabelText('Razão social / Nome') as HTMLInputElement
    const antes = nome.value

    fireEvent.change(screen.getByLabelText('CEP'), { target: { value: '53000-000' } })
    fireEvent.click(screen.getByLabelText('Buscar endereço pelo CEP'))

    await waitFor(() => expect(buscarCep).toHaveBeenCalledWith('53000000'))
    expect((screen.getByLabelText('Endereço') as HTMLInputElement).value).toBe('Rua Nova')
    expect(nome.value).toBe(antes)
  })

  it('CNPJ nao encontrado mostra mensagem e nao altera campo nenhum', async () => {
    const { ApiError } = await import('../../lib/api')
    buscarCnpj.mockRejectedValue(new ApiError(404, 'nao encontrado'))
    await abrirOverride()
    const nome = screen.getByLabelText('Razão social / Nome') as HTMLInputElement
    const antes = nome.value

    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))

    expect(await screen.findByText(/CNPJ não encontrado/i)).toBeInTheDocument()
    expect(nome.value).toBe(antes)
  })

  it('provedor fora do ar mostra mensagem de indisponivel', async () => {
    const { ApiError } = await import('../../lib/api')
    buscarCep.mockRejectedValue(new ApiError(502, 'fora'))
    await abrirOverride()

    fireEvent.change(screen.getByLabelText('CEP'), { target: { value: '53000-000' } })
    fireEvent.click(screen.getByLabelText('Buscar endereço pelo CEP'))

    expect(await screen.findByText(/indisponível/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd frontend && npx vitest run src/app/propostas/PropostaModal.test.tsx`
Expected: FAIL — os botões de lupa e o campo CEP não existem.

- [ ] **Step 3: Somar os imports e o estado da busca**

Em `PropostaModal.tsx`, acrescentar aos imports:

```tsx
import { mascararCEP } from '../../lib/documento'
import {
  buscaApi, aplicarResultadoCep, aplicarResultadoCnpj, mensagemErroBusca,
  type DraftOverride,
} from './buscaEndereco'
```

**Nota:** `soDigitos` e `formatarDocumento` já vêm de `lib/documento` no arquivo — some `mascararCEP` ao import existente em vez de criar outro.

E o estado, junto de `overrideDraft`:

```tsx
  const [buscando, setBuscando] = useState<'cep' | 'cnpj' | null>(null)
  const [erroBusca, setErroBusca] = useState('')
  const [resultadoBusca, setResultadoBusca] = useState<
    { origem: 'CEP' | 'CNPJ'; campos: string[]; situacao?: string } | null
  >(null)
  const [draftAnterior, setDraftAnterior] = useState<DraftOverride | null>(null)
```

- [ ] **Step 3b: Pré-preencher o CEP do cadastro ao abrir o painel**

Em `abrirOverride()`, o ramo que monta o draft a partir do cadastro é um objeto
literal e por isso não ganha o campo novo sozinho (o outro ramo já percorre
`CAMPOS_OVERRIDE` e cobre o `cep` de graça). Acrescentar a linha depois de `estado`:

```tsx
        cep: soDigitos(clienteSelecionado?.cep ?? ''),
```

Sem isso o painel abriria com CEP vazio mesmo para cliente que tem CEP cadastrado.

- [ ] **Step 4: Escrever os handlers de busca**

Logo depois de `salvarOverride`:

```tsx
  function limparBusca() {
    setErroBusca('')
    setResultadoBusca(null)
    setDraftAnterior(null)
  }

  async function buscarPorCnpj() {
    setErroBusca('')
    setBuscando('cnpj')
    const anterior = overrideDraft
    try {
      const r = await buscaApi.cnpj(soDigitos(overrideDraft.documento ?? ''))
      const { draft, preenchidos } = aplicarResultadoCnpj(overrideDraft, r)
      setOverrideDraft(draft)
      setDraftAnterior(anterior)
      setResultadoBusca({
        origem: 'CNPJ',
        campos: preenchidos.map((c) => ROTULOS_OVERRIDE[c]),
        situacao: r.situacao || undefined,
      })
    } catch (e) {
      setResultadoBusca(null)
      setErroBusca(mensagemErroBusca(e, 'CNPJ'))
    } finally {
      setBuscando(null)
    }
  }

  async function buscarPorCep() {
    setErroBusca('')
    setBuscando('cep')
    const anterior = overrideDraft
    try {
      const r = await buscaApi.cep(soDigitos(overrideDraft.cep ?? ''))
      const { draft, preenchidos } = aplicarResultadoCep(overrideDraft, r)
      setOverrideDraft({ ...draft, cep: r.cep || draft.cep })
      setDraftAnterior(anterior)
      setResultadoBusca({ origem: 'CEP', campos: preenchidos.map((c) => ROTULOS_OVERRIDE[c]) })
    } catch (e) {
      setResultadoBusca(null)
      setErroBusca(mensagemErroBusca(e, 'CEP'))
    } finally {
      setBuscando(null)
    }
  }

  function desfazerBusca() {
    if (draftAnterior) setOverrideDraft(draftAnterior)
    limparBusca()
  }
```

Somar `ROTULOS_OVERRIDE` ao import de `./clienteOverride`. E chamar `limparBusca()`
dentro de `abrirOverride()`, `salvarOverride()` e `restaurarOverride()`, para o
aviso de preenchimento não sobreviver ao fechamento do painel.

- [ ] **Step 5: Criar o componente da lupa**

No topo do arquivo, junto de `Secao`:

```tsx
function ComLupa({ aoBuscar, buscando, rotulo, children }: {
  aoBuscar: () => void
  buscando: boolean
  rotulo: string
  children: ReactNode
}) {
  return (
    <div className="flex items-end gap-2">
      <div className="flex-1 min-w-0">{children}</div>
      <button
        type="button"
        onClick={aoBuscar}
        disabled={buscando}
        aria-label={rotulo}
        title={rotulo}
        className="mb-0.5 shrink-0 rounded-lg border border-border bg-background-elevated p-2.5 text-slate-400 hover:text-primary hover:border-primary/40 disabled:opacity-50 transition-colors"
      >
        {buscando ? <Spinner className="w-4 h-4" /> : <IconSearch className="w-4 h-4" />}
      </button>
    </div>
  )
}
```

- [ ] **Step 6: Reorganizar o grid do painel de override**

Substituir a `<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">` do painel
de override inteira por:

```tsx
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Input id="ov-nome" label="Razão social / Nome" value={overrideDraft.nome ?? ''} onChange={(e) => definirOverride('nome', e.target.value)} className="sm:col-span-2" />
                  <ComLupa aoBuscar={buscarPorCnpj} buscando={buscando === 'cnpj'} rotulo="Buscar dados pelo CNPJ">
                    <Input id="ov-documento" label="CNPJ / Documento" value={formatarDocumento(overrideDraft.documento ?? '')} onChange={(e) => definirOverride('documento', soDigitos(e.target.value))} />
                  </ComLupa>
                  <ComLupa aoBuscar={buscarPorCep} buscando={buscando === 'cep'} rotulo="Buscar endereço pelo CEP">
                    <Input id="ov-cep" label="CEP" value={mascararCEP(overrideDraft.cep ?? '')} onChange={(e) => definirOverride('cep', soDigitos(e.target.value))} />
                  </ComLupa>
                  <Input id="ov-endereco" label="Endereço" value={overrideDraft.endereco ?? ''} onChange={(e) => definirOverride('endereco', e.target.value)} className="sm:col-span-2" />
                  <Input id="ov-municipio" label="Município" value={overrideDraft.municipio ?? ''} onChange={(e) => definirOverride('municipio', e.target.value)} />
                  <Select id="ov-estado" label="Estado (UF)" value={overrideDraft.estado ?? ''} onChange={(e) => definirOverride('estado', e.target.value)}>
                    <option value="">—</option>
                    {UFS.map((uf) => <option key={uf} value={uf}>{uf}</option>)}
                  </Select>
                  <Input id="ov-telefone" label="Telefone" value={overrideDraft.telefone ?? ''} onChange={(e) => definirOverride('telefone', e.target.value)} />
                  <Input id="ov-email" label="E-mail" value={overrideDraft.email ?? ''} onChange={(e) => definirOverride('email', e.target.value)} />
                  <Input id="ov-contato" label="Contato (aos cuidados de)" value={overrideDraft.contato ?? ''} onChange={(e) => definirOverride('contato', e.target.value)} className="sm:col-span-2" />
                </div>
```

**Atenção:** o teste procura o campo de contato por `getByLabelText('Contato (aos cuidados de)')`
apenas se você mantiver esse texto — mantenha os rótulos exatamente como acima.

- [ ] **Step 7: Mostrar o resultado da busca e o Desfazer**

Logo **depois** do `</div>` do grid, antes da barra de botões do painel:

```tsx
                {erroBusca && (
                  <p className="text-xs font-medium text-danger">{erroBusca}</p>
                )}
                {resultadoBusca && (
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                    <span className="text-slate-400">
                      Preenchido pelo {resultadoBusca.origem}: {resultadoBusca.campos.join(', ')}.
                    </span>
                    {resultadoBusca.situacao && (
                      <span className={resultadoBusca.situacao === 'ATIVA' ? 'text-slate-500' : 'font-semibold text-warning'}>
                        Situação na Receita: {resultadoBusca.situacao}
                      </span>
                    )}
                    <button type="button" onClick={desfazerBusca} className="font-semibold text-primary hover:underline">
                      Desfazer
                    </button>
                  </div>
                )}
```

- [ ] **Step 8: Rodar os testes e confirmar que passam**

Run: `cd frontend && npx vitest run src/app/propostas/`
Expected: PASS — todos, incluindo os antigos.

- [ ] **Step 9: Verificação completa do frontend**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm test`
Expected: lint e tsc limpos. Em `npm test`, a única falha aceitável é
`src/app/clientes/ClienteEquipamentosTab.test.tsx > esconde "Novo aparelho" para
não-admin`, que **já falhava antes** desta branch. Qualquer outra falha é regressão.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/app/propostas/PropostaModal.tsx frontend/src/app/propostas/PropostaModal.test.tsx
git commit -m "feat(propostas): campo CEP e lupas de busca por CEP e CNPJ no override"
```

---

### Task 9: Changelog v1.32.0

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

**Interfaces:**
- Consumes: nada.
- Produces: nada — conteúdo visível ao usuário.

- [ ] **Step 1: Acrescentar a entrada**

Em `frontend/src/app/changelog/data.ts`, inserir como **primeiro** item de `CHANGELOG` (antes de `1.31.0`):

```ts
  {
    versao: '1.32.0',
    data: '29/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Os dados do cliente na proposta agora têm campo CEP, e ele passa a sair no endereço do PDF.' },
      { tipo: 'novidade', texto: 'Duas lupas no painel "Editar dados nesta proposta": a do CNPJ busca razão social e endereço completo na base pública da Receita; a do CEP preenche endereço, município e estado. Um botão Desfazer volta atrás se a busca atropelar algo.' },
      { tipo: 'melhoria', texto: 'Ao editar os dados do cliente numa proposta, só os campos realmente diferentes do cadastro são guardados — o selo "Dados editados" agora aparece apenas quando algo de fato diverge.' },
    ],
  },
```

- [ ] **Step 2: Verificar tipos**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.32.0 — campo CEP na proposta e busca por CEP e CNPJ"
```

---

## Verificação final da branch

- [ ] `cd backend && source .venv/bin/activate && pytest -q` — tudo verde.
- [ ] `cd frontend && npm run lint && npx tsc -b --noEmit && npm test` — lint e tsc limpos; única falha aceitável é a de `ClienteEquipamentosTab`, pré-existente.
- [ ] Teste manual com a API de pé: abrir uma proposta, "Editar dados nesta proposta", clicar na lupa do CNPJ e conferir o preenchimento e o Desfazer.
- [ ] Baixar o PDF de uma proposta e conferir o CEP na linha de cidade/UF.
