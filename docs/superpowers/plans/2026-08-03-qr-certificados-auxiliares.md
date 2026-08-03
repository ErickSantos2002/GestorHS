# QR dos certificados auxiliares — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Imprimir no rodapé do certificado de calibração três QR codes — gás, termohigrômetro digital e barômetro digital — apontando para os PDFs já cadastrados em Certificados › Gerais, para que o cliente pare de receber esses três documentos impressos junto de cada certificado.

**Architecture:** A Configuração ganha três FKs para `certificado_geral`. Um módulo puro novo transforma `(rótulo, url)` em HTML com o QR em SVG; o link público assinado de cada documento é montado pelo `link_certificado_geral` que já existe. O bloco entra no certificado por um token **estrutural** `[qrcertificados]`, inserido sem escapar — a única categoria de token que escapa da regra de escape, ao lado de `[pulapagina]`.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · **segno** (novo) · pytest · React 19 · TypeScript · Vitest.

**Spec:** [`docs/superpowers/specs/2026-08-03-qr-certificados-auxiliares-design.md`](../specs/2026-08-03-qr-certificados-auxiliares-design.md)

## Global Constraints

- Idioma do domínio é PT-BR. Commits em português **sem acentos** (ASCII), Conventional Commits `tipo(escopo): descricao`, **uma linha**, sem corpo, sem trailer de co-autor. Escopo: `cert`.
- **`core/certificado_qr.py` e `core/certificado_calculo.py` são PUROS:** sem `Session`, sem I/O, sem import de `app.models`.
- **Testes rodam em SQLite in-memory via `create_all` — migrações Alembic NÃO rodam nos testes.** Todo default precisa existir no modelo.
- **NÃO rodar nenhum comando alembic.** O `DATABASE_URL` desta máquina aponta para **produção**.
- Migração `0025`, `down_revision = "0024_certificado_config_padroes"`.
- Fixtures de auth são clients já autenticados (`client_admin`, `client_lab`), não dicionários de header.
- **Rótulos fixos, exatos:** `Certificado do Gás`, `Certificado do Termohigrômetro Digital`, `Certificado do Barômetro Digital`.
- **Documento não configurado é omitido em silêncio** — nunca levanta exceção, nunca bloqueia a emissão.
- Baseline: backend `4 failed, 967 passed` (as 4 são `PermissionError` em `/data`, pré-existentes: 2 em `test_certificados_gerais.py`, 2 em `test_publico_certificado_geral.py`). Frontend `423 passed`, lint/tsc/build limpos.
- Verificação de frontend: `npm test && npm run lint && npx tsc -b --noEmit && npm run build`.

---

## Estrutura de arquivos

**Criar:** `backend/app/core/certificado_qr.py` (geração do HTML dos QR, puro) · `backend/alembic/versions/0025_certificado_docs_qr.py` · `backend/tests/test_certificado_qr.py`

**Modificar:** `backend/requirements.txt` (segno) · `backend/app/models/certificado_config.py` (3 FKs) · `backend/app/core/certificado_config.py` (`documentos_qr`) · `backend/app/core/certificado_gerar.py` (token estrutural + `CAMPOS` + bloco) · `backend/app/schemas/certificado_config.py` (3 campos) · `backend/tests/test_certificado_config.py` · `backend/tests/test_certificado_gerar.py` · `backend/tests/test_certificado_contexto.py` · `frontend/src/app/certificados/api.ts` (`CAMPOS_CERTIFICADO` + tipo) · `frontend/src/app/certificados/ConfiguracoesTab.tsx` · `frontend/src/app/certificados/ConfiguracoesTab.test.tsx`

---

## Task 1: Módulo puro de geração do QR

**Files:**
- Create: `backend/app/core/certificado_qr.py`, `backend/tests/test_certificado_qr.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: nada (primeira task).
- Produces: `qr_data_uri(url: str) -> str` · `bloco_qr(itens: Sequence[tuple[str, str]]) -> str`

- [ ] **Step 1: Instalar a dependência e registrá-la**

Acrescentar `segno` ao fim de `backend/requirements.txt` e instalar no venv:

```bash
cd backend && source .venv/bin/activate && pip install segno && echo "segno" >> requirements.txt
```

`segno` é Python puro, sem compilação e sem dependências transitivas — não precisa de Pillow.

- [ ] **Step 2: Escrever os testes que falham**

Criar `backend/tests/test_certificado_qr.py`:

```python
from app.core.certificado_qr import bloco_qr, qr_data_uri

