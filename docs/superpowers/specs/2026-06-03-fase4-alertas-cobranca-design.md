# GestorHS — Fase 4 (Alertas & Cobrança)

**Data:** 2026-06-03
**Status:** Aprovado para implementação
**Depende de:** Fase 2 (Frota: `EquipamentoCliente`, `status_calibracao`, `/equipamentos-cliente` com filtro cliente+status) e a base de auth/roles. Reusa a Frota para o drill-down.

---

## 1. Objetivo

Entregar ao Comercial Pós-Vendas uma **worklist priorizada de cobrança**: os clientes com aparelhos **vencidos ou vencendo** (próximos 90 dias), agrupados e ordenados por urgência, para que o Comercial os contate por fora (telefone/WhatsApp/e-mail). Inclui registrar o contato (data do último aviso) para acompanhar o trabalho. O v1 **não** dispara mensagens automáticas. Fecha o ciclo de negócio: alerta de vencimento → Comercial trabalha a lista.

## 2. Escopo

**Dentro:**
- Backend: `GET /alertas` (worklist agregada por cliente, paginada) e `POST /alertas/{cliente_id}/contato` (registrar contato em lote).
- Frontend: página **Cobrança** (`/app/cobranca`) com a worklist, filtros, drill-down para a Frota e botão "Registrar contato"; item de nav.

**Fora (com a fase/destino):**
- Disparo automático de mensagens (e-mail/WhatsApp).
- Histórico de contatos (guarda-se só `ult_aviso`, a última data).
- Itens vindos do portal (`solicitacoes`) → Fase 5; a worklist do v1 deriva apenas do status de calibração.

## 3. Contexto do código atual

- `app/core/calibracao.py` → `status_calibracao(prox, hoje, dias=90)` (sem_data|vencido|vencendo|em_dia). A Frota traduz o status para SQL sobre `prox_calibragem` (mesmas fronteiras).
- `app/models/equipamento_cliente.py` → `EquipamentoCliente`: `cliente` (FK), `prox_calibragem` (Date), `ativo` (bool), `status` (char A/I/M), **`ult_aviso`** (DateTime tz, hoje não exposto). `cliente_rel` (lazy joined). `Cliente` tem `nome`.
- `app/api/equipamentos_cliente.py` → padrão de lista paginada e filtro por `cliente`/`status`. Deps `get_current_usuario` / `require_funcao(...)`. `agora()` helper existe em `app/api/ordens_acoes.py` (`datetime.now(timezone.utc)`).
- Frontend: módulos de domínio em `app/<dominio>/` (`api.ts` + páginas); `Table/Badge/Button/Spinner/Input`; `useAuth`/`isAdmin`; `auth/roles.ts` (`isAdmin`, `FUNCAO_EXPEDICAO`, `podeAbrirOS`). Nav em `layout/Sidebar.tsx`; rotas em `app/routes.tsx`. Frota lê `?cliente=`/`?status=` da URL.

## 4. Backend

`app/api/alertas.py` (prefix `/alertas`, tag "alertas"). `app/schemas/alertas.py`. Registrar router em `main.py`.

### 4.1 `GET /alertas` (qualquer interno)
Query params: `q` (busca nome do cliente), `ocultar_recentes` (bool), `offset` (0), `limit` (Query(25, ge=1, le=100)).
- Base: `equipamentos_cliente` com `ativo = True`, `prox_calibragem IS NOT NULL` e `prox_calibragem <= hoje + 90` (só vencido/vencendo), join em `clientes`.
- Agrupa por `cliente, clientes.nome`. Por grupo:
  - `vencidos = sum(CASE WHEN prox_calibragem < hoje THEN 1 ELSE 0 END)`
  - `vencendo = sum(CASE WHEN prox_calibragem >= hoje THEN 1 ELSE 0 END)` (no grupo, `prox <= hoje+90` já garante a janela)
  - `prox_antiga = min(prox_calibragem)`
  - `ult_contato = max(ult_aviso)`
- `q` → `clientes.nome ILIKE %q%`. `ocultar_recentes` → `HAVING (max(ult_aviso) IS NULL OR max(ult_aviso) < hoje - 30 dias)`.
- **Ordenação:** `vencidos DESC, prox_antiga ASC`.
- `total` = nº de grupos (clientes) após filtros; `items` = página (offset/limit). Retorna `AlertaPage`.
- `hoje = date.today()`; comparações de data sobre `prox_calibragem` (Date). Para `ult_aviso` (DateTime), o corte de 30 dias usa `datetime.now(timezone.utc) - timedelta(days=30)`.

### 4.2 `POST /alertas/{cliente_id}/contato` (Comercial Pós-Vendas + Admin)
- `require_funcao("Comercial Pós-Vendas", "Administrador")`.
- 404 se o cliente não existe.
- `UPDATE equipamentos_cliente SET ult_aviso = agora()` para os do cliente com `ativo = True`, `prox_calibragem IS NOT NULL`, `prox_calibragem <= hoje+90` (mesmos elegíveis da worklist). Conta os afetados.
- Retorna `ContatoOut {cliente, atualizados, ult_contato}` (`ult_contato` = a data gravada, ou `None` se `atualizados == 0`).

