# Exportação para Excel nas listas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar à equipe interna um botão "Exportar Excel" nas listas de Clientes, Equipamentos e Ordens, mais um relatório novo de Certificados emitidos, gerando um `.xlsx` formatado com todas as linhas que batem com os filtros da tela.

**Architecture:** O backend gera o arquivo. Um módulo puro `app/core/planilha.py` é o único lugar que sabe montar xlsx com acabamento; cada router ganha um endpoint `/exportar` que reaproveita — via helper extraído — exatamente a mesma query de filtro que a listagem já usa. No frontend, um componente `BotaoExportar` compartilhado leva os filtros da tela e baixa o blob.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · openpyxl (nova) · pytest/SQLite in-memory · React 19 · TS · Vitest + Testing Library

**Spec:** `docs/superpowers/specs/2026-08-19-exportacao-excel-listas-design.md`

## Global Constraints

- **Idioma do domínio é PT-BR.** Nomes de funções, variáveis, rotas e mensagens em português. Mantenha o padrão.
- **Mensagens de commit em português SEM acentos (ASCII)**, uma linha só, sem corpo e **sem trailer de co-autor**. Formato: `tipo(escopo): descricao curta no imperativo`.
- **Não faça `git push`.** Commits locais apenas. O Erick pede o push quando quiser.
- **Autorização das exportações:** `Depends(get_current_usuario)` — igual à listagem correspondente. Nenhuma `require_funcao` nova.
- **`/exportar` DEVE ser declarado antes de qualquer rota `/{id}` do mesmo router.** FastAPI casa na ordem de registro; declarado depois, `/clientes/exportar` cai em `/{cliente_id}`, falha ao converter `"exportar"` para `int` e devolve 422 em vez do arquivo.
- **Teto de linhas:** `LIMITE_LINHAS = 50_000`. Acima disso a API responde 400.
- **Célula vazia para nulo.** Nunca escreva o `—` que a tela usa.
- **Testes existentes de listagem passam sem alteração.** Se um teste de `test_frota_leitura.py`, `test_clientes.py` ou `test_ordens*.py` precisar mudar, a extração do filtro alterou comportamento e está errada.
- **Backend:** `source backend/.venv/bin/activate` antes de rodar `pytest`, e rodar de dentro de `backend/`.
- **Verificação do frontend antes de commitar:** `npm run lint && npx tsc -b --noEmit && npm run build`.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/core/planilha.py` **(novo)** | Puro. Recebe colunas + linhas, devolve bytes de xlsx formatado. Único lugar que conhece openpyxl. |
| `backend/app/core/exportacoes.py` **(novo)** | Puro. Define as `Coluna` de cada uma das quatro planilhas e o texto do rodapé de filtros. Separado de `planilha.py` para que o motor não conheça o domínio. |
| `backend/app/api/clientes.py` | `_query_clientes()` extraído + `GET /clientes/exportar` |
| `backend/app/api/equipamentos_cliente.py` | `_query_frota()` extraído + `GET /equipamentos-cliente/exportar` |
| `backend/app/api/ordens.py` | `_query_ordens()` extraído + `GET /ordens/exportar` |
| `backend/app/api/certificados_emitidos.py` **(novo)** | Query que une `os_certificados` + `certificados_venda` e `GET /certificados-emitidos/exportar` |
| `backend/app/main.py` | `include_router` do router novo |
| `backend/requirements.txt` | `openpyxl` |
| `frontend/src/lib/download.ts` | extrair helpers + `baixarPlanilha()` |
| `frontend/src/components/ui/BotaoExportar.tsx` **(novo)** | Botão compartilhado: monta a query, baixa, mostra carregando/erro |
| `frontend/src/app/{clientes,frota,ordens}/*Page.tsx` | usar o botão |
| `frontend/src/app/certificados/EmitidosTab.tsx` **(novo)** + `CertificadosPage.tsx` | aba nova com filtros + botão |

---

### Task 1: Extrair os filtros das listagens para helpers

Refactor puro, sem mudança de comportamento. Faz `listar()` e o futuro `exportar()` compartilharem a mesma query, para que não divirjam.

**Files:**
- Modify: `backend/app/api/clientes.py:17-37`
- Modify: `backend/app/api/equipamentos_cliente.py:76-111`
- Modify: `backend/app/api/ordens.py:28-68`
- Test: nenhum arquivo novo — os testes existentes são o critério

- [ ] **Step 1: Rodar os testes de listagem ANTES de mexer, para ter a linha de base**

```bash
cd backend && source .venv/bin/activate
pytest tests/test_clientes.py tests/test_frota_leitura.py tests/test_ordens_listar.py -q
```

Anote quantos passaram. Se algum arquivo não existir, rode `pytest -q -k "clientes or frota or ordens"` e use esse conjunto como linha de base. Esse número tem que ser idêntico no fim da task.

- [ ] **Step 2: Extrair `_query_clientes` em `clientes.py`**

Coloque a função **acima** de `listar`. O corpo é exatamente o que está dentro de `listar` hoje, sem `total`/`offset`/`limit`:

```python
def _query_clientes(db: Session, q: str | None = None):
    """Filtros da lista de clientes. Usado por listar() e por exportar() —
    ter um lugar so' impede que a planilha ignore um filtro novo em silencio."""
    query = db.query(Cliente)
    if q:
        termo = f"%{q}%"
        filtros = [Cliente.nome.ilike(termo), Cliente.municipio.ilike(termo)]
        digitos = re.sub(r"\D", "", q)
        if digitos:
            termo_doc = f"%{digitos}%"
            filtros += [Cliente.cgc.ilike(termo_doc), Cliente.cpf.ilike(termo_doc)]
        query = query.filter(or_(*filtros))
    return query.order_by(Cliente.nome)
```

E `listar` passa a ser:

```python
@router.get("", response_model=ClientesPage)
def listar(
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = _query_clientes(db, q=q)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return ClientesPage(items=[ClienteListOut.model_validate(c) for c in items], total=total)
```

Note que o `order_by` mudou de lugar (foi para dentro do helper) mas não de conteúdo — continua `Cliente.nome`.

- [ ] **Step 3: Extrair `_query_frota` em `equipamentos_cliente.py`**

Acima de `listar`:

```python
def _query_frota(db: Session, cliente: int | None = None, status: str | None = None,
                 ativo: bool | None = None, q: str | None = None):
    """Filtros da frota. Usado por listar() e por exportar() — ter um lugar so'
    impede que a planilha ignore um filtro novo em silencio."""
    query = db.query(EquipamentoCliente)
    if cliente is not None:
        query = query.filter(EquipamentoCliente.cliente == cliente)
    if ativo is not None:
        # Filtro opcional: omitido devolve ativos E inativos, como sempre foi.
        query = query.filter(EquipamentoCliente.ativo.is_(ativo))
    if status:
        hoje = date.today()
        if status == "vencido":
            query = query.filter(EquipamentoCliente.prox_calibragem < hoje)
        elif status == "vencendo":
            query = query.filter(
                EquipamentoCliente.prox_calibragem >= hoje,
                EquipamentoCliente.prox_calibragem <= hoje + timedelta(days=90),
            )
        elif status == "em_dia":
            query = query.filter(EquipamentoCliente.prox_calibragem > hoje + timedelta(days=90))
        elif status == "sem_data":
            query = query.filter(EquipamentoCliente.prox_calibragem.is_(None))
    if q:
        termo = f"%{q}%"
        query = query.filter(or_(EquipamentoCliente.serie.ilike(termo),
                                 EquipamentoCliente.patrimonio.ilike(termo)))
    return query.order_by(EquipamentoCliente.id)
```

E `listar` vira `query = _query_frota(db, cliente=cliente, status=status, ativo=ativo, q=q)` seguido de `total = query.count()` e `items = query.offset(offset).limit(limit).all()`.

- [ ] **Step 4: Extrair `_query_ordens` em `ordens.py`**

Acima de `listar`. **Copie os comentários existentes junto** — a explicação da faixa de data é conhecimento que custou caro:

```python
def _query_ordens(db: Session, fase: int | None = None, cliente: int | None = None,
                  tipo: str | None = None, q: str | None = None,
                  chegada_de: date | None = None, chegada_ate: date | None = None):
    """Filtros da lista de OS. Usado por listar() e por exportar() — ter um lugar
    so' impede que a planilha ignore um filtro novo em silencio."""
    query = db.query(Ordem)
    if fase is not None:
        query = query.filter(Ordem.fase == fase)
    if cliente is not None:
        query = query.filter(Ordem.cliente == cliente)
    if tipo:
        query = query.filter(Ordem.tipo_servico == tipo)
    # Faixa de data de chegada, INCLUSIVA nas duas pontas. `data_chegada` e um
    # DateTime: uma data digitada no recebimento fica em 00:00 UTC, mas a que o
    # sistema preenche sozinho carrega a hora. Por isso o fim da faixa e "< dia
    # seguinte" em vez de "<= o dia" — senao uma OS chegada as 14h do ultimo dia
    # ficaria de fora do proprio filtro que a inclui.
    if chegada_de is not None:
        query = query.filter(Ordem.data_chegada >= datetime.combine(chegada_de, datetime.min.time(), tzinfo=timezone.utc))
    if chegada_ate is not None:
        limite = datetime.combine(chegada_ate, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)
        query = query.filter(Ordem.data_chegada < limite)
    if q:
        if q.strip().isdigit():
            query = query.filter(Ordem.id == int(q.strip()))
        else:
            termo = f"%{q}%"
            query = query.join(Cliente, Ordem.cliente == Cliente.id).filter(
                or_(Ordem.etiqueta.ilike(termo), Cliente.nome.ilike(termo))
            )
    return query.order_by(Ordem.id.desc())
```

- [ ] **Step 5: Rodar os testes e confirmar que NADA mudou**

```bash
cd backend && source .venv/bin/activate && pytest -q
```

Expected: PASS, com exatamente a mesma contagem do Step 1. **Se algum teste falhar, a extração mudou comportamento — conserte a extração, não o teste.**

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/clientes.py backend/app/api/equipamentos_cliente.py backend/app/api/ordens.py
git commit -m "refactor(export): extrai os filtros das listagens para helpers reusaveis"
```

---

### Task 2: O motor de planilha (`core/planilha.py`)

**Files:**
- Create: `backend/app/core/planilha.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_planilha.py`

**Interfaces:**
- Consumes: nada (módulo folha)
- Produces:
  - `Coluna(titulo: str, campo: str, largura: int, formato: str = "texto")` — dataclass frozen; `formato` ∈ `"texto" | "data" | "datahora" | "numero" | "inteiro" | "sim_nao"`
  - `LIMITE_LINHAS: int = 50_000`
  - `PlanilhaGrandeDemais(Exception)`
  - `gerar_xlsx(titulo_aba: str, colunas: Sequence[Coluna], linhas: Sequence[dict], rodape: str) -> bytes`

- [ ] **Step 1: Instalar a dependência e registrá-la**

```bash
cd backend && source .venv/bin/activate && pip install openpyxl
printf 'openpyxl\n' >> requirements.txt
```

- [ ] **Step 2: Escrever os testes que falham**

Crie `backend/tests/test_planilha.py`:

```python
from datetime import date, datetime, timezone
from io import BytesIO

import pytest
from openpyxl import load_workbook

from app.core.planilha import Coluna, LIMITE_LINHAS, PlanilhaGrandeDemais, gerar_xlsx

COLUNAS = [
    Coluna("Codigo", "id", 10, "inteiro"),
    Coluna("Nome", "nome", 30),
    Coluna("Nascimento", "nasc", 14, "data"),
    Coluna("Criado em", "criado", 18, "datahora"),
    Coluna("Valor", "valor", 12, "numero"),
    Coluna("Ativo", "ativo", 8, "sim_nao"),
]


def _abrir(conteudo: bytes):
    return load_workbook(BytesIO(conteudo)).active


def test_cabecalho_e_titulo_da_aba():
    aba = _abrir(gerar_xlsx("Clientes", COLUNAS, [], "sem filtros"))
    assert aba.title == "Clientes"
    assert [c.value for c in aba[1]] == ["Codigo", "Nome", "Nascimento", "Criado em", "Valor", "Ativo"]
    assert aba["A1"].font.bold is True


def test_painel_congelado_e_autofiltro():
    aba = _abrir(gerar_xlsx("Clientes", COLUNAS, [{"id": 1}], "sem filtros"))
    assert aba.freeze_panes == "A2"
    # 6 colunas (A..F), cabecalho + 1 linha de dados
    assert aba.auto_filter.ref == "A1:F2"


def test_tipos_das_celulas_sao_reais_nao_texto():
    linha = {
        "id": 7, "nome": "Fulano", "nasc": date(2020, 3, 1),
        "criado": datetime(2021, 5, 2, 14, 30, tzinfo=timezone.utc),
        "valor": 1234.56, "ativo": True,
    }
    aba = _abrir(gerar_xlsx("X", COLUNAS, [linha], "sem filtros"))
    assert aba["A2"].value == 7
    assert aba["C2"].value == date(2020, 3, 1)
    assert aba["C2"].number_format == "DD/MM/YYYY"
    assert aba["D2"].number_format == "DD/MM/YYYY HH:MM"
    assert aba["E2"].value == pytest.approx(1234.56)
    assert aba["F2"].value == "Sim"


def test_datahora_com_fuso_perde_o_tzinfo():
    """Excel nao guarda fuso; openpyxl recusa datetime aware. A conversao e' nossa."""
    linha = {"criado": datetime(2021, 5, 2, 14, 30, tzinfo=timezone.utc)}
    aba = _abrir(gerar_xlsx("X", COLUNAS, [linha], "sem filtros"))
    assert aba["D2"].value == datetime(2021, 5, 2, 14, 30)
    assert aba["D2"].value.tzinfo is None


def test_nulo_vira_celula_vazia_nunca_travessao():
    aba = _abrir(gerar_xlsx("X", COLUNAS, [{"id": 1, "nome": None}], "sem filtros"))
    assert aba["B2"].value is None


def test_booleano_falso_vira_nao_e_nulo_continua_vazio():
    aba = _abrir(gerar_xlsx("X", COLUNAS, [{"ativo": False}, {"ativo": None}], "sem filtros"))
    assert aba["F2"].value == "Nao"
    assert aba["F3"].value is None


def test_campo_ausente_no_dict_nao_quebra():
    aba = _abrir(gerar_xlsx("X", COLUNAS, [{}], "sem filtros"))
    assert aba["A2"].value is None


def test_largura_das_colunas_vem_da_definicao():
    aba = _abrir(gerar_xlsx("X", COLUNAS, [], "sem filtros"))
    assert aba.column_dimensions["A"].width == 10
    assert aba.column_dimensions["B"].width == 30


def test_rodape_registra_os_filtros_depois_de_uma_linha_em_branco():
    aba = _abrir(gerar_xlsx("X", COLUNAS, [{"id": 1}], "Status: Vencido"))
    # linha 1 cabecalho, linha 2 dado, linha 3 em branco, linha 4 rodape
    assert aba["A3"].value is None
    assert "Status: Vencido" in aba["A4"].value


def test_acima_do_teto_levanta():
    with pytest.raises(PlanilhaGrandeDemais):
        gerar_xlsx("X", COLUNAS, [{"id": 1}] * (LIMITE_LINHAS + 1), "sem filtros")


def test_no_teto_exato_nao_levanta(monkeypatch):
    """Baixamos o teto em vez de gerar 50.000 linhas de verdade: a regra sob teste e'
    `len(linhas) > LIMITE_LINHAS`, que nao depende do volume, e escrever um xlsx de
    50k linhas levaria dezenas de segundos numa suite que roda a cada commit."""
    import app.core.planilha as mod
    monkeypatch.setattr(mod, "LIMITE_LINHAS", 3)
    conteudo = gerar_xlsx("X", [Coluna("Codigo", "id", 10, "inteiro")],
                          [{"id": 1}] * 3, "sem filtros")
    assert conteudo[:2] == b"PK"  # xlsx e' um zip
```

- [ ] **Step 3: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_planilha.py -q
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.planilha'`

- [ ] **Step 4: Implementar `core/planilha.py`**

```python
"""Motor de planilhas do sistema.

Puro: nao conhece SQLAlchemy, FastAPI nem o dominio. Recebe colunas e dicionarios,
devolve os bytes de um .xlsx. Existe para que TODA exportacao do GestorHS saia com o
mesmo acabamento — se o cabecalho muda aqui, muda em todas de uma vez.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Literal, Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

Formato = Literal["texto", "data", "datahora", "numero", "inteiro", "sim_nao"]

# Teto de seguranca. Acima disso a geracao sincrona comeca a segurar o worker, e a
# planilha ja passou do tamanho em que alguem consegue trabalhar nela.
LIMITE_LINHAS = 50_000

_FORMATO_NUMERICO = {
    "data": "DD/MM/YYYY",
    "datahora": "DD/MM/YYYY HH:MM",
    "numero": "#,##0.00",
    "inteiro": "0",
}

_FUNDO_CABECALHO = PatternFill("solid", start_color="FF1F3B57", end_color="FF1F3B57")
_FONTE_CABECALHO = Font(bold=True, color="FFFFFFFF")


class PlanilhaGrandeDemais(Exception):
    """Mais linhas do que LIMITE_LINHAS. O chamador transforma em 400."""


@dataclass(frozen=True)
class Coluna:
    titulo: str
    campo: str
    largura: int
    formato: Formato = "texto"


def _valor_da_celula(bruto: Any, formato: Formato) -> Any:
    if bruto is None:
        # Celula VAZIA, nunca o "—" que a tela usa: quem recebe a planilha filtra e
        # soma em cima dela, e um travessao transforma a coluna inteira em texto.
        return None
    if formato == "sim_nao":
        return "Sim" if bruto else "Nao"
    if formato == "datahora" and isinstance(bruto, datetime):
        # O Excel nao tem conceito de fuso e o openpyxl recusa datetime aware.
        # As datas do sistema sao UTC; guardamos o instante sem o rotulo.
        return bruto.replace(tzinfo=None)
    if formato == "data" and isinstance(bruto, datetime):
        return bruto.date()
    if formato in ("numero", "inteiro") and isinstance(bruto, Decimal):
        return float(bruto)
    return bruto


def gerar_xlsx(
    titulo_aba: str,
    colunas: Sequence[Coluna],
    linhas: Sequence[dict],
    rodape: str,
) -> bytes:
    """Monta a planilha e devolve os bytes. `linhas` sao dicionarios; a chave usada
    de cada uma e' o `campo` da Coluna, e chave ausente vale o mesmo que None."""
    if len(linhas) > LIMITE_LINHAS:
        raise PlanilhaGrandeDemais(len(linhas))

    wb = Workbook()
    aba = wb.active
    aba.title = titulo_aba[:31]  # limite do proprio formato xlsx

    aba.append([c.titulo for c in colunas])
    for i, coluna in enumerate(colunas, start=1):
        celula = aba.cell(row=1, column=i)
        celula.font = _FONTE_CABECALHO
        celula.fill = _FUNDO_CABECALHO
        celula.alignment = Alignment(vertical="center")
        aba.column_dimensions[get_column_letter(i)].width = coluna.largura

    for linha in linhas:
        aba.append([_valor_da_celula(linha.get(c.campo), c.formato) for c in colunas])

    for i, coluna in enumerate(colunas, start=1):
        formato_numerico = _FORMATO_NUMERICO.get(coluna.formato)
        if not formato_numerico:
            continue
        for celula in aba.iter_rows(min_row=2, max_row=1 + len(linhas),
                                    min_col=i, max_col=i):
            celula[0].number_format = formato_numerico

    # Congela o cabecalho e liga o autofiltro em toda a faixa de dados. Com o
    # cabecalho fixo da' para rolar mil linhas sem perder de vista o que e' cada coluna.
    aba.freeze_panes = "A2"
    aba.auto_filter.ref = f"A1:{get_column_letter(len(colunas))}{1 + len(linhas)}"

    # Uma linha em branco separa os dados do rodape — sem ela o autofiltro do Excel
    # trataria o rodape como se fosse mais um registro.
    aba.append([])
    aba.append([rodape])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 5: Rodar os testes até passarem**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_planilha.py -q
```

Expected: PASS, 11 testes.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/planilha.py backend/tests/test_planilha.py backend/requirements.txt
git commit -m "feat(export): motor de planilha xlsx com cabecalho, autofiltro e tipos reais"
```

---

### Task 3: As colunas de cada exportação (`core/exportacoes.py`)

Módulo puro que traduz objetos do domínio em dicionários prontos para o motor. Separado de `planilha.py` para que o motor continue sem saber o que é uma OS.

**Files:**
- Create: `backend/app/core/exportacoes.py`
- Test: `backend/tests/test_exportacoes.py`

**Interfaces:**
- Consumes: `Coluna` de `app.core.planilha`
- Produces:
  - `COLUNAS_CLIENTES`, `COLUNAS_FROTA`, `COLUNAS_ORDENS`, `COLUNAS_CERTIFICADOS` — `list[Coluna]`
  - `linha_cliente(c) -> dict`, `linha_frota(e) -> dict`, `linha_ordem(o) -> dict`
  - `montar_rodape(filtros: dict, gerado_em: datetime) -> str`
  - `nome_arquivo(base: str, hoje: date) -> str`
  - `STATUS_POR_EXTENSO: dict[str, str]`

- [ ] **Step 1: Escrever os testes que falham**

Crie `backend/tests/test_exportacoes.py`:

```python
from datetime import date, datetime

from app.core.exportacoes import (
    COLUNAS_CERTIFICADOS, COLUNAS_CLIENTES, COLUNAS_FROTA, COLUNAS_ORDENS,
    linha_cliente, linha_frota, linha_ordem, montar_rodape, nome_arquivo,
)


class _Fake:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_todo_campo_de_coluna_tem_titulo_e_largura():
    for colunas in (COLUNAS_CLIENTES, COLUNAS_FROTA, COLUNAS_ORDENS, COLUNAS_CERTIFICADOS):
        assert colunas, "conjunto de colunas vazio"
        for c in colunas:
            assert c.titulo and c.largura > 0


def test_nao_ha_campo_repetido_em_um_mesmo_conjunto():
    """Campo repetido significa duas colunas mostrando o mesmo dado — quase sempre
    um copiar-e-colar esquecido."""
    for colunas in (COLUNAS_CLIENTES, COLUNAS_FROTA, COLUNAS_ORDENS, COLUNAS_CERTIFICADOS):
        campos = [c.campo for c in colunas]
        assert len(campos) == len(set(campos)), campos


def test_linha_cliente_traz_os_campos_das_colunas():
    c = _Fake(id=1, nome="ACME", cgc="11222333000144", cpf=None, insc_est="123",
              endereco="Rua A", numero=10, complemento=None, bairro="Centro",
              municipio="Recife", estado="PE", cep="50000000", contato="Joao",
              email="a@b.c", telefones="8130000000", celular=None, whatsapp=None,
              datcad=date(2020, 1, 5), ativo=True)
    linha = linha_cliente(c)
    for coluna in COLUNAS_CLIENTES:
        assert coluna.campo in linha, coluna.campo
    assert linha["nome"] == "ACME"
    assert linha["ativo"] is True


def test_linha_frota_escreve_o_status_por_extenso():
    e = _Fake(id=3, cliente_nome="ACME", cliente_rel=_Fake(cgc="11222333000144"),
              equipamento_descricao="Alcotest", equipamento_rel=None, serie="S1",
              patrimonio=None, datacompra=None, ult_calibragem=None,
              prox_calibragem=date(2030, 1, 1), status_calibracao="em_dia",
              calib_cert="C-1", calib_situacao="Aprovado", os_atual=None, ativo=True)
    linha = linha_frota(e)
    assert linha["status_calibracao"] == "Em dia"
    assert linha["cliente_cnpj"] == "11222333000144"


def test_linha_frota_sem_cliente_rel_nao_quebra():
    e = _Fake(id=3, cliente_nome=None, cliente_rel=None, equipamento_descricao=None,
              equipamento_rel=None, serie=None, patrimonio=None, datacompra=None,
              ult_calibragem=None, prox_calibragem=None, status_calibracao="sem_data",
              calib_cert=None, calib_situacao=None, os_atual=None, ativo=False)
    linha = linha_frota(e)
    assert linha["cliente_cnpj"] is None
    assert linha["marca"] is None
    assert linha["status_calibracao"] == "Sem data"


def test_linha_ordem_traz_os_campos_das_colunas():
    o = _Fake(id=99, cliente_nome="ACME", cliente_rel=_Fake(cgc="11222333000144"),
              equipamento_descricao="Alcotest", equipamento_serie="S1",
              fase_descricao="Laboratorio", tipo_servico="C",
              data_chegada=datetime(2026, 1, 2, 9, 0), data_calibracao=None,
              data_retorno=None, data_entrega=None, prox_calibragem=None,
              calib_cert="C-9", calib_situacao=None, nota_fiscal_numero="123",
              valor=10, frete_envio=0, frete_retorno=0, pago=False, caixa=None,
              garantia=True)
    linha = linha_ordem(o)
    for coluna in COLUNAS_ORDENS:
        assert coluna.campo in linha, coluna.campo
    assert linha["tipo_servico"] == "Calibracao"


def test_rodape_lista_os_filtros_usados_e_a_hora():
    texto = montar_rodape({"Status": "Vencido", "Cliente": "ACME"},
                          datetime(2026, 8, 19, 15, 4))
    assert "Status: Vencido" in texto
    assert "Cliente: ACME" in texto
    assert "19/08/2026 15:04" in texto


def test_rodape_sem_filtro_diz_que_nao_houve_filtro():
    texto = montar_rodape({}, datetime(2026, 8, 19, 15, 4))
    assert "sem filtros" in texto.lower()


def test_rodape_ignora_filtro_vazio():
    texto = montar_rodape({"Status": "", "Cliente": None, "Busca": "abc"},
                          datetime(2026, 8, 19, 15, 4))
    assert "Status" not in texto
    assert "Cliente" not in texto
    assert "Busca: abc" in texto


def test_nome_do_arquivo_leva_a_data():
    assert nome_arquivo("equipamentos", date(2026, 8, 19)) == "equipamentos-2026-08-19.xlsx"
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_exportacoes.py -q
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.exportacoes'`

- [ ] **Step 3: Implementar `core/exportacoes.py`**

```python
"""O que cada planilha do GestorHS mostra.

Puro: nao toca no banco. Recebe objetos ja' carregados e devolve dicionarios no
formato que `core.planilha.gerar_xlsx` espera. Fica separado de `planilha.py` para
que o motor continue sem saber o que e' uma OS.
"""
from datetime import date, datetime

from app.core.planilha import Coluna

STATUS_POR_EXTENSO = {
    "em_dia": "Em dia",
    "vencendo": "Vencendo",
    "vencido": "Vencido",
    "sem_data": "Sem data",
}

# Os codigos de uma letra que o banco guarda. Na planilha vao por extenso: quem abre
# o arquivo nao tem a legenda do sistema por perto.
TIPO_SERVICO_POR_EXTENSO = {"C": "Calibracao", "M": "Manutencao"}
TIPO_CERTIFICADO_POR_EXTENSO = {"C": "Calibracao", "M": "Manutencao"}


COLUNAS_CLIENTES = [
    Coluna("Codigo", "id", 10, "inteiro"),
    Coluna("Nome", "nome", 40),
    Coluna("CNPJ", "cgc", 20),
    Coluna("CPF", "cpf", 16),
    Coluna("Inscr. estadual", "insc_est", 18),
    Coluna("Endereco", "endereco", 40),
    Coluna("Numero", "numero", 10),
    Coluna("Complemento", "complemento", 20),
    Coluna("Bairro", "bairro", 22),
    Coluna("Municipio", "municipio", 24),
    Coluna("UF", "estado", 6),
    Coluna("CEP", "cep", 12),
    Coluna("Contato", "contato", 24),
    Coluna("E-mail", "email", 32),
    Coluna("Telefones", "telefones", 26),
    Coluna("Celular", "celular", 20),
    Coluna("WhatsApp", "whatsapp", 20),
    Coluna("Cadastrado em", "datcad", 16, "data"),
    Coluna("Ativo", "ativo", 8, "sim_nao"),
]

COLUNAS_FROTA = [
    Coluna("Codigo", "id", 10, "inteiro"),
    Coluna("Cliente", "cliente_nome", 34),
    Coluna("CNPJ do cliente", "cliente_cnpj", 20),
    Coluna("Aparelho", "equipamento_descricao", 30),
    Coluna("Marca", "marca", 18),
    Coluna("Serie", "serie", 18),
    Coluna("Patrimonio", "patrimonio", 16),
    Coluna("Data da compra", "datacompra", 16, "data"),
    Coluna("Ultima calibracao", "ult_calibragem", 18, "data"),
    Coluna("Proxima calibracao", "prox_calibragem", 18, "data"),
    Coluna("Status", "status_calibracao", 14),
    Coluna("No. do certificado", "calib_cert", 20),
    Coluna("Situacao da calibracao", "calib_situacao", 22),
    Coluna("OS atual", "os_atual", 12, "inteiro"),
    Coluna("Ativo", "ativo", 8, "sim_nao"),
]

COLUNAS_ORDENS = [
    Coluna("OS", "id", 10, "inteiro"),
    Coluna("Cliente", "cliente_nome", 34),
    Coluna("CNPJ do cliente", "cliente_cnpj", 20),
    Coluna("Aparelho", "equipamento_descricao", 30),
    Coluna("Serie", "equipamento_serie", 18),
    Coluna("Fase", "fase_descricao", 20),
    Coluna("Tipo de servico", "tipo_servico", 16),
    Coluna("Chegada", "data_chegada", 18, "datahora"),
    Coluna("Calibracao", "data_calibracao", 18, "datahora"),
    Coluna("Retorno", "data_retorno", 18, "datahora"),
    Coluna("Entrega", "data_entrega", 18, "datahora"),
    Coluna("Proxima calibracao", "prox_calibragem", 18, "datahora"),
    Coluna("No. do certificado", "calib_cert", 20),
    Coluna("Situacao", "calib_situacao", 18),
    Coluna("Nota fiscal", "nota_fiscal_numero", 14),
    Coluna("Valor", "valor", 12, "numero"),
    Coluna("Frete envio", "frete_envio", 12, "numero"),
    Coluna("Frete retorno", "frete_retorno", 12, "numero"),
    Coluna("Pago", "pago", 8, "sim_nao"),
    Coluna("Caixa", "caixa", 10, "inteiro"),
    Coluna("Garantia", "garantia", 10, "sim_nao"),
]

COLUNAS_CERTIFICADOS = [
    Coluna("Cliente", "cliente_nome", 34),
    Coluna("CNPJ", "cliente_cnpj", 20),
    Coluna("Aparelho", "equipamento_descricao", 30),
    Coluna("Serie", "serie", 18),
    Coluna("Origem", "origem", 12),
    Coluna("OS", "os", 10, "inteiro"),
    Coluna("Tipo", "tipo", 16),
    Coluna("No. do certificado", "calib_cert", 20),
    Coluna("Data da calibracao", "data_calibracao", 18, "data"),
    Coluna("Gerado em", "data_geracao", 18, "datahora"),
    Coluna("Gerado por", "usuario_nome", 24),
]


def _cnpj_do_cliente(obj):
    rel = getattr(obj, "cliente_rel", None)
    return rel.cgc if rel else None


def linha_cliente(c) -> dict:
    return {
        "id": c.id, "nome": c.nome, "cgc": c.cgc, "cpf": c.cpf,
        "insc_est": c.insc_est, "endereco": c.endereco, "numero": c.numero,
        "complemento": c.complemento, "bairro": c.bairro, "municipio": c.municipio,
        "estado": c.estado, "cep": c.cep, "contato": c.contato, "email": c.email,
        "telefones": c.telefones, "celular": c.celular, "whatsapp": c.whatsapp,
        "datcad": c.datcad, "ativo": c.ativo,
    }


def linha_frota(e) -> dict:
    # `marca` nao tem property no modelo (diferente de `equipamento_descricao`), entao
    # o endpoint anexa `_marca_nome` no objeto antes de chamar aqui — ver a query do
    # exportar, que ja' faz o join com `marcas`.
    return {
        "id": e.id, "cliente_nome": e.cliente_nome, "cliente_cnpj": _cnpj_do_cliente(e),
        "equipamento_descricao": e.equipamento_descricao,
        "marca": getattr(e, "_marca_nome", None),
        "serie": e.serie, "patrimonio": e.patrimonio, "datacompra": e.datacompra,
        "ult_calibragem": e.ult_calibragem, "prox_calibragem": e.prox_calibragem,
        "status_calibracao": STATUS_POR_EXTENSO.get(e.status_calibracao, e.status_calibracao),
        "calib_cert": e.calib_cert, "calib_situacao": e.calib_situacao,
        "os_atual": e.os_atual, "ativo": e.ativo,
    }


def linha_ordem(o) -> dict:
    return {
        "id": o.id, "cliente_nome": o.cliente_nome, "cliente_cnpj": _cnpj_do_cliente(o),
        "equipamento_descricao": o.equipamento_descricao,
        "equipamento_serie": o.equipamento_serie, "fase_descricao": o.fase_descricao,
        "tipo_servico": TIPO_SERVICO_POR_EXTENSO.get(o.tipo_servico, o.tipo_servico),
        "data_chegada": o.data_chegada, "data_calibracao": o.data_calibracao,
        "data_retorno": o.data_retorno, "data_entrega": o.data_entrega,
        "prox_calibragem": o.prox_calibragem, "calib_cert": o.calib_cert,
        "calib_situacao": o.calib_situacao, "nota_fiscal_numero": o.nota_fiscal_numero,
        "valor": o.valor, "frete_envio": o.frete_envio,
        "frete_retorno": o.frete_retorno, "pago": o.pago, "caixa": o.caixa,
        "garantia": o.garantia,
    }


def montar_rodape(filtros: dict, gerado_em: datetime) -> str:
    """A linha que vai depois dos dados. Quem recebe a planilha por e-mail nao sabe
    que filtro a gerou — sem isso, uma exportacao parcial passa por base completa."""
    usados = [f"{k}: {v}" for k, v in filtros.items() if v not in (None, "")]
    parte = " | ".join(usados) if usados else "sem filtros"
    return f"Gerado pelo GestorHS em {gerado_em.strftime('%d/%m/%Y %H:%M')} — Filtros: {parte}"


def nome_arquivo(base: str, hoje: date) -> str:
    return f"{base}-{hoje.isoformat()}.xlsx"
```

- [ ] **Step 4: Rodar os testes até passarem**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_exportacoes.py -q
```

Expected: PASS, 10 testes.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/exportacoes.py backend/tests/test_exportacoes.py
git commit -m "feat(export): define as colunas das planilhas de clientes, frota, ordens e certificados"
```

---

### Task 4: Endpoints de exportação de Clientes, Frota e Ordens

**Files:**
- Modify: `backend/app/api/clientes.py`
- Modify: `backend/app/api/equipamentos_cliente.py`
- Modify: `backend/app/api/ordens.py`
- Test: `backend/tests/test_exportar_api.py`

**Interfaces:**
- Consumes: `_query_clientes`/`_query_frota`/`_query_ordens` (Task 1); `gerar_xlsx`, `PlanilhaGrandeDemais` (Task 2); `COLUNAS_*`, `linha_*`, `montar_rodape`, `nome_arquivo` (Task 3)
- Produces: `GET /clientes/exportar`, `GET /equipamentos-cliente/exportar`, `GET /ordens/exportar`

- [ ] **Step 1: Escrever os testes que falham**

Crie `backend/tests/test_exportar_api.py`:

```python
from datetime import date, timedelta
from io import BytesIO

from openpyxl import load_workbook

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _headers(client, email="admin@hs.com", senha="senha123"):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _series(resposta):
    """Todas as celulas da planilha como texto, para procurar valores dentro dela."""
    aba = load_workbook(BytesIO(resposta.content)).active
    return {str(c.value) for linha in aba.iter_rows() for c in linha if c.value is not None}


def _base(db_session):
    from app.models import Cliente, Equipamento, Marca
    marca = Marca(descricao="Drager")
    db_session.add(marca)
    db_session.flush()
    c = Cliente(nome="Cliente Export", cgc="11222333000144")
    e = Equipamento(descricao="Alcotest 6820", marca=marca.id)
    db_session.add_all([c, e])
    db_session.commit()
    return c.id, e.id


def test_exportar_frota_exige_token(client):
    assert client.get("/equipamentos-cliente/exportar").status_code == 401


def test_exportar_frota_devolve_xlsx_com_nome_de_arquivo(client, usuario_admin, db_session):
    _base(db_session)
    r = client.get("/equipamentos-cliente/exportar", headers=_headers(client))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(XLSX)
    assert "attachment" in r.headers["content-disposition"]
    assert f"equipamentos-{date.today().isoformat()}.xlsx" in r.headers["content-disposition"]


def test_exportar_frota_respeita_o_filtro_de_status(client, usuario_admin, db_session):
    """O teste que importa: a planilha nao pode trazer linha que o filtro exclui."""
    from app.models import EquipamentoCliente
    cid, eid = _base(db_session)
    hoje = date.today()
    db_session.add_all([
        EquipamentoCliente(cliente=cid, equipamento=eid, serie="SERIEVENCIDA",
                           prox_calibragem=hoje - timedelta(days=1)),
        EquipamentoCliente(cliente=cid, equipamento=eid, serie="SERIEEMDIA",
                           prox_calibragem=hoje + timedelta(days=200)),
    ])
    db_session.commit()
    r = client.get("/equipamentos-cliente/exportar?status=vencido", headers=_headers(client))
    valores = _series(r)
    assert "SERIEVENCIDA" in valores
    assert "SERIEEMDIA" not in valores


def test_exportar_frota_ignora_a_paginacao_da_tela(client, usuario_admin, db_session):
    """A tela mostra 25 por vez; a planilha tem que trazer tudo."""
    from app.models import EquipamentoCliente
    cid, eid = _base(db_session)
    db_session.add_all([
        EquipamentoCliente(cliente=cid, equipamento=eid, serie=f"S{i:03d}")
        for i in range(40)
    ])
    db_session.commit()
    valores = _series(client.get("/equipamentos-cliente/exportar", headers=_headers(client)))
    assert "S000" in valores and "S039" in valores


def test_exportar_frota_traz_a_marca_e_o_cnpj_do_cliente(client, usuario_admin, db_session):
    from app.models import EquipamentoCliente
    cid, eid = _base(db_session)
    db_session.add(EquipamentoCliente(cliente=cid, equipamento=eid, serie="COMMARCA"))
    db_session.commit()
    valores = _series(client.get("/equipamentos-cliente/exportar", headers=_headers(client)))
    assert "Drager" in valores
    assert "11222333000144" in valores


def test_exportar_clientes_respeita_a_busca(client, usuario_admin, db_session):
    from app.models import Cliente
    db_session.add_all([Cliente(nome="Alfa Industria"), Cliente(nome="Beta Comercio")])
    db_session.commit()
    valores = _series(client.get("/clientes/exportar?q=Alfa", headers=_headers(client)))
    assert "Alfa Industria" in valores
    assert "Beta Comercio" not in valores


def test_exportar_clientes_nao_colide_com_a_rota_de_id(client, usuario_admin, db_session):
    """Se /exportar for declarado depois de /{cliente_id}, o FastAPI tenta converter
    "exportar" para int e devolve 422 em vez do arquivo."""
    r = client.get("/clientes/exportar", headers=_headers(client))
    assert r.status_code == 200, r.text


def test_exportar_ordens_respeita_o_filtro_de_fase(client, usuario_admin, db_session, fases_seed):
    from app.models import Ordem
    cid, eid = _base(db_session)
    db_session.add_all([
        Ordem(cliente=cid, fase=4, etiqueta="ETIQ-RECEBIDO"),
        Ordem(cliente=cid, fase=5, etiqueta="ETIQ-LAB"),
    ])
    db_session.commit()
    valores = _series(client.get("/ordens/exportar?fase=4", headers=_headers(client)))
    assert "ETIQ-RECEBIDO" in valores
    assert "ETIQ-LAB" not in valores


def test_exportar_ordens_nao_colide_com_a_rota_de_id(client, usuario_admin):
    assert client.get("/ordens/exportar", headers=_headers(client)).status_code == 200


def test_acima_do_teto_devolve_400(client, usuario_admin, db_session, monkeypatch):
    from app.models import EquipamentoCliente
    import app.core.planilha as planilha
    monkeypatch.setattr(planilha, "LIMITE_LINHAS", 1)
    cid, eid = _base(db_session)
    db_session.add_all([
        EquipamentoCliente(cliente=cid, equipamento=eid, serie="A"),
        EquipamentoCliente(cliente=cid, equipamento=eid, serie="B"),
    ])
    db_session.commit()
    r = client.get("/equipamentos-cliente/exportar", headers=_headers(client))
    assert r.status_code == 400
    assert "filtro" in r.json()["detail"].lower()
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_exportar_api.py -q
```

Expected: FAIL — 404 nas rotas `/exportar`, que ainda não existem.

- [ ] **Step 3: Criar o helper de resposta em `core/exportacoes.py`**

Acrescente ao fim de `backend/app/core/exportacoes.py`:

```python
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

E crie `backend/app/api/exportar_common.py`:

```python
"""Cola entre os endpoints de exportacao e o motor de planilha.

Existe para que os quatro endpoints nao repitam o try/except e a montagem do header
de download — que e' onde erram, se repetidos.
"""
from datetime import date, datetime
from typing import Sequence

from fastapi import HTTPException, Response

from app.core.exportacoes import MIME_XLSX, montar_rodape, nome_arquivo
from app.core.planilha import Coluna, PlanilhaGrandeDemais, gerar_xlsx


def resposta_xlsx(
    base_nome: str,
    titulo_aba: str,
    colunas: Sequence[Coluna],
    linhas: list[dict],
    filtros: dict,
) -> Response:
    try:
        conteudo = gerar_xlsx(titulo_aba, colunas, linhas, montar_rodape(filtros, datetime.now()))
    except PlanilhaGrandeDemais:
        raise HTTPException(
            status_code=400,
            detail="A exportacao ficou grande demais. Refine o filtro e tente de novo.",
        )
    nome = nome_arquivo(base_nome, date.today())
    return Response(
        content=conteudo,
        media_type=MIME_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
```

Note que `resposta_xlsx` importa `gerar_xlsx` diretamente, mas o teste do teto faz `monkeypatch` em `app.core.planilha.LIMITE_LINHAS` — o módulo lê essa constante em tempo de chamada, então o patch pega.

- [ ] **Step 4: Adicionar `GET /clientes/exportar`**

Em `backend/app/api/clientes.py`, **imediatamente depois de `listar` e ANTES de `@router.get("/{cliente_id}")`**:

```python
@router.get("/exportar")
def exportar(
    q: str | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    itens = _query_clientes(db, q=q).all()
    return resposta_xlsx(
        "clientes", "Clientes", COLUNAS_CLIENTES,
        [linha_cliente(c) for c in itens], {"Busca": q},
    )
```

Imports novos no topo do arquivo:

```python
from app.api.exportar_common import resposta_xlsx
from app.core.exportacoes import COLUNAS_CLIENTES, linha_cliente
```

- [ ] **Step 5: Adicionar `GET /equipamentos-cliente/exportar`**

Em `backend/app/api/equipamentos_cliente.py`, depois de `listar` e **antes** de `@router.get("/{item_id}")`:

```python
@router.get("/exportar")
def exportar(
    cliente: int | None = None,
    status: str | None = None,
    ativo: bool | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    itens = _query_frota(db, cliente=cliente, status=status, ativo=ativo, q=q).all()

    # `marca` nao tem property no modelo — e' FK de `equipamentos` para `marcas`.
    # Uma consulta so' para todas as marcas em jogo evita N+1 sem mexer no modelo.
    ids_equip = {e.equipamento for e in itens if e.equipamento is not None}
    marcas = {}
    if ids_equip:
        linhas = (
            db.query(Equipamento.id, Marca.descricao)
            .outerjoin(Marca, Equipamento.marca == Marca.id)
            .filter(Equipamento.id.in_(ids_equip))
            .all()
        )
        marcas = {eid: desc for eid, desc in linhas}
    for e in itens:
        e._marca_nome = marcas.get(e.equipamento)

    return resposta_xlsx(
        "equipamentos", "Equipamentos", COLUNAS_FROTA,
        [linha_frota(e) for e in itens],
        {"Cliente": cliente, "Status": status,
         "Aparelhos": None if ativo is None else ("Ativos" if ativo else "Inativos"),
         "Busca": q},
    )
```

Imports novos:

```python
from app.models import Equipamento, Marca   # acrescentar aos imports de app.models ja' existentes
from app.api.exportar_common import resposta_xlsx
from app.core.exportacoes import COLUNAS_FROTA, linha_frota
```

- [ ] **Step 6: Adicionar `GET /ordens/exportar`**

Em `backend/app/api/ordens.py`, depois de `listar` e **antes** de `@router.get("/{ordem_id}")` (pode ficar junto de `/quadro`, que já está antes):

```python
@router.get("/exportar")
def exportar(
    fase: int | None = None,
    cliente: int | None = None,
    tipo: str | None = None,
    q: str | None = None,
    chegada_de: date | None = None,
    chegada_ate: date | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    itens = _query_ordens(db, fase=fase, cliente=cliente, tipo=tipo, q=q,
                          chegada_de=chegada_de, chegada_ate=chegada_ate).all()
    return resposta_xlsx(
        "ordens", "Ordens de servico", COLUNAS_ORDENS,
        [linha_ordem(o) for o in itens],
        {"Fase": fase, "Cliente": cliente, "Tipo": tipo, "Busca": q,
         "Chegada de": chegada_de, "Chegada ate": chegada_ate},
    )
```

Imports novos:

```python
from app.api.exportar_common import resposta_xlsx
from app.core.exportacoes import COLUNAS_ORDENS, linha_ordem
```

- [ ] **Step 7: Rodar os testes até passarem**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_exportar_api.py -q
```

Expected: PASS, 10 testes.

- [ ] **Step 8: Rodar a suíte inteira**

```bash
cd backend && source .venv/bin/activate && pytest -q
```

Expected: PASS. Nenhum teste antigo pode ter quebrado.

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/exportar_common.py backend/app/api/clientes.py \
        backend/app/api/equipamentos_cliente.py backend/app/api/ordens.py \
        backend/app/core/exportacoes.py backend/tests/test_exportar_api.py
git commit -m "feat(export): exportacao xlsx de clientes, equipamentos e ordens"
```

---

### Task 5: Relatório de certificados emitidos

Une `os_certificados` (com OS) e `certificados_venda` (sem OS) num conjunto só. Router novo, porque não existe hoje.

**Files:**
- Create: `backend/app/api/certificados_emitidos.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_certificados_emitidos.py`

**Interfaces:**
- Consumes: `resposta_xlsx` (Task 4); `COLUNAS_CERTIFICADOS`, `TIPO_CERTIFICADO_POR_EXTENSO` (Task 3)
- Produces: `GET /certificados-emitidos/exportar?cliente=&de=&ate=`

- [ ] **Step 1: Escrever os testes que falham**

Crie `backend/tests/test_certificados_emitidos.py`:

```python
from datetime import date, datetime, timezone
from io import BytesIO

from openpyxl import load_workbook


def _headers(client, email="admin@hs.com", senha="senha123"):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _valores(resposta):
    aba = load_workbook(BytesIO(resposta.content)).active
    return {str(c.value) for linha in aba.iter_rows() for c in linha if c.value is not None}


def _cenario(db_session):
    """Um certificado vindo de OS e um de venda, para o mesmo aparelho."""
    from app.models import (Cliente, Equipamento, EquipamentoCliente, Ordem,
                            OSCertificado, CertificadoVenda)
    c = Cliente(nome="Cliente Cert", cgc="99888777000166")
    e = Equipamento(descricao="Alcotest 6820")
    db_session.add_all([c, e])
    db_session.flush()
    ec = EquipamentoCliente(cliente=c.id, equipamento=e.id, serie="SERIE-CERT")
    db_session.add(ec)
    db_session.flush()
    o = Ordem(cliente=c.id, equipamento_cliente=ec.id, calib_cert="CERT-OS-1",
              data_calibracao=datetime(2026, 3, 10, tzinfo=timezone.utc))
    db_session.add(o)
    db_session.flush()
    db_session.add_all([
        OSCertificado(os=o.id, tipo="C",
                      data_geracao=datetime(2026, 3, 11, tzinfo=timezone.utc)),
        CertificadoVenda(equipamento_cliente=ec.id, html="<p>x</p>",
                         calib_cert="CERT-VENDA-1", data_calibracao=date(2025, 1, 5),
                         data_geracao=datetime(2025, 1, 6, tzinfo=timezone.utc)),
    ])
    db_session.commit()
    return c.id


def test_exige_token(client):
    assert client.get("/certificados-emitidos/exportar").status_code == 401


def test_une_certificados_de_os_e_de_venda(client, usuario_admin, db_session):
    _cenario(db_session)
    valores = _valores(client.get("/certificados-emitidos/exportar", headers=_headers(client)))
    assert "CERT-OS-1" in valores
    assert "CERT-VENDA-1" in valores
    assert "OS" in valores and "Venda" in valores


def test_filtro_de_periodo_corta_pela_data_de_geracao(client, usuario_admin, db_session):
    _cenario(db_session)
    r = client.get("/certificados-emitidos/exportar?de=2026-01-01", headers=_headers(client))
    valores = _valores(r)
    assert "CERT-OS-1" in valores
    assert "CERT-VENDA-1" not in valores


def test_filtro_de_cliente(client, usuario_admin, db_session):
    from app.models import Cliente
    cid = _cenario(db_session)
    outro = Cliente(nome="Outro Cliente")
    db_session.add(outro)
    db_session.commit()
    valores = _valores(client.get(f"/certificados-emitidos/exportar?cliente={outro.id}",
                                  headers=_headers(client)))
    assert "CERT-OS-1" not in valores
    assert "CERT-VENDA-1" not in valores


def test_tipo_sai_por_extenso(client, usuario_admin, db_session):
    _cenario(db_session)
    valores = _valores(client.get("/certificados-emitidos/exportar", headers=_headers(client)))
    assert "Calibracao" in valores
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_certificados_emitidos.py -q
```

Expected: FAIL — 404, o router não existe.

- [ ] **Step 3: Implementar o router**

Crie `backend/app/api/certificados_emitidos.py`:

```python
"""Relatorio de certificados EMITIDOS.

Nao existe tela de lista para isso: os certificados vivem em duas tabelas separadas
(`os_certificados`, gerados a partir de uma OS, e `certificados_venda`, gerados na
venda de um aparelho) e so' aparecem picados no detalhe da OS e do aparelho. Aqui as
duas origens viram um conjunto unico, ordenado por data de geracao.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario
from app.api.exportar_common import resposta_xlsx
from app.core.exportacoes import COLUNAS_CERTIFICADOS, TIPO_CERTIFICADO_POR_EXTENSO
from app.models import (CertificadoVenda, Cliente, Equipamento, EquipamentoCliente,
                        Ordem, OSCertificado, Usuario)
from app.models.database import get_db

router = APIRouter(prefix="/certificados-emitidos", tags=["certificados-emitidos"])


def _inicio(dia: date) -> datetime:
    return datetime.combine(dia, datetime.min.time(), tzinfo=timezone.utc)


def _linhas_de_os(db: Session, cliente, de, ate) -> list[dict]:
    q = (
        db.query(OSCertificado, Ordem, Cliente, EquipamentoCliente, Equipamento)
        .join(Ordem, OSCertificado.os == Ordem.id)
        .join(Cliente, Ordem.cliente == Cliente.id)
        .outerjoin(EquipamentoCliente, Ordem.equipamento_cliente == EquipamentoCliente.id)
        .outerjoin(Equipamento, EquipamentoCliente.equipamento == Equipamento.id)
    )
    if cliente is not None:
        q = q.filter(Ordem.cliente == cliente)
    if de is not None:
        q = q.filter(OSCertificado.data_geracao >= _inicio(de))
    if ate is not None:
        # Fim de faixa inclusivo: `data_geracao` e' DateTime, entao "< dia seguinte"
        # em vez de "<= o dia" — senao um certificado gerado as 14h do ultimo dia
        # ficaria de fora do proprio filtro que o inclui.
        q = q.filter(OSCertificado.data_geracao < _inicio(ate) + timedelta(days=1))
    return [
        {
            "cliente_nome": cli.nome,
            "cliente_cnpj": cli.cgc,
            "equipamento_descricao": equip.descricao if equip else None,
            "serie": ec.serie if ec else None,
            "origem": "OS",
            "os": ordem.id,
            "tipo": TIPO_CERTIFICADO_POR_EXTENSO.get(cert.tipo, cert.tipo),
            "calib_cert": ordem.calib_cert,
            "data_calibracao": ordem.data_calibracao,
            "data_geracao": cert.data_geracao,
            # `os_certificados` nao guarda quem gerou — so' os de venda guardam.
            "usuario_nome": None,
        }
        for cert, ordem, cli, ec, equip in q.all()
    ]


def _linhas_de_venda(db: Session, cliente, de, ate) -> list[dict]:
    q = (
        db.query(CertificadoVenda, EquipamentoCliente, Cliente, Equipamento, Usuario)
        .join(EquipamentoCliente, CertificadoVenda.equipamento_cliente == EquipamentoCliente.id)
        .join(Cliente, EquipamentoCliente.cliente == Cliente.id)
        .outerjoin(Equipamento, EquipamentoCliente.equipamento == Equipamento.id)
        .outerjoin(Usuario, CertificadoVenda.usuario == Usuario.id)
    )
    if cliente is not None:
        q = q.filter(EquipamentoCliente.cliente == cliente)
    if de is not None:
        q = q.filter(CertificadoVenda.data_geracao >= _inicio(de))
    if ate is not None:
        q = q.filter(CertificadoVenda.data_geracao < _inicio(ate) + timedelta(days=1))
    return [
        {
            "cliente_nome": cli.nome,
            "cliente_cnpj": cli.cgc,
            "equipamento_descricao": equip.descricao if equip else None,
            "serie": ec.serie,
            "origem": "Venda",
            "os": None,
            "tipo": TIPO_CERTIFICADO_POR_EXTENSO.get("C", "C"),
            "calib_cert": cert.calib_cert,
            "data_calibracao": cert.data_calibracao,
            "data_geracao": cert.data_geracao,
            "usuario_nome": usr.nome if usr else None,
        }
        for cert, ec, cli, equip, usr in q.all()
    ]


@router.get("/exportar")
def exportar(
    cliente: int | None = None,
    de: date | None = None,
    ate: date | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    linhas = _linhas_de_os(db, cliente, de, ate) + _linhas_de_venda(db, cliente, de, ate)
    # Sem data de geracao vai para o fim, e nao quebra a ordenacao.
    linhas.sort(key=lambda l: (l["data_geracao"] is None, l["data_geracao"]), reverse=False)
    return resposta_xlsx(
        "certificados-emitidos", "Certificados", COLUNAS_CERTIFICADOS, linhas,
        {"Cliente": cliente, "De": de, "Ate": ate,
         "Observacao": "'Gerado por' so' existe nos certificados de venda"},
    )
```

- [ ] **Step 4: Registrar o router em `main.py`**

O projeto não registra routers automaticamente. São duas edições em `backend/app/main.py`.

Primeiro o import: **não é uma linha nova** — `main.py` importa todos os routers num único
`from app.api import ...` na linha 8. Acrescente `certificados_emitidos` ao fim dessa lista,
depois de `certificados_config`.

Depois o registro, junto dos vizinhos (hoje nas linhas 90–91):

```python
app.include_router(certificados_avulsos.router)
app.include_router(certificados_gerais.router)
app.include_router(certificados_emitidos.router)
```

- [ ] **Step 5: Rodar os testes até passarem**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_certificados_emitidos.py -q
```

Expected: PASS, 5 testes.

- [ ] **Step 6: Rodar a suíte inteira**

```bash
cd backend && source .venv/bin/activate && pytest -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/certificados_emitidos.py backend/app/main.py \
        backend/tests/test_certificados_emitidos.py
git commit -m "feat(export): relatorio xlsx de certificados emitidos por os e por venda"
```

---

### Task 6: Download de planilha no frontend

**Files:**
- Modify: `frontend/src/lib/download.ts`
- Test: `frontend/src/lib/download.test.ts`

**Interfaces:**
- Consumes: nada
- Produces: `baixarPlanilha(nomeSugerido: string, obterBlob: () => Promise<Blob>): Promise<void>`

- [ ] **Step 1: Escrever os testes que falham**

Crie `frontend/src/lib/download.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { baixarPlanilha } from './download'

describe('baixarPlanilha', () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:fake')
    URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    delete (window as unknown as { showSaveFilePicker?: unknown }).showSaveFilePicker
    vi.restoreAllMocks()
  })

  it('sem showSaveFilePicker cai no download direto', async () => {
    const blob = new Blob(['x'])
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await baixarPlanilha('lista.xlsx', async () => blob)
    expect(clique).toHaveBeenCalled()
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob)
  })

  it('com showSaveFilePicker grava pela janela nativa', async () => {
    const write = vi.fn(async () => {})
    const close = vi.fn(async () => {})
    const abrir = vi.fn(async () => ({ createWritable: async () => ({ write, close }) }))
    ;(window as unknown as { showSaveFilePicker: unknown }).showSaveFilePicker = abrir

    const blob = new Blob(['x'])
    await baixarPlanilha('lista.xlsx', async () => blob)

    expect(abrir).toHaveBeenCalledWith(
      expect.objectContaining({ suggestedName: 'lista.xlsx' }),
    )
    expect(write).toHaveBeenCalledWith(blob)
    expect(close).toHaveBeenCalled()
  })

  it('cancelar a janela nao lanca e nao busca o arquivo', async () => {
    const abrir = vi.fn(async () => {
      throw new DOMException('cancelado', 'AbortError')
    })
    ;(window as unknown as { showSaveFilePicker: unknown }).showSaveFilePicker = abrir
    const obterBlob = vi.fn(async () => new Blob(['x']))

    await expect(baixarPlanilha('lista.xlsx', obterBlob)).resolves.toBeUndefined()
    expect(obterBlob).not.toHaveBeenCalled()
  })

  it('erro ao buscar o arquivo propaga para o chamador mostrar', async () => {
    const abrir = vi.fn(async () => ({
      createWritable: async () => ({ write: async () => {}, close: async () => {} }),
    }))
    ;(window as unknown as { showSaveFilePicker: unknown }).showSaveFilePicker = abrir

    await expect(
      baixarPlanilha('lista.xlsx', async () => { throw new Error('500') }),
    ).rejects.toThrow('500')
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd frontend && npx vitest run src/lib/download.test.ts
```

Expected: FAIL — `baixarPlanilha` não é exportada.

- [ ] **Step 3: Acrescentar `baixarPlanilha` a `download.ts`**

Não mexa em `baixarPdfComEscolhaDePasta` — ela continua como está. Acrescente ao fim do arquivo:

```ts
const MIME_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/**
 * Salva uma planilha deixando o usuário escolher a pasta, quando o navegador permite.
 *
 * Mesma janela nativa do certificado, com duas diferenças de propósito:
 * - `obterBlob` continua sendo FUNÇÃO: a janela precisa abrir ainda dentro do clique,
 *   e a geração da planilha no servidor pode demorar mais que o crédito do clique.
 * - Não reabre o arquivo numa aba no fim. Isso existe no PDF porque o laboratório
 *   imprime o certificado logo depois; navegador nenhum renderiza xlsx, então aqui
 *   uma aba só mostraria tela em branco ou um segundo download.
 */
