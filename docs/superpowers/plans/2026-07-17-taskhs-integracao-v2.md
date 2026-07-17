# Integração GestorHS → TaskHS v2 (list_id + obs) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adaptar o espelhamento de OS no TaskHS ao contrato v2: endereçar o card por `list_id` (não mais `board`/`list` por nome) e distribuir as informações por etapa em `obs1…obs6` (não mais numa `description` única).

**Architecture:** A lógica pura (`taskhs.py`) monta título, as 6 obs e mapeia fase → `list_id`. O `espelhamento.py` vira a fonte única do payload (junta certificados + nota fiscal → obs → payload) e é consumido tanto pelo caminho de API (async, best-effort) quanto pelo backfill (síncrono, propaga erro). O `taskhs_client.py` fica só como I/O (envia payloads).

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · pytest (SQLite in-memory). Frontend só toca no changelog (`data.ts`).

## Global Constraints

- Domínio em **PT-BR**; commits em **ASCII sem acentos**, uma linha (ver CLAUDE.md).
- **Só commitar quando o Erick pedir** (CLAUDE.md) — os passos de commit abaixo ficam prontos, mas confirme antes de executá-los.
- Ids das listas são **fixos de produção**, hardcoded em `taskhs.py`: fase 4→21, 5→22, 6→27, 10→30, 7→34, 8→35.
- Mapa obs: obs1=Recebido (com cabeçalho no topo), obs2=Laboratório (com link do certificado), obs3=Pós-Vendas, obs4=Financeiro, obs5=Preparando Retorno, obs6=Finalizada.
- O payload manda **sempre as 6 chaves** `obs1…obs6` (`null` nas vazias) e **não** manda `board`, `list` nem `description`.
- Testes: `cd backend && source .venv/bin/activate && pytest -q`.

---

### Task 1: Núcleo puro `taskhs.py` (list_id + obs)

**Files:**
- Modify: `backend/app/core/taskhs.py` (reescrita das funções de mapa/payload; `_sec_*` perdem o título interno)
- Test: `backend/tests/test_taskhs.py` (reescrita)
- Test: `backend/tests/test_taskhs_descricao.py` (reescrita → testa `montar_obs`)

**Interfaces:**
- Produces:
  - `list_id_da_fase(fase: int) -> int | None`
  - `montar_titulo(ordem) -> str` (inalterada)
  - `montar_obs(ordem, *, certificados: list[dict], nota_fiscal_url: str | None = None) -> dict` — chaves `obs1…obs6`, valor `str | None`
  - `montar_payload(ordem, *, list_id: int, arquivado: bool, obs: dict) -> dict`
  - Remove: `BOARD`, `FASE_PARA_LISTA`, `lista_da_fase`, `montar_descricao`

- [ ] **Step 1: Reescrever `backend/tests/test_taskhs.py`**

Substituir o arquivo inteiro por:

```python
from datetime import datetime, timezone
from types import SimpleNamespace

from app.core import taskhs


def _ordem(**kw):
    base = dict(
        id=1234, cliente_nome="Cliente X", equipamento_descricao="Bafômetro",
        equipamento_serie="SN-987", prox_calibragem=None, obs=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_list_id_da_fase_cobre_ativas_e_finalizada():
    assert taskhs.list_id_da_fase(4) == 21
    assert taskhs.list_id_da_fase(5) == 22
    assert taskhs.list_id_da_fase(6) == 27
    assert taskhs.list_id_da_fase(7) == 34
    assert taskhs.list_id_da_fase(8) == 35


def test_list_id_da_fase_financeiro():
    assert taskhs.list_id_da_fase(10) == 30


def test_list_id_da_fase_cancelada_e_desconhecida_none():
    assert taskhs.list_id_da_fase(9) is None
    assert taskhs.list_id_da_fase(999) is None


def test_montar_titulo_completo():
    assert taskhs.montar_titulo(_ordem()) == "OS #1234 · Cliente X · Bafômetro"


def test_montar_titulo_sem_descricao_usa_serie():
    o = _ordem(equipamento_descricao=None)
    assert taskhs.montar_titulo(o) == "OS #1234 · Cliente X · SN-987"


def test_montar_titulo_so_id_quando_resto_vazio():
    o = _ordem(cliente_nome=None, equipamento_descricao=None, equipamento_serie=None)
    assert taskhs.montar_titulo(o) == "OS #1234"


def test_montar_payload_campos_basicos():
    o = _ordem()
    p = taskhs.montar_payload(o, list_id=22, arquivado=False, obs={"obs1": "cab"})
    assert p["source"] == "gestorhs"
    assert p["external_id"] == "1234"
    assert p["list_id"] == 22
    assert p["title"] == "OS #1234 · Cliente X · Bafômetro"
    assert p["priority"] == "medium"
    assert p["archived"] is False
    assert p["due_date"] is None
    assert "board" not in p and "list" not in p and "description" not in p


def test_montar_payload_espalha_as_seis_obs():
    obs = {"obs1": "A", "obs2": "B", "obs6": "F"}
    p = taskhs.montar_payload(_ordem(), list_id=21, arquivado=False, obs=obs)
    assert p["obs1"] == "A"
    assert p["obs2"] == "B"
    assert p["obs3"] is None
    assert p["obs4"] is None
    assert p["obs5"] is None
    assert p["obs6"] == "F"


def test_montar_payload_due_date_de_prox_calibragem():
    o = _ordem(prox_calibragem=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc))
    assert taskhs.montar_payload(o, list_id=22, arquivado=False, obs={})["due_date"] == "2026-07-10"


def test_montar_payload_arquivado_true():
    assert taskhs.montar_payload(_ordem(), list_id=22, arquivado=True, obs={})["archived"] is True
```

