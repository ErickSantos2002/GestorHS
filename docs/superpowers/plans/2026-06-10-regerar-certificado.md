# Regerar certificado (OS finalizada) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir corrigir os valores + a data de calibração e regerar o certificado mesmo com a OS finalizada (Lab/Admin).

**Architecture:** O endpoint de gerar já regenera de `ordem.calib_*` sem checar fase; adicionamos data de calibração editável (para não resetar pra "hoje"); no frontend, o botão Gerar/Regerar passa a aparecer quando há certificado (qualquer fase) e o modal ganha o campo de data.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React 19 + TS + Vite + Tailwind (frontend), pytest/vitest.

**Branch:** `main`. Lançamento: v1.4.3.

**Spec:** `docs/superpowers/specs/2026-06-10-regerar-certificado-design.md`

---

## Task 1: Backend — data de calibração editável no gerar

**Files:**
- Modify: `backend/app/schemas/ordens.py`
- Modify: `backend/app/api/certificados_os.py`
- Test: `backend/tests/test_certificado_os_api.py`

Contexto: o endpoint `gerar` hoje faz `ordem.data_calibracao = agora()` sempre que recebe corpo. Vamos passar a gravar a data vinda do form (UTC) e, sem data no corpo, manter a existente (fallback `agora()` só se ainda for None). pytest roda no container: `docker compose exec -T backend python -m pytest ...`.

- [ ] **Step 1: Escrever os testes (acrescentar ao fim de `backend/tests/test_certificado_os_api.py`)**

```python
def test_gerar_grava_data_calibracao_informada(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "C1", "data_calibracao": "2026-01-15"}, headers=h)
    assert r.status_code == 200
    from app.models import Ordem
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.data_calibracao is not None
    assert o.data_calibracao.date().isoformat() == "2026-01-15"


def test_regerar_sem_data_preserva_a_existente(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "C1", "data_calibracao": "2026-01-15"}, headers=h)
    # regerar corrigindo um valor, SEM enviar data
    r = client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "C2"}, headers=h)
    assert r.status_code == 200
    from app.models import Ordem
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.calib_cert == "C2"
    assert o.data_calibracao.date().isoformat() == "2026-01-15"   # não resetou
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_certificado_os_api.py -q -k "data_calibracao or preserva"`
Expected: FAIL (campo `data_calibracao` ainda ignorado / data reseta).

- [ ] **Step 3: Adicionar o campo ao schema**

Em `backend/app/schemas/ordens.py`, na classe `GerarCertificadoIn`, adicionar o campo (o `date` já é importado no módulo):
```python
class GerarCertificadoIn(BaseModel):
    data_calibracao: date | None = None
    calib_cert: str | None = None
    # ... (demais campos calib_* inalterados)
```
(adicionar `data_calibracao` como primeiro campo da classe; não remover os existentes.)

- [ ] **Step 4: Ajustar o endpoint**

Em `backend/app/api/certificados_os.py`:
- Adicionar import no topo: `from datetime import datetime, timezone`
- No corpo do `gerar`, trocar:
```python
    if dados is not None:
        for campo in _CAMPOS_CALIB:
            setattr(ordem, campo, getattr(dados, campo))
        ordem.data_calibracao = agora()
        db.flush()
```
por:
```python
    if dados is not None:
        for campo in _CAMPOS_CALIB:
            setattr(ordem, campo, getattr(dados, campo))
        if dados.data_calibracao is not None:
            ordem.data_calibracao = datetime(
                dados.data_calibracao.year, dados.data_calibracao.month, dados.data_calibracao.day,
                tzinfo=timezone.utc,
            )
        elif ordem.data_calibracao is None:
            ordem.data_calibracao = agora()
        db.flush()
```
(Não chamar `espelhar_calibracao` — regerar só corrige o certificado.)

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_certificado_os_api.py -q`
Expected: PASS (todos do arquivo, incluindo os 2 novos e o `test_gerar_com_dados_salva_e_preenche` existente).

- [ ] **Step 6: Suíte completa**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: PASS sem regressões.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/ordens.py backend/app/api/certificados_os.py backend/tests/test_certificado_os_api.py
git commit -m "feat(cert): data de calibracao editavel ao gerar/regerar"
```

---

## Task 2: Frontend — campo de data + regerar em qualquer fase

