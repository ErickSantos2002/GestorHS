# Editar OS (Administrador) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que o Administrador edite os campos de recebimento/cabeçalho de uma OS (tipo de serviço, condição de chegada, checklist, pilhas, bocais, garantia, observações, data de chegada) pela interface.

**Architecture:** Novo endpoint `PUT /ordens/{id}/editar` (Admin-only) que aplica só os campos enviados e recomputa o aviso de certificado; modal "Editar OS" no cabeçalho da OrdemDetailPage (Admin-only) espelhando os campos do AbrirOSModal.

**Tech Stack:** Backend Python 3.12 · FastAPI · SQLAlchemy 2 · pytest. Frontend React 19 · TS · Vitest.

## Global Constraints

- Domínio PT-BR; commits Conventional Commits em português **sem acentos** (ASCII), uma linha, sem trailer. Escopos: `os`, `ux`, `changelog`.
- Aparelho (`equipamento_cliente`), `cliente`, `caixa`, `calib_*`, fase/desfecho, financeiro — **FORA de escopo**, não editáveis por este endpoint.
- Só **Administrador** edita (backend `require_funcao("Administrador")`; frontend `isAdmin`).
- **Sem migração** (só colunas existentes). Changelog v1.26.1.
- Testes backend: SQLite in-memory (`conftest.py`); há **4 falhas pré-existentes de upload** (`/data/uploads`) — alheias, não conserte, não introduza novas.
- `git add` explícito sempre (nunca `git add -A`; há untracked alheio: `backend/relatorios/`, PDFs).

---

## Task 1: Backend — schema + endpoint `PUT /ordens/{id}/editar`

**Files:** Modify `backend/app/schemas/ordens.py` (novo `OrdemEditarIn`), `backend/app/api/ordens.py` (endpoint). Test `backend/tests/test_ordens_editar.py`.

**Interfaces:** Produces `PUT /ordens/{id}/editar` (Admin-only) → `OrdemOut`. Corpo `OrdemEditarIn` (todos opcionais): `tipo_servico`, `condicao_chegada`, `checklist`, `pilhas`, `bocais`, `garantia`, `observacoes`, `data_chegada`.

- [ ] **Step 1: Teste (RED)** em `backend/tests/test_ordens_editar.py`

```python
def test_editar_exige_admin(client_lab, client_admin, os_no_lab):
    r = client_lab.put(f"/ordens/{os_no_lab}/editar", json={"tipo_servico": "C"})
    assert r.status_code == 403
    r = client_admin.put(f"/ordens/{os_no_lab}/editar", json={"tipo_servico": "C"})
    assert r.status_code == 200
    assert r.json()["tipo_servico"] == "C"

def test_editar_muda_tipo_recalcula_faltantes(client_admin, os_manutencao_iblow):
    # os_manutencao_iblow: OS tipo 'M' de um aparelho que só tem modelo de Calibração (C)
    r = client_admin.put(f"/ordens/{os_manutencao_iblow}/editar", json={"tipo_servico": "C"})
    assert r.status_code == 200
    assert r.json()["certificado_modelos_faltantes"] == []

def test_editar_condicao_invalida_400(client_admin, os_no_lab):
    r = client_admin.put(f"/ordens/{os_no_lab}/editar", json={"condicao_chegada": "xyz-invalida"})
    assert r.status_code == 400

def test_editar_nao_sobrescreve_campo_ausente(client_admin, os_com_obs):
    r = client_admin.put(f"/ordens/{os_com_obs}/editar", json={"pilhas": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["pilhas"] == 2
    assert body["observacoes"] == "obs original"  # nao apagou o que nao veio
```

> Fixtures: `client_admin` (usuário função "Administrador", login real — ver se já existe no conftest; senão criar espelhando `client_lab`/`client_exp`). `os_no_lab` já existe. `os_manutencao_iblow` (OS tipo 'M' de um equipamento que tem só modelo de cert 'C' — criar um `CertificadoModelo(equipamento=<eq>, tipo='C')` + o aparelho desse equipamento). `os_com_obs` (OS com `obs="obs original"`). Reusar os padrões de fixture do conftest.

- [ ] **Step 2: Rodar e ver falhar** — `cd backend && source .venv/bin/activate && pytest tests/test_ordens_editar.py -v` → FAIL (404).

- [ ] **Step 3: Implementar** — em `backend/app/schemas/ordens.py`:

```python
class OrdemEditarIn(BaseModel):
    tipo_servico: Optional[Literal["C", "M", "A"]] = None
    condicao_chegada: Optional[str] = None
    checklist: Optional[list[int]] = None
    pilhas: Optional[int] = None
    bocais: Optional[int] = None
    garantia: Optional[bool] = None
    observacoes: Optional[str] = None
    data_chegada: Optional[date] = None
```

(garantir imports: `Optional`, `Literal`, `date` — seguir o topo do arquivo, ex.: `from datetime import date`.)

Em `backend/app/api/ordens.py` (após `abrir`; reusa `rec`, `datetime`/`timezone`, `agora`, `registrar_log`, `_anotar_modelos_faltantes`, `ADMIN`/`require_funcao` já importados no módulo). O `bocais` mapeia pra coluna `sopradores`; `observacoes` pra `obs`:

```python
@router.put("/{ordem_id}/editar", response_model=OrdemOut)
def editar(ordem_id: int, dados: OrdemEditarIn, db: Session = Depends(get_db),
           usuario: Usuario = Depends(require_funcao("Administrador"))):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    campos = dados.model_dump(exclude_unset=True)
    if "condicao_chegada" in campos and campos["condicao_chegada"] is not None \
            and campos["condicao_chegada"] not in rec.CONDICOES_CHEGADA:
        raise HTTPException(status_code=400, detail="condição de chegada inválida")
    if "checklist" in campos:
        try:
            ordem.checklist = rec.checklist_ids_para_csv(campos["checklist"])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if "data_chegada" in campos and campos["data_chegada"] is not None:
        d = campos["data_chegada"]
        ordem.data_chegada = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    if "tipo_servico" in campos:
        ordem.tipo_servico = campos["tipo_servico"]
    if "condicao_chegada" in campos:
        ordem.condicao_chegada = campos["condicao_chegada"]
    if "pilhas" in campos:
        ordem.pilhas = campos["pilhas"]
    if "bocais" in campos:
        ordem.sopradores = campos["bocais"]
    if "garantia" in campos and campos["garantia"] is not None:
        ordem.garantia = campos["garantia"]
    if "observacoes" in campos:
        ordem.obs = campos["observacoes"]
    alterados = ", ".join(sorted(campos.keys()))
    registrar_log(db, ordem, usuario, f"OS editada (admin): {alterados}")
    db.commit()
    db.refresh(ordem)
    _anotar_modelos_faltantes(db, ordem)
    return ordem
```

- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_ordens_editar.py -v && pytest -q` (726+ passed, 4 pré-existentes).
- [ ] **Step 5: Commit** — `git add backend/app/schemas/ordens.py backend/app/api/ordens.py backend/tests/test_ordens_editar.py backend/tests/conftest.py && git commit -m "feat(os): admin edita campos de recebimento da os"`

---

## Task 2: Frontend — api + modal "Editar OS" (Admin)

**Files:** Modify `frontend/src/app/ordens/api.ts` (`ordensApi.editar` + `EditarPayload`). Create `frontend/src/app/ordens/EditarOSModal.tsx`. Modify `frontend/src/app/ordens/OrdemDetailPage.tsx` (botão Admin). Test `frontend/src/app/ordens/EditarOSModal.test.tsx`.

**Interfaces:** Consumes `OrdemDetalhe` (campos atuais). Produces `ordensApi.editar(id, payload)` (PUT `/ordens/{id}/editar`); botão "Editar OS" (Admin) → `EditarOSModal` pré-preenchido → salva → recarrega.

- [ ] **Step 1: Teste (RED)** — o botão "Editar OS" só aparece para Admin; submeter o modal chama `ordensApi.editar` com os campos.

```tsx
// EditarOSModal.test.tsx — submit chama editar com o payload
it('submete edicao chamando ordensApi.editar', async () => {
  const spy = vi.spyOn(ordensApi, 'editar').mockResolvedValue({} as any)
  render(<EditarOSModal os={{ id: 5, tipo_servico: 'M', pilhas: 0, bocais: 0, garantia: true, condicao_chegada: null, observacoes: '', data_chegada: null, checklist_ids: [] } as any} onClose={() => {}} onSalvo={() => {}} />)
  fireEvent.change(screen.getByLabelText(/tipo de serviço/i), { target: { value: 'C' } })
  fireEvent.click(screen.getByRole('button', { name: /salvar/i }))
  await waitFor(() => expect(spy).toHaveBeenCalledWith(5, expect.objectContaining({ tipo_servico: 'C' })))
})
```

- [ ] **Step 2: Rodar e ver falhar** — `cd frontend && npx vitest run src/app/ordens/EditarOSModal.test.tsx` → FAIL.
- [ ] **Step 3: Implementar**
  - `frontend/src/app/ordens/api.ts`: `export interface EditarPayload { tipo_servico?: string; condicao_chegada?: string | null; checklist?: number[] | null; pilhas?: number | null; bocais?: number | null; garantia?: boolean; observacoes?: string | null; data_chegada?: string | null }` e no `ordensApi`: `editar: (id: number, payload: EditarPayload): Promise<OrdemDetalhe> => apiJson<OrdemDetalhe>(\`/ordens/\${id}/editar\`, { method: 'PUT', body: JSON.stringify(payload) })`.
  - `EditarOSModal.tsx` (novo) — espelha os campos do `frontend/src/app/ordens/AbrirOSModal.tsx` (LEIA-o), MENOS aparelho e caixa: Select "Tipo de serviço" (C/M/A), Select "Condição de chegada", checklist de acessórios, inputs "Pilhas"/"Bocais", checkbox "Garantia", textarea "Observações", input date "Data de chegada". Pré-preenche com os valores atuais da `os` (props). Ao salvar, monta o payload só com os campos e chama `ordensApi.editar(os.id, payload)`, depois `onSalvo()`. Estilo/design system igual aos outros modais de `ordens/`.
  - `OrdemDetailPage.tsx`: adicionar botão **"Editar OS"** no cabeçalho (perto de "Voltar"/"Liberar do Laboratório"), visível só quando `isAdmin(user)` (de `../../auth/roles`). Abre o `EditarOSModal`; no `onSalvo`, recarrega a OS (padrão de recarregar que o arquivo já usa) e fecha.
  - Garantir que `OrdemDetalhe` (em `ordens/api.ts`) expõe os campos usados pré-preenchidos (`tipo_servico`, `condicao_chegada`, `pilhas`, `bocais`, `garantia`, `observacoes`/`obs`, `data_chegada`, `checklist_ids`); se algum faltar no tipo, adicionar.
- [ ] **Step 4: Rodar e ver passar** — `npx vitest run src/app/ordens/ && npx tsc -b --noEmit && npx eslint src/app/ordens/`.
- [ ] **Step 5: Commit** — `git add frontend/src/app/ordens/api.ts frontend/src/app/ordens/EditarOSModal.tsx frontend/src/app/ordens/OrdemDetailPage.tsx frontend/src/app/ordens/EditarOSModal.test.tsx && git commit -m "feat(ux): botao editar os para administrador"`

---

## Task 3: Changelog v1.26.1 + verificação final

**Files:** Modify `frontend/src/app/changelog/data.ts`.

- [ ] **Step 1: Changelog** — 1ª entrada do array `CHANGELOG`:
```ts
{
  versao: '1.26.1',
  data: '28/07/2026',
  itens: [
    { tipo: 'novidade', texto: 'O Administrador agora pode editar os dados de recebimento de uma OS (tipo de serviço, condição de chegada, acessórios, pilhas, bocais, garantia, observações e data de chegada) — útil para corrigir, por exemplo, uma OS aberta como Manutenção que era Calibração.' },
  ],
},
```
- [ ] **Step 2: Backend** — `cd backend && source .venv/bin/activate && pytest -q` (só as 4 pré-existentes de upload).
- [ ] **Step 3: Frontend** — `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`.
- [ ] **Step 4: Commit** — `git add frontend/src/app/changelog/data.ts && git commit -m "docs(changelog): v1.26.1 - admin edita recebimento da os"`

---

## Self-Review

- **Cobertura da spec:** endpoint Admin (T1) · campos de recebimento editáveis + recompute do aviso de cert (T1) · validação condicao/checklist (T1) · modal + botão Admin (T2) · changelog v1.26.1 (T3). ✅
- **Fora de escopo respeitado:** aparelho/cliente/caixa/calib/fase/financeiro não tocados.
- **Placeholder scan:** sem TBD; código real nos steps.
- **Nomes/tipos consistentes:** `OrdemEditarIn`/`EditarPayload`, `bocais`→`sopradores`, `observacoes`→`obs`, `ordensApi.editar`, `/ordens/{id}/editar`.