- [ ] **Step 2: Reescrever `backend/tests/test_taskhs_descricao.py` (agora testa `montar_obs`)**

Substituir o arquivo inteiro por:

```python
from datetime import datetime, timezone
from types import SimpleNamespace

from app.core import taskhs


def _dt(y, m, d):
    return datetime(y, m, d, 12, 0, tzinfo=timezone.utc)


def _ordem(**kw):
    base = dict(
        id=1234, fase=8, cliente_nome="Cliente X",
        equipamento_descricao="Bafômetro", equipamento_serie="SN-987",
        equipamento_rel=SimpleNamespace(patrimonio="PAT-1"),
        tipo_servico="C",
        data_chegada=_dt(2026, 6, 22), condicao_chegada="bom estado",
        acessorios_presentes=["Bobinas", "Cabos USB"], pilhas=4, bocais=2,
        obs="veio sem maleta",
        calib_situacao="APROVADO", data_calibracao=_dt(2026, 6, 23),
        prox_calibragem=_dt(2027, 7, 10), calib_cert="12345",
        aceite=True, data_aceite=_dt(2026, 6, 24),
        cliente_rel=SimpleNamespace(
            endereco="Rua X", numero=100, complemento="ap 2", bairro="Centro",
            municipio="São Paulo", estado="SP", cep="01000000",
            contato="João", celular="(11) 99999-9999", whatsapp=None, telefones=None,
        ),
        cod_retorno="BR123", data_retorno=_dt(2026, 6, 25),
        pago=True, data_pagamento=_dt(2026, 6, 26),
        nota_fiscal=None, nota_fiscal_numero=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_obs1_tem_cabecalho_recebido_e_sem_titulo_interno():
    obs = taskhs.montar_obs(_ordem(), certificados=[{"tipo": "C", "url": "http://x/c"}])
    o1 = obs["obs1"]
    assert "Cliente: Cliente X" in o1
    assert "Aparelho: Bafômetro · Série SN-987 / Patr. PAT-1" in o1
    assert "Serviço: Calibração" in o1
    assert "Chegada: 22/06/2026 · Condição: bom estado" in o1
    assert "Acessórios: Bobinas, Cabos USB" in o1
    assert "Pilhas: 4 · Bocais: 2" in o1
    assert "Obs: veio sem maleta" in o1
    assert "📋 Recebido" not in o1  # título interno removido


def test_obs2_laboratorio_com_certificado_sem_titulo():
    obs = taskhs.montar_obs(_ordem(), certificados=[{"tipo": "C", "url": "http://x/c"}])
    o2 = obs["obs2"]
    assert "Resultado: APROVADO" in o2
    assert "Calibrado em: 23/06/2026 · Próxima: 10/07/2027" in o2
    assert "Certificado: 12345" in o2
    assert "Certificado de Calibração: http://x/c" in o2
    assert "🔬 Laboratório" not in o2


def test_obs3_posvendas():
    obs = taskhs.montar_obs(_ordem(), certificados=[])
    assert "Contato: João · (11) 99999-9999" in obs["obs3"]
    assert "Aceite: 24/06/2026" in obs["obs3"]


def test_obs5_preparando_endereco():
    obs = taskhs.montar_obs(_ordem(), certificados=[])
    assert "Enviar para: Rua X, 100 ap 2 · Centro · São Paulo/SP · CEP 01000000" in obs["obs5"]


def test_obs6_finalizada_rastreio():
    obs = taskhs.montar_obs(_ordem(), certificados=[])
    assert "Rastreio: BR123 · Postado em: 25/06/2026" in obs["obs6"]


def test_secoes_por_fase_recebido():
    # fase 4: só obs1 (Recebido); demais None
    o = _ordem(fase=4, aceite=False, data_aceite=None, cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[])
    assert obs["obs1"] is not None
    assert obs["obs2"] is None  # sem certificados
    assert obs["obs3"] is None
    assert obs["obs4"] is None
    assert obs["obs5"] is None
    assert obs["obs6"] is None


def test_obs2_aparece_com_certificado_manutencao():
    o = _ordem(fase=6, cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[{"tipo": "M", "url": "http://x/m"}])
    assert "Certificado de Manutenção: http://x/m" in obs["obs2"]


def test_telefone_pega_primeiro_nao_vazio():
    o = _ordem(fase=6, cliente_rel=SimpleNamespace(
        endereco=None, numero=None, complemento=None, bairro=None, municipio=None,
        estado=None, cep=None, contato="Maria", celular=None, whatsapp="(11) 8888",
        telefones="3333-3333"))
    obs = taskhs.montar_obs(o, certificados=[])
    assert "Contato: Maria · (11) 8888" in obs["obs3"]


def test_linhas_vazias_omitidas():
    o = _ordem(fase=4, condicao_chegada=None, acessorios_presentes=[], pilhas=0,
               bocais=0, obs=None, aceite=False, data_aceite=None,
               cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[])
    assert "Chegada: 22/06/2026" in obs["obs1"]
    assert "Condição:" not in obs["obs1"]
    assert "Acessórios:" not in obs["obs1"]
    assert "Pilhas:" not in obs["obs1"]


def test_link_omitido_quando_url_none():
    o = _ordem(fase=6, cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[{"tipo": "C", "url": None}])
    assert obs["obs2"] is not None
    assert "Certificado de Calibração:" not in obs["obs2"]


def test_obs4_financeiro_confirmado():
    obs = taskhs.montar_obs(_ordem(fase=7), certificados=[])
    assert "Pagamento: confirmado em 26/06/2026" in obs["obs4"]


def test_obs4_pendente_e_obs5_oculto_em_financeiro():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[])
    assert "Pagamento: pendente" in obs["obs4"]
    assert obs["obs5"] is None


def test_obs4_oculto_antes_da_fase():
    o = _ordem(fase=6, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[])
    assert obs["obs4"] is None


def test_obs4_com_nota_fiscal():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_numero="12345")
    obs = taskhs.montar_obs(o, certificados=[], nota_fiscal_url="http://x/nf")
    assert "Nota fiscal: 12345 — http://x/nf" in obs["obs4"]


def test_obs4_nota_fiscal_sem_url_mostra_so_numero():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_numero="12345")
    obs = taskhs.montar_obs(o, certificados=[], nota_fiscal_url=None)
    linha = [l for l in obs["obs4"].splitlines() if "Nota fiscal" in l][0]
    assert linha.strip() == "- Nota fiscal: 12345"
```

