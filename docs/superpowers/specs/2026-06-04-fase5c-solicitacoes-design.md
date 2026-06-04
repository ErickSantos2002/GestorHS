# GestorHS — Fase 5C (Solicitar recalibração)

**Data:** 2026-06-04
**Status:** Aprovado para implementação
**Parte de:** Fase 5 (Portal do cliente), sub-projeto 3 de 3 — 5A auth ✅ → 5B informativo ✅ → **5C solicitar recalibração** (fecha a Fase 5).
**Depende de:** 5A (portal, `get_current_cliente`, `portalApi`, `PortalLayout`), 5B (`PortalFrotaPage`), Fase 4 (`FUNCAO_COMERCIAL`, padrão de worklist interna), Fase 2 (`EquipamentoCliente`). Alembic 0001/0002 aplicadas no 9998.

---

## 1. Objetivo

Fechar o ciclo de negócio: o cliente solicita recalibração de um aparelho pelo portal; a solicitação entra numa lista interna onde o Comercial Pós-Vendas a vê e marca como atendida. A OS em si nasce depois, quando o aparelho chega (via Frota/Abrir OS) — atender a solicitação **não** cria OS.

## 2. Escopo

**Dentro:**
- Migração `0003_solicitacoes` (nova tabela) + modelo `Solicitacao`.
- Portal: `POST /portal/solicitar-recalibracao`, `GET /portal/minhas-solicitacoes`; botão na Minha frota + página "Minhas solicitações".
- Interno: `GET /solicitacoes`, `POST /solicitacoes/{id}/atender`; página `/app/solicitacoes`.

**Fora (com a fase/destino):**
- Cancelamento da solicitação pelo cliente (só pendente→atendida no v1).
- Notificação automática ao Comercial; criação automática de OS ao atender.
- Observação no botão do portal (confirmação simples, sem campo de texto).
- Storage de PDF/imagens.

## 3. Contexto do código atual

- **Backend:** Alembic em `backend/alembic/versions/` (0001, 0002); padrão `revision`/`down_revision`, `op.create_table`/`op.drop_table`. `app/api/portal.py` (5A/5B) usa `get_current_cliente` (retorna `UsuarioCliente`; `.cliente` = tenant) e filtra por `cli.cliente`. `agora()` em `app/api/ordens_acoes.py` (`datetime.now(timezone.utc)`). `require_funcao(*descricoes)` em deps. `EquipamentoCliente` (cliente, equipamento, props `equipamento_descricao`). `Cliente.nome`, `Usuario.nome`. Modelos um-por-arquivo + `__init__`. Testes pytest/SQLite (`create_all`); fixtures `cliente_portal` (empresa cgc="11222333000144" + usuário cliente1/portal123), `fases_seed`, `usuario_admin`, `usuario_comercial`, `usuario_lab`, `usuario_comum` (Expedição).
- **Frontend:** `portal/api.ts` (`portalApi.*`); `PortalFrotaPage` (lista com ações por linha); `PortalLayout` (nav Início/Minha frota/Certificados/Minhas OS — acrescentar "Solicitações"). `app/<dominio>/api.ts` + página + nav em `Sidebar.tsx` + rota em `app/routes.tsx`. `auth/roles.ts` (`isAdmin`, `FUNCAO_COMERCIAL`, `podeRegistrarContato`). Componentes `Table/Badge/Button/Spinner/Select`; `apiJson`/`apiVoid`. Padrão lista paginada.

## 4. Backend

### 4.1 Migração `0003_solicitacoes`
`backend/alembic/versions/0003_solicitacoes.py` (revision `0003_solicitacoes`, down_revision `0002_os_schema`):
- `upgrade`: `op.create_table("solicitacoes", ...)` com `id` serial PK; `cliente` Integer FK `clientes.id` NOT NULL; `equipamento_cliente` Integer FK `equipamentos_cliente.id` NOT NULL; `status` String(20) NOT NULL server_default `'pendente'`; `data_solicitacao` DateTime(timezone=True); `data_atendimento` DateTime(timezone=True) null; `atendido_por` Integer FK `usuarios.id` null; `obs` Text null.
- `downgrade`: `op.drop_table("solicitacoes")`.
- **Aplicação:** `alembic upgrade head` no 9998 **após confirmação do usuário** (operação trivial: cria tabela vazia; reversível). Verificar com `\d solicitacoes` (ou `information_schema`).

### 4.2 Modelo `Solicitacao` (`app/models/solicitacao.py`)
Campos espelhando a tabela; PK Integer. Relationships `lazy="joined"`: `cliente_rel` (Cliente), `equipamento_rel` (EquipamentoCliente), `atendente_rel` (Usuario, via `atendido_por`). Properties `cliente_nome`, `equipamento_descricao` (via `equipamento_rel.equipamento_descricao`), `atendido_por_nome`. Registrar em `app/models/__init__.py`.

### 4.3 Schemas (`app/schemas/solicitacoes.py`)
- `SolicitarIn { equipamento_cliente: int, obs: str | None = None }`.
- `PortalSolicitacaoItem { id, equipamento_cliente, equipamento_descricao, status, data_solicitacao, data_atendimento }` + `PortalSolicitacaoPage { items, total }`.
- `SolicitacaoItem { id, cliente, cliente_nome, equipamento_cliente, equipamento_descricao, status, data_solicitacao, data_atendimento, atendido_por, atendido_por_nome, obs }` + `SolicitacaoPage { items, total }`.