export async function baixarPlanilha(
  nomeSugerido: string,
  obterBlob: () => Promise<Blob>,
): Promise<void> {
  const abrir = janelaSalvar()
  if (!abrir) {
    salvarDireto(await obterBlob(), nomeSugerido)
    return
  }

  let handle: HandleGravavel
  try {
    handle = await abrir({
      suggestedName: nomeSugerido,
      types: [{ description: 'Planilha do Excel', accept: { [MIME_XLSX]: ['.xlsx'] } }],
    })
  } catch (e) {
    if (cancelado(e)) return
    salvarDireto(await obterBlob(), nomeSugerido)
    return
  }

  // A partir daqui o arquivo já existe no disco, vazio. Se a busca falhar sobra um
  // arquivo de 0 byte — é o preço de abrir a janela antes de buscar, e o erro sobe
  // para o botão mostrar ao usuário.
  const blob = await obterBlob()
  const escrita = await handle.createWritable()
  await escrita.write(blob)
  await escrita.close()
}
```

- [ ] **Step 4: Rodar os testes até passarem**

```bash
cd frontend && npx vitest run src/lib/download.test.ts
```

Expected: PASS, 4 testes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/download.ts frontend/src/lib/download.test.ts
git commit -m "feat(export): baixarPlanilha reusa a janela nativa de salvar do certificado"
```