- [ ] **Step 3: Rodar os testes e ver falhar**

Run: `cd backend && source .venv/bin/activate && pytest -q tests/test_taskhs.py tests/test_taskhs_descricao.py`
Expected: FAIL (`AttributeError: module 'app.core.taskhs' has no attribute 'list_id_da_fase'` / `montar_obs`).

- [ ] **Step 4: Reescrever `backend/app/core/taskhs.py`**

Substituir o arquivo inteiro por:

```python
"""Integração GestorHS → TaskHS: lógica pura (sem I/O).

Monta o payload do card a partir de uma OS: título, obs por etapa (obs1…obs6)
e mapeia fase → list_id (id da lista no TaskHS, contrato v2).
"""

from app.core import os_workflow as wf

SOURCE = "gestorhs"

# Fase da OS (GestorHS) → id da lista no quadro "Serviço" do TaskHS (contrato v2).
# Ids fixos de produção; a lista tem que existir no TaskHS (senão o upsert dá 404).
FASE_PARA_LIST_ID: dict[int, int] = {
    4: 21,   # 🚚 Expedição (Abrindo caixa)
    5: 22,   # 🔬 Laboratório Calibração
    6: 27,   # 🔬 LIBERADOS DO LABORATÓRIO
    10: 30,  # 💰 Financeiro
    7: 34,   # 🚚 Expedição (Preparando para Envio)
    8: 35,   # 📮 Correios
}

TIPO_SERVICO_LABEL: dict[str, str] = {"C": "Calibração", "M": "Manutenção", "A": "Ambas"}


def list_id_da_fase(fase: int) -> int | None:
    return FASE_PARA_LIST_ID.get(fase)


def montar_titulo(ordem) -> str:
    partes = [f"OS #{ordem.id}"]
    if ordem.cliente_nome:
        partes.append(ordem.cliente_nome)
    descricao = ordem.equipamento_descricao or ordem.equipamento_serie
    if descricao:
        partes.append(descricao)
    return " · ".join(partes)


def _fmt(dt) -> str:
    return dt.date().strftime("%d/%m/%Y") if dt is not None else ""


def _juntar(linhas: list[str | None], sep: str = " · ") -> str:
    return sep.join([x for x in linhas if x])


def _endereco(cli) -> str | None:
    if cli is None:
        return None
    rua = cli.endereco or ""
    if cli.numero:
        rua = f"{rua}, {cli.numero}" if rua else str(cli.numero)
    if cli.complemento:
        rua = f"{rua} {cli.complemento}".strip()
    cidade_uf = "/".join([x for x in (cli.municipio, cli.estado) if x])
    partes = _juntar([rua or None, cli.bairro, cidade_uf or None,
                      f"CEP {cli.cep}" if cli.cep else None])
    return partes or None


def _cabecalho(ordem) -> list[str]:
    linhas: list[str] = []
    if ordem.cliente_nome:
        linhas.append(f"Cliente: {ordem.cliente_nome}")
    patr = getattr(ordem.equipamento_rel, "patrimonio", None) if ordem.equipamento_rel else None
    ids = _juntar([f"Série {ordem.equipamento_serie}" if ordem.equipamento_serie else None,
                   f"Patr. {patr}" if patr else None], sep=" / ")
    aparelho = _juntar([ordem.equipamento_descricao, ids or None])
    if aparelho:
        linhas.append(f"Aparelho: {aparelho}")
    rotulo = TIPO_SERVICO_LABEL.get(ordem.tipo_servico)
    if rotulo:
        linhas.append(f"Serviço: {rotulo}")
    return linhas


def _bloco(linhas: list[str | None]) -> str | None:
    """Junta as linhas não-vazias em bullets. Sem título — a obs já é nomeada no TaskHS."""
    conteudo = [f"- {x}" for x in linhas if x]
    if not conteudo:
        return None
    return "\n".join(conteudo)


def _sec_recebido(ordem) -> str | None:
    chegada = _juntar([f"Chegada: {_fmt(ordem.data_chegada)}" if ordem.data_chegada else None,
                       f"Condição: {ordem.condicao_chegada}" if ordem.condicao_chegada else None])
    acess = ", ".join(ordem.acessorios_presentes) if ordem.acessorios_presentes else None
    pilhas_bocais = _juntar([f"Pilhas: {ordem.pilhas}" if ordem.pilhas else None,
                             f"Bocais: {ordem.bocais}" if ordem.bocais else None])
    return _bloco([
        chegada or None,
        f"Acessórios: {acess}" if acess else None,
        pilhas_bocais or None,
        f"Obs: {ordem.obs}" if ordem.obs else None,
    ])


def _sec_laboratorio(ordem, certificados: list[dict]) -> str | None:
    if not certificados:
        return None
    calibrado = _juntar([f"Calibrado em: {_fmt(ordem.data_calibracao)}" if ordem.data_calibracao else None,
                         f"Próxima: {_fmt(ordem.prox_calibragem)}" if ordem.prox_calibragem else None])
    links = [f"Certificado de {TIPO_SERVICO_LABEL.get(c['tipo'], c['tipo'])}: {c['url']}"
             for c in certificados if c.get("url")]
    return _bloco([
        f"Resultado: {ordem.calib_situacao}" if ordem.calib_situacao else None,
        calibrado or None,
        f"Certificado: {ordem.calib_cert}" if ordem.calib_cert else None,
        *links,
    ])


def _sec_posvendas(ordem) -> str | None:
    if wf.posicao(ordem.fase) < wf.posicao(6):
        return None
    cli = ordem.cliente_rel
    telefone = None
    if cli is not None:
        telefone = next((p for p in (cli.celular, cli.whatsapp, cli.telefones) if p), None)
    contato = _juntar([getattr(cli, "contato", None) if cli else None, telefone])
    aceite = None
    if ordem.aceite:
        aceite = f"Aceite: {_fmt(ordem.data_aceite)}" if ordem.data_aceite else "Aceite: sim"
    return _bloco([
        f"Contato: {contato}" if contato else None,
        aceite,
    ])


def _sec_financeiro(ordem, nota_fiscal_url: str | None = None) -> str | None:
    if wf.posicao(ordem.fase) < wf.posicao(10):
        return None
    if ordem.pago:
        pagamento = f"Pagamento: confirmado em {_fmt(ordem.data_pagamento)}" if ordem.data_pagamento else "Pagamento: confirmado"
    else:
        pagamento = "Pagamento: pendente"
    nota = None
    if ordem.nota_fiscal_numero:
        nota = f"Nota fiscal: {ordem.nota_fiscal_numero}"
        if nota_fiscal_url:
            nota = f"{nota} — {nota_fiscal_url}"
    return _bloco([pagamento, nota])


def _sec_preparando(ordem) -> str | None:
    if wf.posicao(ordem.fase) < wf.posicao(7):
        return None
    end = _endereco(ordem.cliente_rel)
    return _bloco([f"Enviar para: {end}" if end else None])


def _sec_finalizada(ordem) -> str | None:
    if not ordem.cod_retorno:
        return None
    linha = _juntar([f"Rastreio: {ordem.cod_retorno}",
                     f"Postado em: {_fmt(ordem.data_retorno)}" if ordem.data_retorno else None])
    return _bloco([linha or None])


def montar_obs(ordem, *, certificados: list[dict], nota_fiscal_url: str | None = None) -> dict:
    """Monta as 6 obs por etapa. Sempre retorna as 6 chaves (None quando a etapa não se aplica).

    obs1 leva o cabeçalho (Cliente/Aparelho/Serviço) no topo, seguido da seção Recebido.
    """
    cabecalho = "\n".join(_cabecalho(ordem)) or None
    recebido = _sec_recebido(ordem) if wf.posicao(ordem.fase) >= wf.posicao(4) else None
    obs1 = "\n".join([x for x in (cabecalho, recebido) if x]) or None
    return {
        "obs1": obs1,
        "obs2": _sec_laboratorio(ordem, certificados),
        "obs3": _sec_posvendas(ordem),
        "obs4": _sec_financeiro(ordem, nota_fiscal_url),
        "obs5": _sec_preparando(ordem),
        "obs6": _sec_finalizada(ordem),
    }


def montar_payload(ordem, *, list_id: int, arquivado: bool, obs: dict) -> dict:
    due_date = ordem.prox_calibragem.date().isoformat() if ordem.prox_calibragem else None
    return {
        "source": SOURCE,
        "external_id": str(ordem.id),
        "list_id": list_id,
        "title": montar_titulo(ordem),
        "obs1": obs.get("obs1"),
        "obs2": obs.get("obs2"),
        "obs3": obs.get("obs3"),
        "obs4": obs.get("obs4"),
        "obs5": obs.get("obs5"),
        "obs6": obs.get("obs6"),
        "due_date": due_date,
        "priority": "medium",
        "archived": arquivado,
    }
```

