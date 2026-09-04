# Múltiplas notas fiscais por caixa — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que a caixa tenha N notas fiscais (serviço + remessa), anexadas de uma vez pelo botão `+` do modal, removíveis para correção nas fases Financeiro e Preparando Retorno, e espelhadas no card do TaskHS.

**Architecture:** Uma tabela nova `notas_fiscais` ligada à CAIXA substitui as três colunas de `ordens` como fonte de verdade. As colunas antigas **congelam**: nenhum caminho novo escreve nelas, e elas continuam servindo só as rotas de leitura já publicadas nos cards do TaskHS. A migração `0029` faz backfill sem mover nenhum arquivo de disco, apontando as linhas antigas para o subdir da OS onde os arquivos já estão.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · pytest (SQLite in-memory) — React 19 · TS · Vite 8 · Tailwind v4 · Vitest + Testing Library

**Spec:** [docs/superpowers/specs/2026-09-04-multiplas-notas-fiscais-caixa-design.md](../specs/2026-09-04-multiplas-notas-fiscais-caixa-design.md)

## Global Constraints

- **O idioma do domínio é português.** Modelos, rotas, variáveis e mensagens em PT-BR.
- **Comentários e mensagens de commit em ASCII, sem acentos.** Strings visíveis ao usuário (mensagens de erro da API, textos de tela) **levam acento normalmente**.
- **O ID 10 (Financeiro) é numericamente maior que 7 e 8, mas vem ANTES deles no fluxo.** Nunca comparar fase por ID cru nem escrever a janela como `>= 7`. Backend: `os_workflow.posicao()` / `ORDEM_FASES`. Frontend: `posicaoFase()` de `src/app/ordens/api.ts`.
- **Um card por CAIXA, nunca por OS.** Toda rota que precise atualizar o card chama `agendar_espelhamento_caixa(db, background_tasks, cx)`. Jamais um caminho de espelhamento por OS — ele abriria um segundo card para a mesma caixa.
- **`app/core/` é puro, sem I/O.** Quem consulta banco e assina links é a camada `api/`.
- **Router novo precisa de `include_router` manual** em `backend/app/main.py`. (Neste plano não há router novo — `notas_fiscais.py` já está registrado.)
- **Baseline de testes:** medido em 04/09/2026 nesta máquina, na branch `feat/multiplas-notas-fiscais`: **4 falhas pré-existentes** — `test_certificados_gerais.py::test_anexar_lista_e_link`, `::test_excluir_remove`, `test_publico_certificado_geral.py::test_download_publico_com_token_valido`, `::test_download_publico_token_invalido_403`, todas por `PermissionError`. Falha nova = qualquer coisa além dessas quatro.
- **Não commitar nem dar push sem o Erick pedir.** Os passos de commit deste plano ficam prontos para ele autorizar.
- **Baseline do frontend:** **1 falha pré-existente** — `src/app/clientes/ClienteEquipamentosTab.test.tsx > esconde "Novo aparelho" para nao-admin`. Verde = só ela.
- **Verificação de frontend antes de fechar:** `npm run lint && npx tsc -b --noEmit && npm run build`.

## File Structure

**Backend — criar:**
| Arquivo | Responsabilidade |
|---|---|
| `backend/app/models/nota_fiscal.py` | model `NotaFiscal` (uma nota da caixa) |
| `backend/alembic/versions/0029_notas_fiscais.py` | cria a tabela + backfill |
| `backend/tests/test_notas_fiscais_caixa.py` | endpoints de anexar/remover/baixar |
| `backend/tests/test_nota_fiscal_link_nota.py` | token e link público por nota |

**Backend — modificar:**
| Arquivo | O que muda |
|---|---|
| `app/core/nota_fiscal.py` | `subdir_caixa`, `subdir_nota`, `nome_download_nota` (puro) |
| `app/core/nota_fiscal_link.py` | mensagem/token/link por nota (`nf:n:{id}`) |
| `app/core/taskhs.py` | `_sec_financeiro` com N notas + `montar_obs_caixa(notas=...)` |
| `app/core/exportacoes.py` | coluna "Nota fiscal" com os números da caixa |
| `app/models/caixa.py` | relationship `notas_fiscais` |
| `app/models/__init__.py` | exporta `NotaFiscal` |
| `app/schemas/caixas.py` | `NotaFiscalOut` + campo em `CaixaDetalhe` |
| `app/api/notas_fiscais.py` | endpoints novos; sai o `POST` por OS e o `POST` singular da caixa |
| `app/api/caixas.py` | guard de avanço lê a tabela nova |
| `app/api/espelhamento.py` | monta a lista de notas com links assinados |
| `app/api/publico.py` | rotas públicas por nota |

**Frontend — modificar:**
| Arquivo | O que muda |
|---|---|
| `src/app/caixas/api.ts` | `NotaFiscalCaixa`, `enviarNotasFiscaisCaixa`, `removerNotaFiscalCaixa`, `urlNotaFiscalCaixa` |
| `src/app/caixas/NotaFiscalCaixaModal.tsx` | lista dinâmica de blocos com `+` |
| `src/app/caixas/NotaFiscalCaixaModal.test.tsx` | testes do `+` |
| `src/app/caixas/CaixaDetailPage.tsx` | seção "Notas fiscais"; botão nas fases 10 e 7 |
| `src/app/ordens/api.ts` | sai `enviarNotaFiscal`; entra `notas_fiscais` no tipo da OS |
| `src/app/ordens/api.notaFiscal.test.ts` | **apagado** junto com a função |
| `src/app/ordens/OrdemDetailPage.tsx` | lista as notas da caixa, com fallback legado |

---

## Task 1: Model, migração e convenção de subdir

**Files:**
- Create: `backend/app/models/nota_fiscal.py`
- Create: `backend/alembic/versions/0029_notas_fiscais.py`
- Create: `backend/tests/test_nota_fiscal_convencao_caixa.py`
- Modify: `backend/app/core/nota_fiscal.py`
- Modify: `backend/app/models/caixa.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Consumes: nada (primeira task).
- Produces:
  - `app.models.NotaFiscal` com colunas `id, caixa, numero, arquivo_pdf, arquivo_xml, ordem, criado_em, criado_por`
  - `Caixa.notas_fiscais -> list[NotaFiscal]` (ordenada por id)
  - `nota_fiscal.subdir_caixa(caixa_id: int) -> str`
  - `nota_fiscal.subdir_nota(ordem_id: int | None, caixa_id: int) -> str`
  - `nota_fiscal.nome_download_nota(numero: str, basename: str) -> str`

- [ ] **Step 1: Rodar o baseline de testes e anotar o número**

Run: `cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -3`
Esperado: `4 failed, 1238 passed` — as quatro pré-existentes listadas nas Global Constraints. Se der outro número, PARE e avise: a régua do plano inteiro depende dela.

- [ ] **Step 2: Escrever o teste da convenção de subdir**

Create `backend/tests/test_nota_fiscal_convencao_caixa.py`:

```python
"""Convencao de onde os arquivos de nota fiscal ficam no disco.

A nota nova vive no subdir da CAIXA. A nota do backfill da 0029 aponta para o
subdir da OS, porque e' onde o arquivo ja estava — a migracao nao move nada.
"""
from app.core import nota_fiscal


def test_subdir_da_caixa():
    assert nota_fiscal.subdir_caixa(42) == "notas-fiscais/caixa/42"


def test_subdir_de_nota_nova_e_o_da_caixa():
    assert nota_fiscal.subdir_nota(None, 42) == "notas-fiscais/caixa/42"


def test_subdir_de_nota_do_backfill_e_o_da_os():
    """`ordem` preenchido so acontece no backfill: os arquivos ficaram la."""
    assert nota_fiscal.subdir_nota(777, 42) == nota_fiscal.subdir(777)
    assert nota_fiscal.subdir_nota(777, 42) == "notas-fiscais/777"


def test_nome_download_usa_o_numero_da_nota():
    assert nota_fiscal.nome_download_nota("12345", "abc.pdf") == "nota-fiscal-12345.pdf"
    assert nota_fiscal.nome_download_nota("12345", "abc.xml") == "nota-fiscal-12345.xml"


def test_nome_download_higieniza_o_numero():
    """O numero e' digitado e vai para o header Content-Disposition — so sai
    daqui com caracteres de nome de arquivo."""
    assert nota_fiscal.nome_download_nota('12/34 "x"', "abc.pdf") == "nota-fiscal-12-34--x-.pdf"
```

- [ ] **Step 3: Rodar o teste para vê-lo falhar**

Run: `cd backend && pytest tests/test_nota_fiscal_convencao_caixa.py -v`
Esperado: FAIL com `AttributeError: module 'app.core.nota_fiscal' has no attribute 'subdir_caixa'`

- [ ] **Step 4: Implementar as funções puras**

Em `backend/app/core/nota_fiscal.py`, adicionar no topo `import re` e, depois de `subdir`:

```python
def subdir_caixa(caixa_id: int) -> str:
    return f"notas-fiscais/caixa/{caixa_id}"


def subdir_nota(ordem_id: int | None, caixa_id: int) -> str:
    """Onde estao os arquivos de uma nota da tabela `notas_fiscais`.

    `ordem_id` preenchido e' marca do backfill da migracao 0029: aquela nota
    reaproveita os arquivos que ja estavam no subdir da OS. Nota criada pela
    tela nasce com `ordem` nulo e vive no subdir da caixa. Nenhum arquivo e'
    movido de lugar — dai as duas convencoes conviverem.
    """
    return subdir(ordem_id) if ordem_id else subdir_caixa(caixa_id)


def nome_download_nota(numero: str, basename: str) -> str:
    ext = ".xml" if basename.lower().endswith(".xml") else ".pdf"
    # o numero e' digitado pelo Financeiro e vai parar no Content-Disposition:
    # sai daqui reduzido a caracteres de nome de arquivo.
    seguro = re.sub(r"[^A-Za-z0-9._-]", "-", numero.strip()) or "s-n"
    return f"nota-fiscal-{seguro}{ext}"
```

- [ ] **Step 5: Rodar o teste para vê-lo passar**

Run: `cd backend && pytest tests/test_nota_fiscal_convencao_caixa.py -v`
Esperado: 5 passed

- [ ] **Step 6: Criar o model**

Create `backend/app/models/nota_fiscal.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.models.database import Base