---

### Task 7: O componente `BotaoExportar`

**Files:**
- Create: `frontend/src/components/ui/BotaoExportar.tsx`
- Test: `frontend/src/components/ui/BotaoExportar.test.tsx`

**Interfaces:**
- Consumes: `baixarPlanilha` (Task 6); `apiFetch`, `ApiError` de `lib/api`; `Button`, `Spinner`, `IconDownload`
- Produces: `<BotaoExportar caminho={string} params={Record<string, string|number|boolean|undefined|null>} nome={string} />`

- [ ] **Step 1: Escrever os testes que falham**

Crie `frontend/src/components/ui/BotaoExportar.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BotaoExportar } from './BotaoExportar'

const apiFetch = vi.fn()
const baixarPlanilha = vi.fn()

vi.mock('../../lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../lib/api')>()),
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}))

vi.mock('../../lib/download', () => ({
  baixarPlanilha: (nome: string, obterBlob: () => Promise<Blob>) =>
    baixarPlanilha(nome, obterBlob),
}))

describe('BotaoExportar', () => {
  beforeEach(() => {
    apiFetch.mockReset()
    baixarPlanilha.mockReset()
    baixarPlanilha.mockImplementation(async (_nome, obterBlob) => { await obterBlob() })
    apiFetch.mockResolvedValue({ ok: true, blob: async () => new Blob(['x']) })
  })

  it('monta a query com os filtros preenchidos', async () => {
    render(<BotaoExportar caminho="/equipamentos-cliente/exportar"
                          params={{ status: 'vencido', cliente: 7 }} nome="equipamentos" />)
    fireEvent.click(screen.getByRole('button', { name: /exportar/i }))
    await waitFor(() => expect(apiFetch).toHaveBeenCalled())
    const url = apiFetch.mock.calls[0][0] as string
    expect(url).toContain('status=vencido')
    expect(url).toContain('cliente=7')
  })

  it('omite filtro vazio, nulo e indefinido da query', async () => {
    render(<BotaoExportar caminho="/clientes/exportar"
                          params={{ q: '', cliente: null, fase: undefined }} nome="clientes" />)
    fireEvent.click(screen.getByRole('button', { name: /exportar/i }))
    await waitFor(() => expect(apiFetch).toHaveBeenCalled())
    expect(apiFetch.mock.calls[0][0]).toBe('/clientes/exportar')
  })

  it('passa o nome sugerido do arquivo com a data', async () => {
    render(<BotaoExportar caminho="/clientes/exportar" params={{}} nome="clientes" />)
    fireEvent.click(screen.getByRole('button', { name: /exportar/i }))
    await waitFor(() => expect(baixarPlanilha).toHaveBeenCalled())
    expect(baixarPlanilha.mock.calls[0][0]).toMatch(/^clientes-\d{4}-\d{2}-\d{2}\.xlsx$/)
  })

  it('desabilita o botao enquanto gera', async () => {
    let liberar: (v: unknown) => void = () => {}
    apiFetch.mockReturnValue(new Promise((res) => { liberar = res }))
    render(<BotaoExportar caminho="/clientes/exportar" params={{}} nome="clientes" />)
    const botao = screen.getByRole('button', { name: /exportar/i })
    fireEvent.click(botao)
    await waitFor(() => expect(botao).toBeDisabled())
    liberar({ ok: true, blob: async () => new Blob(['x']) })
    await waitFor(() => expect(botao).not.toBeDisabled())
  })

  it('mostra a mensagem da api quando ela recusa', async () => {
    apiFetch.mockResolvedValue({
      ok: false, status: 400,
      json: async () => ({ detail: 'A exportacao ficou grande demais. Refine o filtro.' }),
    })
    render(<BotaoExportar caminho="/clientes/exportar" params={{}} nome="clientes" />)
    fireEvent.click(screen.getByRole('button', { name: /exportar/i }))
    expect(await screen.findByText(/grande demais/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd frontend && npx vitest run src/components/ui/BotaoExportar.test.tsx
```

