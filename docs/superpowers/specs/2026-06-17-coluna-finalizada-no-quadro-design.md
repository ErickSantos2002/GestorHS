# Spec — Coluna "Finalizada" no Quadro de Ordens

**Data:** 2026-06-17
**Status:** Aprovado (aguardando revisão final do spec)

## Problema

No módulo de Ordens de Serviço, a vista **Quadro** (kanban) mostra apenas as 4 fases
ativas (Recebido, Laboratório, Pós-Vendas, Preparando Retorno). Não há como
visualizar, no quadro, as OS já **finalizadas** — a fase Finalizada (id 8) some do
kanban. O usuário quer ver as finalizadas ali também, como visão rápida.

## Restrição de escala (o que guia o design)

A fase Finalizada concentra **todo o histórico** (as OS antigas foram migradas para
Finalizada), podendo ter **milhares** de registros — muito mais que as colunas ativas
(a maior hoje, Pós-Vendas, tem ~290). Hoje o endpoint `/ordens/quadro` carrega
**todos** os cards de cada coluna via `.all()`, sem limite. Adicionar Finalizada sem
teto travaria o quadro.

## Objetivo

Adicionar a coluna **Finalizada** ao Quadro como **visão rápida**, limitada às mais
recentes, com o total real no cabeçalho e um caminho para a lista completa.

## Decisões (aprovadas)

- Apenas **Finalizada** (id 8). **Não** incluir Cancelada.
- A coluna Finalizada mostra no máximo **300** cards (os mais recentes, id desc).
- O cabeçalho da coluna mostra o **total real** da fase (ex.: "Finalizada 12.480"),
  mesmo exibindo só 300 cards.
- Rodapé **"Ver todas →"** na coluna Finalizada leva à vista **Lista já filtrada em
  Finalizada** (a Lista mostra tudo, paginado). Quadro = rápido; Lista = completo.
- As colunas ativas (4–7) **não mudam** — continuam carregando todos os seus cards.

## Escopo

**Inclui:** coluna Finalizada no Quadro (teto 300 + total real), campo `total` no
payload do quadro, link "Ver todas" para a Lista filtrada.

**Não inclui (YAGNI):** coluna Cancelada; paginação/scroll infinito dentro do quadro;
mudar o comportamento das colunas ativas; filtros novos.

## Design

### Backend — `GET /ordens/quadro` ([backend/app/api/ordens.py](../../../backend/app/api/ordens.py))

- Passa a montar colunas para `ATIVAS + [FASE_FINALIZADA]` (4,5,6,7,8), buscando as
  Fases correspondentes (descrição/cor) para todas elas.
- Novo schema: `QuadroColuna` ganha o campo **`total: int`**.
- Para cada coluna:
  - `total` = contagem real da fase (`query.count()`), respeitando o filtro `cliente`.
  - `ordens` = cards. Para as fases ativas, **todos** (como hoje). Para Finalizada,
    apenas os **300 mais recentes** (`order_by(id desc).limit(LIMITE_FINALIZADAS_QUADRO)`).
- Constante no módulo: `LIMITE_FINALIZADAS_QUADRO = 300` (testável/monkeypatchável).

Esboço:

```python
LIMITE_FINALIZADAS_QUADRO = 300

@router.get("/quadro", response_model=list[QuadroColuna])
def quadro(cliente: int | None = None, db: Session = Depends(get_db),
           _: Usuario = Depends(get_current_usuario)):
    fases_ids = list(wf.ATIVAS) + [wf.FASE_FINALIZADA]
    fases = {f.id: f for f in db.query(Fase).filter(Fase.id.in_(fases_ids)).all()}
    colunas: list[QuadroColuna] = []
    for fid in fases_ids:
        query = db.query(Ordem).filter(Ordem.fase == fid)
        if cliente is not None:
            query = query.filter(Ordem.cliente == cliente)
        total = query.count()
        q = query.order_by(Ordem.id.desc())
        if fid == wf.FASE_FINALIZADA:
            q = q.limit(LIMITE_FINALIZADAS_QUADRO)
        ordens = q.all()
        f = fases.get(fid)
        colunas.append(QuadroColuna(
            fase=fid,
            descricao=f.descricao if f else "",
            cor=f.cor if f else "000000",
            total=total,
            ordens=[OrdemListOut.model_validate(o) for o in ordens],
        ))
    return colunas
```

### Schema — [backend/app/schemas/ordens.py](../../../backend/app/schemas/ordens.py)

```python
class QuadroColuna(BaseModel):
    fase: int
    descricao: str
    cor: str
    total: int
    ordens: list[OrdemListOut]
```

### Frontend — [frontend/src/app/ordens/OrdensPage.tsx](../../../frontend/src/app/ordens/OrdensPage.tsx) e api.ts

- `QuadroColuna` (TS, em `api.ts`) ganha `total: number`.
- **Quadro**: o número no cabeçalho passa a usar **`col.total`** (não `ordens.length`).
- Na coluna onde `col.total > col.ordens.length` (caso da Finalizada capada), mostrar
  um rodapé **"Ver todas (N) →"** que aciona um callback `onVerTodas(col.fase)`.
- **OrdensPage**: levanta o estado para a navegação Quadro→Lista:
  - novo estado `faseInicialLista: string` (default `''`).
  - passa `onVerTodas={(fase) => { setFaseInicialLista(String(fase)); setVista('lista') }}`
    para o `Quadro`.
  - passa `faseInicial={faseInicialLista}` para a `Lista`.
  - o **toggle normal de vista** (botões Quadro/Lista) que vai para a Lista **reseta**
    `faseInicialLista` para `''` — assim só o "Ver todas" abre a Lista pré-filtrada; a
    troca manual de vista entra na Lista sem filtro (comportamento de hoje).
- **Lista**: aceita prop opcional `faseInicial?: string` e inicializa
  `const [fase, setFase] = useState(faseInicial ?? '')`. Ao trocar de vista a Lista
  remonta, então o filtro já entra aplicado.

A ordem das colunas no quadro fica: Recebido, Laboratório, Pós-Vendas, Preparando
Retorno, **Finalizada** (por último, refletindo o fim do ciclo).

## Testes

- **Backend** ([test_ordens_leitura.py](../../../backend/tests/test_ordens_leitura.py)):
  - O quadro agora tem 5 colunas, na ordem `[4,5,6,7,8]`, e a coluna 8 é "Finalizada".
  - `total` reflete a contagem real por fase (inclusive quando capada).
  - Cap respeitado: com `LIMITE_FINALIZADAS_QUADRO` reduzido (monkeypatch p/ ex. 2) e 3
    OS finalizadas, a coluna 8 traz `len(ordens) == 2` e `total == 3`; as ativas trazem
    todos (sem cap).
  - Filtro por `cliente` continua aplicado em todas as colunas (incluindo total).
- **Frontend**: teste de que o cabeçalho usa `total` e que o "Ver todas" aparece só
  quando `total > ordens.length` (via componente com `ordensApi.quadro` mockado, ou
  helper isolado — definir no plano conforme o padrão de testes da página).

## Changelog

Ao concluir, adicionar entrada em
[frontend/src/app/changelog/data.ts](../../../frontend/src/app/changelog/data.ts)
(nova versão) descrevendo a coluna Finalizada no quadro.