- [ ] **Step 5: Rodar os testes e ver passar**

Run: `cd backend && source .venv/bin/activate && pytest -q tests/test_taskhs.py tests/test_taskhs_descricao.py`
Expected: PASS.

- [ ] **Step 6: Commit** (confirmar com o Erick antes)

```bash
git add backend/app/core/taskhs.py backend/tests/test_taskhs.py backend/tests/test_taskhs_descricao.py
git commit -m "feat(taskhs): payload v2 com list_id e obs por etapa"
```

---

### Task 2: I/O `taskhs_client.py` (só envia payload)

**Files:**
- Modify: `backend/app/integrations/taskhs_client.py` (remove `espelhar_os` e o import de `taskhs`; adiciona `enviar_card_sync`)
- Test: `backend/tests/test_taskhs_client.py` (troca os testes de `espelhar_os` por `enviar_card_sync`)

**Interfaces:**
- Consumes: nada de outras tasks.
- Produces:
  - `integracao_ativa() -> bool` (inalterada)
  - `enviar_card(payload: dict) -> None` (best-effort; inalterada)
  - `enviar_card_sync(payload: dict) -> None` (envia propagando erro)
  - Remove: `espelhar_os`

- [ ] **Step 1: Ajustar `backend/tests/test_taskhs_client.py`**

