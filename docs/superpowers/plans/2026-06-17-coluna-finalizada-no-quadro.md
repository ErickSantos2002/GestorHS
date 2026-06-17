# Coluna "Finalizada" no Quadro — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar a coluna "Finalizada" (capada em 300, com total real) ao Quadro de Ordens, com um link "Ver todas" para a Lista filtrada.

**Architecture:** O endpoint `/ordens/quadro` passa a incluir a fase Finalizada (8) limitada a 300 cards recentes e ganha um campo `total` por coluna (contagem real). O frontend mostra o `total` no cabeçalho e um rodapé "Ver todas →" nas colunas capadas, que troca para a vista Lista pré-filtrada. Colunas ativas não mudam.

**Tech Stack:** Backend FastAPI + SQLAlchemy 2 + Pydantic v2 (pytest em Docker). Frontend React 19 + TS + Vitest. Commits: PT-BR sem acentos, uma linha, sem co-autor; tipos feat/fix/docs/refactor.

**Spec:** [docs/superpowers/specs/2026-06-17-coluna-finalizada-no-quadro-design.md](../specs/2026-06-17-coluna-finalizada-no-quadro-design.md)

## Ambiente de teste
- Backend (sem venv local): `docker compose exec -T backend pytest <args>` a partir da raiz do repo.
- Frontend: a partir de `frontend/` — `npx vitest run`, `npx tsc -b --noEmit`, `npm run lint`, `npm run build`.

---

## File Structure
- **Modify** `backend/app/schemas/ordens.py` — campo `total: int` em `QuadroColuna`.
- **Modify** `backend/app/api/ordens.py` — constante `LIMITE_FINALIZADAS_QUADRO`; incluir fase 8 e `total` no `quadro`.
- **Modify** `backend/tests/test_ordens_leitura.py` — atualizar teste do quadro + novos testes (total, cap, filtro cliente).
- **Modify** `frontend/src/app/ordens/api.ts` — `total: number` em `QuadroColuna`.
- **Modify** `frontend/src/app/ordens/OrdensPage.tsx` — cabeçalho usa `total`; rodapé "Ver todas"; wiring Quadro→Lista com `faseInicial`.
- **Modify** `frontend/src/app/changelog/data.ts` — entrada de nova versão.

---

## Task 1: Schema `total` em `QuadroColuna`

**Files:**
- Modify: `backend/app/schemas/ordens.py` (classe `QuadroColuna`, ~linhas 29-33)

- [ ] **Step 1: Adicionar o campo**

A classe atual é:
```python
class QuadroColuna(BaseModel):
    fase: int
    descricao: str
    cor: str
    ordens: list[OrdemListOut]
```
Adicionar `total: int` logo após `cor`:
```python
class QuadroColuna(BaseModel):
    fase: int
    descricao: str
    cor: str
    total: int
    ordens: list[OrdemListOut]
```

- [ ] **Step 2: Verificar import**

Run: `docker compose exec -T backend python -c "from app.schemas.ordens import QuadroColuna; print('ok')"`
Expected: `ok`.

(Sem commit isolado — este schema é consumido pelo endpoint na Task 2; commit junto ao final da Task 2 para não deixar a suíte vermelha entre passos. Prossiga direto para a Task 2.)

---

## Task 2: Endpoint `quadro` inclui Finalizada (capada) + `total`

**Files:**
- Modify: `backend/app/api/ordens.py` (função `quadro`, ~linhas 51-67; adicionar constante perto do topo do módulo)
- Test: `backend/tests/test_ordens_leitura.py`

- [ ] **Step 1: Atualizar o teste existente que vai mudar de comportamento**

O teste atual (linhas 51-59) assume só 4 colunas. Substituí-lo por esta versão que espera a coluna Finalizada e checa `total`:

```python
def test_quadro_inclui_finalizada_agrupado(client, usuario_admin, fases_seed, os_base, db_session):
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 6)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)
    h = _headers(client, "admin", "senha123")
    colunas = client.get("/ordens/quadro", headers=h).json()
    assert [c["fase"] for c in colunas] == [4, 5, 6, 7, 8]
    por_fase = {c["fase"]: len(c["ordens"]) for c in colunas}
    assert por_fase == {4: 1, 5: 0, 6: 1, 7: 0, 8: 1}
    por_total = {c["fase"]: c["total"] for c in colunas}
    assert por_total == {4: 1, 5: 0, 6: 1, 7: 0, 8: 1}
    col8 = next(c for c in colunas if c["fase"] == 8)
    assert col8["descricao"] == "Finalizada"
```

- [ ] **Step 2: Adicionar os novos testes (cap + filtro cliente) ao fim do arquivo**

```python
def test_quadro_finalizada_capada_com_total_real(
    client, usuario_admin, fases_seed, os_base, db_session, monkeypatch
):
    import app.api.ordens as ordens_api
    monkeypatch.setattr(ordens_api, "LIMITE_FINALIZADAS_QUADRO", 2)
    for _ in range(3):
        _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 5)  # ativa
    h = _headers(client, "admin", "senha123")
    colunas = client.get("/ordens/quadro", headers=h).json()
    col8 = next(c for c in colunas if c["fase"] == 8)
    assert col8["total"] == 3
    assert len(col8["ordens"]) == 2  # capada
    col5 = next(c for c in colunas if c["fase"] == 5)
    assert col5["total"] == 1
    assert len(col5["ordens"]) == 1  # ativas nao capam


def test_quadro_finalizada_respeita_filtro_cliente(
    client, usuario_admin, fases_seed, os_base, db_session
):
    from app.models import Cliente
    outro = Cliente(nome="Outro Cliente")
    db_session.add(outro); db_session.commit(); db_session.refresh(outro)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)
    _ordem(db_session, outro.id, None, 8)
    h = _headers(client, "admin", "senha123")
    colunas = client.get(
        f"/ordens/quadro?cliente={os_base['cliente']}", headers=h
    ).json()
    col8 = next(c for c in colunas if c["fase"] == 8)
    assert col8["total"] == 1
    assert len(col8["ordens"]) == 1
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

Run: `docker compose exec -T backend pytest tests/test_ordens_leitura.py -q`
Expected: FAIL — a coluna 8 ainda não existe / `total` ausente (KeyError / AssertionError).

- [ ] **Step 4: Adicionar a constante no módulo**

Em `backend/app/api/ordens.py`, perto do topo (após os imports, antes do `router`/primeira rota), adicionar:
```python
LIMITE_FINALIZADAS_QUADRO = 300
```

- [ ] **Step 5: Reescrever a função `quadro`**

Substituir a função atual (linhas ~51-67) por:
```python
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
        ordenadas = query.order_by(Ordem.id.desc())
        if fid == wf.FASE_FINALIZADA:
            ordenadas = ordenadas.limit(LIMITE_FINALIZADAS_QUADRO)
        ordens = ordenadas.all()
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
Observações:
- `wf.FASE_FINALIZADA` já existe em `app/core/os_workflow.py` (valor 8); `wf` já é o alias importado usado por `wf.ATIVAS`. Confirme o nome do import no topo do arquivo antes de editar.
- Mantenha o `return colunas` (o trecho original termina com `return colunas` após o loop).

- [ ] **Step 6: Rodar os testes do arquivo e confirmar PASS**

Run: `docker compose exec -T backend pytest tests/test_ordens_leitura.py -q`
Expected: PASS (incluindo os 3 testes de quadro).

- [ ] **Step 7: Rodar a suíte de backend inteira (nada quebrou)**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit (schema + endpoint + testes juntos)**

```bash
cd /home/ericks/github/GestorHS
git add backend/app/schemas/ordens.py backend/app/api/ordens.py backend/tests/test_ordens_leitura.py
git commit -m "feat(ordens): quadro inclui coluna finalizada capada com total"
```

