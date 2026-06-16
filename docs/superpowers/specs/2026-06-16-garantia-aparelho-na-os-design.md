# Spec — Garantia do aparelho na tela da OS

**Data:** 2026-06-16
**Status:** Aprovado (aguardando revisão final do spec)

## Problema

Ao abrir uma Ordem de Serviço, a equipe não consegue ver de forma rápida se o
aparelho está **em garantia**. Hoje essa informação não aparece em lugar nenhum
da tela da OS, e parte dela (manutenção) nem sequer está calculada no sistema.

Existem **três tipos de garantia**, cada uma com duração de **1 ano**:

- **Garantia de calibração** — 1 ano desde a última calibração.
- **Garantia de manutenção** — 1 ano desde a última manutenção.
- **Garantia de compra** — 1 ano desde a data de compra do aparelho.

## Objetivo

Mostrar, na tela de detalhe da OS (`/app/ordens/:id`), de forma fácil de
visualizar, o status das três garantias do aparelho — com um selo-resumo no topo
e um painel detalhado.

## Escopo

**Inclui:** cálculo das 3 garantias e exibição apenas na tela de detalhe da OS.

**Não inclui (YAGNI):** exibir garantia na frota, no portal do cliente ou em
listas; aviso âmbar de "vencendo"; qualquer migração de banco; campo dedicado de
última manutenção.

## Origem das datas

| Garantia | Data base | Origem |
|----------|-----------|--------|
| Calibração | última calibração | `equipamento_cliente.ult_calibragem` |
| Compra | data de compra | `equipamento_cliente.datacompra` |
| Manutenção | última manutenção | OS finalizada mais recente do aparelho com `tipo_servico IN ('M','A')`, usando `data_calibracao` da OS |

Notas:
- `tipo_servico`: `C` = Calibração, `M` = Manutenção, `A` = **Ambas**. Uma OS `A`
  conta como evento de manutenção (e também de calibração). O critério `("M","A")`
  já é usado em `backend/app/core/certificado_gerar.py:146`.
- "Última manutenção" considera apenas OS **finalizada** (fase `FASE_FINALIZADA = 8`,
  ver `backend/app/core/os_workflow.py`), excluindo canceladas. A OS atual em
  andamento (fases 4–7) naturalmente não entra.
- A calibração usa `ult_calibragem` (valor já espelhado no aparelho ao concluir o
  laboratório), não uma derivação de OS — é a fonte autoritativa existente.

## Definição de "em garantia"

- `vence_em = data_base + 1 ano` (mesma data no ano seguinte; ano-calendário).
  Caso de borda: `29/fev` → `28/fev` do ano seguinte.
- Está **em garantia** enquanto `hoje <= vence_em` (fim **inclusive**).
- Sem `data_base` → estado `sem_registro`.

Estados possíveis por garantia: `em_garantia` | `fora` | `sem_registro`.
Binário (dentro/fora); **sem** estado intermediário de "vencendo".

## Arquitetura

Abordagem escolhida: **calcular no backend e embutir no detalhe da OS** (sem
endpoint novo, sem requisição extra; segue o padrão de como `status_calibracao`
já é exposto).

### 1. Lógica pura — `backend/app/core/garantia.py` (novo)

Módulo sem I/O, no espírito de `core/calibracao.py`.

```python
DURACAO_GARANTIA_ANOS = 1

def status_garantia(base: date | None, hoje: date) -> dict:
    """Status de uma garantia a partir da data base.
    sem base -> {"estado": "sem_registro", "data_base": None, "vence_em": None}
    com base -> {"estado": "em_garantia"|"fora", "data_base": base, "vence_em": <base+1ano>}
    em garantia enquanto hoje <= vence_em (inclusive).
    """

def garantias(datacompra, ult_calibragem, ult_manutencao, hoje) -> dict:
    """Monta os 3 status + resumo.
    {"em_garantia": <qualquer uma em_garantia>,
     "calibracao": {...}, "manutencao": {...}, "compra": {...}}
    """
```

O cálculo de `base + 1 ano` usa apenas a **stdlib** (`python-dateutil` não é
dependência do projeto): `base.replace(year=base.year + 1)`, com fallback para
`28/fev` quando `base` for `29/fev` (ano de destino não bissexto). Esse helper
fica no próprio `core/garantia.py`.

### 2. Backend — busca da manutenção e endpoint

- A busca da última manutenção fica na **camada de API** (tem `db`), não no
  `core/` (que permanece puro): query em `Ordem` filtrando o aparelho,
  `tipo_servico IN ('M','A')`, fase `= FASE_FINALIZADA`, ordenado por
  `data_calibracao` desc, pegando o primeiro `data_calibracao` não nulo.
- `GET /ordens/{id}` (`backend/app/api/ordens.py`) monta o objeto e chama
  `garantias(...)`, lendo `datacompra` e `ult_calibragem` de `equipamento_rel`.
- Se a OS não tiver aparelho vinculado (`equipamento_rel is None`) →
  `garantias: null`.

### 3. Schemas — `backend/app/schemas/ordens.py`

```python
class GarantiaItem(BaseModel):
    estado: Literal["em_garantia", "fora", "sem_registro"]
    data_base: date | None = None
    vence_em: date | None = None

class GarantiasOut(BaseModel):
    em_garantia: bool
    calibracao: GarantiaItem
    manutencao: GarantiaItem
    compra: GarantiaItem
```

`OrdemOut` ganha `garantias: GarantiasOut | None = None`.

### 4. Frontend — `frontend/src/app/ordens/OrdemDetailPage.tsx`

- **Selo-resumo** perto do título da OS: `Badge` tone `primary` "EM GARANTIA" se
  `garantias.em_garantia`, senão tone `neutral` "SEM GARANTIA". Não renderiza nada
  se `garantias` for `null`.
- **Painel "Garantia"** (nova seção, próximo de "Datas"): três linhas
  (Calibração, Manutenção, Compra), cada uma com um `Badge`.
- Mapa `estado → {label, tone}`:
  - `em_garantia` → tone `primary`, label `"Em garantia até DD/MM/AAAA"` (data = `vence_em`)
  - `fora` → tone `neutral`, label `"Fora da garantia"`
  - `sem_registro` → tone `neutral`, label `"Sem registro"`
- Tipo TS correspondente a `GarantiasOut` no client/tipos da OS.

Exemplo visual:

```
OS #10410   [ EM GARANTIA ]
...
Garantia
  Calibração   [ Em garantia ate 12/03/2027 ]
  Manutenção   [ Fora da garantia ]
  Compra       [ Em garantia ate 05/08/2026 ]
```

## Testes

- **Backend** `tests/test_garantia.py`: função pura — `em_garantia`, `fora`,
  `sem_registro`; fronteira exata (`hoje == vence_em` ainda em garantia,
  `hoje == vence_em + 1 dia` fora); ano bissexto (`29/fev`).
- **Backend** (API): `GET /ordens/{id}` retorna `garantias` derivando a manutenção
  da última OS `M`/`A` finalizada; retorna `null` quando não há aparelho.
- **Frontend**: teste do mapa `estado→badge` e da renderização do painel + selo.

## Changelog

Ao concluir, adicionar entrada em `frontend/src/app/changelog/data.ts` (nova
versão) descrevendo a visualização de garantia na OS.