Remover os dois testes `test_espelhar_os_*` (linhas 60–87) e o import `from types import SimpleNamespace` (não é mais usado). Adicionar, ao final do arquivo:

```python
def test_enviar_card_sync_chama_post(monkeypatch, ativa):
    enviados = {}
    monkeypatch.setattr(taskhs_client, "_post", lambda payload: enviados.update(payload))
    taskhs_client.enviar_card_sync({"external_id": "9"})
    assert enviados["external_id"] == "9"


def test_enviar_card_sync_propaga_excecao(monkeypatch, ativa):
    def boom(payload):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(taskhs_client, "_post", boom)
    with pytest.raises(httpx.ConnectError):
        taskhs_client.enviar_card_sync({"external_id": "1"})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && source .venv/bin/activate && pytest -q tests/test_taskhs_client.py`
Expected: FAIL (`AttributeError: ... has no attribute 'enviar_card_sync'`).

- [ ] **Step 3: Reescrever `backend/app/integrations/taskhs_client.py`**

Substituir o arquivo inteiro por:

```python
"""Cliente HTTP da integracao com o TaskHS (best-effort, gating por env)."""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def integracao_ativa() -> bool:
    return bool(settings.TASKHS_BASE_URL and settings.TASKHS_API_KEY)


def _post(payload: dict) -> None:
    """Faz o POST e levanta em erro (httpx.HTTPStatusError / rede)."""
    url = f"{settings.TASKHS_BASE_URL.rstrip('/')}/integration/cards"
    resp = httpx.post(
        url, json=payload,
        headers={"X-API-Key": settings.TASKHS_API_KEY},
        timeout=5,
    )
    resp.raise_for_status()


def enviar_card(payload: dict) -> None:
    """Alvo do BackgroundTask: no-op se desligada; nunca propaga (best-effort)."""
    if not integracao_ativa():
        return
    try:
        _post(payload)
    except Exception:
        logger.exception(
            "falha ao espelhar card no TaskHS (external_id=%s) — reconcilia no proximo upsert",
            payload.get("external_id"),
        )


def enviar_card_sync(payload: dict) -> None:
    """Envia PROPAGANDO erro (uso no script de backfill, que quer relatar falhas)."""
    _post(payload)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && source .venv/bin/activate && pytest -q tests/test_taskhs_client.py`