URL = "https://gestor.exemplo.com/publico/certificado-geral/1?t=abc123"


def test_qr_data_uri_e_svg_pronto_para_src_de_img():
    uri = qr_data_uri(URL)
    # SVG e nao PNG: o certificado e IMPRESSO, e vetor sai nitido em qualquer
    # resolucao. QR borrado nao escaneia.
    assert uri.startswith("data:image/svg+xml")


def test_qr_data_uri_e_deterministico_para_a_mesma_url():
    # Sustenta os testes que provam QUAL url foi codificada comparando o data URI.
    assert qr_data_uri(URL) == qr_data_uri(URL)


def test_qr_data_uri_muda_quando_a_url_muda():
    assert qr_data_uri(URL) != qr_data_uri(URL + "x")


def test_bloco_com_tres_itens_traz_os_tres_rotulos_e_tres_imagens():
    html = bloco_qr([
        ("Certificado do Gás", URL),
        ("Certificado do Termohigrômetro Digital", URL + "/2"),
        ("Certificado do Barômetro Digital", URL + "/3"),
    ])
    assert "Certificado do Gás" in html
    assert "Certificado do Termohigrômetro Digital" in html
    assert "Certificado do Barômetro Digital" in html
    assert html.count("<img") == 3


def test_bloco_codifica_a_url_recebida_em_cada_qr():
    # Prova QUAL url entrou em cada QR sem precisar de leitor optico: o data URI e
    # deterministico, entao gerar o esperado e procurar no bloco basta.
    html = bloco_qr([("Certificado do Gás", URL)])
    assert qr_data_uri(URL) in html


def test_bloco_sem_itens_e_string_vazia():
    # Nenhum documento configurado: o certificado sai sem o bloco, e nao com uma
    # tabela vazia ocupando espaco no rodape.
    assert bloco_qr([]) == ""


def test_bloco_com_um_item_so_sai_com_um_qr():
    html = bloco_qr([("Certificado do Gás", URL)])
    assert html.count("<img") == 1


def test_bloco_escapa_o_rotulo():
    # Hoje os rotulos sao constantes do codigo, mas o bloco entra no certificado SEM
    # passar pelo escape geral — o escape tem de estar aqui desde o inicio.
    html = bloco_qr([("<script>alerta</script>", URL)])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_qr.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core.certificado_qr'`

- [ ] **Step 4: Implementar o módulo**

Criar `backend/app/core/certificado_qr.py`:

```python
"""QR codes dos certificados auxiliares (gas, termohigrometro, barometro) que vao no
rodape do certificado de calibracao.

Modulo PURO: sem Session, sem I/O, sem import de app.models. Descobrir QUAIS documentos
entram e qual e a URL de cada um e trabalho de `core/certificado_config.documentos_qr`;
aqui so se transforma (rotulo, url) em HTML.
"""
from collections.abc import Sequence
from html import escape as _html_escape

import segno

# Escala do QR. 3 da ~90px de lado no PDF: grande o bastante para a camera de um celular
# pegar e pequeno o bastante para os tres caberem lado a lado no rodape da pagina 2 —
# que e o requisito, porque o pedido nasceu de economizar papel.
_ESCALA = 3

# Lado da imagem no HTML, em px. Casado com _ESCALA para o QR nao ser reamostrado.
_LADO_PX = 90


def qr_data_uri(url: str) -> str:
    """URL -> QR como SVG num data: URI, pronto para o `src` de um `<img>`.

    SVG e nao PNG porque o certificado e IMPRESSO: vetor sai nitido em qualquer
    resolucao, enquanto um PNG de poucos pixels borra no papel — e QR borrado nao
    escaneia. De quebra, dispensa Pillow.
    """
    return segno.make(url).svg_data_uri(scale=_ESCALA)


def bloco_qr(itens: Sequence[tuple[str, str]]) -> str:
    """Os QRs lado a lado, cada um com seu rotulo acima. Sem itens devolve ''.

    O retorno entra no certificado SEM passar pelo escape geral (e um token
    estrutural), entao o escape do rotulo tem de acontecer aqui. Hoje os rotulos sao
    constantes do codigo; o dia em que virarem configuraveis, o escape ja esta no lugar.
    """
    if not itens:
        return ""
    celulas = "".join(
        '<td style="text-align:center; padding:0 10px; border:0">'
        f'<div style="font-size:11px; margin-bottom:3px">{_html_escape(rotulo)}</div>'
        f'<img src="{qr_data_uri(url)}" width="{_LADO_PX}" height="{_LADO_PX}" '
        f'alt="{_html_escape(rotulo)}" />'
        "</td>"
        for rotulo, url in itens
    )
    return (
        '<table align="center" cellpadding="0" cellspacing="0" '
        'style="border:0; margin:0 auto"><tbody><tr>'
        f"{celulas}"
        "</tr></tbody></table>"
    )
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_qr.py -v`
Expected: PASS — 8 testes.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/certificado_qr.py backend/tests/test_certificado_qr.py backend/requirements.txt
git commit -m "feat(cert): modulo puro que gera o bloco de qr dos certificados auxiliares"
```

---

## Task 2: Os três documentos na Configuração

**Files:**
- Create: `backend/alembic/versions/0025_certificado_docs_qr.py`
- Modify: `backend/app/models/certificado_config.py`, `backend/app/core/certificado_config.py`, `backend/app/schemas/certificado_config.py`
- Test: `backend/tests/test_certificado_config.py` (acrescentar)

**Interfaces:**
- Consumes: nada da Task 1 (independente).
- Produces: colunas `CertificadoConfig.doc_gas_id` / `doc_termohigrometro_id` / `doc_barometro_id` · `DOCUMENTOS_QR: tuple[tuple[str, str], ...]` · `documentos_qr(db: Session, config: CertificadoConfig) -> list[tuple[str, str]]`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `backend/tests/test_certificado_config.py`:

```python
# --- documentos auxiliares que viram QR no certificado ---------------------------

