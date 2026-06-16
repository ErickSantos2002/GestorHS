# Garantia do aparelho na OS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar, na tela de detalhe da OS, se o aparelho está em garantia (calibração, manutenção e compra), com um selo-resumo no topo e um painel detalhado.

**Architecture:** Lógica de garantia pura em `core/garantia.py` (sem I/O). O endpoint `GET /ordens/{id}` busca a última manutenção (OS finalizada `tipo IN ('M','A')`) e embute um objeto `garantias` no `OrdemOut`. O frontend só renderiza badges. Sem migração de banco.

**Tech Stack:** Backend FastAPI + SQLAlchemy 2 + Pydantic v2 (pytest, SQLite in-memory). Frontend React 19 + TS + Vitest. Convenção de commit: `tipo(escopo): descricao` em PT-BR sem acentos, uma linha, sem co-autor.

**Spec:** [docs/superpowers/specs/2026-06-16-garantia-aparelho-na-os-design.md](../specs/2026-06-16-garantia-aparelho-na-os-design.md)

---

## File Structure

- **Create** `backend/app/core/garantia.py` — lógica pura (cálculo das 3 garantias).
- **Create** `backend/tests/test_garantia.py` — testes da lógica pura.
- **Modify** `backend/app/schemas/ordens.py` — schemas `GarantiaItem`, `GarantiasOut`; campo `garantias` em `OrdemOut`.
- **Modify** `backend/app/api/ordens.py` — helper `_ultima_manutencao` + popular `garantias` no `obter`.
- **Modify** `backend/tests/test_ordens_leitura.py` — teste de API das garantias no detalhe.
- **Modify** `frontend/src/app/ordens/api.ts` — tipos `Garantias`/`GarantiaItem`, campo em `OrdemDetalhe`, helper `garantiaBadge`.
- **Create** `frontend/src/app/ordens/api.garantia.test.ts` — teste do helper `garantiaBadge`.
- **Modify** `frontend/src/app/ordens/OrdemDetailPage.tsx` — selo no header + painel "Garantia".
- **Modify** `frontend/src/app/changelog/data.ts` — entrada v1.6.0.

---

## Task 1: Lógica pura de garantia (`core/garantia.py`)

**Files:**
- Create: `backend/app/core/garantia.py`
- Test: `backend/tests/test_garantia.py`

- [ ] **Step 1: Escrever os testes que falham**

Create `backend/tests/test_garantia.py`:

```python
from datetime import date

from app.core.garantia import status_garantia, garantias


def test_sem_base_retorna_sem_registro():
    r = status_garantia(None, date(2026, 6, 16))
    assert r == {"estado": "sem_registro", "data_base": None, "vence_em": None}


def test_dentro_do_prazo_em_garantia():
    base = date(2026, 3, 12)
    r = status_garantia(base, date(2026, 6, 16))
    assert r["estado"] == "em_garantia"
    assert r["data_base"] == base
    assert r["vence_em"] == date(2027, 3, 12)


def test_fronteira_ultimo_dia_inclusive():
    base = date(2025, 6, 16)
    # hoje == vence_em -> ainda em garantia
    r = status_garantia(base, date(2026, 6, 16))
    assert r["estado"] == "em_garantia"


def test_dia_seguinte_ao_vencimento_fora():
    base = date(2025, 6, 16)
    r = status_garantia(base, date(2026, 6, 17))
    assert r["estado"] == "fora"
    assert r["vence_em"] == date(2026, 6, 16)


def test_bissexto_29_fev_vira_28_fev():
    base = date(2024, 2, 29)
    r = status_garantia(base, date(2024, 6, 1))
    assert r["vence_em"] == date(2025, 2, 28)


def test_garantias_resumo_qualquer_ativa():
    hoje = date(2026, 6, 16)
    r = garantias(
        datacompra=date(2020, 1, 1),       # fora
        ult_calibragem=date(2026, 1, 1),   # em garantia
        ult_manutencao=None,               # sem registro
        hoje=hoje,
    )
    assert r["em_garantia"] is True
    assert r["calibracao"]["estado"] == "em_garantia"
    assert r["manutencao"]["estado"] == "sem_registro"
    assert r["compra"]["estado"] == "fora"


def test_garantias_resumo_nenhuma_ativa():
    hoje = date(2026, 6, 16)
    r = garantias(date(2010, 1, 1), date(2010, 1, 1), None, hoje)
    assert r["em_garantia"] is False
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `cd backend && pytest tests/test_garantia.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core.garantia'`.

