# Financeiro com acesso a Propostas/Serviços/Produtos — Plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Dar à função Financeiro o mesmo acesso completo (ver/criar/editar) que o Comercial Pós-Vendas tem a Propostas, Serviços e Produtos, espelhado no frontend e no backend.

**Architecture:** Adicionar `Financeiro` ao gate único de gestão nos dois lados — `podeGerenciarPropostas` (frontend) e os 3 `require_funcao` de escrita (backend).

**Tech Stack:** Frontend React/TS/Vitest; Backend FastAPI/pytest.

## Global Constraints
- Domínio PT-BR; commits Conventional Commits sem acentos, uma linha, sem trailer. Escopos: `acesso`, `changelog`.
- **Espelhar nos dois lados** (regra do CLAUDE.md). Sem migração. Mini versão **v1.27.4**.
- `git add` explícito (nunca `-A`). Falhas de teste pré-existentes alheias (4 upload backend; `ClienteEquipamentosTab` frontend) — não conserte, não introduza novas.

---

## Task 1: adicionar Financeiro ao gate de gestão (frontend + backend) + tests + changelog

**Files:** Modify `frontend/src/auth/roles.ts`, `backend/app/api/propostas.py`, `backend/app/api/servicos.py`, `backend/app/api/produtos.py`, `frontend/src/app/changelog/data.ts`. Tests: backend permissão (extend/create), frontend `roles.test.ts` se existir.

- [ ] **Step 1: Testes (RED)**
  - **Backend:** achar os testes de permissão existentes (`grep -rln "servicos\|produtos\|propostas" backend/tests`) e adicionar/estender casos: um usuário com `funcao="Financeiro"` faz POST/PUT de escrita em **propostas, serviços e produtos** e recebe 2xx (hoje daria 403). Reusar fixtures/helpers do `conftest.py` (padrão de criar usuário por função + client autenticado). Se não houver teste de permissão dedicado, criar `backend/tests/test_permissao_financeiro_catalogo.py`.
  - **Frontend:** se existir `frontend/src/auth/roles.test.ts`, adicionar: `podeGerenciarPropostas({funcao:'Financeiro'})` → `true`; `podeGerenciarPropostas({funcao:'Laboratório'})` → `false`. Se não existir, criar o arquivo com esses casos (importando o helper e um User mock).
- [ ] **Step 2: Rodar e ver falhar** — `cd backend && source .venv/bin/activate && pytest <arquivos novos> -v` (403 onde espera 2xx) e `cd frontend && npx vitest run src/auth/roles.test.ts`.
- [ ] **Step 3: Implementar**
  - `frontend/src/auth/roles.ts` (linhas 27-29): `podeGerenciarPropostas` passa a:
    ```ts
    export function podeGerenciarPropostas(user: User | null): boolean {
      return isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL || user?.funcao === FUNCAO_FINANCEIRO
    }
    ```
  - `backend/app/api/propostas.py:25`: `_escrever = require_funcao("Comercial Pós-Vendas", "Administrador", "Financeiro")`
  - `backend/app/api/servicos.py:9`: `_escrita = require_funcao("Comercial Pós-Vendas", "Administrador", "Financeiro")`
  - `backend/app/api/produtos.py:9`: `_escrita = require_funcao("Comercial Pós-Vendas", "Administrador", "Financeiro")`
  - Use a string exata `"Financeiro"` (bate com `FUNCAO_FINANCEIRO` do frontend e o valor de `usuario.funcao`).
- [ ] **Step 4: Rodar e ver passar** — backend `pytest -q` (só as 4 de upload) + os novos verdes; frontend `npx vitest run src/auth && npx tsc -b --noEmit && npm run lint`.
- [ ] **Step 5: Changelog** — 1ª entrada de `frontend/src/app/changelog/data.ts`:
  ```ts
  {
    versao: '1.27.4',
    data: '28/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'A função Financeiro agora tem acesso completo a Propostas, Serviços e Produtos (ver, criar e editar), igual ao Comercial.' },
    ],
  },
  ```
- [ ] **Step 6: Verificação final** — `cd frontend && npm run build`.
- [ ] **Step 7: Commit** — `git add frontend/src/auth/roles.ts backend/app/api/propostas.py backend/app/api/servicos.py backend/app/api/produtos.py frontend/src/app/changelog/data.ts <arquivos de teste>` (explícito) && `git commit -m "feat(acesso): financeiro gerencia propostas servicos e produtos"`. Se preferir separar, um commit de código e um `docs(changelog): v1.27.4 - ...`.

---

## Self-Review
- **Cobertura:** frontend gate (cascateia menu/páginas/botões) + 3 gates backend + testes dos dois lados + changelog. ✅
- **Espelhamento:** mesma string `"Financeiro"` nos dois lados; sem gate de leitura separado (acesso total).
- **Sem migração, sem tocar outras permissões do Financeiro.**