def _doc_geral(db, nome="Certificado do Gás", arquivo="a.pdf"):
    from app.models import CertificadoGeral
    d = CertificadoGeral(nome=nome, arquivo=arquivo)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def test_documentos_qr_traz_os_tres_configurados(db_session, monkeypatch):
    from app.core import certificado_geral_link
    from app.core.certificado_config import documentos_qr, obter_config
    monkeypatch.setattr(certificado_geral_link.settings, "CERT_PUBLIC_BASE_URL", "https://x.com")

    gas = _doc_geral(db_session, "Gás", "g.pdf")
    termo = _doc_geral(db_session, "Termo", "t.pdf")
    baro = _doc_geral(db_session, "Baro", "b.pdf")
    cfg = obter_config(db_session)
    cfg.doc_gas_id, cfg.doc_termohigrometro_id, cfg.doc_barometro_id = gas.id, termo.id, baro.id
    db_session.commit()

    itens = documentos_qr(db_session, cfg)
    assert [rotulo for rotulo, _ in itens] == [
        "Certificado do Gás",
        "Certificado do Termohigrômetro Digital",
        "Certificado do Barômetro Digital",
    ]
    assert all(f"/publico/certificado-geral/" in url for _, url in itens)


def test_documentos_qr_pula_o_que_nao_foi_configurado(db_session, monkeypatch):
    from app.core import certificado_geral_link
    from app.core.certificado_config import documentos_qr, obter_config
    monkeypatch.setattr(certificado_geral_link.settings, "CERT_PUBLIC_BASE_URL", "https://x.com")

    gas = _doc_geral(db_session, "Gás", "g.pdf")
    cfg = obter_config(db_session)
    cfg.doc_gas_id = gas.id          # os outros dois ficam nulos
    db_session.commit()

    itens = documentos_qr(db_session, cfg)
    assert [rotulo for rotulo, _ in itens] == ["Certificado do Gás"]


def test_documentos_qr_pula_documento_excluido_do_cadastro(db_session, monkeypatch):
    from app.core import certificado_geral_link
    from app.core.certificado_config import documentos_qr, obter_config
    monkeypatch.setattr(certificado_geral_link.settings, "CERT_PUBLIC_BASE_URL", "https://x.com")

    cfg = obter_config(db_session)
    cfg.doc_gas_id = 9999            # id que nao existe mais
    db_session.commit()

    # Nao levanta: um documento excluido nao pode impedir a emissao do certificado.
    assert documentos_qr(db_session, cfg) == []


def test_documentos_qr_vazio_sem_base_url_publica(db_session, monkeypatch):
    from app.core import certificado_geral_link
    from app.core.certificado_config import documentos_qr, obter_config
    monkeypatch.setattr(certificado_geral_link.settings, "CERT_PUBLIC_BASE_URL", "")

    gas = _doc_geral(db_session, "Gás", "g.pdf")
    cfg = obter_config(db_session)
    cfg.doc_gas_id = gas.id
    db_session.commit()

    # Sem base publica nao ha link para o QR apontar — sai sem bloco, sem erro.
    assert documentos_qr(db_session, cfg) == []


