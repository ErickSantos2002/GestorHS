# Proposta: marcar como Faturada — Design

**Data:** 2026-07-28
**Área:** backend (model/schema/endpoints + migração 0022) + frontend (roles/api/PropostasPage).
**Tipo:** feature pequena com migração.

## Problema

A proposta não tem status. O **Financeiro** precisa marcar uma proposta como **Faturada**; depois de faturada, **só o Administrador** desfaz. Nada de workflow completo — só um estado booleano + selo + ação na lista. **Faturada NÃO trava a edição** (só o "desfazer" é restrito).

## Design

### Backend
- **Model `Proposta`** (+ migração **0022**, down_revision `0021_caixa_cliente_principal`): 3 colunas novas:
  - `faturada` (Boolean, `nullable=False`, `server_default false`)
  - `faturada_em` (DateTime tz, nullable)
  - `faturada_por` (String(255), nullable) — nome de quem faturou (auditoria).
- **Schema:** expor `faturada`, `faturada_em`, `faturada_por` **no `PropostaOut`** (output — vale para lista e detalhe). **Não** entram em `PropostaBase`/`PropostaCreate` (não são editáveis por criar/atualizar; só pelos endpoints abaixo).
- **Endpoints** (em `api/propostas.py`):
  - `POST /propostas/{id}/faturar` → gate `require_funcao("Financeiro", "Administrador")`. Marca `faturada=True`, `faturada_em=agora`, `faturada_por=usuario.nome`. Idempotente (se já faturada, no-op 200). Retorna `PropostaOut`.
  - `POST /propostas/{id}/desfaturar` → gate `require_funcao("Administrador")`. Marca `faturada=False`, limpa `faturada_em`/`faturada_por`. Idempotente. Retorna `PropostaOut`.

### Frontend
- **`roles.ts`:** `podeFaturarProposta(user)` = `isAdmin || funcao === Financeiro`; `podeDesfaturarProposta(user)` = `isAdmin`. (Espelham os gates do backend — regra do CLAUDE.md.)
- **`propostas/api.ts`:** tipo `Proposta` ganha `faturada`, `faturada_em`, `faturada_por`; `propostasApi.faturar(id)` e `propostasApi.desfaturar(id)` (POST, retornam a proposta atualizada).
- **`PropostasPage` (lista):**
  - Um **selo "Faturada"** (Badge tone ok) na linha quando `p.faturada` (ex.: numa coluna de status/perto do número).
  - Ação em ícone: quando **não** faturada e `podeFaturarProposta` → "Marcar como Faturada" (IconCheck, tone ok); quando **faturada** e `podeDesfaturarProposta` (Admin) → "Desfazer faturamento" (IconX, tone neutro). Quando faturada e não-admin → só o selo, sem ação. Ao clicar, chama o endpoint e recarrega a lista.

## Fora de escopo
- Travar edição/exclusão da proposta faturada (só o "desfazer" é restrito).
- Workflow de status (rascunho/andamento/etc.) — não existe e não faremos.

## Rollout
Backend + frontend. **Migração 0022** aplicar em produção (após deploy, `alembic upgrade head`). Versão **v1.29.0**.

## Testes
- **Backend:** Financeiro fatura (2xx, `faturada=True`, `faturada_por` preenchido); Comercial NÃO fatura (403) — só Fin/Admin; desfaturar: Admin ok (limpa campos), Financeiro 403 (só Admin); idempotência (faturar 2x → segue faturada; desfaturar não-faturada → no-op). `faturada` aparece em `PropostaOut`.
- **Frontend:** `podeFaturarProposta`/`podeDesfaturarProposta` retornam certo por função; na lista, proposta faturada mostra o selo; a ação de faturar chama `propostasApi.faturar`; o "desfazer" só aparece para Admin.

## Arquivos
Backend: `models/proposta.py`, `alembic/versions/0022_*.py`, `schemas/proposta.py`, `api/propostas.py`, testes. Frontend: `auth/roles.ts`, `app/propostas/api.ts`, `app/propostas/PropostasPage.tsx`, testes. Changelog v1.29.0.
