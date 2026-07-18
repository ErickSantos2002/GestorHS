# GrowthHS — Base comum + Etapa 1 (backfill dos atrasados) — Plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans. Passos usam checkbox (`- [ ]`).

**Goal:** Construir a base da integração com o GrowthHS (config + cliente HTTP + montagem de payload) e, sobre ela, o script de carga única dos aparelhos com calibração já vencida — um card por cliente no board de Cobrança.

**Architecture:** `hsgrowth_client.py` espelha o `taskhs_client.py` (gating por env, best-effort, duas variantes: silenciosa e propagando). A montagem do payload fica em `core/growthhs_payload.py`, **pura e sem I/O**, para ser testada isolada — inclusive a regra do elo Phoebus↔Módulo. A Etapa 1 é um script no molde do `importar_elo_modulos` (`--dry-run`, CSV de pendências, best-effort por item).

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · httpx · pytest.

**Escopo deste plano:** base comum + Etapa 1. As Etapas 2 (gatilho na saída do laboratório) e 3 (job diário dos 50 dias) terão planos próprios, reaproveitando a base.

## Global Constraints

- Idioma PT-BR em nomes, mensagens e docstrings.
- **Gating por env:** sem `HSGROWTH_BASE_URL` **ou** sem `HSGROWTH_API_KEY`, a integração é **no-op**. Nasce desligada; nada quebra em dev/teste.
- **Best-effort:** nenhuma falha da integração pode derrubar ou reverter fluxo do GestorHS.
- **`client.external_id` é SEMPRE `clientes.id`** — nunca CPF/CNPJ (não é único no GestorHS).
- **Sempre enviar `contact`** quando o cliente tiver contato — sem ele o card nasce sem pessoa e vira trava para o vendedor.
- Endpoint: `POST {HSGROWTH_BASE_URL}/api/v1/integration/service-cards`, header `X-API-Key`. `HSGROWTH_BASE_URL` **não** inclui `/api/v1`.
- `201` e `200` são ambos **sucesso** (200 = já existia; a chamada é idempotente).
- Números mágicos vão para config: `EQUIPAMENTO_PHOEBUS_ID=36`, `EQUIPAMENTO_EBS_ID=37`, `CLIENTE_ESTOQUE_HS_ID=2` (junto do `EQUIPAMENTO_MODULO_ID=47` que já existe).
- Backend: `docker exec gestorhs-backend pytest -q` (NÃO há venv local).
- Commits Conventional Commits em PT-BR sem acentos, uma linha, sem trailer.

**Dependência externa:** o `source` `gestorhs.atrasados` ainda **não existe** no enum do GrowthHS (`backend/app/schemas/integration.py:42`) — enviar antes disso devolve `422`. Isso **não bloqueia construir nem testar** (os testes não batem na rede); bloqueia só a execução real do script.

---

### Task 1: Config + cliente HTTP `hsgrowth_client.py`

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/integrations/hsgrowth_client.py`
- Test: `backend/tests/test_hsgrowth_client.py`

**Interfaces:**
- Config novo: `HSGROWTH_BASE_URL: str = ""`, `HSGROWTH_API_KEY: str = ""`, `HSGROWTH_BOARD_SERVICOS: int = 1`, `HSGROWTH_BOARD_COBRANCA: int = 2`, `EQUIPAMENTO_PHOEBUS_ID: int = 36`, `EQUIPAMENTO_EBS_ID: int = 37`, `CLIENTE_ESTOQUE_HS_ID: int = 2`.
- `integracao_ativa() -> bool` — ambas as envs preenchidas.
- `enviar_card(payload: dict) -> None` — best-effort: no-op se desligada, **nunca propaga** (loga).
- `enviar_card_sync(payload: dict) -> dict` — propaga erro; devolve o JSON da resposta (para o script saber se foi `201` ou `200`).

- [ ] **Step 1: Escrever o teste que falha**

```python
# backend/tests/test_hsgrowth_client.py
import pytest