def test_config_api_grava_os_tres_documentos(client_admin, db_session):
    gas = _doc_geral(db_session, "Gás", "g.pdf")
    r = client_admin.put("/certificado-config", json={"doc_gas_id": gas.id})
    assert r.status_code == 200
    assert r.json()["doc_gas_id"] == gas.id
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_config.py -v -k documentos_qr`
Expected: FAIL com `ImportError: cannot import name 'documentos_qr'`

- [ ] **Step 3: Acrescentar as colunas ao modelo**

Em `backend/app/models/certificado_config.py`, acrescentar ao fim da classe (e `ForeignKey` ao import de `sqlalchemy`, se ainda não estiver lá):

```python
    # Documentos auxiliares que viram QR no rodape do certificado. Guarda-se o ID e nao
    # a URL: o link publico e assinado e derivado na hora, entao continua valido se a
    # chave HMAC ou a CERT_PUBLIC_BASE_URL mudarem.
    doc_gas_id = Column(Integer, ForeignKey("certificados_gerais.id"), nullable=True)
    doc_termohigrometro_id = Column(Integer, ForeignKey("certificados_gerais.id"), nullable=True)
    doc_barometro_id = Column(Integer, ForeignKey("certificados_gerais.id"), nullable=True)
```

> Nomes de tabela conferidos: `CertificadoGeral.__tablename__ == "certificados_gerais"` e `CertificadoConfig.__tablename__ == "certificado_config"`. São esses os nomes usados nas FKs e na migração.

- [ ] **Step 4: Implementar `documentos_qr`**

Em `backend/app/core/certificado_config.py`, acrescentar ao import de models `CertificadoGeral`, importar `from app.core.certificado_geral_link import link_certificado_geral`, e acrescentar ao fim do arquivo:

```python
# Rotulo fixo de cada documento, na ordem em que sai no certificado. O nome cadastrado
# do documento nao serve como rotulo: hoje sao "LV09700-06672-26" e afins, numeros de
# certificado que nao dizem ao cliente o que ele esta baixando.
DOCUMENTOS_QR: tuple[tuple[str, str], ...] = (
    ("doc_gas_id", "Certificado do Gás"),
    ("doc_termohigrometro_id", "Certificado do Termohigrômetro Digital"),
    ("doc_barometro_id", "Certificado do Barômetro Digital"),
)


def documentos_qr(db: Session, config: CertificadoConfig) -> list[tuple[str, str]]:
    """(rotulo, link publico) de cada documento auxiliar configurado.

    Descarta EM SILENCIO o que nao da para montar — FK nula, documento excluido do
    cadastro, ou sem CERT_PUBLIC_BASE_URL. Um documento faltando nao pode impedir a
    emissao do certificado: o laboratorio percebe pela ausencia do QR e corrige em
    Configuracoes, sem ninguem ficar sem certificado.
    """
    itens: list[tuple[str, str]] = []
    for campo, rotulo in DOCUMENTOS_QR:
        cert_id = getattr(config, campo, None)
        if not cert_id:
            continue
        doc = db.get(CertificadoGeral, cert_id)
        if doc is None:
            continue
        url = link_certificado_geral(doc.id)
        if not url:
            continue
        itens.append((rotulo, url))
    return itens
```

- [ ] **Step 5: Acrescentar os três campos aos schemas**

Em `backend/app/schemas/certificado_config.py`, dentro de `CertificadoConfigIn`, depois de `margem_temperatura`:

```python
    doc_gas_id: int | None = None
    doc_termohigrometro_id: int | None = None
    doc_barometro_id: int | None = None
```

`CertificadoConfigOut` herda de `CertificadoConfigIn`, então ganha os três automaticamente.

- [ ] **Step 6: Rodar os testes e confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_config.py -v`
Expected: PASS.

- [ ] **Step 7: Escrever a migração**

Criar `backend/alembic/versions/0025_certificado_docs_qr.py`:

```python
"""certificado: documentos auxiliares (gas, termohigrometro, barometro) que viram QR"""
import sqlalchemy as sa
from alembic import op

revision = "0025_certificado_docs_qr"
down_revision = "0024_certificado_config_padroes"
branch_labels = None
depends_on = None

_COLUNAS = ("doc_gas_id", "doc_termohigrometro_id", "doc_barometro_id")


def upgrade() -> None:
    for coluna in _COLUNAS:
        op.add_column("certificado_config", sa.Column(coluna, sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_certificado_config_{coluna}", "certificado_config",
            "certificados_gerais", [coluna], ["id"],
        )


def downgrade() -> None:
    for coluna in reversed(_COLUNAS):
        op.drop_constraint(f"fk_certificado_config_{coluna}", "certificado_config", type_="foreignkey")
        op.drop_column("certificado_config", coluna)
```

**Não aplicar.** O `DATABASE_URL` desta máquina aponta para produção; aplicar é passo de deploy que o Erick executa.

- [ ] **Step 8: Rodar a suíte inteira e commitar**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: `4 failed` (as pré-existentes), nenhuma nova.

```bash
git add backend/app/models/certificado_config.py backend/app/core/certificado_config.py \
        backend/app/schemas/certificado_config.py backend/tests/test_certificado_config.py \
        backend/alembic/versions/0025_certificado_docs_qr.py
git commit -m "feat(cert): configuracao guarda os tres documentos auxiliares do qr"
```

---

## Task 3: O token estrutural `[qrcertificados]`

**Files:**
- Modify: `backend/app/core/certificado_gerar.py`
- Test: `backend/tests/test_certificado_gerar.py`, `backend/tests/test_certificado_contexto.py` (acrescentar)

**Interfaces:**
- Consumes: `bloco_qr` (Task 1) · `documentos_qr`, `DOCUMENTOS_QR` (Task 2).
- Produces: chave de contexto `qrcertificados` emitida pelos três caminhos · `_TOKENS_ESTRUTURAIS: frozenset[str]`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `backend/tests/test_certificado_gerar.py`:

```python
def test_preencher_nao_escapa_o_token_estrutural_do_qr():
    from app.core.certificado_gerar import preencher
    bloco = '<table><tr><td><img src="data:image/svg+xml,abc" /></td></tr></table>'
    html = preencher("<p>[qrcertificados]</p>", {"qrcertificados": bloco})
    # HTML que NOS geramos entra inteiro; escapado sairia "&lt;table&gt;" impresso no PDF
    assert bloco in html
    assert "&lt;table&gt;" not in html


def test_preencher_continua_escapando_dado_do_usuario():
    from app.core.certificado_gerar import preencher
    html = preencher("<p>[nomecli]</p>", {"nomecli": "<script>x</script>", "qrcertificados": ""})
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_preencher_sem_documentos_nao_deixa_o_token_no_html():
    from app.core.certificado_gerar import preencher
    html = preencher("<p>[qrcertificados]</p>", {"qrcertificados": ""})
    # Token nao substituido sai LITERALMENTE escrito no PDF do cliente
    assert "[qrcertificados]" not in html
```

Acrescentar a `backend/tests/test_certificado_contexto.py`:

```python
def test_contexto_da_os_emite_a_chave_do_qr(db_session, os_base):
    ordem = _os_com_dados(db_session, os_base)
    ctx = montar_contexto(db_session, ordem)
    # Sem nenhum documento configurado o valor e vazio — mas a CHAVE tem de existir,
    # senao o token sai literalmente escrito no certificado.
    assert "qrcertificados" in ctx
    assert ctx["qrcertificados"] == ""


def test_contexto_com_documento_configurado_traz_o_bloco(db_session, os_base, monkeypatch):
    from app.core import certificado_geral_link
    from app.core.certificado_config import obter_config
    from app.models import CertificadoGeral
    monkeypatch.setattr(certificado_geral_link.settings, "CERT_PUBLIC_BASE_URL", "https://x.com")

    doc = CertificadoGeral(nome="Gás", arquivo="g.pdf")
    db_session.add(doc)
    db_session.commit()
    cfg = obter_config(db_session)
    cfg.doc_gas_id = doc.id
    db_session.commit()

    ordem = _os_com_dados(db_session, os_base)
    ctx = montar_contexto(db_session, ordem)
    assert "Certificado do Gás" in ctx["qrcertificados"]
    assert "<img" in ctx["qrcertificados"]
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_gerar.py tests/test_certificado_contexto.py -v -k "qr or escapa"`
Expected: FAIL — `KeyError: 'qrcertificados'` e o token saindo escapado.