### 4.4 Endpoints do portal (`app/api/portal.py`, `get_current_cliente`)
- **`POST /portal/solicitar-recalibracao`** (`SolicitarIn`): carrega o `EquipamentoCliente` por id **e** `cliente == cli.cliente`; se não for do cliente → 404. Se já existe `Solicitacao` com esse `equipamento_cliente` e `status == 'pendente'` → **409** "já há uma solicitação pendente para este aparelho". Senão cria `Solicitacao(cliente=cli.cliente, equipamento_cliente=..., status='pendente', data_solicitacao=agora(), obs=...)`. Retorna `PortalSolicitacaoItem` (201).
- **`GET /portal/minhas-solicitacoes?offset=&limit=`** → `PortalSolicitacaoPage`: solicitações com `cliente == cli.cliente`, `order_by id desc`, paginado.

### 4.5 Endpoints internos (`app/api/solicitacoes.py`, prefix `/solicitacoes`)
- **`GET /solicitacoes?status=&offset=&limit=`** (`get_current_usuario`): todas; filtro `status` (pendente/atendida) opcional; ordena por (`status == 'pendente'` desc → pendentes primeiro) e `data_solicitacao desc`; paginado. Item `SolicitacaoItem`.
- **`POST /solicitacoes/{id}/atender`** (`require_funcao("Comercial Pós-Vendas", "Administrador")`): 404 se não existe; **409** se `status != 'pendente'`; seta `status='atendida'`, `atendido_por`=usuário.id, `data_atendimento=agora()`. Retorna `SolicitacaoItem`.
- Registrar o router em `main.py`.

### 4.6 Testes (pytest)
- Portal: `POST /portal/solicitar-recalibracao` cria pendente; **409** se já pendente p/ o aparelho; **404** se o aparelho é de outro cliente; `GET /portal/minhas-solicitacoes` só do token.
- Interno: `GET /solicitacoes` lista (filtro status; pendentes primeiro); `POST /atender` por Comercial e Admin muda status+atendido_por+data; **403** p/ Laboratório/Expedição/comum; **409** reatender; **404** inexistente; sem token → 401.

## 5. Frontend

### 5.1 Portal
- `portal/api.ts` (estender): `portalApi.solicitar({ equipamento_cliente, obs? })` (`POST /portal/solicitar-recalibracao`), `portalApi.minhasSolicitacoes({offset?,limit?})`; tipos `PortalSolicitacaoItem`/`Page`; mapa `STATUS_SOLIC` (pendente=warning, atendida=primary).
- `PortalFrotaPage`: coluna **Ações** com botão **"Solicitar"** por linha → `window.confirm("Solicitar recalibração deste aparelho?")` → `portalApi.solicitar({ equipamento_cliente: e.id })`; sucesso → mensagem inline "Solicitação enviada"; **409** → "Já há uma solicitação pendente".
- `PortalSolicitacoesPage` (`/portal/solicitacoes`): nav "Solicitações" no `PortalLayout`; tabela (Aparelho, Data, **Status** badge) + paginação; vazio "Nenhuma solicitação.".

### 5.2 Interno (`app/solicitacoes/`)
- `api.ts`: `solicitacoesApi.listar({status?,offset?,limit?})`, `atender(id)`; tipos `SolicitacaoItem`/`Page`.
- `auth/roles.ts`: `podeAtenderSolicitacao(user) = isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL`.
- `SolicitacoesPage` (`/app/solicitacoes`): nav **"Solicitações"** (sem `adminOnly`); `Select` de status (todas/pendentes/atendidas) + tabela (Cliente, Aparelho, Data, **Status** badge, Atendido por) + botão **"Marcar como atendida"** (só `podeAtenderSolicitacao`, só em pendentes) + link "Ver frota" (`/app/frota?cliente=ID`) + paginação. Atender atualiza a linha; erro inline.

### 5.3 Testes (Vitest)
- `portal/api.test.ts` (estender): `solicitar`/`minhasSolicitacoes` paths/método; propaga `ApiError`.
- `app/solicitacoes/api.test.ts`: `listar` monta query; `atender` faz `POST /solicitacoes/{id}/atender`.
- `auth/roles.test.ts` (estender): `podeAtenderSolicitacao` (admin/Comercial true; outras false).
- Telas: `tsc`/`lint`/`build`.

## 6. Verificação / E2E
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos.
- Migração 0003 aplicada no 9998 (com confirmação) e verificada (tabela existe).
- **E2E:** logar no portal (cliente de teste), solicitar num aparelho; no `/app` abrir Solicitações, ver a pendente, marcar como atendida. Como **escreve** no banco real, o controlador avisa antes, usa o cliente de teste e **remove as solicitações de teste ao fim** (e o usuário-cliente de teste).

## 7. Critérios de aceite
- O cliente solicita recalibração de um aparelho (409 se já pendente; só aparelho próprio) e acompanha o status em "Minhas solicitações".
- O Comercial/Admin vê as solicitações em `/app/solicitacoes` (pendentes primeiro), filtra e marca como atendida (registra quem/quando); 403 para não-autorizados; reatender → 409.
- Migração 0003 aplicada no 9998 (reversível); isolamento por token no portal.
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos; E2E ok. **Fase 5 completa.**

## 8. Fora de escopo (reafirmando)
Cancelamento pelo cliente; notificação automática; OS automática ao atender; obs no botão do portal; storage de PDF.