Expected: FAIL — o módulo não existe.

- [ ] **Step 3: Implementar o componente**

Crie `frontend/src/components/ui/BotaoExportar.tsx`:

```tsx
import { useState } from 'react'
import { Button } from './Button'
import { Spinner } from './Spinner'
import { IconDownload } from './icons'
import { apiFetch } from '../../lib/api'
import { baixarPlanilha } from '../../lib/download'

type Valor = string | number | boolean | null | undefined

interface Props {
  /** Rota da exportação, ex.: `/equipamentos-cliente/exportar` */
  caminho: string
  /** Filtros que estão na tela AGORA. Vazio, nulo e indefinido não entram na query. */
  params: Record<string, Valor>
  /** Base do nome do arquivo; a data entra aqui. */
  nome: string
  desabilitado?: boolean
}

function montarQuery(params: Record<string, Valor>): string {
  const sp = new URLSearchParams()
  for (const [chave, valor] of Object.entries(params)) {
    if (valor === undefined || valor === null || valor === '') continue
    sp.set(chave, String(valor))
  }
  const query = sp.toString()
  return query ? `?${query}` : ''
}

export function BotaoExportar({ caminho, params, nome, desabilitado }: Props) {
  const [gerando, setGerando] = useState(false)
  const [erro, setErro] = useState('')

  async function exportar() {
    setErro('')
    setGerando(true)
    try {
      const hoje = new Date().toISOString().slice(0, 10)
      await baixarPlanilha(`${nome}-${hoje}.xlsx`, async () => {
        const res = await apiFetch(`${caminho}${montarQuery(params)}`)
        if (!res.ok) {
          let detalhe = 'Falha ao gerar a planilha'
          try {
            const corpo = (await res.json()) as { detail?: string }
            if (corpo.detail) detalhe = corpo.detail
          } catch {
            // sem corpo JSON
          }
          throw new Error(detalhe)
        }
        return res.blob()
      })
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Falha ao gerar a planilha')
    } finally {
      setGerando(false)
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant="secondary" onClick={exportar} disabled={gerando || desabilitado}>
        {gerando ? <Spinner className="w-4 h-4" /> : <IconDownload className="w-4 h-4" />}
        {gerando ? 'Gerando planilha…' : 'Exportar Excel'}
      </Button>
      {erro && <span className="text-xs text-danger max-w-xs text-right">{erro}</span>}
    </div>
  )
}
```