- [ ] **Step 3: Declarar os tokens estruturais e mudar `preencher`**

Em `backend/app/core/certificado_gerar.py`, logo abaixo de `_PAGE_BREAK`:

```python
# Tokens cujo valor e HTML que NOS geramos — nao dado digitado — e por isso entra sem
# escapar. Todo o resto do contexto e escapado, e e o que impede um nome de cliente com
# <script> de virar HTML executavel no certificado.
#
# Os dois funcionam diferente: `pulapagina` NAO esta no contexto (seu valor e a
# constante _PAGE_BREAK); `qrcertificados` esta, porque muda a cada certificado.
# Este conjunto so decide quem escapa do escape.
_TOKENS_ESTRUTURAIS = frozenset({"pulapagina", "qrcertificados"})
```

E substituir `preencher` por:

```python
def preencher(html: str, contexto: dict[str, str]) -> str:
    # O template é HTML confiável (editado só por admin/laboratório), mas os
    # VALORES vêm de dados (cliente, série, etc.) e são escapados para evitar
    # injeção de HTML/script no certificado renderizado.
    if not html:
        return html or ""
    for campo, valor in contexto.items():
        if campo in _TOKENS_ESTRUTURAIS:
            continue
        html = html.replace(f"[{campo}]", _html_escape(valor or "", quote=True))
    # Estruturais, sem escapar.
    html = html.replace("[qrcertificados]", contexto.get("qrcertificados") or "")
    html = html.replace("[pulapagina]", _PAGE_BREAK)
    return html
```

- [ ] **Step 4: Emitir a chave nos três caminhos**

Acrescentar `"qrcertificados"` ao fim de `_CHAVES_CALCULADAS` — é o que garante que OS, avulso e venda emitam a chave, com valor vazio onde não houver bloco.

Acrescentar a `CAMPOS`, logo antes de `("pulapagina", ...)`:

```python
    ("qrcertificados", "QR dos certificados auxiliares (gás, termohigrômetro, barômetro)"),
```

Em `_bloco_certificado`, acrescentar ao import local e ao dicionário `bloco`:

```python
    from app.core.certificado_config import documentos_qr, obter_config, parametros_de
    from app.core.certificado_qr import bloco_qr
```

```python
        "qrcertificados": bloco_qr(documentos_qr(db, config)),
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_gerar.py tests/test_certificado_contexto.py tests/test_certificado_contexto_venda.py -v`
Expected: PASS — os três compartilham `_montar_contexto` e são a guarda da paridade de chaves.

- [ ] **Step 6: Rodar a suíte inteira e commitar**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: `4 failed` (as pré-existentes), nenhuma nova.

```bash
git add backend/app/core/certificado_gerar.py backend/tests/test_certificado_gerar.py \
        backend/tests/test_certificado_contexto.py
git commit -m "feat(cert): token estrutural qrcertificados no motor de certificado"
```

---

## Task 4: Os três selects em Configurações

**Files:**
- Modify: `frontend/src/app/certificados/api.ts`, `frontend/src/app/certificados/ConfiguracoesTab.tsx`
- Test: `frontend/src/app/certificados/ConfiguracoesTab.test.tsx` (acrescentar)

**Interfaces:**
- Consumes: `PUT /certificado-config` com `doc_gas_id`/`doc_termohigrometro_id`/`doc_barometro_id` (Task 2) · `certificadosApi.listarGerais()` (já existe, devolve `CertGeralItem[]`).
- Produces: nada consumido por código posterior.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao `describe` de `frontend/src/app/certificados/ConfiguracoesTab.test.tsx`. O mock de `./api` no topo do arquivo precisa ganhar `listarGerais: vi.fn()`, e o `beforeEach`, `vi.mocked(certificadosApi.listarGerais).mockResolvedValue(GERAIS)` com:

```tsx
const GERAIS = [
  { id: 1, nome: 'Certificado do Gás', data_upload: null, usuario_nome: null, link: 'https://x/1' },
  { id: 3, nome: 'LV09700-06672-26', data_upload: null, usuario_nome: null, link: 'https://x/3' },
]
```