---

## Task 3: Tipo `total` no frontend

**Files:**
- Modify: `frontend/src/app/ordens/api.ts` (interface `QuadroColuna`, ~linhas 64-69)

- [ ] **Step 1: Adicionar o campo**

A interface atual:
```ts
export interface QuadroColuna {
  fase: number
  descricao: string
  cor: string
  ordens: OrdemListItem[]
}
```
Adicionar `total: number` após `cor`:
```ts
export interface QuadroColuna {
  fase: number
  descricao: string
  cor: string
  total: number
  ordens: OrdemListItem[]
}
```

- [ ] **Step 2: Type-check**

Run: `cd /home/ericks/github/GestorHS/frontend && npx tsc -b --noEmit`
Expected: erro(s) apontando onde `total` é necessário OU sucesso. (O uso de `total` no cabeçalho vem na Task 4 — se o tsc passar aqui, ok; não comitar isoladamente, seguir para a Task 4 e comitar junto.)

(Prossiga para a Task 4; commit conjunto no fim da Task 4.)

---

## Task 4: Quadro mostra `total` + rodapé "Ver todas" + wiring para a Lista

**Files:**
- Modify: `frontend/src/app/ordens/OrdensPage.tsx`

Contexto do arquivo (confirme lendo): `OrdensPage` (linhas 23-64) tem `const [vista, setVista] = useState<Vista>('quadro')` e renderiza `<Quadro clienteId onAbrir>` ou `<Lista clienteId onAbrir>` (linhas 57-61). `Quadro` (linha 66) busca via `ordensApi.quadro` e renderiza colunas; o cabeçalho mostra `{col.ordens.length}` (linha 102). `Lista` (linha 134) tem `const [fase, setFase] = useState('')` (linha 135). O toggle de vista está nas linhas 35-46.

- [ ] **Step 1: `OrdensPage` — estado e wiring**

Adicionar o estado da fase inicial da Lista, logo após `const [vista, setVista] = useState<Vista>('quadro')` (linha 28):
```tsx
  const [faseInicialLista, setFaseInicialLista] = useState('')
```

No botão do toggle (linhas 36-46), trocar o `onClick` para resetar o filtro ao entrar na Lista manualmente:
```tsx
              onClick={() => { if (v === 'lista') setFaseInicialLista(''); setVista(v) }}
```

Na renderização condicional (linhas 57-61), passar os novos props:
```tsx
      {vista === 'quadro' ? (
        <Quadro
          clienteId={clienteId}
          onAbrir={(id) => navigate(`/app/ordens/${id}`)}
          onVerTodas={(fase) => { setFaseInicialLista(String(fase)); setVista('lista') }}
        />
      ) : (
        <Lista clienteId={clienteId} faseInicial={faseInicialLista} onAbrir={(id) => navigate(`/app/ordens/${id}`)} />
      )}
```

- [ ] **Step 2: `Quadro` — assinatura, cabeçalho com `total`, rodapé "Ver todas"**

Atualizar a assinatura do componente `Quadro` (linha 66):
```tsx
function Quadro({ clienteId, onAbrir, onVerTodas }: { clienteId?: number; onAbrir: (id: number) => void; onVerTodas: (fase: number) => void }) {
```

No cabeçalho da coluna, trocar `{col.ordens.length}` (linha 102) por `{col.total}`:
```tsx
            <span className="text-xs text-slate-500">{col.total}</span>
```

Adicionar um rodapé logo após o `</div>` que fecha a lista de cards (o `<div className="p-3 space-y-2 ...">`, que termina na linha 127), ainda dentro do `<div key={col.fase} ...>`:
```tsx
          {col.total > col.ordens.length && (
            <button
              onClick={() => onVerTodas(col.fase)}
              className="w-full text-center px-4 py-2.5 text-xs font-semibold text-primary hover:bg-primary/5 border-t border-border transition-colors"
            >
              Ver todas ({col.total}) →
            </button>
          )}
```