def _ligar(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "chave-123")


def test_desligada_sem_env(monkeypatch):
    from app.core.config import settings
    from app.integrations import hsgrowth_client as cli
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "")
    assert cli.integracao_ativa() is False

    chamou = []
    monkeypatch.setattr(cli, "_post", lambda p: chamou.append(p))
    cli.enviar_card({"external_id": "1"})
    assert chamou == []          # nem tentou


def test_ligada_com_as_duas_envs(monkeypatch):
    from app.integrations import hsgrowth_client as cli
    _ligar(monkeypatch)
    assert cli.integracao_ativa() is True


def test_enviar_card_nunca_propaga(monkeypatch):
    """Best-effort: falha de rede nao pode derrubar o fluxo chamador."""
    from app.integrations import hsgrowth_client as cli
    _ligar(monkeypatch)

    def explode(_):
        raise RuntimeError("rede caiu")
    monkeypatch.setattr(cli, "_post", explode)
    cli.enviar_card({"external_id": "1"})      # nao levanta


def test_enviar_card_sync_propaga(monkeypatch):
    """A variante do script quer saber da falha para relatar."""
    from app.integrations import hsgrowth_client as cli
    _ligar(monkeypatch)

    def explode(_):
        raise RuntimeError("rede caiu")
    monkeypatch.setattr(cli, "_post", explode)
    with pytest.raises(RuntimeError):
        cli.enviar_card_sync({"external_id": "1"})


def test_url_e_header(monkeypatch):
    """Monta {base}/api/v1/integration/service-cards e manda X-API-Key."""
    from app.integrations import hsgrowth_client as cli
    _ligar(monkeypatch)
    capturado = {}

    class RespFake:
        status_code = 201
        def raise_for_status(self): pass
        def json(self): return {"id": 9, "created": True}

    def post_fake(url, json=None, headers=None, timeout=None):
        capturado.update(url=url, json=json, headers=headers)
        return RespFake()
    monkeypatch.setattr(cli.httpx, "post", post_fake)

    r = cli.enviar_card_sync({"external_id": "1"})
    assert capturado["url"] == "https://growth.test/api/v1/integration/service-cards"
    assert capturado["headers"]["X-API-Key"] == "chave-123"
    assert r["created"] is True
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_hsgrowth_client.py`
Expected: FAIL — módulo/settings não existem.

- [ ] **Step 3: Config**

Em `backend/app/core/config.py`, junto das envs do TaskHS:

```python
    # Integracao GrowthHS (CRM). Vazio = desligada (mesmo gating do TaskHS).
    HSGROWTH_BASE_URL: str = ""   # raiz do backend, SEM /api/v1
    HSGROWTH_API_KEY: str = ""    # header X-API-Key
    HSGROWTH_BOARD_SERVICOS: int = 1
    HSGROWTH_BOARD_COBRANCA: int = 2

    # Ids de catalogo dos hospedeiros (nao calibram) e do estoque interno.
    EQUIPAMENTO_PHOEBUS_ID: int = 36
    EQUIPAMENTO_EBS_ID: int = 37
    CLIENTE_ESTOQUE_HS_ID: int = 2