class NotaFiscal(Base):
    """Uma nota fiscal da CAIXA. A caixa pode levar mais de uma — alem da nota do
    servico vai, as vezes, a nota de remessa do envio.

    `ordem` e' preenchido SO pelo backfill da migracao 0029: marca que os
    arquivos daquela nota ficaram no subdir antigo, o da OS. Nota criada pela
    tela nasce com `ordem` nulo e vive no subdir da caixa.

    O par PDF+XML e' obrigatorio (as duas colunas NOT NULL): nota pela metade foi
    justamente o problema que fez o campo unico virar dois, na migracao 0026.
    """
    __tablename__ = "notas_fiscais"

    id = Column(Integer, primary_key=True, index=True)
    caixa = Column(Integer, ForeignKey("caixas.id"), nullable=False, index=True)
    numero = Column(String(50), nullable=False)
    arquivo_pdf = Column(String(50), nullable=False)   # basename em disco
    arquivo_xml = Column(String(50), nullable=False)   # basename em disco
    ordem = Column(Integer, ForeignKey("ordens.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    criado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
```

- [ ] **Step 7: Registrar o model e a relationship**

Em `backend/app/models/__init__.py`, adicionar o import junto dos outros (antes do `__all__`):

```python
from app.models.nota_fiscal import NotaFiscal
```

e `"NotaFiscal",` na lista `__all__`.

Em `backend/app/models/caixa.py`, dentro da classe `Caixa`, junto das outras relationships:

```python
    # selectin, nao lazy padrao: a exportacao para Excel percorre muitas caixas e
    # o lazy load viraria uma consulta por linha da planilha.
    notas_fiscais = relationship("NotaFiscal", lazy="selectin", order_by="NotaFiscal.id")
```

- [ ] **Step 8: Provar que o model sobe no metadata dos testes**

Create em `backend/tests/test_notas_fiscais_caixa.py` (o arquivo cresce na Task 2):

```python
def test_model_cria_tabela_e_relationship(db_session, caixa_financeiro):
    from app.models import Caixa, NotaFiscal
    nf = NotaFiscal(caixa=caixa_financeiro, numero="12345",
                    arquivo_pdf="a.pdf", arquivo_xml="a.xml")
    db_session.add(nf)
    db_session.commit()
    cx = db_session.query(Caixa).filter(Caixa.id == caixa_financeiro).first()
    assert [n.numero for n in cx.notas_fiscais] == ["12345"]
```

Run: `cd backend && pytest tests/test_notas_fiscais_caixa.py -v`
Esperado: 1 passed

- [ ] **Step 9: Escrever a migração 0029**

Create `backend/alembic/versions/0029_notas_fiscais.py`:

```python
"""notas fiscais por CAIXA (varias por caixa) + backfill do que ja existe

Ate aqui a nota fiscal eram tres colunas em `ordens` e so cabia UMA por OS. O
Financeiro precisa anexar mais de uma na mesma caixa (a do servico e a de
remessa do envio), e precisa poder remover a errada para corrigir.

As colunas antigas de `ordens` NAO sao apagadas e param de receber escrita:
existem para continuar servindo `GET /ordens/{id}/nota-fiscal` e o link publico
`nf:{ordem_id}`, que ja estao publicados nos cards do TaskHS.

O backfill NAO move arquivo nenhum: cada linha criada aponta, por `ordem`, para
a OS em cujo subdir os arquivos ja estao.
"""
import sqlalchemy as sa
from alembic import op

revision = "0029_notas_fiscais"
down_revision = "0028_manutencao_servico_codigo"
branch_labels = None
depends_on = None

# Uma linha por caixa. Representante = a primeira OS (por id) com PDF **e** XML.
# OS antiga so com PDF fica de fora: `arquivo_xml` e' NOT NULL. Essas caixas
# seguem servidas pelas colunas legadas, e o guard de avanco aceita as duas
# fontes justamente para elas nao travarem no Financeiro.
BACKFILL = """
INSERT INTO notas_fiscais (caixa, numero, arquivo_pdf, arquivo_xml, ordem, criado_em)
SELECT DISTINCT ON (o.caixa)
       o.caixa,
       COALESCE(NULLIF(o.nota_fiscal_numero, ''), 's/n'),
       o.nota_fiscal,
       o.nota_fiscal_xml,
       o.id,
       NOW()
  FROM ordens o
 WHERE o.caixa IS NOT NULL
   AND o.nota_fiscal IS NOT NULL AND o.nota_fiscal <> ''
   AND o.nota_fiscal_xml IS NOT NULL AND o.nota_fiscal_xml <> ''
 ORDER BY o.caixa, o.id
"""


def upgrade() -> None:
    op.create_table(
        "notas_fiscais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("caixa", sa.Integer(), sa.ForeignKey("caixas.id"), nullable=False),
        sa.Column("numero", sa.String(50), nullable=False),
        sa.Column("arquivo_pdf", sa.String(50), nullable=False),
        sa.Column("arquivo_xml", sa.String(50), nullable=False),
        sa.Column("ordem", sa.Integer(), sa.ForeignKey("ordens.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("criado_por", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
    )
    op.create_index("ix_notas_fiscais_caixa", "notas_fiscais", ["caixa"])
    op.execute(BACKFILL)


def downgrade() -> None:
    op.drop_index("ix_notas_fiscais_caixa", table_name="notas_fiscais")
    op.drop_table("notas_fiscais")
```

- [ ] **Step 9b: Conferir que a migração encadeia na head certa**

Run: `cd backend && grep -n "revision\|down_revision" alembic/versions/0029_notas_fiscais.py alembic/versions/0028_manutencao_servico_codigo.py`
Esperado: `0029` tem `down_revision = "0028_manutencao_servico_codigo"`, e `0028` tem `revision = "0028_manutencao_servico_codigo"`. Nenhuma outra migração pode ter `down_revision = "0028_manutencao_servico_codigo"` — conferir com:

Run: `cd backend && grep -rn 'down_revision = "0028' alembic/versions/`
Esperado: **uma** linha só, a da 0029.

> ⚠️ **A migração NÃO é exercitada pelos testes.** O pytest sobe o schema por `Base.metadata.create_all` em SQLite, e o `DISTINCT ON` do backfill é sintaxe exclusiva do PostgreSQL. Antes de aplicar em produção, rodar o `SELECT` equivalente à mão (trocando o `INSERT INTO ... SELECT` por só o `SELECT`) e conferir a contagem contra `SELECT COUNT(DISTINCT caixa) FROM ordens WHERE nota_fiscal <> '' AND nota_fiscal_xml <> ''`. Não rodar `alembic upgrade head` sem esse conferido.

- [ ] **Step 10: Rodar a suíte inteira e comparar com o baseline**

Run: `cd backend && pytest -q 2>&1 | tail -3`
Esperado: mesmo número de falhas do Step 1. Nenhuma falha nova.

- [ ] **Step 11: Commit (só depois do Erick autorizar)**

```bash
git add backend/app/models/nota_fiscal.py backend/app/models/caixa.py backend/app/models/__init__.py \
        backend/app/core/nota_fiscal.py backend/alembic/versions/0029_notas_fiscais.py \
        backend/tests/test_nota_fiscal_convencao_caixa.py backend/tests/test_notas_fiscais_caixa.py
git commit -m "feat(nf): tabela de notas fiscais por caixa e migracao com backfill"
```

---

## Task 2: Endpoints de anexar, remover e baixar

**Files:**
- Modify: `backend/app/api/notas_fiscais.py`
- Modify: `backend/app/schemas/caixas.py`
- Test: `backend/tests/test_notas_fiscais_caixa.py`

**Interfaces:**
- Consumes: `app.models.NotaFiscal`, `nota_fiscal.subdir_caixa`, `nota_fiscal.subdir_nota`, `nota_fiscal.nome_download_nota` (Task 1).
- Produces:
  - `POST /caixas/{caixa_id}/notas-fiscais` → `CaixaDetalhe` — form-data `numeros[]`, `arquivos_pdf[]`, `arquivos_xml[]`
  - `DELETE /caixas/{caixa_id}/notas-fiscais/{nota_id}` → `CaixaDetalhe`
  - `GET /caixas/{caixa_id}/notas-fiscais/{nota_id}/pdf` e `.../xml` → `FileResponse`
  - `schemas.caixas.NotaFiscalOut` (`id: int`, `numero: str`, `criado_em: datetime | None`)
  - `CaixaDetalhe.notas_fiscais: list[NotaFiscalOut]`
  - `notas_fiscais.FASES_NOTA = (10, 7)` e `_exigir_fase_de_nota(cx)`

- [ ] **Step 1: Escrever os testes dos endpoints**

Substituir o conteúdo de `backend/tests/test_notas_fiscais_caixa.py` por (mantendo o teste do model da Task 1 no topo):

```python
import io


def test_model_cria_tabela_e_relationship(db_session, caixa_financeiro):
    from app.models import Caixa, NotaFiscal
    nf = NotaFiscal(caixa=caixa_financeiro, numero="12345",
                    arquivo_pdf="a.pdf", arquivo_xml="a.xml")
    db_session.add(nf)
    db_session.commit()
    cx = db_session.query(Caixa).filter(Caixa.id == caixa_financeiro).first()
    assert [n.numero for n in cx.notas_fiscais] == ["12345"]


def _pdf(nome="nf.pdf"):
    return (nome, io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")


def _xml(nome="nf.xml"):
    return (nome, io.BytesIO(b"<nfse/>"), "application/xml")


def _files(n=1):
    """n pares PDF+XML, no formato que o httpx manda como listas paralelas."""
    return [("arquivos_pdf", _pdf(f"nf{i}.pdf")) for i in range(n)] + \
           [("arquivos_xml", _xml(f"nf{i}.xml")) for i in range(n)]


def _arquivos_no_disco(upload_tmp, caixa_id):
    d = upload_tmp / "notas-fiscais" / "caixa" / str(caixa_id)
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


def test_anexar_tres_notas_de_uma_vez(client_fin, caixa_financeiro, upload_tmp, db_session):
    from app.models import NotaFiscal
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(3), data={"numeros": ["1", "2", "3"]})
    assert r.status_code == 200
    assert [n["numero"] for n in r.json()["notas_fiscais"]] == ["1", "2", "3"]
    assert db_session.query(NotaFiscal).filter(NotaFiscal.caixa == caixa_financeiro).count() == 3
    # 3 notas = 6 arquivos, todos no subdir da CAIXA (nao no da OS)
    assert len(_arquivos_no_disco(upload_tmp, caixa_financeiro)) == 6


def test_anexar_de_novo_acumula_em_vez_de_substituir(client_fin, caixa_financeiro, upload_tmp):
    """Inversao do comportamento antigo: `_gravar_par` apagava a nota anterior.
    Com varias notas por caixa, anexar sempre acrescenta."""
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["1"]})
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(1), data={"numeros": ["2"]})
    assert [n["numero"] for n in r.json()["notas_fiscais"]] == ["1", "2"]


def test_listas_de_tamanhos_diferentes_422_sem_gravar_nada(client_fin, caixa_financeiro, upload_tmp):
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(2), data={"numeros": ["1"]})
    assert r.status_code == 422
    assert _arquivos_no_disco(upload_tmp, caixa_financeiro) == []


def test_arquivo_invalido_no_meio_do_lote_nao_grava_nenhuma(client_fin, caixa_financeiro,
                                                            upload_tmp, db_session):
    """Tudo ou nada: a terceira nota invalida nao pode deixar as duas primeiras
    gravadas — o Financeiro reenviaria o lote e duplicaria as boas."""
    from app.models import NotaFiscal
    files = [("arquivos_pdf", _pdf("a.pdf")), ("arquivos_pdf", _pdf("b.pdf")),
             ("arquivos_pdf", ("c.png", io.BytesIO(b"\x89PNG"), "image/png")),
             ("arquivos_xml", _xml("a.xml")), ("arquivos_xml", _xml("b.xml")),
             ("arquivos_xml", _xml("c.xml"))]
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=files, data={"numeros": ["1", "2", "3"]})
    assert r.status_code == 415
    assert db_session.query(NotaFiscal).count() == 0
    assert _arquivos_no_disco(upload_tmp, caixa_financeiro) == []


def test_numero_vazio_422(client_fin, caixa_financeiro, upload_tmp):
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(1), data={"numeros": ["   "]})
    assert r.status_code == 422


def test_anexar_em_preparando_retorno_ok(client_fin, caixa_preparando, upload_tmp):
    """A janela de correcao vai ate a fase 7: o Financeiro descobre a nota errada
    quando a expedicao reclama, ja fora do Financeiro."""
    r = client_fin.post(f"/caixas/{caixa_preparando}/notas-fiscais",
                        files=_files(1), data={"numeros": ["9"]})
    assert r.status_code == 200


def test_anexar_em_pos_vendas_409(client_fin, caixa_posvendas, upload_tmp):
    r = client_fin.post(f"/caixas/{caixa_posvendas}/notas-fiscais",
                        files=_files(1), data={"numeros": ["9"]})
    assert r.status_code == 409