Expected: PASS.

- [ ] **Step 5: Commit** (confirmar com o Erick antes)

```bash
git add backend/app/integrations/taskhs_client.py backend/tests/test_taskhs_client.py
git commit -m "refactor(taskhs): client so envia payload; enviar_card_sync"
```

---

### Task 3: `espelhamento.py` monta o payload v2 e callers usam `list_id`

**Files:**
- Modify: `backend/app/api/espelhamento.py` (fonte única do payload; `agendar_espelhamento` passa a receber `list_id`; novo `espelhar_os_sync`)
- Modify: `backend/app/api/ordens.py:187,238,258` (`lista=taskhs.lista_da_fase(...)` → `list_id=taskhs.list_id_da_fase(...)`)
- Modify: `backend/app/api/notas_fiscais.py:50` (idem)
- Test: `backend/tests/test_ordens_taskhs.py` (asserções de payload: `list_id`/`obs`)

**Interfaces:**
- Consumes (Task 1): `taskhs.list_id_da_fase`, `taskhs.montar_obs`, `taskhs.montar_payload`. (Task 2): `taskhs_client.enviar_card_sync`.
- Produces:
  - `agendar_espelhamento(db, background_tasks, ordem, *, list_id, arquivado) -> None`
  - `espelhar_os_sync(db, ordem, *, list_id, arquivado) -> None`
  - `_montar_payload_os(db, ordem, *, list_id, arquivado) -> dict` (interno)

- [ ] **Step 1: Ajustar `backend/tests/test_ordens_taskhs.py`**

Fazer estas trocas de asserção:

Em `test_abrir_agenda_card_recebido`, trocar a linha 32:
```python
    assert p["list"] == "🚚 Expedição (Abrindo caixa)"
```
por:
```python
    assert p["list_id"] == 21
```

Em `test_avancar_agenda_card_laboratorio`, trocar a linha 61:
```python
    assert captura[0]["list"] == "🔬Laboratório Calibração"
```
por:
```python
    assert captura[0]["list_id"] == 22
```

Em `test_cancelar_agenda_card_arquivado_na_lista_de_origem`, trocar a linha 77:
```python
    assert p["list"] == "🚚 Expedição (Abrindo caixa)"  # fase de origem (Recebido)
```
por:
```python
    assert p["list_id"] == 21  # fase de origem (Recebido)
```

Substituir o corpo de `test_abrir_descricao_no_payload` (linhas 80–90) por (renomeando):
```python
def test_abrir_obs_no_payload(client, usuario_comum, fases_seed, os_base, caixa_base, captura):
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    p = captura[0]
    assert "Cliente: Cliente OS" in p["obs1"]  # cabeçalho no topo da obs1
    assert p["obs3"] is None  # ainda em Recebido, sem Pós-Vendas
    assert "description" not in p
```

Em `test_upload_nota_fiscal_reagenda_card`, trocar as linhas 108–109:
```python
    assert captura[0]["list"] == "💰 Financeiro"
    assert "Nota fiscal:" in captura[0]["description"]
```
por:
```python
    assert captura[0]["list_id"] == 30
    assert "Nota fiscal:" in captura[0]["obs4"]
```

Em `test_descricao_inclui_link_certificado`, trocar as linhas 129–130:
```python
    assert f"Certificado de Calibração: http://localhost:8001/publico/certificado/{oid}/calibracao?t=" \
        in captura[-1]["description"]
```
por:
```python
    assert f"Certificado de Calibração: http://localhost:8001/publico/certificado/{oid}/calibracao?t=" \
        in captura[-1]["obs2"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && source .venv/bin/activate && pytest -q tests/test_ordens_taskhs.py`
Expected: FAIL (`KeyError: 'list_id'` / `TypeError: agendar_espelhamento() got an unexpected keyword argument 'lista'`).

- [ ] **Step 3: Reescrever `backend/app/api/espelhamento.py`**

