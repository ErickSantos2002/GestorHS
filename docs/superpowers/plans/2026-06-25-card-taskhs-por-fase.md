# Card do TaskHS por fase + certificado público — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enriquecer a `description` do card do TaskHS com um resumo cumulativo por fase da OS e adicionar um link de download público (sem login) do certificado.

**Architecture:** Lógica pura em `app/core/taskhs.py` (montagem da descrição) e novo `app/core/certificado_link.py` (token HMAC + URL). Endpoint público sem auth em `app/api/publico.py`. Wiring nos endpoints de OS consulta os certificados e passa a descrição montada ao payload. Tudo best-effort, idempotente, off-by-default como a integração já existente.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, httpx, hmac/hashlib (stdlib), pytest (SQLite in-memory, container Docker).

## Global Constraints

- Domínio em **PT-BR**. Backend roda em Docker: testes com `docker compose exec -T backend pytest ... -q`.
- A descrição é **remontada do zero a cada upsert**; cada seção só entra se tiver ≥1 linha com valor; seção aparece quando a OS atinge a fase dona dela.
- Fases: `Recebido=4, Laboratório=5, Pós-Vendas=6, Preparando Retorno=7, Finalizada=8`.
- Rótulos de serviço: `{"C": "Calibração", "M": "Manutenção", "A": "Ambas"}`.
- Datas no card: formato `DD/MM/AAAA` (usar `.date()` do DateTime).
- Token do certificado: `hmac_sha256(JWT_SECRET_KEY, f"cert:{ordem_id}:{tipo_codigo}").hexdigest()`, `tipo_codigo ∈ {"C","M"}`, **sem expiração**, validação com `hmac.compare_digest`.
- Endpoint público: `GET /publico/certificado/{ordem_id}/{tipo}` com `tipo ∈ {"calibracao","manutencao"}`, **sem autenticação**; token inválido → 403; tipo fora da whitelist ou certificado inexistente → 404; falha de render → 500; resposta `application/pdf` com `Content-Disposition: inline`.
- `CERT_PUBLIC_BASE_URL` (default `""`, sem barra final); vazio → card sai sem link (degradação graciosa).
- Integração off-by-default: testes rodam com integração desligada por padrão.
- Commits: Conventional Commits PT-BR **sem acentos**, uma linha, sem trailer de co-autor.

---

### Task 1: Montagem da descrição — `app/core/taskhs.py`

**Files:**
- Modify: `backend/app/core/taskhs.py`
- Test: `backend/tests/test_taskhs_descricao.py`