- [ ] **Step 3: Implementar `core/garantia.py`**

Create `backend/app/core/garantia.py`:

```python
"""Cálculo das garantias do aparelho (calibração, manutenção, compra).

Puro, sem I/O. Cada garantia dura 1 ano a partir da sua data base.
"""
from datetime import date

DURACAO_GARANTIA_ANOS = 1


def _mais_um_ano(base: date) -> date:
    """base + 1 ano (mesma data no ano seguinte); 29/fev -> 28/fev."""
    try:
        return base.replace(year=base.year + DURACAO_GARANTIA_ANOS)
    except ValueError:
        # 29/fev em ano de destino não bissexto
        return base.replace(year=base.year + DURACAO_GARANTIA_ANOS, day=28)


def status_garantia(base: date | None, hoje: date) -> dict:
    """Status de uma garantia a partir da data base.

    sem base -> sem_registro
    com base -> em_garantia enquanto hoje <= vence_em (inclusive), senão fora.
    """
    if base is None:
        return {"estado": "sem_registro", "data_base": None, "vence_em": None}
    vence_em = _mais_um_ano(base)
    estado = "em_garantia" if hoje <= vence_em else "fora"
    return {"estado": estado, "data_base": base, "vence_em": vence_em}


def garantias(
    datacompra: date | None,
    ult_calibragem: date | None,
    ult_manutencao: date | None,
    hoje: date,
) -> dict:
    """Monta os 3 status + resumo (em_garantia = qualquer uma ativa)."""
    calibracao = status_garantia(ult_calibragem, hoje)
    manutencao = status_garantia(ult_manutencao, hoje)
    compra = status_garantia(datacompra, hoje)
    em_garantia = any(
        g["estado"] == "em_garantia" for g in (calibracao, manutencao, compra)
    )
    return {
        "em_garantia": em_garantia,
        "calibracao": calibracao,
        "manutencao": manutencao,
        "compra": compra,
    }
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd backend && pytest tests/test_garantia.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/garantia.py backend/tests/test_garantia.py
git commit -m "feat(ordens): core de garantia (calibracao/manutencao/compra)"
```

---

## Task 2: Schemas `GarantiaItem` / `GarantiasOut` no `OrdemOut`

**Files:**
- Modify: `backend/app/schemas/ordens.py` (inserir antes de `class OrdemOut` na linha 36; adicionar campo no `OrdemOut`)

- [ ] **Step 1: Inserir os schemas antes de `OrdemOut`**

Em `backend/app/schemas/ordens.py`, logo após `class QuadroColuna` (linha 33, antes de `class OrdemOut`), inserir:

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

(`Literal` e `date` já estão importados no topo do arquivo — linhas 1-2.)

- [ ] **Step 2: Adicionar o campo no `OrdemOut`**

No final da classe `OrdemOut` (após `bocais: int = 0`, linha 76), adicionar:

```python
    garantias: "GarantiasOut | None" = None
```

- [ ] **Step 3: Verificar que importa sem erro**

Run: `cd backend && python -c "from app.schemas.ordens import OrdemOut, GarantiasOut; print('ok')"`
Expected: imprime `ok` (sem ImportError / NameError).

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/ordens.py
git commit -m "feat(ordens): schema GarantiasOut no detalhe da OS"
```

---

## Task 3: Expor `garantias` no `GET /ordens/{id}`

**Files:**
- Modify: `backend/app/api/ordens.py` (imports no topo; helper novo; função `obter` na linha 69-74)
- Test: `backend/tests/test_ordens_leitura.py` (adicionar teste no fim do arquivo)

- [ ] **Step 1: Escrever o teste de API que falha**

Adicionar ao fim de `backend/tests/test_ordens_leitura.py`:

```python
def test_detalhe_traz_garantias_derivando_manutencao(
    client, usuario_admin, fases_seed, os_base, db_session
):
    from datetime import date, datetime, timezone
    from app.models import EquipamentoCliente

    # aparelho com compra antiga (fora) e calibracao recente (em garantia)
    ec = db_session.query(EquipamentoCliente).get(os_base["equipamento_cliente"])
    ec.datacompra = date(2010, 1, 1)
    ec.ult_calibragem = date.today()
    db_session.commit()

    # OS de manutencao FINALIZADA recente -> vira a ultima manutencao
    _ordem(
        db_session, os_base["cliente"], os_base["equipamento_cliente"], 8,
        tipo_servico="M",
        data_calibracao=datetime.now(timezone.utc),
    )
    # OS atual (em andamento) que estamos consultando
    o = _ordem(
        db_session, os_base["cliente"], os_base["equipamento_cliente"], 5,
        tipo_servico="C",
    )

    h = _headers(client, "admin", "senha123")
    g = client.get(f"/ordens/{o.id}", headers=h).json()["garantias"]
    assert g is not None
    assert g["em_garantia"] is True
    assert g["calibracao"]["estado"] == "em_garantia"
    assert g["manutencao"]["estado"] == "em_garantia"   # derivada da OS 'M'
    assert g["compra"]["estado"] == "fora"