- [ ] **Step 4: Rodar os testes até passarem**

```bash
cd frontend && npx vitest run src/components/ui/BotaoExportar.test.tsx
```

Expected: PASS, 5 testes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/BotaoExportar.tsx frontend/src/components/ui/BotaoExportar.test.tsx
git commit -m "feat(export): componente BotaoExportar com estado de geracao e erro"
```

---

### Task 8: Ligar o botão nas três telas

**Files:**
- Modify: `frontend/src/app/clientes/ClientesPage.tsx`
- Modify: `frontend/src/app/frota/FrotaPage.tsx`
- Modify: `frontend/src/app/ordens/OrdensPage.tsx`

**Interfaces:**
- Consumes: `BotaoExportar` (Task 7)
- Produces: nada para tasks seguintes

- [ ] **Step 1: FrotaPage — colocar o botão no cabeçalho**

Em `frontend/src/app/frota/FrotaPage.tsx`, o cabeçalho hoje é:

```tsx
<div className="flex items-center justify-between">
  <h1 className="text-2xl font-extrabold text-slate-100">Equipamentos</h1>
  {podeGerenciarCadastros(user) && (
    <Button
      onClick={() => { if (clienteId) navigate(`/app/equipamentos/novo?cliente=${clienteId}`) }}
      disabled={!clienteId}
      title={clienteId ? undefined : 'Filtre por um cliente para adicionar'}
    >
      Novo aparelho
    </Button>
  )}
