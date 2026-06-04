# GestorHS — Fase 5B (Portal informativo: frota, certificados, OS)

**Data:** 2026-06-04
**Status:** Aprovado para implementação
**Parte de:** Fase 5 (Portal do cliente), sub-projeto 2 de 3 — 5A auth & shell ✅ → **5B páginas informativas** → 5C solicitar recalibração.
**Depende de:** 5A (portal `/portal`, `PortalAuthProvider`, `PortalLayout`, `get_current_cliente`, `portalApi`, rotas com `EmBrevePage`). Fase 2 (`EquipamentoCliente`, `status_calibracao`), Fase 3 (`Ordem`, fases). Migração 0002 (`fases.cor`).

---

## 1. Objetivo

Substituir os placeholders "em breve" do portal por três páginas só-leitura que dão ao cliente visibilidade da própria operação: **Minha frota** (aparelhos + status de calibração), **Certificados** (nº e referência do PDF) e **Minhas OS** (fase atual). Tudo escopado ao cliente do token — isolamento de tenant é a preocupação central.

## 2. Escopo

**Dentro:**
- Backend: `GET /portal/minha-frota`, `GET /portal/certificados`, `GET /portal/minhas-os` (em `app/api/portal.py`), todos escopados pelo `cliente` do token.
- Frontend: `PortalFrotaPage`, `PortalCertificadosPage`, `PortalOSPage` (substituem os `EmBrevePage`), extensão de `portal/api.ts`.

**Fora (com a fase/destino):**
- Solicitar recalibração → **5C**.
- Upload/serving real de PDF (storage indefinido) — aqui o PDF é só um link quando `pdf_certificado` já é URL.
- Página de detalhe de OS no portal.
- Auto-atendimento de senha do cliente → Fase 6.

## 3. Contexto do código atual

- **Backend:** `app/api/portal.py` (5A) tem `me`/`resumo` com `get_current_cliente` (retorna `UsuarioCliente`; `.cliente` = tenant). `app/core/calibracao.py` → `status_calibracao(prox, hoje, dias=90)`. `EquipamentoCliente`: `cliente`, `equipamento`, `serie`, `patrimonio`, `prox_calibragem` (Date), `ult_calibragem` (Date), `ativo`, `status`, **`os_atual`** (Integer, sem FK), `calib_cert` (e demais `calib_*`). **`pdf_certificado` NÃO existe em `equipamentos_cliente`** — está em `ordens`. `EquipamentoCliente` tem `@property equipamento_descricao` (via relationship). `Ordem`: `cliente`, `equipamento_cliente`, `fase`, `tipo_servico`, `data_chegada`, `prox_calibragem`, `pdf_certificado`, props `equipamento_descricao`/`equipamento_serie`/`fase_descricao`/`fase_cor`. A frota interna (`app/api/equipamentos_cliente.py`) traduz `status` para SQL sobre `prox_calibragem` (vencido `<hoje`; vencendo `≤hoje+90`; em_dia `>hoje+90`; sem_data `is None`).
- **Frontend:** `portal/api.ts` (`portalApi.me/resumo` + tipos). `portal/routes.tsx` (5A) tem `/portal/frota|certificados|os` → `EmBrevePage` dentro do `PortalLayout`. Componentes `Table/TH/TD`, `Badge` (tones primary/warning/danger/info/neutral), `Spinner`, `Input`, `Select`, `Button`; `formatData` em `portal`? (a 5A não criou; criar/local). Padrão de lista paginada server-side (`{items,total}`, offset/limit 25). `apiJson`.

## 4. Backend (`app/api/portal.py` — estender) + `app/schemas/portal.py`

Todos os endpoints: `Depends(get_current_cliente)` e `filter(<Modelo>.cliente == cli.cliente)`. `hoje = date.today()`, `limite = hoje + timedelta(days=90)`.

### 4.1 `GET /portal/minha-frota?status=&q=&offset=&limit=`
- Base: `EquipamentoCliente` com `cliente == cli.cliente` e `ativo == True`.
- `status`: `vencido` (`prox < hoje`), `vencendo` (`hoje ≤ prox ≤ limite`), `em_dia` (`prox > limite`), `sem_data` (`prox is None`) — mesmas fronteiras da frota interna.
- `q`: `ilike` em `serie`/`patrimonio`.
- `total` = count; `items` = página (`order_by id`, offset/limit, `limit=Query(25, ge=1, le=100)`).
- Item `PortalFrotaItem { id, equipamento_descricao, serie, patrimonio, prox_calibragem, status_calibracao }` — `status_calibracao` via a `@property` do modelo (já existe).

### 4.2 `GET /portal/certificados?offset=&limit=`
- Base: `EquipamentoCliente` com `cliente == cli.cliente` e `calib_cert` não-nulo/não-vazio. `LEFT OUTER JOIN Ordem ON EquipamentoCliente.os_atual == Ordem.id` para puxar `Ordem.pdf_certificado`.
- `order_by EquipamentoCliente.ult_calibragem desc nulls last` (ou `desc()`); paginação.
- Item `PortalCertItem { equipamento_cliente, equipamento_descricao, serie, calib_cert, ult_calibragem, prox_calibragem, pdf }` — `pdf` = `Ordem.pdf_certificado` (ou `None`). Selecionar colunas explicitamente (query com tupla) para acessar o pdf do join.