- [ ] **Step 3: `Lista` — aceitar `faseInicial`**

Atualizar a assinatura do componente `Lista` (linha 134):
```tsx
function Lista({ clienteId, faseInicial, onAbrir }: { clienteId?: number; faseInicial?: string; onAbrir: (id: number) => void }) {
```
E inicializar o estado da fase com ele (linha 135):
```tsx
  const [fase, setFase] = useState(faseInicial ?? '')
```

- [ ] **Step 4: Type-check + lint**

Run: `cd /home/ericks/github/GestorHS/frontend && npx tsc -b --noEmit && npm run lint`
Expected: limpo.

- [ ] **Step 5: Testes do frontend (nada quebrou)**

Run: `cd /home/ericks/github/GestorHS/frontend && npm test`
Expected: PASS (a suíte atual continua verde; não há teste de render do Quadro no projeto — a lógica nova é JSX trivial guiada por `col.total`, verificada no passo visual da Task 5; decisão consciente, mesmo critério usado na feature de garantia).

- [ ] **Step 6: Commit (tipo + UI juntos)**

```bash
cd /home/ericks/github/GestorHS
git add frontend/src/app/ordens/api.ts frontend/src/app/ordens/OrdensPage.tsx
git commit -m "feat(ordens): coluna finalizada no quadro com ver todas"
```

---

## Task 5: Verificação completa + changelog

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Backend completo**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS.

- [ ] **Step 2: Frontend completo**

Run: `cd /home/ericks/github/GestorHS/frontend && npm test && npx tsc -b --noEmit && npm run lint && npm run build`
Expected: tudo PASS / build OK.

- [ ] **Step 3: Verificação visual no app**

Com backend e frontend no ar, abrir `http://localhost:5173/app/ordens`:
- Confirmar a 5ª coluna **"Finalizada"** no Quadro, com um número alto no cabeçalho (total real) e até 300 cards.
- Confirmar o rodapé **"Ver todas (N) →"** e que clicar leva à vista **Lista** já com o filtro **Finalizada** aplicado.
- Confirmar que trocar de vista manualmente (botão Lista) entra **sem** filtro.

- [ ] **Step 4: Entrada no changelog**

Ler `frontend/src/app/changelog/data.ts` e inserir no TOPO do array `CHANGELOG` (antes de `1.6.0`):
```ts
  {
    versao: '1.7.0',
    data: '17/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'O quadro de Ordens de Serviço agora tem a coluna "Finalizada", mostrando as ordens já concluídas (as 300 mais recentes) com o total no topo. Para ver todas, é só clicar em "Ver todas" e abrir a lista completa filtrada.' },
    ],
  },
```

- [ ] **Step 5: Teste do changelog**

Run: `cd /home/ericks/github/GestorHS/frontend && npx vitest run src/app/changelog/data.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit do changelog**

```bash
cd /home/ericks/github/GestorHS
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.7.0 — coluna finalizada no quadro"
```

---

## Self-review (preenchido)

- **Cobertura do spec:** coluna Finalizada com cap 300 (Task 2); `total` real no schema/endpoint/cabeçalho (Tasks 1,2,3,4); "Ver todas" → Lista filtrada + reset no toggle manual (Task 4); só Finalizada, ativas intocadas (Task 2); testes backend incl. cap e filtro cliente (Task 2); changelog (Task 5).
- **Placeholders:** nenhum — todo passo tem código/comando reais. A ausência de teste de render do Quadro é decisão consciente e justificada (Task 4, Step 5), coerente com o projeto.
- **Consistência de tipos:** `QuadroColuna` ganha `total: int`/`number` nos dois lados; `onVerTodas(fase: number)`, `faseInicial?: string` casam entre `OrdensPage`/`Quadro`/`Lista`; `wf.FASE_FINALIZADA` e `wf.ATIVAS` já existem em `os_workflow.py`.