def test_anexar_em_caixa_finalizada_409(client_fin, caixa_financeiro, db_session, upload_tmp):
    from app.models import Caixa
    cx = db_session.query(Caixa).filter(Caixa.id == caixa_financeiro).first()
    cx.fase = 8
    db_session.commit()
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(1), data={"numeros": ["9"]})
    assert r.status_code == 409


def test_anexar_sem_funcao_403(client_com, caixa_financeiro, upload_tmp):
    r = client_com.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(1), data={"numeros": ["9"]})
    assert r.status_code == 403


def test_remover_apaga_registro_e_arquivos(client_fin, caixa_financeiro, upload_tmp, db_session):
    from app.models import NotaFiscal
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["1"]})
    nota_id = db_session.query(NotaFiscal).first().id
    assert len(_arquivos_no_disco(upload_tmp, caixa_financeiro)) == 2
    r = client_fin.delete(f"/caixas/{caixa_financeiro}/notas-fiscais/{nota_id}")
    assert r.status_code == 200
    assert r.json()["notas_fiscais"] == []
    assert db_session.query(NotaFiscal).count() == 0
    assert _arquivos_no_disco(upload_tmp, caixa_financeiro) == []


def test_remover_nota_de_outra_caixa_404(client_fin, caixa_financeiro, caixa_preparando,
                                          upload_tmp, db_session):
    from app.models import NotaFiscal
    client_fin.post(f"/caixas/{caixa_preparando}/notas-fiscais",
                    files=_files(1), data={"numeros": ["1"]})
    nota_id = db_session.query(NotaFiscal).first().id
    r = client_fin.delete(f"/caixas/{caixa_financeiro}/notas-fiscais/{nota_id}")
    assert r.status_code == 404


def test_baixar_pdf_e_xml_da_nota(client_fin, caixa_financeiro, upload_tmp, db_session):
    from app.models import NotaFiscal
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["12345"]})
    nota_id = db_session.query(NotaFiscal).first().id
    rp = client_fin.get(f"/caixas/{caixa_financeiro}/notas-fiscais/{nota_id}/pdf")
    assert rp.status_code == 200
    assert rp.headers["content-type"] == "application/pdf"
    assert "nota-fiscal-12345.pdf" in rp.headers["content-disposition"]
    rx = client_fin.get(f"/caixas/{caixa_financeiro}/notas-fiscais/{nota_id}/xml")
    assert rx.status_code == 200
    # octet-stream de proposito (core/nota_fiscal.media_type): XML de usuario
    # servido como application/xml executaria <script> via polyglot XHTML.
    assert rx.headers["content-type"] == "application/octet-stream"
    assert rx.headers["x-content-type-options"] == "nosniff"


def test_anexar_registra_log_em_todas_as_os_ativas(client_fin, caixa_financeiro,
                                                   upload_tmp, db_session):
    """A correcao precisa deixar rastro — e' a pergunta que o Financeiro faz depois."""
    from app.models import LogOS
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["12345"]})
    textos = [l.texto for l in db_session.query(LogOS).all()]
    assert textos.count("Nota fiscal 12345 anexada") == 2  # a fixture tem 2 OS ativas
```

- [ ] **Step 2: Rodar os testes para vê-los falhar**

Run: `cd backend && pytest tests/test_notas_fiscais_caixa.py -q`
Esperado: FAIL — `404 Not Found` nos POSTs (a rota ainda não existe).

- [ ] **Step 3: Adicionar os schemas**

Em `backend/app/schemas/caixas.py`, trocar a primeira linha de import por `from datetime import date, datetime` e adicionar, antes de `CaixaDetalhe`:

```python
class NotaFiscalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: str
    criado_em: datetime | None = None
```

e dentro de `CaixaDetalhe`:

```python
class CaixaDetalhe(CaixaOut):
    ordens: list[OrdemResumoCaixa] = []
    # Os basenames em disco NAO vao para o schema: o download e' por rota
    # dedicada, o frontend nao precisa saber o nome do arquivo.
    notas_fiscais: list[NotaFiscalOut] = []
```

- [ ] **Step 4: Implementar os endpoints**

Em `backend/app/api/notas_fiscais.py`: acrescentar aos imports

```python
from app.models import Usuario, Ordem, Caixa, NotaFiscal
from app.api.ordens_acoes import agora, registrar_log
```

(mantendo os demais), e adicionar depois de `_validar_numero`:

```python
# Anexar e remover valem no Financeiro (10) e em Preparando Retorno (7): e' a
# janela em que o Financeiro ainda consegue corrigir a nota errada. Lista
# explicita, NUNCA `fase >= 7` — o ID 10 e' maior que o 7 mas vem antes dele.
FASES_NOTA = (wf.FASE_FINANCEIRO, 7)


def _exigir_fase_de_nota(cx: Caixa) -> None:
    if cx.fase not in FASES_NOTA:
        raise HTTPException(
            409, "a nota fiscal só pode ser anexada ou removida no Financeiro ou em Preparando Retorno")


def _nota_ou_404(db: Session, cx: Caixa, nota_id: int) -> NotaFiscal:
    nf = db.query(NotaFiscal).filter(NotaFiscal.id == nota_id,
                                     NotaFiscal.caixa == cx.id).first()
    if nf is None:
        raise HTTPException(404, "nota fiscal não encontrada")
    return nf


@router.post("/caixas/{caixa_id}/notas-fiscais", response_model=CaixaDetalhe)
def anexar_notas_fiscais(
    caixa_id: int,
    background_tasks: BackgroundTasks,
    arquivos_pdf: list[UploadFile] = File(...),
    arquivos_xml: list[UploadFile] = File(...),
    numeros: list[str] = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_funcao(*GESTOR_NF)),
):
    """Anexa N notas de uma vez — a caixa pode levar a nota do servico e a de
    remessa. ACUMULA: as notas ja anexadas continuam.

    As tres listas sao paralelas (numero[i] casa com pdf[i] e xml[i]) e o lote e'
    tudo-ou-nada: se a terceira nota tiver um arquivo invalido, as duas primeiras
    nao ficam gravadas — senao o Financeiro reenviaria o lote e duplicaria as boas.
    """
    cx = _caixa_ou_404(db, caixa_id)
    _exigir_fase_de_nota(cx)
    ativas = _ordens_ativas_caixa(cx)
    if not ativas:
        raise HTTPException(409, "caixa sem OS ativa")
    if not numeros or not (len(arquivos_pdf) == len(arquivos_xml) == len(numeros)):
        raise HTTPException(422, "informe número, PDF e XML para cada nota")
    nums = [_validar_numero(n) for n in numeros]

    sub = nota_fiscal.subdir_caixa(cx.id)
    gravados: list[str] = []
    pares: list[tuple[str, str]] = []
    try:
        for pdf, xml in zip(arquivos_pdf, arquivos_xml):
            pdf.file.seek(0)
            base_pdf = storage.salvar_upload(pdf, subdir=sub, tipos_permitidos=storage.TIPOS_PDF)
            gravados.append(base_pdf)
            xml.file.seek(0)
            base_xml = storage.salvar_upload(xml, subdir=sub, tipos_permitidos=storage.TIPOS_XML)
            gravados.append(base_xml)
            pares.append((base_pdf, base_xml))
    except storage.ArquivoInvalido as e:
        for b in gravados:
            storage.remover_arquivo(sub, b)
        raise HTTPException(e.status, e.detail)

    for num, (base_pdf, base_xml) in zip(nums, pares):
        db.add(NotaFiscal(caixa=cx.id, numero=num, arquivo_pdf=base_pdf,
                          arquivo_xml=base_xml, criado_em=agora(), criado_por=usuario.id))
        for o in ativas:
            registrar_log(db, o, usuario, f"Nota fiscal {num} anexada")
    db.commit()
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx)
    return cx


@router.delete("/caixas/{caixa_id}/notas-fiscais/{nota_id}", response_model=CaixaDetalhe)
def remover_nota_fiscal(
    caixa_id: int,
    nota_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_funcao(*GESTOR_NF)),
):
    """Remove a nota e APAGA os arquivos. E' o caminho de correcao: a nota errada
    nao pode continuar baixavel por ninguem."""
    cx = _caixa_ou_404(db, caixa_id)
    _exigir_fase_de_nota(cx)
    nf = _nota_ou_404(db, cx, nota_id)
    sub = nota_fiscal.subdir_nota(nf.ordem, nf.caixa)
    storage.remover_arquivo(sub, nf.arquivo_pdf)
    storage.remover_arquivo(sub, nf.arquivo_xml)
    numero = nf.numero
    db.delete(nf)
    for o in _ordens_ativas_caixa(cx):
        registrar_log(db, o, usuario, f"Nota fiscal {numero} removida")
    db.commit()
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx)
    return cx


def _servir_nota(nf: NotaFiscal, basename: str):
    try:
        caminho = storage.caminho_arquivo(nota_fiscal.subdir_nota(nf.ordem, nf.caixa), basename)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    if not caminho.exists():
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(
        caminho,
        media_type=nota_fiscal.media_type(basename),
        filename=nota_fiscal.nome_download_nota(nf.numero, basename),
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/caixas/{caixa_id}/notas-fiscais/{nota_id}/pdf")
def baixar_nota_pdf(caixa_id: int, nota_id: int, db: Session = Depends(get_db),
                    _: Usuario = Depends(get_current_usuario)):
    cx = _caixa_ou_404(db, caixa_id)
    nf = _nota_ou_404(db, cx, nota_id)
    return _servir_nota(nf, nf.arquivo_pdf)


@router.get("/caixas/{caixa_id}/notas-fiscais/{nota_id}/xml")
def baixar_nota_xml(caixa_id: int, nota_id: int, db: Session = Depends(get_db),
                    _: Usuario = Depends(get_current_usuario)):
    cx = _caixa_ou_404(db, caixa_id)
    nf = _nota_ou_404(db, cx, nota_id)
    return _servir_nota(nf, nf.arquivo_xml)
```

- [ ] **Step 5: Conferir que o import de `ordens_acoes` não faz ciclo**

Run: `cd backend && python -c "import app.main" && grep -n "^from\|^import" app/api/ordens_acoes.py`
Esperado: import sem erro, e nenhuma linha importando `app.api.notas_fiscais`. Se houver ciclo, mover o import de `agora`/`registrar_log` para dentro das funções.

- [ ] **Step 6: Rodar os testes para vê-los passar**

Run: `cd backend && pytest tests/test_notas_fiscais_caixa.py -q`
Esperado: todos passando.

- [ ] **Step 7: Rodar a suíte e comparar com o baseline**

Run: `cd backend && pytest -q 2>&1 | tail -3`
Esperado: **o baseline de 4 falhas**. Esta task só ACRESCENTA endpoints e um campo ao `CaixaDetalhe`; nada existente deveria quebrar. Se quebrou, é regressão desta task — conserte antes de seguir. (A quebra proposital dos testes que usam o `POST` por OS acontece na Task 3, não aqui.)

- [ ] **Step 8: Commit (só depois do Erick autorizar)**

```bash
git add backend/app/api/notas_fiscais.py backend/app/schemas/caixas.py backend/tests/test_notas_fiscais_caixa.py
git commit -m "feat(nf): endpoints de anexar em lote, remover e baixar nota da caixa"
```

---

## Task 3: Guard de avanço e aposentadoria do caminho por OS

**Files:**
- Modify: `backend/app/api/caixas.py:205-245`
- Modify: `backend/app/api/notas_fiscais.py` (remover os dois POSTs antigos)
- Modify: `backend/tests/test_nota_fiscal.py`, `test_publico_nota_fiscal.py`, `test_caixa_avancar.py`, `test_ordens_taskhs.py`, `test_taskhs_bloqueio_modulo.py`
- Test: `backend/tests/test_notas_fiscais_caixa.py`

**Interfaces:**
- Consumes: `NotaFiscal`, `POST /caixas/{id}/notas-fiscais` (Task 2).
- Produces: `caixas._tem_nota_fiscal(db, cx, ativas) -> bool`. Some `POST /ordens/{ordem_id}/nota-fiscal` e `POST /caixas/{caixa_id}/nota-fiscal` (singular).

- [ ] **Step 1: Escrever os testes do guard**

Acrescentar em `backend/tests/test_notas_fiscais_caixa.py`:

```python
def test_avancar_sem_nota_409(client_fin, caixa_financeiro, upload_tmp):
    r = client_fin.post(f"/caixas/{caixa_financeiro}/avancar",
                        json={"obs": None, "cod_retorno": None})
    assert r.status_code == 409


def test_avancar_com_nota_na_tabela_nova_passa(client_fin, caixa_financeiro, upload_tmp):
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["1"]})
    r = client_fin.post(f"/caixas/{caixa_financeiro}/avancar",
                        json={"obs": None, "cod_retorno": None})
    assert r.status_code == 200
    assert r.json()["fase"] == 7