def test_detalhe_sem_aparelho_garantias_null(
    client, usuario_admin, fases_seed, db_session
):
    from app.models import Cliente
    cli = Cliente(nome="Sem aparelho")
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    o = _ordem(db_session, cli.id, None, 4, tipo_servico="C")
    h = _headers(client, "admin", "senha123")
    assert client.get(f"/ordens/{o.id}", headers=h).json()["garantias"] is None
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `cd backend && pytest tests/test_ordens_leitura.py::test_detalhe_traz_garantias_derivando_manutencao -q`
Expected: FAIL — `garantias` é `None` (KeyError/AssertionError), pois o endpoint ainda não popula.

- [ ] **Step 3: Adicionar imports no topo de `ordens.py`**

No bloco de imports de `backend/app/api/ordens.py`, adicionar:

```python
from datetime import date
from app.core.garantia import garantias as _calc_garantias
from app.core.os_workflow import FASE_FINALIZADA
```

- [ ] **Step 4: Adicionar o helper `_ultima_manutencao`**

Antes da função `obter` (linha 69) em `ordens.py`:

```python
def _ultima_manutencao(db: Session, equipamento_cliente_id: int) -> date | None:
    """Data da última manutenção: data_calibracao da OS finalizada mais recente
    com tipo_servico em ('M', 'A') para o aparelho."""
    o = (
        db.query(Ordem)
        .filter(
            Ordem.equipamento_cliente == equipamento_cliente_id,
            Ordem.tipo_servico.in_(("M", "A")),
            Ordem.fase == FASE_FINALIZADA,
            Ordem.data_calibracao.isnot(None),
        )
        .order_by(Ordem.data_calibracao.desc())
        .first()
    )
    return o.data_calibracao.date() if o is not None else None
```

- [ ] **Step 5: Popular `garantias` na função `obter`**

Substituir o corpo de `obter` (linhas 69-74) por:

```python
@router.get("/{ordem_id}", response_model=OrdemOut)
def obter(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    eqc = obj.equipamento_rel
    if eqc is not None:
        obj.garantias = _calc_garantias(
            datacompra=eqc.datacompra,
            ult_calibragem=eqc.ult_calibragem,
            ult_manutencao=_ultima_manutencao(db, eqc.id),
            hoje=date.today(),
        )
    else:
        obj.garantias = None
    return obj
```

(Atribuir `obj.garantias` num atributo não-mapeado da instância SQLAlchemy é válido; o `OrdemOut` com `from_attributes=True` lê esse atributo e valida o dict aninhado.)

- [ ] **Step 6: Rodar os testes e confirmar que passam**

Run: `cd backend && pytest tests/test_ordens_leitura.py -q`
Expected: PASS (incluindo os dois novos testes).

- [ ] **Step 7: Rodar a suíte de OS inteira (não quebrou nada)**

Run: `cd backend && pytest tests/test_ordens_leitura.py tests/test_ordens_abrir.py tests/test_ordens_avancar.py tests/test_ordens_cancelar.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/ordens.py backend/tests/test_ordens_leitura.py
git commit -m "feat(ordens): expor garantias no GET da OS (manutencao via OS M/A)"
```

---

## Task 4: Tipos e helper `garantiaBadge` no frontend

**Files:**
- Modify: `frontend/src/app/ordens/api.ts` (tipos novos; campo em `OrdemDetalhe`; helper exportado)
- Test: `frontend/src/app/ordens/api.garantia.test.ts`