Substituir o arquivo inteiro por:

```python
"""Espelhamento da OS como card no TaskHS — compartilhado entre routers (ordens, notas_fiscais)
para evitar import circular. Fonte única do payload (contrato v2: list_id + obs)."""

from app.core import certificado_link
from app.core import nota_fiscal_link
from app.core import taskhs
from app.integrations import taskhs_client
from app.models import OSCertificado


def _montar_payload_os(db, ordem, *, list_id, arquivado) -> dict:
    """Junta certificados + nota fiscal, monta as obs e devolve o payload v2 completo."""
    certs = db.query(OSCertificado).filter(OSCertificado.os == ordem.id).all()
    certificados = [
        {"tipo": c.tipo, "url": certificado_link.link_certificado(ordem.id, c.tipo)}
        for c in certs
    ]
    nf_url = nota_fiscal_link.link_nota_fiscal(ordem.id) if ordem.nota_fiscal else None
    obs = taskhs.montar_obs(ordem, certificados=certificados, nota_fiscal_url=nf_url)
    return taskhs.montar_payload(ordem, list_id=list_id, arquivado=arquivado, obs=obs)


def agendar_espelhamento(db, background_tasks, ordem, *, list_id, arquivado):
    """Agenda o upsert no TaskHS (async, best-effort). No-op se sem list_id ou integração desligada."""
    if list_id is None or not taskhs_client.integracao_ativa():
        return
    payload = _montar_payload_os(db, ordem, list_id=list_id, arquivado=arquivado)
    background_tasks.add_task(taskhs_client.enviar_card, payload)


def espelhar_os_sync(db, ordem, *, list_id, arquivado):
    """Monta o payload e envia sincronamente, PROPAGANDO erro (uso no backfill)."""
    payload = _montar_payload_os(db, ordem, list_id=list_id, arquivado=arquivado)
    taskhs_client.enviar_card_sync(payload)
```

- [ ] **Step 4: Atualizar os callers em `backend/app/api/ordens.py`**

Trocar as três chamadas (linhas 187, 238, 258):
```python
    _agendar_espelhamento(db, background_tasks, ordem, lista=taskhs.lista_da_fase(ordem.fase), arquivado=False)
```
→ (linhas 187 e 238):
```python
    _agendar_espelhamento(db, background_tasks, ordem, list_id=taskhs.list_id_da_fase(ordem.fase), arquivado=False)
```
E a linha 258:
```python
    _agendar_espelhamento(db, background_tasks, ordem, lista=taskhs.lista_da_fase(origem), arquivado=True)
```
→
```python
    _agendar_espelhamento(db, background_tasks, ordem, list_id=taskhs.list_id_da_fase(origem), arquivado=True)
```

- [ ] **Step 5: Atualizar o caller em `backend/app/api/notas_fiscais.py:50`**

Trocar:
```python
    _agendar_espelhamento(db, background_tasks, o, lista=taskhs.lista_da_fase(o.fase), arquivado=False)
```
→
```python
    _agendar_espelhamento(db, background_tasks, o, list_id=taskhs.list_id_da_fase(o.fase), arquivado=False)
```

- [ ] **Step 6: Rodar e ver passar**

Run: `cd backend && source .venv/bin/activate && pytest -q tests/test_ordens_taskhs.py`
Expected: PASS.

- [ ] **Step 7: Commit** (confirmar com o Erick antes)

```bash
git add backend/app/api/espelhamento.py backend/app/api/ordens.py backend/app/api/notas_fiscais.py backend/tests/test_ordens_taskhs.py
git commit -m "feat(taskhs): espelhamento monta payload v2 (list_id e obs)"
```

---

### Task 4: Backfill `sincronizar_taskhs.py`

**Files:**
- Modify: `backend/app/scripts/sincronizar_taskhs.py` (`list_id_da_fase` + `espelhamento.espelhar_os_sync`)
- Test: `backend/tests/test_sincronizar_taskhs.py`

**Interfaces:**
- Consumes (Task 1): `taskhs.list_id_da_fase`. (Task 3): `espelhamento.espelhar_os_sync`.
- Produces: `sincronizar(db) -> tuple[int, int]` (assinatura inalterada).

- [ ] **Step 1: Ajustar `backend/tests/test_sincronizar_taskhs.py`**