**Interfaces:**
- Consumes: nada (puro; lê atributos do `ordem` e do `ordem.cliente_rel`/`ordem.equipamento_rel`).
- Produces:
  - `TIPO_SERVICO_LABEL: dict[str, str]`
  - `montar_descricao(ordem, *, certificados: list[dict]) -> str | None` — `certificados` é lista de `{"tipo": "C"|"M", "url": str | None}`.
  - `montar_payload(ordem, *, lista: str, arquivado: bool, descricao: str | None = None) -> dict` (assinatura estendida; quando `descricao` é `None`, mantém o comportamento atual `ordem.obs or None`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_taskhs_descricao.py`:

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
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_descricao_completa_finalizada():
    d = taskhs.montar_descricao(_ordem(), certificados=[{"tipo": "C", "url": "http://x/c"}])
    assert "Cliente: Cliente X" in d
    assert "Aparelho: Bafômetro · Série SN-987 / Patr. PAT-1" in d
    assert "Serviço: Calibração" in d
    assert "📋 Recebido" in d
    assert "Chegada: 22/06/2026 · Condição: bom estado" in d
    assert "Acessórios: Bobinas, Cabos USB" in d
    assert "Pilhas: 4 · Bocais: 2" in d
    assert "Obs: veio sem maleta" in d
    assert "🔬 Laboratório" in d
    assert "Resultado: APROVADO" in d
    assert "Calibrado em: 23/06/2026 · Próxima: 10/07/2027" in d
    assert "Certificado: 12345" in d
    assert "Certificado de Calibração: http://x/c" in d
    assert "🤝 Pós-Vendas" in d
    assert "Contato: João · (11) 99999-9999" in d
    assert "Aceite: 24/06/2026" in d
    assert "🚚 Preparando Retorno" in d
    assert "Enviar para: Rua X, 100 ap 2 · Centro · São Paulo/SP · CEP 01000000" in d
    assert "📮 Finalizada" in d
    assert "Rastreio: BR123 · Postado em: 25/06/2026" in d


def test_secoes_aparecem_por_fase():
    # Em Recebido (fase 4): só cabeçalho + Recebido; sem Pós-Vendas/Retorno/Finalizada
    o = _ordem(fase=4, aceite=False, data_aceite=None, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[])
    assert "📋 Recebido" in d
    assert "🤝 Pós-Vendas" not in d
    assert "🚚 Preparando Retorno" not in d
    assert "📮 Finalizada" not in d
    assert "🔬 Laboratório" not in d  # sem certificados


def test_laboratorio_aparece_com_certificado():
    o = _ordem(fase=6, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[{"tipo": "M", "url": "http://x/m"}])
    assert "🔬 Laboratório" in d
    assert "Certificado de Manutenção: http://x/m" in d


def test_telefone_pega_primeiro_nao_vazio():
    o = _ordem(fase=6, cliente_rel=SimpleNamespace(
        endereco=None, numero=None, complemento=None, bairro=None, municipio=None,
        estado=None, cep=None, contato="Maria", celular=None, whatsapp="(11) 8888",
        telefones="3333-3333"))
    d = taskhs.montar_descricao(o, certificados=[])
    assert "Contato: Maria · (11) 8888" in d


def test_linhas_vazias_omitidas():
    o = _ordem(fase=4, condicao_chegada=None, acessorios_presentes=[], pilhas=0,
               bocais=0, obs=None, aceite=False, data_aceite=None,
               cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[])
    assert "Chegada: 22/06/2026" in d
    assert "Condição:" not in d
    assert "Acessórios:" not in d
    assert "Pilhas:" not in d


def test_link_omitido_quando_url_none():
    o = _ordem(fase=6, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[{"tipo": "C", "url": None}])
    assert "🔬 Laboratório" in d
    assert "Certificado de Calibração:" not in d


def test_montar_payload_usa_descricao_quando_passada():
    p = taskhs.montar_payload(_ordem(), lista="L", arquivado=False, descricao="RESUMO")
    assert p["description"] == "RESUMO"


def test_montar_payload_sem_descricao_mantem_obs():
    o = SimpleNamespace(id=1, cliente_nome=None, equipamento_descricao=None,
                        equipamento_serie=None, prox_calibragem=None, obs="apenas obs")
    p = taskhs.montar_payload(o, lista="L", arquivado=False)
    assert p["description"] == "apenas obs"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T backend pytest tests/test_taskhs_descricao.py -q`
Expected: FAIL (`AttributeError: module 'app.core.taskhs' has no attribute 'montar_descricao'`).

- [ ] **Step 3: Implement in `app/core/taskhs.py`**

Add the label map after the `FASE_PARA_LISTA` block:

```python
TIPO_SERVICO_LABEL: dict[str, str] = {"C": "Calibração", "M": "Manutenção", "A": "Ambas"}
```

Add these helpers and `montar_descricao` (after `montar_titulo`):

```python
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


def _bloco(titulo: str, linhas: list[str | None]) -> str | None:
    conteudo = [f"- {x}" for x in linhas if x]
    if not conteudo:
        return None
    return "\n".join([titulo, *conteudo])


def _sec_recebido(ordem) -> str | None:
    chegada = _juntar([f"Chegada: {_fmt(ordem.data_chegada)}" if ordem.data_chegada else None,
                       f"Condição: {ordem.condicao_chegada}" if ordem.condicao_chegada else None])
    acess = ", ".join(ordem.acessorios_presentes) if ordem.acessorios_presentes else None
    pilhas_bocais = _juntar([f"Pilhas: {ordem.pilhas}" if ordem.pilhas else None,
                             f"Bocais: {ordem.bocais}" if ordem.bocais else None])
    return _bloco("📋 Recebido", [
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
    nome = {"C": "Calibração", "M": "Manutenção"}
    links = [f"Certificado de {nome.get(c['tipo'], c['tipo'])}: {c['url']}"
             for c in certificados if c.get("url")]
    return _bloco("🔬 Laboratório", [
        f"Resultado: {ordem.calib_situacao}" if ordem.calib_situacao else None,
        calibrado or None,
        f"Certificado: {ordem.calib_cert}" if ordem.calib_cert else None,
        *links,
    ])


def _sec_posvendas(ordem) -> str | None:
    if ordem.fase < 6:
        return None
    cli = ordem.cliente_rel
    telefone = None
    if cli is not None:
        telefone = next((p for p in (cli.celular, cli.whatsapp, cli.telefones) if p), None)
    contato = _juntar([getattr(cli, "contato", None) if cli else None, telefone])
    aceite = None
    if ordem.aceite:
        aceite = f"Aceite: {_fmt(ordem.data_aceite)}" if ordem.data_aceite else "Aceite: sim"
    return _bloco("🤝 Pós-Vendas", [
        f"Contato: {contato}" if contato else None,
        aceite,
    ])


def _sec_preparando(ordem) -> str | None:
    if ordem.fase < 7:
        return None
    end = _endereco(ordem.cliente_rel)
    return _bloco("🚚 Preparando Retorno", [f"Enviar para: {end}" if end else None])


def _sec_finalizada(ordem) -> str | None:
    if not ordem.cod_retorno:
        return None
    linha = _juntar([f"Rastreio: {ordem.cod_retorno}",
                     f"Postado em: {_fmt(ordem.data_retorno)}" if ordem.data_retorno else None])
    return _bloco("📮 Finalizada", [linha or None])


def montar_descricao(ordem, *, certificados: list[dict]) -> str | None:
    cabecalho = "\n".join(_cabecalho(ordem)) or None
    secoes = [
        _sec_recebido(ordem) if ordem.fase >= 4 else None,
        _sec_laboratorio(ordem, certificados),
        _sec_posvendas(ordem),
        _sec_preparando(ordem),
        _sec_finalizada(ordem),
    ]
    blocos = [b for b in [cabecalho, *secoes] if b]
    return "\n\n".join(blocos) if blocos else None
```

Change `montar_payload` to accept and use `descricao`:

```python
def montar_payload(ordem, *, lista: str, arquivado: bool, descricao: str | None = None) -> dict:
    due_date = ordem.prox_calibragem.date().isoformat() if ordem.prox_calibragem else None
    return {
        "source": SOURCE,
        "external_id": str(ordem.id),
        "board": BOARD,
        "list": lista,
        "title": montar_titulo(ordem),
        "description": descricao if descricao is not None else (ordem.obs or None),
        "due_date": due_date,
        "priority": "medium",
        "archived": arquivado,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_taskhs_descricao.py tests/test_taskhs.py -q`
Expected: PASS (novos testes + os existentes de `test_taskhs.py` continuam verdes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/taskhs.py backend/tests/test_taskhs_descricao.py
git commit -m "feat(integracao): descricao cumulativa do card por fase"
```

---

### Task 2: Link assinado do certificado — `app/core/certificado_link.py`

**Files:**
- Modify: `backend/app/core/config.py` (1 setting)
- Create: `backend/app/core/certificado_link.py`
- Test: `backend/tests/test_certificado_link.py`

**Interfaces:**
- Consumes: `app.core.config.settings`.
- Produces:
  - `assinar(ordem_id: int, tipo_codigo: str) -> str`
  - `verificar(ordem_id: int, tipo_codigo: str, token: str) -> bool`
  - `link_certificado(ordem_id: int, tipo_codigo: str) -> str | None`
  - `NOME_PUBLICO = {"C": "calibracao", "M": "manutencao"}`

- [ ] **Step 1: Add the config setting**

In `backend/app/core/config.py`, dentro de `class Settings`, após `TASKHS_API_KEY`:

```python
    # Base pública do backend para o link de download do certificado no card do TaskHS.
    # Vazio = card sai sem link. Sem barra final. Ex.: "https://api.gestorhs..." / "http://localhost:8001"
    CERT_PUBLIC_BASE_URL: str = ""
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_certificado_link.py`:

```python
from app.core import certificado_link as cl
from app.core.config import settings


def test_assinar_deterministico():
    a = cl.assinar(1234, "C")
    b = cl.assinar(1234, "C")
    assert a == b and len(a) == 64  # sha256 hex


def test_assinar_varia_por_os_e_tipo():
    assert cl.assinar(1234, "C") != cl.assinar(1234, "M")
    assert cl.assinar(1234, "C") != cl.assinar(1235, "C")


def test_verificar_aceita_correto_rejeita_adulterado():
    tok = cl.assinar(1234, "C")
    assert cl.verificar(1234, "C", tok) is True
    assert cl.verificar(1234, "C", tok[:-1] + ("0" if tok[-1] != "0" else "1")) is False
    assert cl.verificar(1234, "M", tok) is False
    assert cl.verificar(1234, "C", "") is False


def test_link_none_quando_base_vazia(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "")
    assert cl.link_certificado(1234, "C") is None


def test_link_completo_com_base(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "http://localhost:8001")
    url = cl.link_certificado(1234, "C")
    assert url.startswith("http://localhost:8001/publico/certificado/1234/calibracao?t=")
    assert url.endswith(cl.assinar(1234, "C"))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker compose exec -T backend pytest tests/test_certificado_link.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.core.certificado_link'`).

- [ ] **Step 4: Write the implementation**

Create `backend/app/core/certificado_link.py`:

```python
"""Link público assinado para download do certificado (sem login no GestorHS)."""
import hashlib
import hmac

from app.core.config import settings

NOME_PUBLICO = {"C": "calibracao", "M": "manutencao"}


def assinar(ordem_id: int, tipo_codigo: str) -> str:
    mensagem = f"cert:{ordem_id}:{tipo_codigo}".encode()
    return hmac.new(settings.JWT_SECRET_KEY.encode(), mensagem, hashlib.sha256).hexdigest()


def verificar(ordem_id: int, tipo_codigo: str, token: str) -> bool:
    return hmac.compare_digest(assinar(ordem_id, tipo_codigo), token or "")


def link_certificado(ordem_id: int, tipo_codigo: str) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    nome = NOME_PUBLICO[tipo_codigo]
    return f"{base.rstrip('/')}/publico/certificado/{ordem_id}/{nome}?t={assinar(ordem_id, tipo_codigo)}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_certificado_link.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py backend/app/core/certificado_link.py backend/tests/test_certificado_link.py
git commit -m "feat(cert): link publico assinado para download do certificado"
```

---

### Task 3: Endpoint público do certificado — `app/api/publico.py`

**Files:**
- Create: `backend/app/api/publico.py`
- Modify: `backend/app/main.py` (registrar o router)
- Test: `backend/tests/test_publico_certificado.py`

**Interfaces:**
- Consumes: `app.core.certificado_link.{verificar, NOME_PUBLICO}`; `app.core.certificado_pdf.html_para_pdf`; modelos `Ordem`, `OSCertificado`.
- Produces: router `publico.router` com `GET /publico/certificado/{ordem_id}/{tipo}`.

`html_para_pdf(html_cert: str) -> bytes` já existe em `app/core/certificado_pdf.py`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_publico_certificado.py`:

```python
from app.core import certificado_link as cl


def _os_com_cert(db_session):
    from app.models import Cliente, Ordem, OSCertificado
    cli = Cliente(nome="Cliente Pub"); db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, fase=8, tipo_servico="C", situacao="F")
    db_session.add(o); db_session.flush()
    db_session.add(OSCertificado(os=o.id, tipo="C", html="<html>cert</html>"))
    db_session.commit()
    return o.id


def test_download_ok_com_token_valido(client, db_session, monkeypatch):
    from app.api import publico
    monkeypatch.setattr(publico, "html_para_pdf", lambda html: b"%PDF-fake")
    oid = _os_com_cert(db_session)
    tok = cl.assinar(oid, "C")
    r = client.get(f"/publico/certificado/{oid}/calibracao?t={tok}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == b"%PDF-fake"


def test_403_token_errado(client, db_session):
    oid = _os_com_cert(db_session)
    r = client.get(f"/publico/certificado/{oid}/calibracao?t=errado")
    assert r.status_code == 403


def test_404_tipo_invalido(client, db_session):
    oid = _os_com_cert(db_session)
    tok = cl.assinar(oid, "C")
    r = client.get(f"/publico/certificado/{oid}/xpto?t={tok}")
    assert r.status_code == 404


def test_404_certificado_inexistente(client, db_session):
    from app.models import Cliente, Ordem
    cli = Cliente(nome="Cliente Pub"); db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, fase=8, tipo_servico="C", situacao="F")
    db_session.add(o); db_session.commit()
    tok = cl.assinar(o.id, "M")
    r = client.get(f"/publico/certificado/{o.id}/manutencao?t={tok}")
    assert r.status_code == 404


def test_nao_exige_login(client, db_session, monkeypatch):
    from app.api import publico
    monkeypatch.setattr(publico, "html_para_pdf", lambda html: b"%PDF-fake")
    oid = _os_com_cert(db_session)
    tok = cl.assinar(oid, "C")
    # sem header Authorization
    assert client.get(f"/publico/certificado/{oid}/calibracao?t={tok}").status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T backend pytest tests/test_publico_certificado.py -q`
Expected: FAIL (`404` para todas — rota inexistente — ou ImportError de `app.api.publico`).

- [ ] **Step 3: Write the endpoint**

Create `backend/app/api/publico.py`:

```python
"""Endpoints públicos (sem autenticação). Hoje: download de certificado por token."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core import certificado_link
from app.core.certificado_pdf import html_para_pdf
from app.models import OSCertificado
from app.models.database import get_db

router = APIRouter(prefix="/publico", tags=["publico"])

# nome público -> código do tipo no OSCertificado
_TIPO_POR_NOME = {v: k for k, v in certificado_link.NOME_PUBLICO.items()}  # calibracao->C, manutencao->M


@router.get("/certificado/{ordem_id}/{tipo}")
def baixar_certificado_publico(ordem_id: int, tipo: str, t: str = "", db: Session = Depends(get_db)):
    tipo_codigo = _TIPO_POR_NOME.get(tipo)
    if tipo_codigo is None:
        raise HTTPException(status_code=404, detail="tipo inválido")
    if not certificado_link.verificar(ordem_id, tipo_codigo, t):
        raise HTTPException(status_code=403, detail="link inválido")
    osc = db.query(OSCertificado).filter(
        OSCertificado.os == ordem_id, OSCertificado.tipo == tipo_codigo
    ).first()
    if osc is None or not osc.html:
        raise HTTPException(status_code=404, detail="certificado não encontrado")
    try:
        pdf = html_para_pdf(osc.html)
    except Exception:
        raise HTTPException(status_code=500, detail="falha ao gerar PDF")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="certificado-{ordem_id}-{tipo}.pdf"'},
    )
```

In `backend/app/main.py`, add `publico` to the `from app.api import ...` line and register it with the other routers:

```python
app.include_router(publico.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_publico_certificado.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/publico.py backend/app/main.py backend/tests/test_publico_certificado.py
git commit -m "feat(cert): endpoint publico de download do certificado por token"
```

---

### Task 4: Wiring — descrição + certificados em `app/api/ordens.py`

**Files:**
- Modify: `backend/app/api/ordens.py` (imports + `abrir`/`avancar`/`cancelar`)
- Test: `backend/tests/test_ordens_taskhs.py` (estender)

**Interfaces:**
- Consumes: `taskhs.montar_descricao`, `taskhs.montar_payload(..., descricao=...)`, `certificado_link.link_certificado`, `OSCertificado`.
- Produces: helper `_agendar_espelhamento(db, background_tasks, ordem, *, lista, arquivado)` que centraliza a consulta de certificados + montagem da descrição + agendamento.

Hoje os três endpoints repetem o bloco `if taskhs_client.integracao_ativa(): payload = taskhs.montar_payload(...); background_tasks.add_task(...)` (linhas ~175-177, ~221-225, ~244-248). Substituir pelos chamados do helper.

- [ ] **Step 1: Write the failing test (extend)**

Append to `backend/tests/test_ordens_taskhs.py`:

```python
def test_abrir_descricao_no_payload(client, usuario_comum, fases_seed, os_base, caixa_base, captura):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    p = captura[0]
    assert "Cliente: Cliente OS" in p["description"]
    assert "📋 Recebido" in p["description"]
    assert "🤝 Pós-Vendas" not in p["description"]  # ainda em Recebido


def test_descricao_inclui_link_certificado(client, usuario_comum, fases_seed,
                                           os_base, caixa_base, captura, db_session, monkeypatch):
    from app.core.config import settings
    from app.models import OSCertificado
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "http://localhost:8001")
    h = _headers(client, "comum", "senha123")
    oid = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h).json()["id"]
    # simula laboratório concluído: certificado já gravado para a OS
    db_session.add(OSCertificado(os=oid, tipo="C", html="<html/>"))
    db_session.commit()
    captura.clear()
    # avança Recebido(4)→Laboratório(5) — função da fase de origem = Expedição (usuario_comum)
    r = client.post(f"/ordens/{oid}/avancar", json={}, headers=h)
    assert r.status_code == 200
    assert f"Certificado de Calibração: http://localhost:8001/publico/certificado/{oid}/calibracao?t=" \
        in captura[-1]["description"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T backend pytest tests/test_ordens_taskhs.py -q`
Expected: FAIL no novo `test_abrir_descricao_no_payload` (description ainda é só `obs`, sem cabeçalho/seções).

- [ ] **Step 3: Implement the wiring**

In `backend/app/api/ordens.py`, add the import near the other `app.core` imports:

```python
from app.core import certificado_link
```

Add the helper near the top of the module (after the imports, before the router routes — e.g. right after `LIMITE_FINALIZADAS_QUADRO = 300`):

```python
def _agendar_espelhamento(db, background_tasks, ordem, *, lista, arquivado):
    """Monta descrição (com links de certificado) e agenda o upsert no TaskHS."""
    if lista is None or not taskhs_client.integracao_ativa():
        return
    certs = db.query(OSCertificado).filter(OSCertificado.os == ordem.id).all()
    certificados = [
        {"tipo": c.tipo, "url": certificado_link.link_certificado(ordem.id, c.tipo)}
        for c in certs
    ]
    descricao = taskhs.montar_descricao(ordem, certificados=certificados)
    payload = taskhs.montar_payload(ordem, lista=lista, arquivado=arquivado, descricao=descricao)
    background_tasks.add_task(taskhs_client.enviar_card, payload)
```

Replace the three inline blocks:

`abrir` (atual):
```python
    if taskhs_client.integracao_ativa():
        payload = taskhs.montar_payload(ordem, lista=taskhs.lista_da_fase(ordem.fase), arquivado=False)
        background_tasks.add_task(taskhs_client.enviar_card, payload)
    return ordem
```
→
```python
    _agendar_espelhamento(db, background_tasks, ordem, lista=taskhs.lista_da_fase(ordem.fase), arquivado=False)
    return ordem
```

`avancar` (atual):
```python
    if taskhs_client.integracao_ativa():
        lista = taskhs.lista_da_fase(ordem.fase)
        if lista is not None:
            payload = taskhs.montar_payload(ordem, lista=lista, arquivado=False)
            background_tasks.add_task(taskhs_client.enviar_card, payload)
    return ordem
```
→
```python
    _agendar_espelhamento(db, background_tasks, ordem, lista=taskhs.lista_da_fase(ordem.fase), arquivado=False)
    return ordem
```

`cancelar` (atual):
```python
    if taskhs_client.integracao_ativa():
        lista = taskhs.lista_da_fase(origem)
        if lista is not None:
            payload = taskhs.montar_payload(ordem, lista=lista, arquivado=True)
            background_tasks.add_task(taskhs_client.enviar_card, payload)
    return ordem
```
→
```python
    _agendar_espelhamento(db, background_tasks, ordem, lista=taskhs.lista_da_fase(origem), arquivado=True)
    return ordem
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_ordens_taskhs.py -q`
Expected: PASS (testes existentes do wiring + os 2 novos).

- [ ] **Step 5: Run the full suite (no regression)**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/ordens.py backend/tests/test_ordens_taskhs.py
git commit -m "feat(integracao): card leva descricao por fase e link do certificado"
```

---

### Task 5: Verificação final + docs + changelog

**Files:**
- Modify: `backend/.env.example` (1 setting)
- Modify: `CLAUDE.md` (atualizar nota da integração)
- Modify: `frontend/src/app/changelog/data.ts` (entrada v1.10.0)

- [ ] **Step 1: Rodar a suíte completa**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS (tudo verde).

- [ ] **Step 2: Documentar a env**

Em `backend/.env.example`, após as envs do TaskHS, acrescentar:
```
# Base publica do backend para o link de download do certificado no card do TaskHS (vazio = sem link)
CERT_PUBLIC_BASE_URL=
```

- [ ] **Step 3: Atualizar a nota no CLAUDE.md**

Na subseção "Integração com o TaskHS" (em Arquitetura), acrescentar uma frase:
```markdown
O card leva uma descrição que cresce por fase (cabeçalho + seções Recebido/Laboratório/
Pós-Vendas/Preparando Retorno/Finalizada) e, na seção de Laboratório, um link público de
download do certificado (`/publico/certificado/...`, token HMAC sem login, via `app/core/certificado_link.py`
e `app/api/publico.py`; base em `CERT_PUBLIC_BASE_URL`).
```

- [ ] **Step 4: Changelog v1.10.0**

Em `frontend/src/app/changelog/data.ts`, inserir como **primeira** entrada do array `CHANGELOG`:
```ts
  {
    versao: '1.10.0',
    data: '25/06/2026',
    itens: [
      { tipo: 'melhoria', texto: 'O cartão da OS no TaskHS agora mostra um resumo que cresce a cada fase: dados do cliente e do aparelho, recebimento, resultado da calibração, contato para o Pós-Vendas, endereço de envio e código de rastreio. Na fase de Laboratório, o cartão traz um link para baixar o PDF do certificado direto do TaskHS, sem precisar entrar no GestorHS.' },
    ],
  },
```

- [ ] **Step 5: Verificar o frontend**

Run: `cd frontend && npx tsc -b --noEmit && npm run build`
Expected: tsc sem erros, build OK.

- [ ] **Step 6: Commit**

```bash
git add backend/.env.example CLAUDE.md frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.10.0 — card do TaskHS por fase e certificado publico"
```

---

## Notas de validação manual (fora dos testes)

Após implementar, com a integração ligada localmente (já configurada no `.env`) e
`CERT_PUBLIC_BASE_URL=http://localhost:8001`:

1. Reiniciar o container do backend (recarrega o `.env`).
2. Criar uma OS → conferir no card a descrição com cabeçalho + 📋 Recebido.
3. Avançar até o laboratório, gerar certificado, avançar → conferir 🔬 Laboratório com o link.
4. Clicar no link (anônimo/sem login) → o PDF abre.
5. Avançar até Preparando Retorno e Finalizada → conferir endereço e rastreio surgindo.