</div>
```

Passa a ser — o `<Button>` de "Novo aparelho" fica **exatamente como está**, só ganha um
irmao e um `<div>` em volta:

```tsx
<div className="flex items-center justify-between">
  <h1 className="text-2xl font-extrabold text-slate-100">Equipamentos</h1>
  <div className="flex items-start gap-2">
    <BotaoExportar
      caminho="/equipamentos-cliente/exportar"
      params={{ cliente: clienteId, status: statusFiltro, ativo: ativoFiltro, q: busca }}
      nome="equipamentos"
    />
    {podeGerenciarCadastros(user) && (
      <Button
        onClick={() => { if (clienteId) navigate(`/app/equipamentos/novo?cliente=${clienteId}`) }}
        disabled={!clienteId}
        title={clienteId ? undefined : 'Filtre por um cliente para adicionar'}
      >
        Novo aparelho
      </Button>
    )}
  </div>
</div>
```

`ativoFiltro` já é a string `''`/`'true'`/`'false'` do `<Select>`; `''` é descartado pelo `montarQuery` e `'true'`/`'false'` chegam como o booleano que o FastAPI espera. Import:

```tsx
import { BotaoExportar } from '../../components/ui/BotaoExportar'
```

- [ ] **Step 2: ClientesPage — mesmo padrão**

Adicione ao cabeçalho de `ClientesPage.tsx`, ao lado do botão de novo cliente:

```tsx
<BotaoExportar caminho="/clientes/exportar" params={{ q: busca }} nome="clientes" />
```

Use o estado `busca` (o termo já submetido), **não** `termo` (o que está sendo digitado) — a planilha tem que bater com a lista que está na tela.

- [ ] **Step 3: OrdensPage — mesmo padrão, com a faixa de datas**

Adicione ao cabeçalho de `OrdensPage.tsx`:

```tsx
<BotaoExportar
  caminho="/ordens/exportar"
  params={{
    fase: fase ? Number(fase) : undefined,
    cliente: clienteId,
    tipo: tipo || undefined,
    q: busca || undefined,
    chegada_de: faixa.de,
    chegada_ate: faixa.ate,
  }}
  nome="ordens"