def test_avancar_com_caixa_antiga_so_na_coluna_legada_passa(client_fin, caixa_financeiro_com_nf,
                                                            upload_tmp):
    """Caixa antiga com PDF e sem XML ficou de fora do backfill da 0029. Sem o
    segundo termo do guard ela travaria no Financeiro sem ter o que corrigir."""
    r = client_fin.post(f"/caixas/{caixa_financeiro_com_nf}/avancar",
                        json={"obs": None, "cod_retorno": None})
    assert r.status_code == 200


def test_dispensa_do_admin_nao_carimba_caixa_que_tem_nota(client, usuario_admin, fases_seed,
                                                          caixa_financeiro, upload_tmp,
                                                          db_session):
    """O log de dispensa tambem parou de olhar a coluna: senao a caixa COM nota
    nova ganharia o carimbo de 'sem nota fiscal' por a coluna legada estar vazia."""
    from app.models import LogOS
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    client.post(f"/caixas/{caixa_financeiro}/notas-fiscais", files=_files(1),
                data={"numeros": ["1"]}, headers=h)
    client.post(f"/caixas/{caixa_financeiro}/avancar",
                json={"obs": None, "cod_retorno": None, "sem_nota_fiscal": True}, headers=h)
    textos = [l.texto for l in db_session.query(LogOS).all()]
    assert not any("dispensada pelo Administrador" in t for t in textos)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `cd backend && pytest tests/test_notas_fiscais_caixa.py -q -k "avancar or dispensa"`
Esperado: `test_avancar_com_nota_na_tabela_nova_passa` falha com 409 (o guard ainda olha `o.nota_fiscal`), e `test_dispensa...` falha por encontrar o carimbo.

- [ ] **Step 3: Trocar o guard em `caixas.py`**

Adicionar `NotaFiscal` ao import de models no topo de `backend/app/api/caixas.py` e, antes de `executar_avanco_caixa`:

```python
def _tem_nota_fiscal(db, cx, ativas) -> bool:
    """Aceita as DUAS fontes de proposito.

    A tabela `notas_fiscais` e' a fonte nova. A coluna legada entra porque caixa
    antiga com PDF e sem XML ficou fora do backfill da 0029 (`arquivo_xml` e'
    NOT NULL) — sem esse segundo termo ela travaria no Financeiro sem ter o que
    corrigir.
    """
    if db.query(NotaFiscal.id).filter(NotaFiscal.caixa == cx.id).first() is not None:
        return True
    return any(o.nota_fiscal for o in ativas)
```

Dentro de `executar_avanco_caixa`, antes do `for o in ativas:`:

```python
    tem_nf = _tem_nota_fiscal(db, cx, ativas) if origem == 10 else False
```

e trocar os dois pontos que liam a coluna:

```python
        elif origem == 10:     # Financeiro -> Preparando
            # `sem_nota_fiscal` so chega aqui como True se o chamador ja conferiu
            # que quem pediu e' Administrador (ver avancar_caixa).
            if not tem_nf and not sem_nota_fiscal:
                raise HTTPException(status_code=409, detail="anexe a nota fiscal da caixa antes de confirmar o pagamento")
```

```python
        if sem_nota_fiscal and origem == 10 and not tem_nf:
            texto = f"{texto} (sem nota fiscal, dispensada pelo Administrador)"
```

- [ ] **Step 4: Rodar para ver passar**

Run: `cd backend && pytest tests/test_notas_fiscais_caixa.py -q`
Esperado: todos passando.

- [ ] **Step 5: Remover os dois POSTs antigos**

Em `backend/app/api/notas_fiscais.py`, apagar por inteiro:
- a função `enviar_nota_fiscal` (`@router.post("/ordens/{ordem_id}/nota-fiscal")`)
- a função `enviar_nota_fiscal_caixa` (`@router.post("/caixas/{caixa_id}/nota-fiscal")`)
- a função `_gravar_par`, que só elas usavam
- a função `_os_ou_404` **fica**: os dois `GET` por OS continuam usando.

Motivo, para o comentário do arquivo: eram os últimos caminhos que escreviam nas colunas de `ordens`, que a partir daqui são só leitura de dados legados.

- [ ] **Step 6: Ver quais testes quebraram**

Run: `cd backend && pytest -q 2>&1 | tail -20`
Esperado: falham os testes que usavam o POST por OS como setup, em `test_nota_fiscal.py`, `test_publico_nota_fiscal.py`, `test_caixa_avancar.py`, `test_ordens_taskhs.py`, `test_taskhs_bloqueio_modulo.py`.

- [ ] **Step 7: Reescrever o setup desses testes**

A regra: **teste sobre o comportamento legado** (download por OS, link público `nf:{ordem_id}`) monta o cenário gravando as colunas direto e escrevendo o arquivo no subdir da OS; **teste sobre o comportamento novo** usa `POST /caixas/{id}/notas-fiscais`.

Em `backend/tests/test_nota_fiscal.py`, trocar o helper de upload por um que grava direto — os testes desse arquivo cobrem as rotas de leitura legadas:

```python
def _anexar_legado(db_session, upload_tmp, ordem, numero="12345"):
    """Grava o par direto nas colunas legadas e no subdir da OS.

    O `POST /ordens/{id}/nota-fiscal` foi removido: era o ultimo caminho que
    escrevia nessas colunas. Elas continuam existindo so para servir as rotas de
    leitura ja publicadas nos cards do TaskHS, e e' isso que estes testes cobrem.
    """
    from app.core import nota_fiscal
    d = upload_tmp / nota_fiscal.subdir(ordem.id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "nf.pdf").write_bytes(b"%PDF-1.4 fake")
    (d / "nf.xml").write_bytes(b"<nfse/>")
    ordem.nota_fiscal = "nf.pdf"
    ordem.nota_fiscal_xml = "nf.xml"
    ordem.nota_fiscal_numero = numero
    db_session.commit()
    return ordem
```

Apagar de `test_nota_fiscal.py` os testes que só existiam para validar o **upload** por OS, porque a rota deixou de existir: `test_upload_pdf_ok`, `test_upload_grava_pdf_e_xml_em_campos_separados`, `test_upload_so_com_pdf_422`, `test_upload_recusa_dois_pdfs`, `test_upload_tipo_invalido_415`. As regras que eles cobriam (par obrigatório, cada campo com seu tipo, 415 em tipo inválido) já estão cobertas em `test_notas_fiscais_caixa.py` — confira uma a uma antes de apagar, e se alguma não tiver equivalente, escreva o equivalente lá.

Os testes de **download** (`test_download_do_xml` e afins) ficam, trocando a chamada de upload por `_anexar_legado(db_session, upload_tmp, o)`.

Nos outros quatro arquivos, aplicar a mesma troca: onde havia `client.post(f"/ordens/{o.id}/nota-fiscal", ...)` apenas para "ter uma nota em cena", setar as colunas na fixture. Em `test_caixa_avancar.py`, os testes que provam o 409 do Financeiro devem passar a usar `POST /caixas/{id}/notas-fiscais` quando o ponto do teste é "com nota, avança".

- [ ] **Step 8: Apagar o cliente de frontend correspondente**

Em `frontend/src/app/ordens/api.ts`, remover a função `enviarNotaFiscal` (linha ~387). Apagar `frontend/src/app/ordens/api.notaFiscal.test.ts`, que era o único chamador.

Run: `cd frontend && grep -rn "enviarNotaFiscal\b" src`
Esperado: nenhuma ocorrência.

- [ ] **Step 9: Rodar tudo e comparar com o baseline**

Run: `cd backend && pytest -q 2>&1 | tail -3`
Esperado: **de volta ao baseline** — nenhuma falha além das 4 pré-existentes.

Run: `cd frontend && npx vitest run 2>&1 | tail -5`
Esperado: só a falha pré-existente de `ClienteEquipamentosTab.test.tsx`.

- [ ] **Step 10: Commit (só depois do Erick autorizar)**

```bash
git add backend/app/api/caixas.py backend/app/api/notas_fiscais.py backend/tests/ \
        frontend/src/app/ordens/api.ts
git rm frontend/src/app/ordens/api.notaFiscal.test.ts
git commit -m "feat(nf): guard de avanco pela tabela nova e remocao do anexo por os"
```

---

## Task 4: Link público por nota e obs4 do TaskHS

**Files:**
- Modify: `backend/app/core/nota_fiscal_link.py`
- Modify: `backend/app/core/taskhs.py:105-131` e `:166-190`
- Modify: `backend/app/api/publico.py`
- Modify: `backend/app/api/espelhamento.py:22-53`
- Create: `backend/tests/test_nota_fiscal_link_nota.py`
- Test: `backend/tests/test_taskhs_caixa.py`

**Interfaces:**
- Consumes: `NotaFiscal` (Task 1), endpoints da Task 2.
- Produces:
  - `nota_fiscal_link.assinar_nota(nota_id, tipo=PDF) -> str`
  - `nota_fiscal_link.verificar_nota(nota_id, token, tipo=PDF) -> bool`
  - `nota_fiscal_link.link_nota(nota_id, tipo=PDF) -> str | None`
  - `taskhs.montar_obs_caixa(..., notas: list[dict] | None = None)` — cada nota é `{"numero": str, "pdf": str | None, "xml": str | None}`
  - `GET /publico/nota-fiscal/nota/{nota_id}` e `.../xml`

- [ ] **Step 1: Escrever o teste do token por nota**

Create `backend/tests/test_nota_fiscal_link_nota.py`:

```python
"""Token do link publico por NOTA.

O formato antigo (`nf:{ordem_id}`) nao pode mudar: ha links ja publicados nos
cards do TaskHS. O novo nasce com prefixo proprio, ao lado dele.
"""
from app.core import nota_fiscal_link as l


def test_token_do_pdf_nao_abre_o_xml():
    tok = l.assinar_nota(7)
    assert l.verificar_nota(7, tok) is True
    assert l.verificar_nota(7, tok, l.XML) is False


def test_token_de_uma_nota_nao_abre_outra():
    assert l.verificar_nota(8, l.assinar_nota(7)) is False


def test_token_de_nota_nao_colide_com_o_de_ordem():
    """`nf:n:7` e `nf:7` sao mensagens distintas — um link de OS nao pode virar
    link de nota so porque os numeros batem."""
    assert l.verificar_nota(7, l.assinar(7)) is False
    assert l.verificar(7, l.assinar_nota(7)) is False


def test_link_da_nota_aponta_para_a_rota_publica(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "https://gestor.hs/")
    assert l.link_nota(7).startswith("https://gestor.hs/publico/nota-fiscal/nota/7?t=")
    assert l.link_nota(7, l.XML).startswith("https://gestor.hs/publico/nota-fiscal/nota/7/xml?t=")


def test_sem_base_url_nao_ha_link(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "")
    assert l.link_nota(7) is None
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `cd backend && pytest tests/test_nota_fiscal_link_nota.py -q`
Esperado: FAIL com `AttributeError: ... has no attribute 'assinar_nota'`

- [ ] **Step 3: Implementar o link por nota**

Acrescentar ao fim de `backend/app/core/nota_fiscal_link.py`:

```python
# --- link por NOTA (tabela `notas_fiscais`) -------------------------------
# Prefixo proprio `nf:n:` para nao colidir com `nf:{ordem_id}`: os dois espacos
# de id sao numericos e se cruzariam sem ele.

def _mensagem_nota(nota_id: int, tipo: str = PDF) -> str:
    return f"nf:n:{nota_id}" if tipo == PDF else f"nf:n:{nota_id}:{tipo}"


def assinar_nota(nota_id: int, tipo: str = PDF) -> str:
    return assinatura.assinar(_mensagem_nota(nota_id, tipo))


def verificar_nota(nota_id: int, token: str | None, tipo: str = PDF) -> bool:
    return assinatura.verificar(_mensagem_nota(nota_id, tipo), token)


def link_nota(nota_id: int, tipo: str = PDF) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    sufixo = "" if tipo == PDF else "/xml"
    return f"{base.rstrip('/')}/publico/nota-fiscal/nota/{nota_id}{sufixo}?t={assinar_nota(nota_id, tipo)}"
```

- [ ] **Step 4: Rodar para ver passar**

Run: `cd backend && pytest tests/test_nota_fiscal_link_nota.py -q`
Esperado: 5 passed

- [ ] **Step 5: Escrever o teste da obs4 com N notas**

Acrescentar em `backend/tests/test_taskhs_caixa.py`:

```python
def test_obs4_uma_linha_por_nota():
    """A caixa pode levar a nota do servico e a de remessa: a expedicao precisa
    dos dois pares de link, um por linha."""
    from app.core import taskhs
    from types import SimpleNamespace
    o = SimpleNamespace(fase=10, pago=True, data_pagamento=None,
                        nota_fiscal_numero=None, cliente_nome="X",
                        equipamento_descricao=None, equipamento_serie=None,
                        aceite=None, data_aceite=None, cod_retorno=None,
                        cliente_rel=None, desfecho_lab="concluido", calib_situacao=None,
                        calib_cert=None, prox_calibragem=None)
    obs = taskhs.montar_obs_caixa(
        SimpleNamespace(id=1, numero_proposta=None), [o], certificados_por_os={},
        notas=[{"numero": "111", "pdf": "u1", "xml": "u2"},
               {"numero": "222", "pdf": "u3", "xml": "u4"}])
    assert "NF 111 — PDF: u1 · XML: u2" in obs["obs4"]
    assert "NF 222 — PDF: u3 · XML: u4" in obs["obs4"]


def test_obs4_cai_no_formato_legado_sem_notas():
    """Caixa antiga, sem linha na tabela nova, mantem o card que a expedicao ja
    conhece — alimentado pelas colunas de `ordens`."""
    from app.core import taskhs
    from types import SimpleNamespace
    o = SimpleNamespace(fase=10, pago=False, data_pagamento=None,
                        nota_fiscal_numero="999", cliente_nome="X",
                        equipamento_descricao=None, equipamento_serie=None,
                        aceite=None, data_aceite=None, cod_retorno=None,
                        cliente_rel=None, desfecho_lab="concluido", calib_situacao=None,
                        calib_cert=None, prox_calibragem=None)
    obs = taskhs.montar_obs_caixa(
        SimpleNamespace(id=1, numero_proposta=None), [o], certificados_por_os={},
        nota_fiscal_url="u1", nota_fiscal_xml_url="u2")
    assert "Nota fiscal: 999" in obs["obs4"]
    assert "NF em PDF: u1" in obs["obs4"]
```

> Antes de escrever, abra `backend/tests/test_taskhs_caixa.py` e siga o jeito que **aquele arquivo** monta as OS falsas — se ele já tem um helper de `SimpleNamespace` ou usa objetos do banco, use o helper existente em vez do bloco acima.

- [ ] **Step 6: Rodar para ver falhar**

Run: `cd backend && pytest tests/test_taskhs_caixa.py -q -k obs4`
Esperado: FAIL com `TypeError: montar_obs_caixa() got an unexpected keyword argument 'notas'`

- [ ] **Step 7: Implementar a obs4 com N notas**

Em `backend/app/core/taskhs.py`, substituir `_sec_financeiro` e ajustar `montar_obs_caixa`:

```python
def _linha_nota(nota: dict) -> str:
    links = _juntar([f"PDF: {nota.get('pdf')}" if nota.get("pdf") else None,
                     f"XML: {nota.get('xml')}" if nota.get("xml") else None])
    base = f"NF {nota['numero']}"
    return f"{base} — {links}" if links else base


def _sec_financeiro(ordem, notas: list[dict] | None = None,
                    nota_fiscal_url: str | None = None,
                    nota_fiscal_xml_url: str | None = None) -> str | None:
    if wf.posicao(ordem.fase) < wf.posicao(10):
        return None
    if ordem.pago:
        pagamento = f"Pagamento: confirmado em {_fmt(ordem.data_pagamento)}" if ordem.data_pagamento else "Pagamento: confirmado"
    else:
        pagamento = "Pagamento: pendente"
    if notas:
        # uma linha por nota: alem da nota do servico, a caixa pode levar a de
        # remessa do envio, e a expedicao precisa clicar em todas.
        linhas = [_linha_nota(n) for n in notas]
    else:
        # Caixa sem linha na tabela `notas_fiscais` (legado, ou nota antiga sem
        # XML que ficou fora do backfill da 0029): formato de antes, alimentado
        # pelas colunas de `ordens`. E' o card que a expedicao ja conhece.
        linhas = [
            f"Nota fiscal: {ordem.nota_fiscal_numero}" if ordem.nota_fiscal_numero else None,
            f"NF em PDF: {nota_fiscal_url}" if nota_fiscal_url else None,
            f"NF em XML: {nota_fiscal_xml_url}" if nota_fiscal_xml_url else None,
        ]
    return _bloco([pagamento, *linhas])
```

e na assinatura de `montar_obs_caixa`, acrescentar `notas=None` e repassar:

```python
def montar_obs_caixa(caixa, ordens, *, certificados_por_os: dict, nota_fiscal_url=None,
                     nota_fiscal_xml_url=None, proposta_url=None, notas=None) -> dict:
```

```python
        "obs4": _sec_financeiro(rep, notas, nota_fiscal_url, nota_fiscal_xml_url) if rep else None,
```

- [ ] **Step 8: Rodar para ver passar**

Run: `cd backend && pytest tests/test_taskhs_caixa.py -q`
Esperado: verde, incluindo os testes de obs4 que já existiam.

- [ ] **Step 9: Alimentar as notas no espelhamento**

Em `backend/app/api/espelhamento.py`, dentro de `_montar_payload_caixa`, adicionar `NotaFiscal` ao import de models e, antes do bloco `rep_nf`:

```python
    # Fonte nova: uma linha por nota da CAIXA, com os dois links assinados.
    notas = [
        {"numero": nf.numero,
         "pdf": nota_fiscal_link.link_nota(nf.id),
         "xml": nota_fiscal_link.link_nota(nf.id, nota_fiscal_link.XML)}
        for nf in db.query(NotaFiscal).filter(NotaFiscal.caixa == caixa.id)
                    .order_by(NotaFiscal.id).all()
    ]
```

O bloco `rep_nf` existente **fica como está** — ele alimenta o formato legado, usado só quando `notas` está vazia. Na chamada:

```python
    obs = taskhs.montar_obs_caixa(caixa, ordens, certificados_por_os=certificados_por_os,
                                   nota_fiscal_url=nf_url, nota_fiscal_xml_url=nf_xml_url,
                                   proposta_url=proposta_url, notas=notas)
```

- [ ] **Step 10: Escrever o teste das rotas públicas por nota**

Acrescentar em `backend/tests/test_publico_nota_fiscal.py`:

```python
def test_publico_baixa_nota_da_caixa(client, client_fin, caixa_financeiro, upload_tmp, db_session):
    import io
    from app.core import nota_fiscal_link
    from app.models import NotaFiscal
    files = [("arquivos_pdf", ("a.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")),
             ("arquivos_xml", ("a.xml", io.BytesIO(b"<n/>"), "application/xml"))]
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais", files=files,
                    data={"numeros": ["12345"]})
    nid = db_session.query(NotaFiscal).first().id
    tok = nota_fiscal_link.assinar_nota(nid)
    assert client.get(f"/publico/nota-fiscal/nota/{nid}?t={tok}").status_code == 200
    assert client.get(f"/publico/nota-fiscal/nota/{nid}?t=errado").status_code == 403
    # o token do PDF nao serve para o XML
    assert client.get(f"/publico/nota-fiscal/nota/{nid}/xml?t={tok}").status_code == 403