Substituir o corpo de `test_sincronizar_envia_so_fases_4_a_8` (linhas 16–30) por:
```python
def test_sincronizar_envia_so_fases_4_a_8(db_session, os_base, fases_seed, monkeypatch):
    from app.api import espelhamento
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://t/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    _abrir_os(db_session, os_base, 4)
    _abrir_os(db_session, os_base, 8)
    _abrir_os(db_session, os_base, 9)  # cancelada: ignorada
    _abrir_os(db_session, os_base, 10)
    enviados = []
    monkeypatch.setattr(espelhamento, "espelhar_os_sync",
                        lambda db, ordem, *, list_id, arquivado=False: enviados.append((ordem.fase, list_id)))
    enviadas, total = sincronizar_taskhs.sincronizar(db_session)
    assert enviadas == 3
    assert total == 3
    assert sorted(f for f, _ in enviados) == [4, 8, 10]
    assert {lid for _, lid in enviados} == {21, 35, 30}
```
(O import `from app.integrations import taskhs_client` no topo pode ficar — ainda é usado por `test_sincronizar_desligada_levanta` via o gate em `sincronizar`.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && source .venv/bin/activate && pytest -q tests/test_sincronizar_taskhs.py`
Expected: FAIL (o script ainda chama `taskhs_client.espelhar_os` / `lista_da_fase`).

- [ ] **Step 3: Reescrever `backend/app/scripts/sincronizar_taskhs.py`**

Substituir o arquivo inteiro por:

```python
"""Backfill: espelha no TaskHS as OS já existentes (fases ativas + Finalizada).

Uso: python -m app.scripts.sincronizar_taskhs
Idempotente — pode rodar quantas vezes quiser.
"""
from sqlalchemy.orm import Session

from app.api import espelhamento
from app.core import taskhs
from app.core import os_workflow as wf
from app.integrations import taskhs_client
from app.models import Ordem
from app.models.database import SessionLocal

FASES_BACKFILL = list(wf.ATIVAS) + [wf.FASE_FINALIZADA]


def sincronizar(db: Session) -> tuple[int, int]:
    """Faz upsert de cada OS em fases ativas + Finalizada. Retorna (enviadas, total)."""
    if not taskhs_client.integracao_ativa():
        raise RuntimeError(
            "Integração desligada: configure TASKHS_BASE_URL e TASKHS_API_KEY."
        )
    ordens = (
        db.query(Ordem)
        .filter(Ordem.fase.in_(FASES_BACKFILL))
        .order_by(Ordem.id)
        .all()
    )
    enviadas = 0
    for o in ordens:
        list_id = taskhs.list_id_da_fase(o.fase)
        if list_id is None:
            continue
        try:
            espelhamento.espelhar_os_sync(db, o, list_id=list_id, arquivado=False)
            enviadas += 1
            print(f"OK   OS #{o.id} -> lista {list_id}")
        except Exception as e:  # noqa: BLE001 — relatório, segue para a próxima
            print(f"ERRO OS #{o.id}: {e}")
    return enviadas, len(ordens)


def main() -> None:
    db = SessionLocal()
    try:
        enviadas, total = sincronizar(db)
        print(f"\n{enviadas}/{total} OS sincronizadas com o TaskHS.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && source .venv/bin/activate && pytest -q tests/test_sincronizar_taskhs.py`
Expected: PASS.

- [ ] **Step 5: Commit** (confirmar com o Erick antes)

```bash
git add backend/app/scripts/sincronizar_taskhs.py backend/tests/test_sincronizar_taskhs.py
git commit -m "feat(taskhs): backfill usa list_id e obs ricas"
```

---

### Task 5: Changelog v1.18.0

**Files:**
- Modify: `frontend/src/app/changelog/data.ts` (nova entrada no topo do array `CHANGELOG`)

**Interfaces:**
- Consumes: nada.
- Produces: nada de código (só nota de release).

- [ ] **Step 1: Adicionar a entrada no topo do array `CHANGELOG`**

Em `frontend/src/app/changelog/data.ts`, inserir logo após `export const CHANGELOG: VersaoChangelog[] = [` (antes da entrada `1.17.0`):

```ts
  {
    versao: '1.18.0',
    data: '17/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Integração com o TaskHS atualizada: os cards de OS agora são posicionados na lista exata (por id) e as informações de cada etapa vão em campos de observação separados (Recebido, Laboratório, Pós-Vendas, Financeiro, Preparando Retorno e Finalizada), em vez de tudo na descrição — que passa a ser livre para anotações da equipe direto no TaskHS.' },
    ],
  },
```

- [ ] **Step 2: Verificar build/tipos do frontend**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: sem erros.

- [ ] **Step 3: Commit** (confirmar com o Erick antes)

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.18.0 — integracao TaskHS por list_id e obs"
```

---

## Verificação final (após todas as tasks)

- [ ] Rodar a suíte de backend inteira: `cd backend && source .venv/bin/activate && pytest -q`
  Expected: tudo verde.
- [ ] Conferir que não sobrou referência ao contrato v1:
  Run: `grep -rn "lista_da_fase\|FASE_PARA_LISTA\|montar_descricao\|\"board\"\|\"list\"\|espelhar_os\b" backend/app`
  Expected: nenhuma saída (fora de `list_id`).
```