### 4.3 Schemas (`app/schemas/alertas.py`)
- `AlertaItem`: `cliente: int`, `cliente_nome: str | None`, `vencidos: int`, `vencendo: int`, `prox_antiga: date | None`, `ult_contato: datetime | None`.
- `AlertaPage`: `{ items: list[AlertaItem], total: int }`.
- `ContatoOut`: `{ cliente: int, atualizados: int, ult_contato: datetime | None }`.

### 4.4 Testes (pytest, SQLite)
Fixtures: um cliente A com (2 vencidos + 1 vencendo + 1 em_dia + 1 inativo-vencido), cliente B com (1 vencido), cliente C com (1 em_dia só) — datas relativas a `date.today()`.
- Lista: A aparece com `vencidos=2, vencendo=1` (ignora em_dia, sem_data e o inativo); B com `vencidos=1`; C **não** aparece. Ordenação coloca A antes de B (mais vencidos). `total` conta os clientes com pendência.
- `q` filtra por nome; `ocultar_recentes` esconde quem tem `ult_aviso` recente (setar `ult_aviso` em A e conferir que some).
- `POST /alertas/{A}/contato` (Comercial e Admin): grava `ult_aviso` nos 3 elegíveis de A (2 vencidos + 1 vencendo), **não** no em_dia nem no inativo; `atualizados == 3`. 403 para Laboratório/Expedição/comum; 404 cliente inexistente.

## 5. Frontend

### 5.1 API + permissão
- `app/alertas/api.ts`: `AlertaItem`/`AlertaPage`/`ContatoOut`; `alertasApi.listar({q?, ocultar_recentes?, offset?, limit?})` (monta query string; `ocultar_recentes` só quando true) e `registrarContato(clienteId)` (`POST /alertas/{id}/contato`). Helper `formatData` local (ISO→pt-BR; "—" se nulo).
- `auth/roles.ts`: `FUNCAO_COMERCIAL = 'Comercial Pós-Vendas'`; `podeRegistrarContato(user) = isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL`.

### 5.2 Nav + rota
- Sidebar: item **"Cobrança"** (sem `adminOnly`) → `/app/cobranca`, ícone `IconCobranca` novo.
- Rota `cobranca` → `CobrancaPage`.

### 5.3 `CobrancaPage` (`/app/cobranca`)
- Estado: `q`/busca, `ocultarRecentes` (checkbox), `offset`, itens/total/erro (padrão das outras listas, com guarda `ativo`).
- Filtros: form de busca (nome do cliente) + checkbox "Ocultar contatados nos últimos 30 dias". Paginação 25/pág ("X–Y de N").
- Tabela: **Cliente** (nome), **Vencidos** (`Badge` danger com o número), **Vencendo** (`Badge` warning), **Venc. mais antigo** (`formatData(prox_antiga)`), **Último contato** (`formatData(ult_contato)`), **Ações**.
- Ações por linha:
  - **"Ver frota"** → `navigate('/app/frota?cliente=' + item.cliente)` (drill-down reusa a Frota).
  - **"Registrar contato"** (só se `podeRegistrarContato`) → `alertasApi.registrarContato(cliente)`; ao sucesso, atualiza a linha (`ult_contato` = retorno) localmente; erro inline.
- Vazio: "Nenhum cliente com pendências."; `Spinner` no carregamento; erros via `ApiError`.

### 5.4 Testes (Vitest)
- `alertas/api.test.ts`: `listar` monta a query (`q`/`ocultar_recentes`/`offset`/`limit`, omitindo ausentes); `registrarContato` no path `/alertas/{id}/contato` (POST); propaga `ApiError`.
- `auth/roles.test.ts` (estender): `podeRegistrarContato` true p/ admin e Comercial Pós-Vendas; false p/ Laboratório/Expedição/null.
- Telas: `tsc -b` + `lint` + `build`.

## 6. Verificação / E2E
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos.
- **E2E manual não-destrutivo**: abrir "Cobrança", conferir a lista priorizada (clientes com vencidos reais no topo), busca, "ocultar recentes", e o drill-down "Ver frota". O "Registrar contato" é escrita (`ult_aviso`) — por padrão **não** submeto; só com pedido explícito (e aviso antes de gravar).

## 7. Critérios de aceite
- Qualquer interno abre "Cobrança" e vê os clientes com aparelhos vencidos/vencendo, ordenados por urgência (mais vencidos primeiro), com contagens, vencimento mais antigo e último contato.
- Busca por cliente e "ocultar contatados (30 dias)" funcionam; "Ver frota" abre a Frota filtrada pelo cliente.
- Comercial/Admin registra contato (lote por cliente) e o "último contato" atualiza; não-autorizado não vê o botão e o backend nega (403).
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos; E2E não-destrutivo ok.

## 8. Fora de escopo (reafirmando)
Disparo automático de mensagens; histórico de contatos; `solicitacoes`/portal (Fase 5).