```tsx
  it('lista os documentos gerais nos tres selects', async () => {
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByLabelText(/certificado do g.s/i)).toBeInTheDocument())
    expect(screen.getByLabelText(/termohigr/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/bar.metro/i)).toBeInTheDocument()
    // cada select oferece os documentos cadastrados
    expect(screen.getAllByRole('option', { name: 'LV09700-06672-26' })).toHaveLength(3)
  })

  it('salva os ids dos documentos escolhidos', async () => {
    vi.mocked(certificadosApi.salvarConfig).mockResolvedValue({ ...CONFIG, doc_gas_id: 1 })
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByLabelText(/certificado do g.s/i)).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText(/certificado do g.s/i), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: /^salvar$/i }))

    await waitFor(() => expect(certificadosApi.salvarConfig).toHaveBeenCalledTimes(1))
    expect(vi.mocked(certificadosApi.salvarConfig).mock.calls[0][0]).toMatchObject({ doc_gas_id: 1 })
  })

  it('nenhum documento selecionado envia nulo, nao string vazia', async () => {
    vi.mocked(certificadosApi.salvarConfig).mockResolvedValue(CONFIG)
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByLabelText(/certificado do g.s/i)).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText(/certificado do g.s/i), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /^salvar$/i }))

    await waitFor(() => expect(certificadosApi.salvarConfig).toHaveBeenCalledTimes(1))
    expect(vi.mocked(certificadosApi.salvarConfig).mock.calls[0][0].doc_gas_id).toBeNull()
  })
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd frontend && npx vitest run src/app/certificados/ConfiguracoesTab.test.tsx`
Expected: FAIL — os selects não existem.

- [ ] **Step 3: Acrescentar os campos ao tipo e o token à paleta**

Em `frontend/src/app/certificados/api.ts`, na interface `CertificadoConfig`, depois de `margem_temperatura`:

```ts
  doc_gas_id: number | null
  doc_termohigrometro_id: number | null
  doc_barometro_id: number | null
```

E em `CAMPOS_CERTIFICADO`, antes de `{ campo: '[pulapagina]', ... }`:

```ts
  { campo: '[qrcertificados]', desc: 'QR dos certificados auxiliares (gás, termohigrômetro, barômetro)' },
```

Essa segunda lista alimenta a paleta do editor de modelos. Token que só entra no backend existe no motor mas fica **invisível** para quem monta o template.

- [ ] **Step 4: Acrescentar o bloco de selects**

Em `ConfiguracoesTab.tsx`: carregar a lista no `useEffect` inicial (`certificadosApi.listarGerais().then(setGerais).catch(() => setGerais([]))`, com `const [gerais, setGerais] = useState<CertGeralItem[]>([])`), e acrescentar um bloco depois do de *Laboratório*:

```tsx
      <div className="space-y-3">
        <p className={secao}>Documentos anexos ao certificado</p>
        <p className="text-xs text-slate-500">
          Viram QR code no rodapé do certificado de calibração, no lugar de irem impressos junto.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {DOCUMENTOS_QR.map(([chave, rotulo]) => (
            <div key={chave}>
              <label htmlFor={chave} className="block text-xs text-slate-400 mb-1">{rotulo}</label>
              <select id={chave} disabled={!podeEditar} value={config[chave] ?? ''}
                className="w-full rounded-lg bg-background-elevated border border-slate-700 p-2 text-sm text-slate-200"
                onChange={(e) => alterar({ [chave]: e.target.value ? Number(e.target.value) : null } as Partial<CertificadoConfig>)}>
                <option value="">— nenhum —</option>
                {gerais.map((g) => <option key={g.id} value={g.id}>{g.nome}</option>)}
              </select>
            </div>
          ))}
        </div>
      </div>
```

com a lista, junto de `CAMPOS_NUMERICOS`:

```tsx
/** Espelha DOCUMENTOS_QR em backend/app/core/certificado_config.py — mudou lá, mude aqui. */
const DOCUMENTOS_QR = [
  ['doc_gas_id', 'Certificado do Gás'],
  ['doc_termohigrometro_id', 'Certificado do Termohigrômetro Digital'],
  ['doc_barometro_id', 'Certificado do Barômetro Digital'],
] as const
```

- [ ] **Step 5: Rodar os testes e a verificação completa**

Run: `cd frontend && npx vitest run src/app/certificados/ConfiguracoesTab.test.tsx`, depois `npm test && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: PASS, tudo limpo.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/certificados/api.ts frontend/src/app/certificados/ConfiguracoesTab.tsx \
        frontend/src/app/certificados/ConfiguracoesTab.test.tsx
git commit -m "feat(cert): selecao dos documentos auxiliares na aba configuracoes"
```

---

## Task 5: Verificação no PDF de verdade

