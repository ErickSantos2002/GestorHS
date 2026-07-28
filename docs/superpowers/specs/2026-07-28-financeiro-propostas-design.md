# Financeiro com acesso a Propostas/Serviços/Produtos — Design

**Data:** 2026-07-28
**Área:** autorização — frontend (`auth/roles.ts`) + backend (`api/propostas.py`, `api/servicos.py`, `api/produtos.py`).
**Tipo:** mudança de permissão (pequena, espelhada nos dois lados).

## Problema

A função **Financeiro** não tem acesso a Propostas, Serviços e Produtos. Precisa ter o **mesmo acesso completo** que o Comercial Pós-Vendas já tem (ver, criar, editar).

## Estado atual

- **Frontend:** um único helper `podeGerenciarPropostas(user)` (`auth/roles.ts:27-29`) = `isAdmin || funcao === 'Comercial Pós-Vendas'` controla tudo: os 3 itens do menu (`Sidebar.tsx`), o bloqueio das páginas de catálogo (`CatalogoServicosPage`/`CatalogoProdutosPage` retornam bloqueio se `!podeGerenciarPropostas`) e as ações de escrita da `PropostasPage` (`podeEscrever`).
- **Backend:** leitura via `get_current_usuario` (qualquer usuário interno — Financeiro já lê); escrita gateada por `require_funcao("Comercial Pós-Vendas", "Administrador")` em `propostas.py` (`_escrever`), `servicos.py` (`_escrita`), `produtos.py` (`_escrita`).

## Design

Adicionar **Financeiro** ao gate de gestão, nos dois lados (o CLAUDE.md exige espelhar):

- **Frontend** (`auth/roles.ts`): `podeGerenciarPropostas` passa a incluir `FUNCAO_FINANCEIRO`. Uma linha — cascateia sozinho pro menu, páginas de catálogo e botões da PropostasPage.
- **Backend:** os 3 gates de escrita passam a `require_funcao("Comercial Pós-Vendas", "Administrador", "Financeiro")` (`propostas.py`, `servicos.py`, `produtos.py`).

Resultado: Financeiro ganha acesso **completo** (ver + criar + editar) às três áreas.

## Fora de escopo
- Não criar gate separado de leitura (é acesso total, mesmo do Comercial).
- Não mexer em outras permissões do Financeiro (NF/fase 10 continuam como estão).

## Rollout
Frontend + backend, **sem migração**. Mini versão **v1.27.4**.

## Testes
- **Backend:** um usuário `Financeiro` consegue criar/editar em propostas, serviços e produtos (endpoints de escrita retornam 2xx onde antes dariam 403).
- **Frontend:** `podeGerenciarPropostas(userFinanceiro)` retorna `true` (e continua `false` para funções sem acesso, ex.: Laboratório).

## Arquivos
Frontend: `auth/roles.ts` (+ teste se houver `roles.test.ts`). Backend: `api/propostas.py`, `api/servicos.py`, `api/produtos.py` (+ testes de permissão). Changelog v1.27.4.