/>
```

Os nomes das chaves são os do **backend** (`chegada_de`/`chegada_ate`), não os do cliente de API do frontend (`chegadaDe`/`chegadaAte`) — o `BotaoExportar` monta a URL direto, sem passar pelo `ordensApi.listar`.

- [ ] **Step 4: Verificação completa do frontend**

```bash
cd frontend && npm run lint && npx tsc -b --noEmit && npm run build
```

Expected: sem erros. Depois:

```bash
cd frontend && npm test
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/clientes/ClientesPage.tsx frontend/src/app/frota/FrotaPage.tsx \
        frontend/src/app/ordens/OrdensPage.tsx
git commit -m "feat(export): botao de exportar excel nas listas de clientes, equipamentos e ordens"
```

---

### Task 9: Aba "Emitidos" na página de Certificados

**Files:**
- Create: `frontend/src/app/certificados/EmitidosTab.tsx`
- Modify: `frontend/src/app/certificados/CertificadosPage.tsx`
- Test: `frontend/src/app/certificados/EmitidosTab.test.tsx`

**Interfaces:**
- Consumes: `BotaoExportar` (Task 7); `Input`, `Select` de `components/ui`
- Produces: aba nova na página de Certificados

- [ ] **Step 1: Escrever o teste que falha**

Crie `frontend/src/app/certificados/EmitidosTab.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EmitidosTab } from './EmitidosTab'