**Files:**
- Modify: `frontend/src/app/ordens/api.ts`
- Modify: `frontend/src/app/ordens/GerarCertificadoModal.tsx`
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx`

Contexto: adicionar `data_calibracao` ao payload e ao formulário (default hoje / valor atual da OS), e liberar o botão Regerar quando já existe certificado em qualquer fase.

- [ ] **Step 1: Payload no `api.ts`**

Em `frontend/src/app/ordens/api.ts`, na interface `GerarCertificadoPayload`, adicionar como primeiro campo:
```ts
  data_calibracao?: string | null
```

- [ ] **Step 2: Campo de data no `GerarCertificadoModal.tsx`**

Adicionar um helper antes do componente (após `calcMedia`):
```ts
function hojeISO(): string {
  return new Date().toISOString().slice(0, 10)
}
```
Adicionar o estado (junto aos outros `useState`, ex.: após `cert`):
```tsx
  const [dataCalib, setDataCalib] = useState(os.data_calibracao ? os.data_calibracao.slice(0, 10) : hojeISO())
```
No `payload` do `submeter`, adicionar como primeira propriedade:
```ts
      data_calibracao: dataCalib || null,
```
No formulário, adicionar o campo como PRIMEIRO filho do `<form id="form-gerar-cert" ...>` (antes do `<div className="grid grid-cols-2 gap-3">` do certificado):
```tsx
        <Input id="data-calib" label="Data de calibração" type="date" value={dataCalib} onChange={(e) => setDataCalib(e.target.value)} />
```

- [ ] **Step 3: Liberar regerar em qualquer fase no `OrdemDetailPage.tsx`**

Na seção "Certificados", trocar a condição do `acao` do botão de:
```tsx
        acao={podeGerarCert && naFaseLab && (
```
para:
```tsx
        acao={podeGerarCert && (naFaseLab || certs.length > 0) && (
```
(O texto auxiliar "Nenhum certificado gerado. Clique em..." continua condicionado a `podeGerarCert && naFaseLab` — não alterar essa linha; numa OS finalizada sem certificado o botão não aparece, e a dica também não, o que é o correto.)

- [ ] **Step 4: Verificar**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/ordens/api.ts src/app/ordens/GerarCertificadoModal.tsx src/app/ordens/OrdemDetailPage.tsx && npm run build`
Expected: sem erros, build verde.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/ordens/api.ts frontend/src/app/ordens/GerarCertificadoModal.tsx frontend/src/app/ordens/OrdemDetailPage.tsx
git commit -m "feat(cert): data de calibracao no form + regerar em qualquer fase"
```

---

## Task 3: Changelog v1.4.3 + verificação final + memória

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Adicionar v1.4.3 no topo do array `CHANGELOG`**

```ts
  {
    versao: '1.4.3',
    data: '10/06/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Agora é possível corrigir os valores (e a data) de calibração e regerar o certificado mesmo com a OS finalizada — útil quando um certificado sai com algum valor errado. A data de calibração passou a ser um campo do formulário e não é mais redefinida ao regerar.' },
    ],
  },
```

- [ ] **Step 2: Verificar build + suíte**

Run: `cd frontend && npm run build && npx vitest run`
Expected: build verde; testes passando.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.4.3 — regerar certificado com valores corrigidos"
```

- [ ] **Step 4: E2E manual (com o usuário)**

Abrir uma OS finalizada com certificado → "Regerar certificado" → corrigir um valor e a data → Gerar → Baixar PDF e conferir valor/data corrigidos; confirmar que a data NÃO virou "hoje" quando não alterada.

- [ ] **Step 5: Atualizar memória**

Em `C:\Users\TI\.claude\projects\d--GitHub-GestorHS\memory\project_gestorhs.md`: registrar que dá pra regerar certificado em qualquer fase (inclusive finalizada) para Lab/Admin, com data de calibração editável no `GerarCertificadoModal` (endpoint grava a data do form; sem data, preserva a existente; não espelha no aparelho).

---

## Self-Review (preenchido)

**Spec coverage:** schema `data_calibracao` + lógica de data no endpoint (T1); payload + campo no modal + condição do botão (T2); changelog/memória/E2E (T3). Tudo coberto. "Só corrige o certificado / não espelha" já é o comportamento (endpoint não chama `espelhar_calibracao`), preservado.

**Type consistency:** `data_calibracao` é `date | None` no schema backend e `string | null` (YYYY-MM-DD) no payload frontend; o endpoint converte para datetime UTC. `GerarCertificadoPayload`/`GerarCertificadoIn` mantêm os demais campos.

**Placeholders:** nenhum — todo passo tem código/comando concretos.