### 4.3 `GET /portal/minhas-os?em_andamento=&offset=&limit=`
- Base: `Ordem` com `cliente == cli.cliente`. `em_andamento=true` → `fase.in_((4,5,6,7))`.
- `order_by id desc`; paginação.
- Item `PortalOSItem { id, equipamento_descricao, serie, fase, fase_descricao, fase_cor, tipo_servico, data_chegada, prox_calibragem, situacao }`.

### 4.4 Schemas (`app/schemas/portal.py`, acrescentar)
- `PortalFrotaItem` + `PortalFrotaPage { items, total }`.
- `PortalCertItem` + `PortalCertPage { items, total }`.
- `PortalOSItem` + `PortalOSPage { items, total }`.
- `*Item` com `from_attributes` onde mapeiam direto do modelo; o de certificados é montado manualmente (vem de uma tupla do join).

### 4.5 Testes (pytest)
Fixtures: `cliente_portal` + para o `cliente_portal.cliente`: aparelhos (1 vencido, 1 vencendo, 1 em_dia, 1 com `calib_cert`+`os_atual`→OS com `pdf_certificado="http://x/cert.pdf"`) e algumas OS (ativas e finalizada); e aparelhos/OS de **outro** cliente. `fases_seed` p/ a FK de `Ordem.fase`.
- **minha-frota:** lista só os ativos do token; `status=vencido` retorna só o vencido; `q` por série; `total` correto; **não** traz aparelho do outro cliente.
- **certificados:** lista só os com `calib_cert`; o item traz `pdf` da OS via `os_atual`; isolamento.
- **minhas-os:** lista as OS do token; `em_andamento=true` filtra 4–7; isolamento.
- Sem token de cliente → 401 nos três.

## 5. Frontend (`frontend/src/portal/`)

### 5.1 API (`portal/api.ts` — estender)
- Tipos: `PortalFrotaItem { id, equipamento_descricao, serie, patrimonio, prox_calibragem, status_calibracao }`; `PortalCertItem { equipamento_cliente, equipamento_descricao, serie, calib_cert, ult_calibragem, prox_calibragem, pdf }`; `PortalOSItem { id, equipamento_descricao, serie, fase, fase_descricao, fase_cor, tipo_servico, data_chegada, prox_calibragem, situacao }`; `*Page { items, total }`.
- `portalApi.minhaFrota({status?,q?,offset?,limit?})`, `portalApi.certificados({offset?,limit?})`, `portalApi.minhasOs({em_andamento?,offset?,limit?})` (montam query string; `em_andamento` só quando true).
- `STATUS_CALIB: Record<status, {label, tone}>` (em_dia=primary, vencendo=warning, vencido=danger, sem_data=neutral) e `TIPO_LABEL` (C/M/A) locais; `formatData` (criar em `portal/api.ts` se a 5A não deixou um exportável).

### 5.2 Páginas (substituem `EmBrevePage` nas rotas)
- **`PortalFrotaPage`** (`/portal/frota`): `Select` status (todos/em dia/vencendo/vencido/sem data) + busca (série/patrimônio) + tabela (Aparelho, Série/Patrimônio, Próx. calibração, **Badge** de status) + paginação 25 ("X–Y de N"). Padrão das listas (`useEffect` com guarda `ativo`, `Spinner`, erro inline).
- **`PortalCertificadosPage`** (`/portal/certificados`): tabela (Aparelho, Série, Nº do certificado, Última calibração, Próxima calibração, **PDF** — `<a href target=_blank>` se `pdf` começa com `http`, senão "—") + paginação. Vazio: "Nenhum certificado disponível."
- **`PortalOSPage`** (`/portal/os`): checkbox "Em andamento" + tabela (OS #, Aparelho, **Fase** com bolinha `fase_cor` + descrição, Tipo, Chegada) + paginação 25.

### 5.3 Rotas (`portal/routes.tsx`)
- Trocar os três `<Route ... element={<EmBrevePage/>}>` por `<PortalFrotaPage/>`, `<PortalCertificadosPage/>`, `<PortalOSPage/>`. Remover o `EmBrevePage` (não mais usado). Nav da 5A já aponta para os paths.

### 5.4 Testes (Vitest)
- `portal/api.test.ts` (estender): `minhaFrota`/`certificados`/`minhasOs` montam a query certa e batem nos paths; propagam `ApiError`.
- Telas: `tsc -b` + `lint` + `build`.

## 6. Verificação / E2E
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos.
- **E2E manual não-destrutivo:** logar no portal como o cliente de teste (reusar o fluxo da 5A — criar usuário-cliente de teste e remover ao fim) e abrir Minha frota (status/busca), Certificados e Minhas OS (filtro em andamento); tudo só-leitura.

## 7. Critérios de aceite
- O cliente vê Minha frota (status de calibração, filtro, busca), Certificados (nº + link de PDF quando URL) e Minhas OS (fase atual, filtro "em andamento") — só do próprio cliente.
- Isolamento garantido pelo token (`get_current_cliente`); endpoints nunca aceitam `cliente` por parâmetro; nenhum dado de outro cliente aparece.
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos; E2E ok.

## 8. Fora de escopo (reafirmando)
Solicitar recalibração (5C); upload/serving de PDF; detalhe de OS no portal; auto-atendimento de senha (Fase 6).