**Files:** nenhum de código — é a prova de que o recurso funciona no artefato final.

**Interfaces:**
- Consumes: tudo das Tasks 1–4.

- [ ] **Step 1: Reconstruir a imagem do container**

A dependência `segno` vive na imagem, não no código montado. Sem isto a API quebra ao gerar certificado.

Run: `cd /home/ericks/github/GestorHS && docker compose build backend && docker compose up -d`
Expected: build sem erro; `docker ps` mostra o container de pé.

- [ ] **Step 2: Configurar os três documentos e colar o token**

Selecionar os três documentos em Certificados › Configurações pela tela, e colar `[qrcertificados]` no template do **Interlock X6** (equipamento 38), depois da assinatura `FIEMS / SENAI - Metrologia`.

- [ ] **Step 3: Renderizar o PDF e conferir que continua em 2 páginas**

Run:
```bash
cd /home/ericks/github/GestorHS/backend && docker exec gestorhs-backend python -c "
from datetime import date
from app.models.database import SessionLocal
from app.core.certificado_gerar import montar_contexto_avulso, preencher
from app.core.certificado_pdf import html_para_pdf
from app.models import CertificadoModelo
db = SessionLocal()
m = db.query(CertificadoModelo).filter(CertificadoModelo.equipamento==38, CertificadoModelo.tipo=='C').first()
ctx = montar_contexto_avulso(db, {'equipamento': 38, 'data_calibracao': date.today()})
pdf = html_para_pdf(preencher(m.texto, ctx))
open('/app/.tmp-qr.pdf','wb').write(pdf)
print('paginas:', pdf.count(b'/Type /Page') - pdf.count(b'/Type /Pages'))
"
```
Expected: `paginas: 2`. Se sair 3, reduzir `_LADO_PX` em `certificado_qr.py` ou os espaçadores do template — uma folha a mais por certificado contraria o motivo do pedido.

- [ ] **Step 4: Decodificar os QR do PDF renderizado**

Provar que cada QR resolve no link certo, em vez de confiar que "parece um QR":

```bash
cd /home/ericks/github/GestorHS/backend && pdftoppm -png -r 150 -f 2 -l 2 .tmp-qr.pdf /tmp/qrpag
/tmp/claude-1000/-home-ericks-github-GestorHS/c7a214ee-3515-400f-b371-798fa1b27a23/scratchpad/qrenv/bin/python -c "
import zxingcpp
from PIL import Image
lidos = zxingcpp.read_barcodes(Image.open('/tmp/qrpag-2.png'))
print('QRs lidos:', len(lidos))
for r in lidos: print(' ', r.text)
"
```
Expected: 3 QRs, cada um com uma URL `/publico/certificado-geral/{id}?t=...`. O venv `qrenv` do scratchpad tem `zxing-cpp` e Pillow instalados só para esta conferência — **não** são dependências do projeto.

- [ ] **Step 5: Conferir que o link abre sem login**

Pegar uma das URLs decodificadas e acessá-la, confirmando que devolve o PDF do documento sem autenticação — que é o ponto do recurso.

Run: `curl -s -o /dev/null -w "%{http_code} %{content_type}\n" "<url decodificada>"`
Expected: `200 application/pdf`

- [ ] **Step 6: Limpar e commitar o changelog**

```bash
rm -f /home/ericks/github/GestorHS/backend/.tmp-qr.pdf /tmp/qrpag-2.png
```

Acrescentar à entrada v1.37.0 em `frontend/src/app/changelog/data.ts` (formato `{ tipo, texto }`, `tipo` em `'novidade' | 'melhoria' | 'correcao'`):

```ts
      { tipo: 'novidade', texto: 'O certificado de calibração passa a trazer QR codes dos certificados do gás, do termohigrômetro e do barômetro — não é mais preciso enviá-los impressos junto.' },
```

```bash
cd /home/ericks/github/GestorHS && npx --prefix frontend tsc -b --noEmit
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): qr dos certificados auxiliares no certificado"
```

---

## Depois do plano — o que fica com o Erick

1. **`alembic upgrade head`** para aplicar a `0025` — passo de deploy, não de implementação.
2. **Colar `[qrcertificados]` nos templates de produção**, aparelho por aparelho. A implementação só o aplica no Interlock X6, que é o de teste.
3. **Conferir se o QR escaneia no papel impresso**, não só na tela — é o uso real, e é a única verificação que nenhum teste automatizado substitui.