```

> `client_fin` já embute o header no mesmo objeto `client`, então depois dele o `client` sai autenticado. As rotas públicas não olham o header, então o teste continua válido — mas se preferir isolar, use um `TestClient` limpo.

- [ ] **Step 11: Rodar para ver falhar, implementar as rotas públicas**

Run: `cd backend && pytest tests/test_publico_nota_fiscal.py -q -k caixa`
Esperado: FAIL com 404 (rota inexistente).

Em `backend/app/api/publico.py`, adicionar `NotaFiscal` ao import de models e, **antes** dos dois endpoints `/nota-fiscal/{ordem_id}` (rota específica sempre declarada antes da paramétrica):

```python
def _servir_nota_da_caixa(db: Session, nota_id: int, tipo: str):
    nf = db.query(NotaFiscal).filter(NotaFiscal.id == nota_id).first()
    if nf is None:
        raise HTTPException(status_code=404, detail="nota fiscal não encontrada")
    basename = nf.arquivo_pdf if tipo == nota_fiscal_link.PDF else nf.arquivo_xml
    try:
        caminho = storage.caminho_arquivo(nota_fiscal.subdir_nota(nf.ordem, nf.caixa), basename)
    except storage.ArquivoInvalido:
        raise HTTPException(status_code=404, detail="nota fiscal não encontrada")
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    return FileResponse(
        caminho,
        media_type=nota_fiscal.media_type(basename),
        filename=nota_fiscal.nome_download_nota(nf.numero, basename),
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/nota-fiscal/nota/{nota_id}")
def baixar_nota_da_caixa_publica(nota_id: int, t: str = "", db: Session = Depends(get_db)):
    if not nota_fiscal_link.verificar_nota(nota_id, t):
        raise HTTPException(status_code=403, detail="link inválido")
    return _servir_nota_da_caixa(db, nota_id, nota_fiscal_link.PDF)


@router.get("/nota-fiscal/nota/{nota_id}/xml")
def baixar_nota_da_caixa_xml_publica(nota_id: int, t: str = "", db: Session = Depends(get_db)):
    """Token separado do PDF: sao dois arquivos distintos."""
    if not nota_fiscal_link.verificar_nota(nota_id, t, nota_fiscal_link.XML):
        raise HTTPException(status_code=403, detail="link inválido")
    return _servir_nota_da_caixa(db, nota_id, nota_fiscal_link.XML)
```

- [ ] **Step 11b: Repor a cobertura de INTEGRAÇÃO do obs4**

A Task 3 removeu, de `backend/tests/test_ordens_taskhs.py`, a assertion `"Nota fiscal:" in captura[0]["obs4"]` — ela lia a coluna legada, que o caminho novo não escreve. Era o **único** teste do repositório que exercitava a corrente inteira (HTTP → `agendar_espelhamento_caixa` → `_montar_payload_caixa` → `obs4`); todo o resto chama `montar_obs_caixa` direto, como função pura.

Sem repor, este cenário passa despercebido: alguém implementa o Step 7 (função pura, testes verdes) e esquece o `notas=notas` do Step 9, ou filtra a query pela caixa errada. **A suíte fica 100% verde e o card chega em produção sem número de NF e sem links** — a mesma classe de falha silenciosa que gerou 28 cards órfãos neste repo em set/2026.

Em `test_ordens_taskhs.py`, no teste que anexa a nota e confere o reagendamento do card, reponha a assertion na forma nova — anexando pelo endpoint da caixa com um número conhecido e afirmando que ele chega ao `obs4`:

```python
    # Cobertura de INTEGRACAO, nao de unidade: e' o unico teste que percorre
    # HTTP -> agendar_espelhamento_caixa -> _montar_payload_caixa -> obs4. Os
    # testes de `test_taskhs_caixa.py` chamam montar_obs_caixa direto e nao
    # pegariam um `notas=notas` esquecido na chamada de espelhamento.py.
    assert "NF 555" in captura[0]["obs4"]
```

usando `555` como o número anexado no setup do teste. Rode `pytest tests/test_ordens_taskhs.py -q` e confirme que passa.

- [ ] **Step 11c: Limpar três minors herdados da Task 3**

Achados da revisão da Task 3, baratos e no mesmo território:

1. `backend/tests/test_nota_fiscal.py:42,56` — a fixture `usuario_financeiro` ficou nas duas assinaturas de teste mas não é mais usada (os testes usam só o header de admin). Remova das assinaturas.
2. `backend/tests/test_ordens_taskhs.py:73-75` — o docstring diz que a linha do número "é coberta em `test_taskhs_caixa.py`". É cobertura de **unidade** da função pura, não a mesma afirmação. Corrija a redação para não sugerir equivalência (e, depois do Step 11b, o próprio teste volta a afirmar isso).
3. `backend/app/api/caixas.py` — `_tem_nota_fiscal(db, cx, ativas)` está sem type hints, ao lado de `_ordens_ativas(cx: Caixa)`, que tem. Anote os parâmetros.

E acrescente em `backend/tests/test_notas_fiscais_caixa.py` o teste que falta do guard — nota de OUTRA caixa não pode liberar o avanço:

```python
def test_nota_de_outra_caixa_nao_libera_o_avanco(client_fin, caixa_financeiro, caixa_preparando,
                                                  upload_tmp):
    """O guard filtra por `NotaFiscal.caixa == cx.id`. Sem isso, qualquer nota no
    sistema destravaria qualquer caixa no Financeiro."""
    client_fin.post(f"/caixas/{caixa_preparando}/notas-fiscais",
                    files=_files(1), data={"numeros": ["1"]})
    r = client_fin.post(f"/caixas/{caixa_financeiro}/avancar",
                        json={"obs": None, "cod_retorno": None})
    assert r.status_code == 409
```

- [ ] **Step 12: Rodar tudo e comparar com o baseline**

Run: `cd backend && pytest -q 2>&1 | tail -3`
Esperado: baseline, sem falha nova.

- [ ] **Step 13: Commit (só depois do Erick autorizar)**

```bash
git add backend/app/core/nota_fiscal_link.py backend/app/core/taskhs.py \
        backend/app/api/publico.py backend/app/api/espelhamento.py backend/tests/
git commit -m "feat(nf): link publico por nota e card do taskhs com varias notas"
```

---

## Task 5: Coluna da planilha com os números da caixa

**Files:**
- Modify: `backend/app/core/exportacoes.py:136-151`
- Test: `backend/tests/test_exportacoes.py`

**Interfaces:**
- Consumes: `Caixa.notas_fiscais` (Task 1).
- Produces: `exportacoes._numeros_nota(o) -> str | None`.

- [ ] **Step 1: Escrever o teste**

Acrescentar em `backend/tests/test_exportacoes.py`:

```python
def test_linha_ordem_junta_os_numeros_das_notas_da_caixa():
    from types import SimpleNamespace
    from app.core.exportacoes import linha_ordem
    cx = SimpleNamespace(notas_fiscais=[SimpleNamespace(numero="111"),
                                        SimpleNamespace(numero="222")])
    o = _ordem_falsa(caixa_rel=cx, nota_fiscal_numero=None)
    assert linha_ordem(o)["nota_fiscal_numero"] == "111, 222"


def test_linha_ordem_cai_na_coluna_legada_sem_notas():
    from types import SimpleNamespace
    from app.core.exportacoes import linha_ordem
    o = _ordem_falsa(caixa_rel=SimpleNamespace(notas_fiscais=[]), nota_fiscal_numero="999")
    assert linha_ordem(o)["nota_fiscal_numero"] == "999"


def test_linha_ordem_com_os_sem_caixa():
    """OS solta nao existe mais no fluxo, mas o legado tem — nao pode explodir."""
    from app.core.exportacoes import linha_ordem
    o = _ordem_falsa(caixa_rel=None, nota_fiscal_numero="999")
    assert linha_ordem(o)["nota_fiscal_numero"] == "999"
```

> `_ordem_falsa` é um helper a escrever no topo do arquivo, ou a reaproveitar se `test_exportacoes.py` já tiver um construtor de OS falsa. Abra o arquivo primeiro: **use o que já existe lá** em vez de criar um segundo. Se não houver, escreva:
> ```python
> def _ordem_falsa(**over):
>     from types import SimpleNamespace
>     campos = dict(id=1, etiqueta=None, cliente_nome="X", cliente_rel=None,
>                   equipamento_descricao=None, equipamento_serie=None,
>                   fase_descricao=None, tipo_servico="C", data_chegada=None,
>                   data_calibracao=None, data_retorno=None, data_entrega=None,
>                   prox_calibragem=None, calib_cert=None, calib_situacao=None,
>                   nota_fiscal_numero=None, valor=None, frete_envio=None,
>                   frete_retorno=None, pago=False, caixa=1, garantia=False,
>                   caixa_rel=None)
>     campos.update(over)
>     return SimpleNamespace(**campos)
> ```
> Se `linha_ordem` reclamar de um campo faltando, acrescente-o ao dicionário — a lista acima veio de `linha_ordem` em 04/09/2026 e pode ter crescido.

- [ ] **Step 2: Rodar para ver falhar**

Run: `cd backend && pytest tests/test_exportacoes.py -q -k nota`
Esperado: FAIL — a coluna traz `None` em vez de `"111, 222"`.

- [ ] **Step 3: Implementar**

Em `backend/app/core/exportacoes.py`, antes de `linha_ordem`:

```python
def _numeros_nota(o) -> str | None:
    """Os numeros das notas da CAIXA da OS, ou a coluna legada da propria OS.

    A caixa pode levar mais de uma nota (servico + remessa), e a planilha e' por
    OS: os numeros entram na mesma celula, separados por virgula.
    """
    cx = getattr(o, "caixa_rel", None)
    notas = getattr(cx, "notas_fiscais", None) if cx is not None else None
    if notas:
        return ", ".join(n.numero for n in notas)
    return o.nota_fiscal_numero
```

e trocar em `linha_ordem`:

```python
        "calib_situacao": o.calib_situacao, "nota_fiscal_numero": _numeros_nota(o),
```

O header da coluna (`Coluna("Nota fiscal", "nota_fiscal_numero", 14)`) **não muda** — só a origem do valor. Considere aumentar a largura de `14` para `24`, já que a célula agora pode ter dois ou três números.

- [ ] **Step 4: Rodar para ver passar**

Run: `cd backend && pytest tests/test_exportacoes.py -q`
Esperado: verde.

- [ ] **Step 5: Rodar a suíte e comparar com o baseline**

Run: `cd backend && pytest -q 2>&1 | tail -3`
Esperado: baseline.

- [ ] **Step 6: Commit (só depois do Erick autorizar)**

```bash
git add backend/app/core/exportacoes.py backend/tests/test_exportacoes.py
git commit -m "feat(nf): planilha traz os numeros das notas da caixa"
```

---

## Task 6: Cliente de API e modal com o botão `+`

**Files:**
- Modify: `frontend/src/app/caixas/api.ts`
- Modify: `frontend/src/app/caixas/NotaFiscalCaixaModal.tsx`
- Test: `frontend/src/app/caixas/NotaFiscalCaixaModal.test.tsx`

**Interfaces:**
- Consumes: `POST /caixas/{id}/notas-fiscais`, `DELETE .../{nota_id}` (Task 2).
- Produces:
  - `interface NotaFiscalCaixa { id: number; numero: string; criado_em: string | null }`
  - `CaixaDetalhe.notas_fiscais: NotaFiscalCaixa[]`
  - `caixasApi.enviarNotasFiscaisCaixa(id, notas: NotaParaEnviar[]) => Promise<CaixaDetalhe>`
  - `caixasApi.removerNotaFiscalCaixa(id, notaId) => Promise<CaixaDetalhe>`
  - `caixasApi.baixarNotaFiscalCaixa(id, notaId, numero: string, tipo: 'pdf' | 'xml') => Promise<void>` — o `numero` só serve para nomear o arquivo baixado
  - `interface NotaParaEnviar { numero: string; pdf: File; xml: File }`

- [ ] **Step 1: Escrever o teste do modal**

Substituir `frontend/src/app/caixas/NotaFiscalCaixaModal.test.tsx` por (mantendo o estilo de mock que o arquivo já usa — **abra o arquivo antes** e reaproveite o `vi.mock` que ele tem):

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { NotaFiscalCaixaModal } from './NotaFiscalCaixaModal'
import { caixasApi } from './api'

vi.mock('./api', () => ({ caixasApi: { enviarNotasFiscaisCaixa: vi.fn() } }))

const enviar = vi.mocked(caixasApi.enviarNotasFiscaisCaixa)

function arquivo(nome: string, tipo: string) {
  return new File(['x'], nome, { type: tipo })
}

function preencherBloco(i: number, numero: string) {
  fireEvent.change(screen.getByLabelText(`Número da nota fiscal ${i + 1}`), { target: { value: numero } })
  fireEvent.change(screen.getByLabelText(`PDF da nota ${i + 1}`), {
    target: { files: [arquivo('a.pdf', 'application/pdf')] },
  })
  fireEvent.change(screen.getByLabelText(`XML da nota ${i + 1}`), {
    target: { files: [arquivo('a.xml', 'application/xml')] },
  })
}

describe('NotaFiscalCaixaModal', () => {
  beforeEach(() => {
    enviar.mockReset()
    enviar.mockResolvedValue({} as never)
  })

  it('abre com um bloco so, e sem botao de remover', () => {
    render(<NotaFiscalCaixaModal caixaId={1} onClose={vi.fn()} onEnviado={vi.fn()} />)
    expect(screen.getByLabelText('Número da nota fiscal 1')).toBeInTheDocument()
    expect(screen.queryByLabelText('Número da nota fiscal 2')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /remover nota 1/i })).not.toBeInTheDocument()
  })

  it('o + acrescenta um bloco e o X tira', () => {
    render(<NotaFiscalCaixaModal caixaId={1} onClose={vi.fn()} onEnviado={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /adicionar nota/i }))
    expect(screen.getByLabelText('Número da nota fiscal 2')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /remover nota 2/i }))
    expect(screen.queryByLabelText('Número da nota fiscal 2')).not.toBeInTheDocument()
  })

  it('o erro diz QUAL bloco esta incompleto', async () => {
    render(<NotaFiscalCaixaModal caixaId={1} onClose={vi.fn()} onEnviado={vi.fn()} />)
    preencherBloco(0, '111')
    fireEvent.click(screen.getByRole('button', { name: /adicionar nota/i }))
    fireEvent.change(screen.getByLabelText('Número da nota fiscal 2'), { target: { value: '222' } })
    fireEvent.click(screen.getByRole('button', { name: 'Anexar' }))
    expect(await screen.findByText(/nota 2/i)).toBeInTheDocument()
    expect(enviar).not.toHaveBeenCalled()
  })

  it('envia as duas notas numa chamada so', async () => {
    const onEnviado = vi.fn()
    render(<NotaFiscalCaixaModal caixaId={9} onClose={vi.fn()} onEnviado={onEnviado} />)
    preencherBloco(0, '111')
    fireEvent.click(screen.getByRole('button', { name: /adicionar nota/i }))
    preencherBloco(1, '222')
    fireEvent.click(screen.getByRole('button', { name: 'Anexar' }))
    await waitFor(() => expect(enviar).toHaveBeenCalledTimes(1))
    const [id, notas] = enviar.mock.calls[0]
    expect(id).toBe(9)
    expect(notas.map((n) => n.numero)).toEqual(['111', '222'])
    expect(onEnviado).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `cd frontend && npx vitest run src/app/caixas/NotaFiscalCaixaModal.test.tsx`
Esperado: FAIL — `enviarNotasFiscaisCaixa` não existe e os labels numerados não estão na tela.

- [ ] **Step 3: Implementar o cliente de API**

Em `frontend/src/app/caixas/api.ts`, adicionar as interfaces junto das outras:

```ts
export interface NotaFiscalCaixa {
  id: number
  numero: string
  criado_em: string | null
}

/** Um bloco do modal: numero + o par de arquivos. O par e' obrigatorio — a nota
 *  so esta completa com os dois, regra que vem da migracao 0026. */
export interface NotaParaEnviar {
  numero: string
  pdf: File
  xml: File
}
```

e o campo em `CaixaDetalhe`:

```ts
export interface CaixaDetalhe extends CaixaListItem {
  ordens: OrdemResumoCaixa[]
  notas_fiscais: NotaFiscalCaixa[]
}
```

Substituir `enviarNotaFiscalCaixa` por:

```ts
  // Anexa N notas da caixa numa chamada so — a caixa pode levar a nota do servico
  // e a de remessa. As tres listas vao PARALELAS (numero[i] casa com pdf[i] e
  // xml[i]), espelhando o Form do backend em app/api/notas_fiscais.py.
  enviarNotasFiscaisCaixa: async (id: number, notas: NotaParaEnviar[]): Promise<CaixaDetalhe> => {
    const fd = new FormData()
    for (const n of notas) {
      fd.append('numeros', n.numero)
      fd.append('arquivos_pdf', n.pdf)
      fd.append('arquivos_xml', n.xml)
    }
    const res = await apiFetch(`/caixas/${id}/notas-fiscais`, { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = (await res.json()) as { detail?: string }
        if (body.detail) detail = body.detail
      } catch {
        // sem corpo JSON
      }
      throw new ApiError(res.status, detail)
    }
    return (await res.json()) as CaixaDetalhe
  },
  removerNotaFiscalCaixa: (id: number, notaId: number): Promise<CaixaDetalhe> =>
    apiJson<CaixaDetalhe>(`/caixas/${id}/notas-fiscais/${notaId}`, { method: 'DELETE' }),
```

E o download, no mesmo molde de `ordensApi.baixarNotaFiscal` (`frontend/src/app/ordens/api.ts:403`):

```ts
  // Nunca abrir o arquivo numa aba (blob: herda a origem do app — um XML malicioso
  // executaria <script>). Forca download via link com atributo `download`, como o
  // PDF do certificado. A extensao vem do `tipo`, nao do Content-Disposition, que
  // so e legivel via JS cross-origin se o backend expuser o header no CORS.
  baixarNotaFiscalCaixa: async (id: number, notaId: number, numero: string,
                                tipo: 'pdf' | 'xml'): Promise<void> => {
    const res = await apiFetch(`/caixas/${id}/notas-fiscais/${notaId}/${tipo}`)
    if (!res.ok) throw new ApiError(res.status, 'Falha ao baixar nota fiscal')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `nota-fiscal-${numero}.${tipo}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
```

- [ ] **Step 4: Implementar o modal**

Substituir o corpo de `frontend/src/app/caixas/NotaFiscalCaixaModal.tsx`:

```tsx
import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { caixasApi, type NotaParaEnviar } from './api'

interface Props {
  caixaId: number
  onClose: () => void
  onEnviado: () => void
}

interface Bloco {
  numero: string
  pdf: File | null
  xml: File | null
}

const vazio = (): Bloco => ({ numero: '', pdf: null, xml: null })

// Anexa as notas fiscais de uma caixa. A caixa pode levar mais de uma — alem da
// nota do servico vai, as vezes, a nota de remessa do envio —, entao o modal tem
// uma lista de blocos e manda todos num POST so.
export function NotaFiscalCaixaModal({ caixaId, onClose, onEnviado }: Props) {
  const [blocos, setBlocos] = useState<Bloco[]>([vazio()])
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  function alterar(i: number, campo: Partial<Bloco>) {
    setBlocos((bs) => bs.map((b, j) => (j === i ? { ...b, ...campo } : b)))
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    // Validacao por bloco, dizendo QUAL: com quatro blocos na tela, "escolha o
    // XML" sozinho nao diz onde olhar.
    for (const [i, b] of blocos.entries()) {
      const rotulo = blocos.length > 1 ? `Nota ${i + 1}: ` : ''
      if (!b.numero.trim()) { setErro(`${rotulo}informe o número da nota fiscal.`); return }
      if (!b.pdf) { setErro(`${rotulo}escolha o PDF da nota.`); return }
      if (!b.xml) { setErro(`${rotulo}escolha o XML da nota.`); return }
    }
    const notas: NotaParaEnviar[] = blocos.map((b) => ({
      numero: b.numero.trim(), pdf: b.pdf as File, xml: b.xml as File,
    }))
    setEnviando(true)
    try {
      await caixasApi.enviarNotasFiscaisCaixa(caixaId, notas)
      onEnviado()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao anexar a nota fiscal')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Anexar nota fiscal da caixa"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">
            Cancelar
          </button>
          <button type="submit" form="form-nota-fiscal-caixa" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">
            Anexar
          </button>
        </>
      }
    >
      <form id="form-nota-fiscal-caixa" className="space-y-4" onSubmit={onSubmit}>
        <p className="text-sm text-slate-400">
          As notas são anexadas a esta caixa de uma só vez. O PDF e o XML são obrigatórios
          em cada nota — sempre vêm juntos. Use “Adicionar nota” quando a caixa levar mais
          de uma (por exemplo, a nota de remessa do envio).
        </p>
        {blocos.map((b, i) => (
          <div key={i} className="space-y-3 rounded-lg border border-border p-3">
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Input
                  id={`numero-nf-caixa-${i}`}
                  label={`Número da nota fiscal ${i + 1}`}
                  value={b.numero}
                  onChange={(e) => alterar(i, { numero: e.target.value })}
                  maxLength={50}
                />
              </div>
              {i > 0 && (
                <button
                  type="button"
                  aria-label={`Remover nota ${i + 1}`}
                  onClick={() => setBlocos((bs) => bs.filter((_, j) => j !== i))}
                  className="mb-1 px-3 py-2 rounded-lg border border-border text-sm text-slate-400 hover:bg-background-elevated transition-colors"
                >
                  ✕
                </button>
              )}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor={`nf-caixa-pdf-${i}`} className="block text-sm font-medium text-slate-300 mb-1.5">
                  PDF da nota {i + 1}
                </label>
                <input
                  id={`nf-caixa-pdf-${i}`}
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(e) => alterar(i, { pdf: e.target.files?.[0] ?? null })}
                  className="block w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-background-elevated file:text-slate-200 file:text-sm"
                />
              </div>
              <div>
                <label htmlFor={`nf-caixa-xml-${i}`} className="block text-sm font-medium text-slate-300 mb-1.5">
                  XML da nota {i + 1}
                </label>
                <input
                  id={`nf-caixa-xml-${i}`}
                  type="file"
                  accept="application/xml,text/xml,.xml"
                  onChange={(e) => alterar(i, { xml: e.target.files?.[0] ?? null })}
                  className="block w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-background-elevated file:text-slate-200 file:text-sm"
                />
              </div>
            </div>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setBlocos((bs) => [...bs, vazio()])}
          className="w-full py-2 rounded-lg border border-dashed border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors"
        >
          + Adicionar nota
        </button>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
```

> O `required` saiu do `Input`: com vários blocos, a validação nativa do browser dispara antes da nossa e não diz qual bloco está incompleto. A validação passa a ser toda no `onSubmit`.
>
> Confira em `frontend/src/components/ui/Input.tsx` se o componente associa o `label` ao `id` via `htmlFor` — o teste depende de `getByLabelText`. Se não associar, use o `<label htmlFor>` explícito, como nos campos de arquivo.

- [ ] **Step 5: Rodar os testes do modal**

Run: `cd frontend && npx vitest run src/app/caixas/NotaFiscalCaixaModal.test.tsx`
Esperado: 4 passed

- [ ] **Step 6: Verificação de tipos e lint**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit`
Esperado: sem erros. Se `tsc` reclamar de `notas_fiscais` faltando em algum objeto `CaixaDetalhe` de teste, acrescente `notas_fiscais: []` ao mock.

- [ ] **Step 7: Commit (só depois do Erick autorizar)**

```bash
git add frontend/src/app/caixas/api.ts frontend/src/app/caixas/NotaFiscalCaixaModal.tsx \
        frontend/src/app/caixas/NotaFiscalCaixaModal.test.tsx
git commit -m "feat(nf): modal anexa varias notas com o botao de adicionar"
```

---

## Task 7: Seção de notas na tela da caixa e na tela da OS

**Files:**
- Modify: `frontend/src/app/caixas/CaixaDetailPage.tsx:352-362` e `:551-560`
- Modify: `frontend/src/app/ordens/api.ts:175-182`
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx:627-662`
- Modify: `backend/app/schemas/ordens.py`
- Test: `frontend/src/app/caixas/CaixaDetailPage.test.tsx`

**Interfaces:**
- Consumes: `caixasApi.removerNotaFiscalCaixa`, `caixasApi.baixarNotaFiscalCaixa`, `CaixaDetalhe.notas_fiscais` (Task 6); `posicaoFase` de `../ordens/api`.
- Produces: nada consumido por tasks posteriores.

- [ ] **Step 1: Escrever os testes da tela da caixa**

Acrescentar em `frontend/src/app/caixas/CaixaDetailPage.test.tsx` (seguindo o setup de mocks que o arquivo já tem — **abra-o antes** e reaproveite a fixture de caixa dele, só acrescentando `notas_fiscais`):

```tsx
it('lista as notas fiscais da caixa', async () => {
  // caixa em fase 10 com duas notas
  expect(await screen.findByText('NF 111')).toBeInTheDocument()
  expect(screen.getByText('NF 222')).toBeInTheDocument()
})

it('remover chama a API e recarrega', async () => {
  fireEvent.click(screen.getByRole('button', { name: /remover nota 111/i }))
  fireEvent.click(screen.getByRole('button', { name: /confirmar/i }))
  await waitFor(() => expect(caixasApi.removerNotaFiscalCaixa).toHaveBeenCalledWith(1, 10))
})

it('o botao de anexar aparece em preparando retorno', async () => {
  // caixa em fase 7: a janela de correcao vai ate aqui
  expect(await screen.findByRole('button', { name: /anexar nota fiscal/i })).toBeInTheDocument()
})

it('o botao de anexar some em finalizada', async () => {
  // caixa em fase 8
  await screen.findByText(/ordens de serviço/i)
  expect(screen.queryByRole('button', { name: /anexar nota fiscal/i })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `cd frontend && npx vitest run src/app/caixas/CaixaDetailPage.test.tsx`
Esperado: FAIL — os textos das notas não existem na tela.

- [ ] **Step 3: Implementar a seção na tela da caixa**

Em `frontend/src/app/caixas/CaixaDetailPage.tsx`:

Acrescentar aos imports `import { posicaoFase } from '../ordens/api'` e, junto dos outros `useState`, `const [removendoNota, setRemovendoNota] = useState<number | null>(null)`.

Definir, junto dos outros derivados no topo do componente:

```tsx
  // A janela de correcao da nota vai do Financeiro (10) ate Preparando Retorno (7).
  // Comparacao por POSICAO, nunca por ID: o 10 e' maior que o 7 mas vem antes dele.
  const posCaixa = posicaoFase(caixa?.fase ?? null)
  const naJanelaDaNota = posCaixa >= posicaoFase(10) && posCaixa <= posicaoFase(7)
```

Trocar as duas condições de `caixa.fase === 10` do bloco de ações por `naJanelaDaNota`:

```tsx
          {(podeEscrever || (naJanelaDaNota && podeAnexarNF)) && (
            <div className="flex gap-2 flex-wrap">
              {podeEscrever && <Button onClick={abrirPicker}>Abrir OS</Button>}
              {naJanelaDaNota && podeAnexarNF && (
                <Button variant="secondary" onClick={() => setNotaFiscalAberta(true)}>
                  Anexar nota fiscal
                </Button>
              )}
            </div>
          )}
```

Acrescentar a seção, logo acima da tabela de OS:

```tsx
          {(caixa.notas_fiscais.length > 0 || naJanelaDaNota) && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
                Notas fiscais ({caixa.notas_fiscais.length})
              </h2>
              {caixa.notas_fiscais.length === 0 ? (
                <p className="text-sm text-slate-500">Nenhuma nota fiscal anexada ainda.</p>
              ) : (
                <ul className="space-y-2">
                  {caixa.notas_fiscais.map((nf) => (
                    <li key={nf.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                      <span className="text-sm text-slate-200">NF {nf.numero}</span>
                      <div className="flex items-center gap-3">
                        <button onClick={() => caixasApi.baixarNotaFiscalCaixa(caixa.id, nf.id, nf.numero, 'pdf')}
                                className="text-xs font-semibold text-primary hover:underline">
                          Baixar PDF
                        </button>
                        <button onClick={() => caixasApi.baixarNotaFiscalCaixa(caixa.id, nf.id, nf.numero, 'xml')}
                                className="text-xs font-semibold text-primary hover:underline">
                          Baixar XML
                        </button>
                        {naJanelaDaNota && podeAnexarNF && (
                          removendoNota === nf.id ? (
                            <>
                              <button onClick={() => onRemoverNota(nf.id)}
                                      className="text-xs font-semibold text-danger hover:underline">
                                Confirmar
                              </button>
                              <button onClick={() => setRemovendoNota(null)}
                                      className="text-xs font-semibold text-slate-400 hover:underline">
                                Cancelar
                              </button>
                            </>
                          ) : (
                            <button aria-label={`Remover nota ${nf.numero}`}
                                    onClick={() => setRemovendoNota(nf.id)}
                                    className="text-xs font-semibold text-danger hover:underline">
                              Remover
                            </button>
                          )
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
```

e a função de remoção, junto das outras ações:

```tsx
  async function onRemoverNota(notaId: number) {
    setErroAcao('')
    try {
      await caixasApi.removerNotaFiscalCaixa(caixaId, notaId)
      setRemovendoNota(null)
      await recarregar()
    } catch (err) {
      setErroAcao(err instanceof ApiError ? err.message : 'Falha ao remover a nota fiscal')
    }
  }
```

> `recarregar` e `setErroAcao` já existem nesse componente — confira o nome exato da função de recarga usada em `onEnviado` do `NotaFiscalCaixaModal` (linha ~556) e use **a mesma**, em vez de criar outra.
>
> A confirmação é inline, com dois botões. **Não usar `window.confirm`**: o diálogo modal do browser trava a automação de navegador e não é o padrão do resto da tela.

- [ ] **Step 4: Rodar os testes da tela da caixa**

Run: `cd frontend && npx vitest run src/app/caixas/CaixaDetailPage.test.tsx`
Esperado: verde.

- [ ] **Step 5: Expor as notas da caixa no detalhe da OS (backend)**

Em `backend/app/schemas/ordens.py`, junto dos campos de nota fiscal (linhas ~91-93), acrescentar:

```python
    # As notas da CAIXA da OS. As tres colunas acima ficam por causa do legado:
    # OS antiga sem linha na tabela nova continua exibindo por elas.
    notas_fiscais: list[NotaFiscalOut] = []
```

importando `NotaFiscalOut` de `app.schemas.caixas`. Se isso criar import circular, mova `NotaFiscalOut` para `app/schemas/notas_fiscais.py` e importe nos dois.

O valor vem da relationship — acrescentar uma property em `backend/app/models/ordem.py`, junto de `caixa_obs`:

```python
    @property
    def notas_fiscais(self):
        return self.caixa_rel.notas_fiscais if self.caixa_rel else []
```

Escrever o teste em `backend/tests/test_notas_fiscais_caixa.py`:

```python
def test_detalhe_da_os_traz_as_notas_da_caixa(client_fin, caixa_financeiro, upload_tmp, db_session):
    from app.models import Ordem
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["12345"]})
    os_id = db_session.query(Ordem).filter(Ordem.caixa == caixa_financeiro).first().id
    r = client_fin.get(f"/ordens/{os_id}")
    assert r.status_code == 200
    assert [n["numero"] for n in r.json()["notas_fiscais"]] == ["12345"]
```

Run: `cd backend && pytest tests/test_notas_fiscais_caixa.py -q -k detalhe`
Esperado: passa depois da mudança.

- [ ] **Step 6: Implementar a tela da OS**

Em `frontend/src/app/ordens/api.ts`, no tipo do detalhe da OS (linhas ~175-182), acrescentar:

```ts
  /** Notas da CAIXA da OS. Os tres campos acima ficam para OS antiga, que nao
   *  tem linha na tabela nova — e' o fallback exibido quando esta lista vem vazia. */
  notas_fiscais: { id: number; numero: string; criado_em: string | null }[]
```

Em `frontend/src/app/ordens/OrdemDetailPage.tsx`, dentro da seção "Nota fiscal", trocar a condição principal para preferir a lista:

```tsx
          {os.notas_fiscais.length > 0 ? (
            <ul className="space-y-2">
              {os.notas_fiscais.map((nf) => (
                <li key={nf.id} className="flex items-center justify-between gap-3">
                  <Campo label="Número" valor={nf.numero} />
                  <div className="flex items-center gap-3">
                    <button onClick={() => onBaixarNotaDaCaixa(nf.id, nf.numero, 'pdf')}
                            className="text-xs font-semibold text-primary hover:underline">
                      Baixar PDF
                    </button>
                    <button onClick={() => onBaixarNotaDaCaixa(nf.id, nf.numero, 'xml')}
                            className="text-xs font-semibold text-primary hover:underline">
                      Baixar XML
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : os.nota_fiscal ? (
            // Fallback legado: OS antiga, sem linha na tabela nova. Bloco atual do
            // arquivo, sem mudanca — inclusive o XML condicional, porque OS anexada
            // antes da migracao 0026 so tem PDF.
            <div className="flex items-center justify-between gap-3">
              <Campo label="Número" valor={os.nota_fiscal_numero} />
              <div className="flex items-center gap-3">
                <button
                  onClick={() => onBaixarNotaFiscal('pdf')}
                  className="text-xs font-semibold text-primary hover:underline"
                >
                  Baixar PDF
                </button>
                {os.nota_fiscal_xml && (
                  <button
                    onClick={() => onBaixarNotaFiscal('xml')}
                    className="text-xs font-semibold text-primary hover:underline"
                  >
                    Baixar XML
                  </button>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              Nenhuma nota fiscal anexada ainda — é anexada na tela da caixa, no Financeiro
              ou em Preparando Retorno.
            </p>
          )}
```

`onBaixarNotaFiscal` (o handler antigo, por OS) **fica**: é ele que serve o fallback legado.

`onBaixarNotaDaCaixa` chama `caixasApi.baixarNotaFiscalCaixa(os.caixa, notaId, numero, tipo)` — a OS conhece a própria caixa pelo campo `caixa`. Se importar `caixasApi` dentro de `ordens/` criar dependência circular entre os módulos, replique o download local no `ordensApi`, seguindo `baixarNotaFiscal`.

A seção continua **só de leitura**: sem botão de anexar nem de remover aqui. O anexo é sempre pela tela da caixa.

- [ ] **Step 7: Rodar toda a verificação de frontend**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npx vitest run && npm run build`
Esperado: tudo verde. Os testes de `OrdemDetailPage.*.test.tsx` que montam uma OS falsa vão precisar de `notas_fiscais: []` no mock — acrescente.

- [ ] **Step 8: Rodar a suíte de backend e comparar com o baseline**

Run: `cd backend && pytest -q 2>&1 | tail -3`
Esperado: baseline, sem falha nova.

- [ ] **Step 9: Atualizar o changelog visível ao usuário**

Em `frontend/src/app/changelog/data.ts`, adicionar a entrada nova **no topo** (a primeira é a versão atual). Abrir o arquivo, ver a versão atual e subir o **minor** (mudança visível de funcionalidade). Texto sugerido:

- "Uma caixa pode ter mais de uma nota fiscal — o botão “+ Adicionar nota” anexa quantas forem necessárias de uma vez (por exemplo, a nota do serviço e a de remessa)."
- "A nota errada pode ser removida e reanexada, no Financeiro e também em Preparando Retorno. O card do TaskHS é atualizado sozinho."

- [ ] **Step 10: Commit (só depois do Erick autorizar)**

```bash
git add frontend/src backend/app/schemas/ordens.py backend/app/models/ordem.py backend/tests/
git commit -m "feat(nf): tela da caixa lista e remove notas, tela da os exibe as da caixa"
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): vX.Y.0 — varias notas fiscais por caixa e correcao da nota"
```

---

## Verificação final antes de dizer que está pronto

- [ ] `cd backend && pytest -q` → só as 4 falhas pré-existentes
- [ ] `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build` → verde
- [ ] `cd frontend && npx vitest run` → verde
- [ ] `grep -rn "nota_fiscal =" backend/app/api/` → nenhuma escrita nova nas colunas legadas
- [ ] `grep -rn "enviarNotaFiscal\b\|/nota-fiscal\"" frontend/src` → nenhuma referência às rotas removidas
- [ ] `grep -rn "fase === 10\|fase >= 7" frontend/src/app/caixas/` → nenhuma comparação de fase por ID cru sobrando
- [ ] `cd backend && grep -rn 'down_revision = "0028' alembic/versions/` → uma linha só
- [ ] Migração: rodar o `SELECT` do backfill à mão no Postgres e conferir a contagem **antes** de `alembic upgrade head`