const props = vi.fn()

vi.mock('../../components/ui/BotaoExportar', () => ({
  BotaoExportar: (p: unknown) => {
    props(p)
    return <button>Exportar Excel</button>
  },
}))

describe('EmitidosTab', () => {
  it('leva o periodo digitado para a exportacao', () => {
    props.mockReset()
    render(<EmitidosTab />)
    fireEvent.change(screen.getByLabelText(/de/i), { target: { value: '2026-01-01' } })
    fireEvent.change(screen.getByLabelText(/at[eé]/i), { target: { value: '2026-06-30' } })
    const ultima = props.mock.calls.at(-1)![0] as { params: Record<string, unknown> }
    expect(ultima.params.de).toBe('2026-01-01')
    expect(ultima.params.ate).toBe('2026-06-30')
  })

  it('aponta para a rota de certificados emitidos', () => {
    props.mockReset()
    render(<EmitidosTab />)
    const primeira = props.mock.calls[0][0] as { caminho: string }
    expect(primeira.caminho).toBe('/certificados-emitidos/exportar')
  })

  it('avisa que a planilha sai sem previa na tela', () => {
    render(<EmitidosTab />)
    expect(screen.getByText(/planilha/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd frontend && npx vitest run src/app/certificados/EmitidosTab.test.tsx
```

Expected: FAIL — o módulo não existe.

- [ ] **Step 3: Implementar a aba**

Crie `frontend/src/app/certificados/EmitidosTab.tsx`:

```tsx
import { useState } from 'react'
import { Input } from '../../components/ui/Input'
import { BotaoExportar } from '../../components/ui/BotaoExportar'

/** Relatório de certificados emitidos.
 *
 * Só exportação, sem tabela: os certificados emitidos não têm tela de lista no
 * sistema — vivem em duas tabelas separadas e aparecem picados no detalhe da OS e
 * do aparelho. Aqui o usuário escolhe o recorte e leva a planilha.
 */
export function EmitidosTab() {
  const [de, setDe] = useState('')
  const [ate, setAte] = useState('')

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400 max-w-2xl">
        Gera uma planilha com todos os certificados já emitidos no período — tanto os
        que saíram de uma OS quanto os de venda. Sem período, traz todos.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-44">
          <Input id="de" label="De" type="date" value={de} onChange={(e) => setDe(e.target.value)} />
        </div>
        <div className="w-44">
          <Input id="ate" label="Até" type="date" value={ate} onChange={(e) => setAte(e.target.value)} />
        </div>
        <BotaoExportar
          caminho="/certificados-emitidos/exportar"
          params={{ de, ate }}
          nome="certificados-emitidos"
        />
      </div>

      <p className="text-xs text-slate-500 max-w-2xl">
        A coluna "Gerado por" só existe nos certificados de venda — o sistema não
        registra o autor dos certificados gerados a partir de uma OS.
      </p>
    </div>
  )
}
```

Confira a assinatura real de `components/ui/Input.tsx` antes de escrever — se a prop de rótulo não for `label`, ajuste a chamada **e** o `getByLabelText` do teste.

- [ ] **Step 4: Registrar a aba em `CertificadosPage.tsx`**

Três mudanças pontuais no arquivo. Primeiro o import, junto dos outros:

```tsx
import { EmitidosTab } from './EmitidosTab'
```

Depois o array de abas — `Aba` é derivado dele (`type Aba = (typeof ABAS)[number]`), então
acrescentar aqui já atualiza o tipo. "Emitidos" entra **antes** de "Configurações", que é
a aba de administração e fica por último:

```tsx
const ABAS = ['Modelos', 'Imagens', 'Em branco', 'Gerais', 'Emitidos', 'Configurações'] as const
```

E o encadeamento de renderização:

```tsx
{aba === 'Modelos' ? <ModelosTab />
  : aba === 'Imagens' ? <ImagensTab />
  : aba === 'Em branco' ? <AvulsosTab />
  : aba === 'Gerais' ? <CertificadosGeraisTab />
  : aba === 'Emitidos' ? <EmitidosTab />
  : <ConfiguracoesTab />}
```

O subtítulo da página lista o que há nela e ficou desatualizado — atualize junto:

```tsx
<p className="text-sm text-slate-500 mt-0.5">Modelos de certificado por aparelho, biblioteca de imagens, certificados em branco e a relação dos certificados já emitidos.</p>
```

- [ ] **Step 5: Rodar os testes até passarem**

```bash
cd frontend && npx vitest run src/app/certificados/
```

Expected: PASS.

- [ ] **Step 6: Verificação completa do frontend**

```bash
cd frontend && npm run lint && npx tsc -b --noEmit && npm run build && npm test
```

Expected: sem erros, todos os testes passando.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/certificados/EmitidosTab.tsx \
        frontend/src/app/certificados/EmitidosTab.test.tsx \
        frontend/src/app/certificados/CertificadosPage.tsx
git commit -m "feat(export): aba de certificados emitidos com exportacao por periodo"
```

---

### Task 10: Verificação ponta a ponta e changelog

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`
- Modify: `CLAUDE.md` (seção de comandos do backend, se necessário)

- [ ] **Step 1: Rodar tudo**

```bash
cd backend && source .venv/bin/activate && pytest -q
cd ../frontend && npm run lint && npx tsc -b --noEmit && npm run build && npm test
```

Expected: tudo passando. **Se algo falhar, conserte antes de seguir — não marque o passo.**

- [ ] **Step 2: Conferir na mão, com a API de pé**

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload
# noutro terminal
cd frontend && npm run dev
```

Abra `/app/equipamentos`, filtre por Status = Vencido, clique em "Exportar Excel" e **abra o arquivo**. Confira:
- só aparecem aparelhos vencidos
- o cabeçalho está congelado e com autofiltro
- as datas estão como data (dá para ordenar por elas)
- o rodapé registra "Status: vencido" e a hora

Repita em `/app/clientes`, `/app/ordens` e na aba Emitidos de `/app/certificados`.

- [ ] **Step 3: Atualizar o changelog**

Em `frontend/src/app/changelog/data.ts`, acrescente a entrada como **primeiro elemento** do
array `CHANGELOG` (a primeira é a que vira a versão atual na sidebar). A anterior é `1.38.0`,
então esta é `1.39.0`. O formato é um objeto `VersaoChangelog`, com `data` em DD/MM/AAAA e
cada item tipado como `'novidade' | 'melhoria' | 'correcao'` — texto voltado ao usuário,
não ao desenvolvedor:

```ts
  {
    versao: '1.39.0',
    data: '19/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'As listas de Clientes, Equipamentos e Ordens ganharam o botão “Exportar Excel”. A planilha sai com todas as linhas que batem com os filtros da tela — não só as 25 que aparecem — e com mais colunas do que a lista mostra: no aparelho, por exemplo, vêm CNPJ do cliente, marca, patrimônio, data da compra e número do certificado.' },
      { tipo: 'novidade', texto: 'Nova aba “Emitidos” em Certificados: escolhe o período e baixa a relação de todos os certificados já gerados, tanto os que saíram de uma OS quanto os de venda, no mesmo arquivo.' },
      { tipo: 'melhoria', texto: 'As planilhas já vêm prontas para trabalhar: cabeçalho fixo ao rolar, filtro em cada coluna, datas e valores como data e número de verdade (dá para ordenar e somar) e, no rodapé, o registro de quais filtros geraram o arquivo.' },
    ],
  },
```

Ajuste a data se o dia da entrega for outro.

- [ ] **Step 4: Avisar no CLAUDE.md que o deploy precisa de rebuild**

`openpyxl` é a primeira dependência nova do backend em muito tempo, e quem for subir a
release vai supor que basta o pull de sempre. Acrescente à seção **Docker** do `CLAUDE.md`
da raiz, logo depois da linha que explica o `docker compose up -d`:

```markdown
> ⚠️ **A exportação para Excel usa `openpyxl`.** Ele entrou no `requirements.txt` em
> ago/2026 — subir essa versão exige **reconstruir a imagem** (`docker compose build`),
> não só `pull` + restart. Sem isso a API sobe e só quebra quando alguém clica em
> "Exportar Excel".
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/changelog/data.ts CLAUDE.md
git commit -m "docs(changelog): v1.39.0 — exportacao para excel nas listas"
```

- [ ] **Step 6: Avisar o Erick**

Relate o que foi entregue, o que você conferiu na mão, e lembre que:
- **não houve push** — os commits estão só locais
- o deploy precisa de **rebuild da imagem Docker** por causa do `openpyxl`