```

- [ ] **Step 4: Cliente HTTP**

```python
# backend/app/integrations/hsgrowth_client.py
"""Cliente HTTP da integracao com o GrowthHS (best-effort, gating por env).

Espelha o molde do taskhs_client, com uma diferenca importante de SEMANTICA:
o endpoint do GrowthHS e create-or-return, nao upsert — chamar de novo com o
mesmo (source, external_id) devolve o card existente e NAO altera nada.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_CAMINHO = "/api/v1/integration/service-cards"


def integracao_ativa() -> bool:
    return bool(settings.HSGROWTH_BASE_URL and settings.HSGROWTH_API_KEY)


def _post(payload: dict) -> dict:
    """POST no endpoint; levanta em erro. Devolve o JSON da resposta."""
    url = f"{settings.HSGROWTH_BASE_URL.rstrip('/')}{_CAMINHO}"
    resp = httpx.post(
        url, json=payload,
        headers={"X-API-Key": settings.HSGROWTH_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()      # 201 e 200 passam; 4xx/5xx levantam
    return resp.json()


def enviar_card(payload: dict) -> None:
    """Alvo do BackgroundTask: no-op se desligada; nunca propaga (best-effort)."""
    if not integracao_ativa():
        return
    try:
        _post(payload)
    except Exception:
        logger.exception(
            "falha ao criar card no GrowthHS (source=%s external_id=%s)",
            payload.get("source"), payload.get("external_id"),
        )


def enviar_card_sync(payload: dict) -> dict:
    """Envia PROPAGANDO erro (uso nos scripts, que querem relatar falhas)."""
    return _post(payload)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_hsgrowth_client.py`
Expected: PASS (5 testes).

- [ ] **Step 6: Suíte completa + commit**

Run: `docker exec gestorhs-backend pytest -q`

```bash
git add backend/app/core/config.py backend/app/integrations/hsgrowth_client.py backend/tests/test_hsgrowth_client.py
git commit -m "feat(growthhs): cliente http e config da integracao"
```

---

### Task 2: Montagem de payload pura `core/growthhs_payload.py`

**Files:**
- Create: `backend/app/core/growthhs_payload.py`
- Test: `backend/tests/test_growthhs_payload.py`

**Interfaces:**
- `montar_cliente(cliente) -> dict` — `{external_id: str(cliente.id), name, document, email, phone, address, city, state}`. `document` = `cgc or cpf`. `address` monta logradouro+número+bairro se houver.
- `montar_contato(cliente) -> dict | None` — `{name, email, phone}` de `cliente.contato`; `None` se sem nome de contato. `phone` = primeiro disponível entre `celular`, `whatsapp`, `telefones`.
- `montar_device(ec, equipamento_desc, elo=None) -> dict` — item de `devices[]`:
  - com `elo` (o Phoebus onde o módulo está): `serial_number` = série do Phoebus, `model` = descrição do Phoebus, `alcohol_module` = série do módulo;
  - sem `elo`: `serial_number` = série do próprio, `model` = `equipamento_desc`, `alcohol_module` = `None`.
  - `next_recalibration_date` = `prox_calibragem` em `YYYY-MM-DD` (ou `None`).
- Puro: recebe objetos/valores já carregados, **não consulta o banco**.

- [ ] **Step 1: Escrever o teste que falha**

```python
# backend/tests/test_growthhs_payload.py
from datetime import date
from types import SimpleNamespace as NS

from app.core.growthhs_payload import montar_cliente, montar_contato, montar_device


def _cliente(**kw):
    base = dict(id=512, nome="ACME Ltda", cgc="12345678000199", cpf=None,
                email="fin@acme.com", contato="Marcos", celular="11987654321",
                whatsapp=None, telefones="1133334444", endereco="Rua X", numero=220,
                bairro="Centro", municipio="Sao Paulo", estado="SP")
    base.update(kw)
    return NS(**base)


def test_cliente_usa_id_como_external_id_nunca_documento():
    c = montar_cliente(_cliente())
    assert c["external_id"] == "512"          # string, e o id — nao o CNPJ
    assert c["name"] == "ACME Ltda"
    assert c["document"] == "12345678000199"
    assert c["city"] == "Sao Paulo" and c["state"] == "SP"


def test_cliente_sem_cnpj_usa_cpf():
    c = montar_cliente(_cliente(cgc=None, cpf="12345678901"))
    assert c["document"] == "12345678901"


def test_contato_none_quando_nao_ha_nome():
    assert montar_contato(_cliente(contato=None)) is None
    assert montar_contato(_cliente(contato="  ")) is None


def test_contato_prefere_celular():
    ct = montar_contato(_cliente())
    assert ct["name"] == "Marcos" and ct["phone"] == "11987654321"


def test_contato_cai_para_telefones_sem_celular():
    ct = montar_contato(_cliente(celular=None, whatsapp=None))
    assert ct["phone"] == "1133334444"


def test_device_sem_elo_usa_a_serie_do_proprio():
    ec = NS(serie="SN-4471", prox_calibragem=date(2027, 7, 30))
    d = montar_device(ec, "HS PASS - IBLOW")
    assert d["serial_number"] == "SN-4471"
    assert d["model"] == "HS PASS - IBLOW"
    assert d["alcohol_module"] is None
    assert d["next_recalibration_date"] == "2027-07-30"


def test_device_com_elo_manda_o_phoebus_no_serial_e_o_modulo_no_alcohol_module():
    """O ponto do elo: o cliente reconhece o APARELHO, nao o numero do modulo."""
    modulo = NS(serie="F005065", prox_calibragem=date(2026, 9, 8))
    elo = NS(serie="WATFR01-00340", descricao="Phoebus")
    d = montar_device(modulo, "Modulo de Calibracao ... PHOEBUS", elo=elo)
    assert d["serial_number"] == "WATFR01-00340"
    assert d["model"] == "Phoebus"
    assert d["alcohol_module"] == "F005065"
    assert d["next_recalibration_date"] == "2026-09-08"


def test_device_sem_data():
    ec = NS(serie="SN-1", prox_calibragem=None)
    assert montar_device(ec, "X")["next_recalibration_date"] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_payload.py`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Implementar**

Criar `backend/app/core/growthhs_payload.py` com as três funções conforme as interfaces
acima. Pontos obrigatórios:
- `external_id` do cliente é `str(cliente.id)` — deixar um comentário explicando **por que
  não é o documento** (CPF/CNPJ não tem unicidade no GestorHS; casar por documento juntaria
  clientes errados).
- `montar_contato` devolve `None` quando `contato` é vazio/só espaços.
- Telefone do contato: primeiro não-vazio entre `celular`, `whatsapp`, `telefones`.
- Endereço: juntar `endereco`, `numero` e `bairro` no que existir, sem vírgulas soltas.
- Datas sempre `YYYY-MM-DD` ou `None`.

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_payload.py`
Expected: PASS (8 testes).

- [ ] **Step 5: Suíte completa + commit**

Run: `docker exec gestorhs-backend pytest -q`

```bash
git add backend/app/core/growthhs_payload.py backend/tests/test_growthhs_payload.py
git commit -m "feat(growthhs): montagem pura do payload de card"
```

---

### Task 3: Seleção dos atrasados (pura) — `core/growthhs_atrasados.py`

**Files:**
- Create: `backend/app/core/growthhs_atrasados.py`
- Test: `backend/tests/test_growthhs_atrasados.py`

**Interfaces:**
- `agrupar_por_cliente(linhas) -> list[dict]` — recebe as linhas já lidas do banco
  (`[{cliente_id, cliente, ec, equipamento_desc, elo}]`) e devolve, por cliente:
  `{cliente_id, cliente, itens: [...], vencimento_mais_antigo: date}`.
  Ordena os clientes por `cliente_id` e, dentro de cada um, os itens pela `prox_calibragem`
  mais antiga primeiro (determinismo).
- `montar_card_atrasados(grupo, data_carga, board_id) -> dict` — o corpo completo do POST:
  `source="gestorhs.atrasados"`, `external_id=f"{cliente_id}:{data_carga:%Y-%m-%d}"`,
  `title=f"Calibração vencida · {nome} · {N} aparelho(s)"`, `description` com o resumo,
  `due_date` = `vencimento_mais_antigo`, `client`, `contact`, `devices[]`, `business_info`.
- Puro: nenhuma consulta ao banco, nenhum request.

- [ ] **Step 1: Escrever o teste que falha**

Cobrir: agrupamento por cliente com contagem correta; `vencimento_mais_antigo` é mesmo o
menor; `external_id` no formato `"{cliente_id}:{YYYY-MM-DD}"`; `due_date` = vencimento mais
antigo; `title` com o plural certo (1 aparelho vs N aparelhos); `source` fixo em
`"gestorhs.atrasados"`; `devices[]` com um item por equipamento; `contact` ausente quando o
cliente não tem contato; ordenação determinística.

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_atrasados.py`
Expected: FAIL.

- [ ] **Step 3: Implementar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_atrasados.py`
Expected: PASS.

- [ ] **Step 4: Suíte completa + commit**

```bash
git add backend/app/core/growthhs_atrasados.py backend/tests/test_growthhs_atrasados.py
git commit -m "feat(growthhs): agrupamento e card dos atrasados por cliente"
```

---

### Task 4: Script da Etapa 1 — `enviar_atrasados_growthhs`

**Files:**
- Create: `backend/app/scripts/enviar_atrasados_growthhs.py`
- Test: `backend/tests/test_enviar_atrasados_growthhs.py`

**Interfaces:**
- CLI: `python -m app.scripts.enviar_atrasados_growthhs [--enviar] [--pendencias CAMINHO.csv] [--limite N]`

> **SEGURANÇA — o padrão é NÃO enviar.** Sem `--enviar`, o script monta tudo, imprime o
> resumo e escreve o CSV, **sem fazer nenhum request**. O envio real exige `--enviar`
> explícito. Motivo: a chave é `{cliente_id}:{data_da_carga}`, então rodar a carga em **duas
> datas diferentes cria um card duplicado por cliente** — e o GrowthHS não expõe leitura, logo
> o script não tem como detectar que já enviou. Invertendo o default, um comando repetido por
> engano é inofensivo.
- `buscar_atrasados(db) -> list[dict]` — a consulta:
  - `equipamentos_cliente.ativo` e `prox_calibragem < hoje`;
  - **exclui** `equipamento in (PHOEBUS_ID, EBS_ID)` e `cliente = CLIENTE_ESTOQUE_HS_ID`;
  - traz junto o cliente, a descrição do catálogo e, quando o equipamento é um módulo com
    instalação aberta em `instalacoes_modulo`, o Phoebus correspondente (o `elo`).
- `main()` — busca → `agrupar_por_cliente` → para cada grupo `montar_card_atrasados` →
  `enviar_card_sync`; conta `criados` (201) / `existentes` (200) / `falhas`; escreve CSV e
  imprime resumo. **Sem `--enviar`, para antes do request** (monta, resume, grava CSV).
- `--limite N` envia só os N primeiros grupos (para um teste real controlado antes da carga cheia).

- [ ] **Step 1: Escrever o teste que falha**

Testar contra SQLite, criando dados de propósito:
- um equipamento vencido de cliente normal → **entra**;
- um Phoebus vencido → **não entra**;
- um EBS vencido → **não entra**;
- um equipamento vencido do cliente de estoque (id 2) → **não entra**;
- um equipamento **não** vencido → não entra;
- um equipamento vencido **inativo** → não entra;
- um módulo vencido **com** instalação aberta → o device sai com a série do Phoebus e
  `alcohol_module` preenchido;
- **sem `--enviar`** não chama `enviar_card_sync` (monkeypatch conta chamadas) — e **com
  `--enviar`** chama uma vez por grupo;
- falha em um grupo não interrompe os demais (o segundo ainda é enviado) e entra no CSV.

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_enviar_atrasados_growthhs.py`
Expected: FAIL — script não existe.

- [ ] **Step 3: Implementar**

Pontos obrigatórios:
- A consulta usa as constantes de config (nada de `36`/`37`/`2` soltos no código).
- Best-effort **por cliente**: exceção num grupo é capturada, registrada no CSV com o motivo e
  o laço segue.
- CSV de pendências (colunas `cliente_id,cliente,qtd_equipamentos,motivo`) resolvido contra a
  **raiz do repositório** (`docs/`), com o diretório criado **antes** de qualquer envio —
  mesma lição aprendida no `importar_elo_modulos`.
- Resumo no terminal: total de clientes, equipamentos, criados/existentes/falhas, **quantos
  clientes foram sem contato** e **quantos módulos foram sem elo**.
- Se `integracao_ativa()` for falso, abortar cedo com mensagem clara (em vez de "enviar" para
  o vazio).
- Sem `--enviar`, imprimir de forma destacada que **nada foi enviado** e como enviar de
  verdade — o operador não pode achar que a carga aconteceu.

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_enviar_atrasados_growthhs.py`
Expected: PASS.

- [ ] **Step 5: Suíte completa + commit**

Run: `docker exec gestorhs-backend pytest -q`

```bash
git add backend/app/scripts/enviar_atrasados_growthhs.py backend/tests/test_enviar_atrasados_growthhs.py
git commit -m "feat(growthhs): script de carga dos atrasados"
```

---

### Task 5: Documentação da operação + verificação

**Files:**
- Modify: `docs/integracao-gestorhs.md`
- Modify: `CLAUDE.md` (seção de comandos)

- [ ] **Step 1: Atualizar o contrato**

Em `docs/integracao-gestorhs.md`, acrescentar `gestorhs.atrasados` na tabela de `source`
(seção 3) e na seção 4 (com o formato `{cliente_id}:{data_da_carga}` e a explicação de que é
carga única, um card por cliente). Registrar também as duas divergências já conhecidas para
não deixar o documento mentindo: o gatilho do board de Serviços passou a ser a **saída do
laboratório** (5→6), não a abertura (§7.1), e a etapa de entrada do Board 1 é **"Liberados do
Laboratório"** (§9). **Copiar o arquivo atualizado para o repositório do hsgrowth** (os dois
devem seguir idênticos).

- [ ] **Step 2: Documentar o comando no CLAUDE.md**

Acrescentar na seção de comandos do backend:
```
python -m app.scripts.enviar_atrasados_growthhs             # simula (padrao): nao envia nada
python -m app.scripts.enviar_atrasados_growthhs --enviar    # carga real (cuidado: rodar em
                                                           # duas datas duplica os cards)
```

- [ ] **Step 3: Verificação completa**

Run: `docker exec gestorhs-backend pytest -q`
Expected: tudo verde.

- [ ] **Step 4: Commit**

```bash
git add docs/integracao-gestorhs.md CLAUDE.md
git commit -m "docs(growthhs): atualiza contrato e documenta o script de atrasados"
```

---

## Self-Review (feita)

- **Cobertura da spec (base + Etapa 1):** config e gating (T1), cliente HTTP com as duas variantes (T1), payload puro incluindo a regra do elo (T2), agrupamento por cliente e formato da chave (T3), script com dry-run/CSV/best-effort e as três exclusões (T4), documentação (T5). ✔
- **Sem placeholders:** T1 e T2 trazem o código e os testes completos; T3 e T4 descrevem os casos de teste um a um e os pontos obrigatórios da implementação, com os comandos e resultados esperados. ✔
- **Consistência de tipos:** `montar_cliente`/`montar_contato`/`montar_device` (T2) são consumidos por `montar_card_atrasados` (T3), que é consumido pelo script (T4); `enviar_card_sync` (T1) devolve o JSON que o script usa para separar `201` de `200`. ✔
- **Lições já aprendidas neste projeto, aplicadas:** caminho do CSV resolvido na raiz do repo e diretório criado **antes** de qualquer escrita (bug real do `importar_elo_modulos`); números de catálogo em config e não espalhados; best-effort por item para não perder o lote inteiro. ✔
- **Fora deste plano:** Etapas 2 e 3 (planos próprios). O script **pode ser construído e testado** agora; a execução real depende do enum `gestorhs.atrasados` no GrowthHS. ✔