- [ ] **Step 1: Escrever o teste do helper que falha**

Create `frontend/src/app/ordens/api.garantia.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { garantiaBadge, type GarantiaItem } from './api'

describe('garantiaBadge', () => {
  it('em_garantia -> verde com data de vencimento', () => {
    const item: GarantiaItem = { estado: 'em_garantia', data_base: '2026-03-12', vence_em: '2027-03-12' }
    expect(garantiaBadge(item)).toEqual({ label: 'Em garantia até 12/03/2027', tone: 'primary' })
  })

  it('fora -> cinza "Fora da garantia"', () => {
    const item: GarantiaItem = { estado: 'fora', data_base: '2020-01-01', vence_em: '2021-01-01' }
    expect(garantiaBadge(item)).toEqual({ label: 'Fora da garantia', tone: 'neutral' })
  })

  it('sem_registro -> cinza "Sem registro"', () => {
    const item: GarantiaItem = { estado: 'sem_registro', data_base: null, vence_em: null }
    expect(garantiaBadge(item)).toEqual({ label: 'Sem registro', tone: 'neutral' })
  })
})
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `cd frontend && npx vitest run src/app/ordens/api.garantia.test.ts`
Expected: FAIL — `garantiaBadge` não existe (import error).

- [ ] **Step 3: Adicionar os tipos de garantia em `api.ts`**

Em `frontend/src/app/ordens/api.ts`, antes de `export interface OrdemDetalhe` (linha 71), adicionar:

```ts
export type EstadoGarantia = 'em_garantia' | 'fora' | 'sem_registro'

export interface GarantiaItem {
  estado: EstadoGarantia
  data_base: string | null
  vence_em: string | null
}

export interface Garantias {
  em_garantia: boolean
  calibracao: GarantiaItem
  manutencao: GarantiaItem
  compra: GarantiaItem
}
```

- [ ] **Step 4: Adicionar o campo `garantias` em `OrdemDetalhe`**

No fim da interface `OrdemDetalhe` (após `acessorios_presentes: string[]`, linha 95), adicionar:

```ts
  garantias: Garantias | null
```

- [ ] **Step 5: Adicionar o helper `garantiaBadge`**

Após a interface `Garantias` (ou no fim do arquivo), adicionar — reutiliza `formatData` já existente (linhas 37-40):

```ts
export function garantiaBadge(item: GarantiaItem): { label: string; tone: 'primary' | 'neutral' } {
  if (item.estado === 'em_garantia') {
    return { label: `Em garantia até ${formatData(item.vence_em)}`, tone: 'primary' }
  }
  if (item.estado === 'fora') {
    return { label: 'Fora da garantia', tone: 'neutral' }
  }
  return { label: 'Sem registro', tone: 'neutral' }
}
```

- [ ] **Step 6: Rodar o teste e confirmar que passa**

Run: `cd frontend && npx vitest run src/app/ordens/api.garantia.test.ts`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/ordens/api.ts frontend/src/app/ordens/api.garantia.test.ts
git commit -m "feat(ordens): tipos e badge de garantia no front"
```

---

## Task 5: Selo no header + painel "Garantia" na tela da OS

**Files:**
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx` (import; selo no header ~linha 240; painel após "Datas" ~linha 359; mini-componente)

Nota de teste: a lógica (mapa estado→badge) já é coberta pelo teste de `garantiaBadge` na Task 4. A renderização aqui é JSX trivial; será validada manualmente no app rodando (verification step na Task 6). Não adicionamos teste de render de página inteira (custo alto, muitas dependências de router/auth) — decisão consciente.

- [ ] **Step 1: Importar `garantiaBadge` e o tipo**

Na linha 14 de `OrdemDetailPage.tsx`, acrescentar `garantiaBadge` e `type GarantiaItem` ao import de `'./api'`:

```ts
import { ordensApi, fotosApi, TIPO_SERVICO, TRANSICOES, formatData, garantiaBadge, type OrdemDetalhe, type GarantiaItem, type LogOS, type Foto, type OSCertificado } from './api'
```

- [ ] **Step 2: Adicionar o mini-componente `GarantiaBadge`**

Junto aos helpers `Campo`/`Secao` (perto da linha 31-40), adicionar:

```tsx
function GarantiaBadge({ item }: { item: GarantiaItem }) {
  const b = garantiaBadge(item)
  return <Badge tone={b.tone}>{b.label}</Badge>
}
```

- [ ] **Step 3: Adicionar o selo-resumo no header**

No header, dentro do `<div className="flex items-center gap-3 flex-wrap">` (logo após o bloco da fase que termina na linha 240, antes do `</div>` da linha 241), adicionar:

```tsx
              {os.garantias && (
                <Badge tone={os.garantias.em_garantia ? 'primary' : 'neutral'}>
                  {os.garantias.em_garantia ? 'EM GARANTIA' : 'SEM GARANTIA'}
                </Badge>
              )}
```

- [ ] **Step 4: Adicionar o painel "Garantia" após a seção "Datas"**

Logo após o fechamento da `Secao` de "Datas" (linha 359), inserir:

```tsx
      {/* Garantia */}
      {os.garantias && (
        <Secao icon={<IconCheck className="w-4 h-4" />} titulo="Garantia">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4 gap-y-5">
            <Campo label="Calibração" valor={<GarantiaBadge item={os.garantias.calibracao} />} />
            <Campo label="Manutenção" valor={<GarantiaBadge item={os.garantias.manutencao} />} />
            <Campo label="Compra" valor={<GarantiaBadge item={os.garantias.compra} />} />
          </div>
        </Secao>
      )}
```

(`IconCheck` já está importado — linha 8. `Badge`, `Campo`, `Secao` já existem no arquivo.)

- [ ] **Step 5: Checagem de tipos e lint**

Run: `cd frontend && npx tsc -b --noEmit && npm run lint`
Expected: sem erros.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/ordens/OrdemDetailPage.tsx
git commit -m "feat(ordens): selo e painel de garantia na tela da OS"
```

---

## Task 6: Verificação completa + changelog

**Files:**
- Modify: `frontend/src/app/changelog/data.ts` (nova entrada no topo)

- [ ] **Step 1: Backend — suíte completa**

Run: `cd backend && pytest -q`
Expected: PASS (todos, incluindo `test_garantia.py` e os novos de `test_ordens_leitura.py`).

- [ ] **Step 2: Frontend — testes + tipos + build**

Run: `cd frontend && npm test && npx tsc -b --noEmit && npm run lint && npm run build`
Expected: tudo PASS / build sem erros.

- [ ] **Step 3: Verificação visual no app rodando**

Com backend (`docker compose up -d`) e frontend (`npm run dev`) no ar, abrir `http://localhost:5173/app/ordens/10410`:
- Confirmar o selo "EM GARANTIA" (verde) no topo, ao lado do badge de fase.
- Confirmar o painel "Garantia" com Calibração / Manutenção / Compra e os badges corretos.

- [ ] **Step 4: Adicionar entrada no changelog**

No topo do array `CHANGELOG` em `frontend/src/app/changelog/data.ts` (antes da entrada `1.5.0`), adicionar:

```ts
  {
    versao: '1.6.0',
    data: '16/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Ao abrir uma Ordem de Serviço agora aparece, no topo, um selo indicando se o aparelho está em garantia, e um painel detalhado com as três garantias (calibração, manutenção e compra) — cada uma mostrando até quando vale.' },
    ],
  },
```

- [ ] **Step 5: Rodar o teste do changelog**

Run: `cd frontend && npx vitest run src/app/changelog/data.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit do changelog (fecha a release)**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.6.0 — garantia do aparelho na OS"
```

---

## Self-review (preenchido)

- **Cobertura do spec:** origem das datas (Task 3 helper + Task 1) ✓; "1 ano" inclusive + bissexto (Task 1) ✓; backend sem migração/endpoint novo (Task 3) ✓; schemas (Task 2) ✓; selo + painel (Task 5) ✓; testes pura/API/front (Tasks 1, 3, 4) ✓; changelog (Task 6) ✓.
- **Placeholders:** nenhum — todo passo tem código/comando reais.
- **Consistência de tipos:** `status_garantia`/`garantias` (dict com `estado`/`data_base`/`vence_em`) batem entre core, schema (`GarantiaItem`/`GarantiasOut`) e front (`GarantiaItem`/`Garantias`); `garantiaBadge` retorna `tone` `'primary'|'neutral'` compatível com `Badge`.
