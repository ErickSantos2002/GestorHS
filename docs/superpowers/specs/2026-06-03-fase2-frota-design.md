# GestorHS — Fase 2 (Equipamentos do cliente / Frota)

**Data:** 2026-06-03
**Status:** Aprovado para implementação
**Depende de:** Fase 1 completa (na `main`) — clientes, catálogo de equipamentos, acesso. Reusa `crudClient`/`useCrud`, lista+busca+paginação, `excluir_protegido`, gating por função.

---

## 1. Objetivo

Gerir a **frota física** de bafômetros de cada cliente (`equipamentos_cliente`, 8.548 instâncias) e expor o **status de calibração** de cada aparelho — em dia, vencendo, vencido ou sem data. É onde o sistema começa a entregar o valor central de negócio: enxergar os ~5.037 aparelhos vencidos. Entrega lista filtrável (cliente + status) com busca, detalhe com status calculado, histórico de movimentação e CRUD.

## 2. Escopo

**Dentro:** lista da frota (filtros por cliente e por status de calibração + busca por série/patrimônio, paginada), detalhe do aparelho (campos + status calculado + resultados-espelho da última OS, só-leitura + histórico de movimentação), CRUD de instâncias.

**Decisões:**
- **Status de calibração (4 estados, calculado no servidor)** a partir de `prox_calibragem`: `vencido` (prox < hoje), `vencendo` (hoje ≤ prox ≤ hoje+90), `em_dia` (prox > hoje+90), `sem_data` (prox nulo). Janela de 90 dias.
- **Permissão:** leitura (`GET`) para qualquer interno autenticado; escrita (`POST`/`PATCH`/`DELETE`) só Administrador. Nav "Frota" visível a todos os internos.
- **Campos-espelho** da última OS (`calib_cert, calib_temp, calib_pressao, calib_teste1/2/3, calib_teste_media, calib_situacao`) e `os_atual` são **só-leitura** (preenchidos pela OS na Fase 3) — exibidos no detalhe, não editáveis.
- **Criar exige contexto de cliente** (`/app/frota/novo?cliente=ID`, aberto a partir da frota filtrada de um cliente) — evita um seletor de 1.833 clientes.
- **Guarda de exclusão:** excluir um aparelho com histórico/OS referenciando → **409 "registro em uso"**.

**Fora (com a fase de destino):**
- Atalhos para certificados e OS do aparelho → Fase 3 (esses módulos ainda não existem).
- Edição dos campos-espelho `calib_*` / `os_atual` → preenchidos pelo fluxo de OS (Fase 3).
- Worklist priorizada de cobrança → Fase 4 (esta fase só expõe o status; a worklist agrega).
- Disparo de avisos (`ult_aviso`) → fora do v1.

## 3. Contexto do código atual

- Backend FastAPI + SQLAlchemy 2 + Pydantic v2. Deps `get_current_usuario` (qualquer interno; 401 sem token) e `require_funcao("Administrador")` (403 se não-admin). `app/api/cadastros_common.py` → `excluir_protegido(db, obj)` (IntegrityError → 409). Modelos existentes: `Cliente`, `Equipamento` (catálogo), e os demais. Routers registrados em `app/main.py`. Teste: SQLite in-memory com `PRAGMA foreign_keys=ON`; fixtures `client`, `db_session`, `usuario_admin` (admin/senha123), `usuario_comum` (comum/senha123).
- Frontend React 19 + Vite 8 + Tailwind v4. Reusa `Table/TH/TD`, `Modal`, `Button`, `Input`, `Select`, `Badge`, `Spinner`; `apiJson`/`apiFetch`/`ApiError`; `useAuth`/`isAdmin`; `crudClient`/`useCrud`; `equipamentosApi` (catálogo) de `app/cadastros/api.ts`; `ClienteDetailPage` (a ganhar o link de frota). Sidebar filtra por `adminOnly` (itens sem a flag aparecem a todos). Padrão de lista paginada + página de detalhe já estabelecido (clientes).

### Tabelas (já existentes no banco)

```
equipamentos_cliente(id, cliente→clientes NOT NULL, equipamento→equipamentos NOT NULL, modulo,
                     serie, patrimonio, datacompra, ult_calibragem, prox_calibragem, ult_aviso,
                     ativo, status char(1) IN ('A','I','M'), os_atual,
                     calib_cert, calib_temp, calib_pressao, calib_teste1, calib_teste2,
                     calib_teste3, calib_teste_media, calib_situacao)
historico_equipamentos(id, equipamento_cliente→equipamentos_cliente NOT NULL, datamov, saida, entrada)
```

## 4. Backend

Modelos novos `EquipamentoCliente` e `HistoricoEquipamento` (um arquivo por modelo). Helper de status em `app/core/calibracao.py` (puro e testável). Schemas em `app/schemas/frota.py`. Routers `app/api/equipamentos_cliente.py` (e o histórico no mesmo router). Registrar em `app/main.py`.

### 4.1 Status de calibração

`app/core/calibracao.py`:
```python
def status_calibracao(prox, hoje, dias=90) -> str
```
Retorna `"sem_data"` se `prox` é `None`; `"vencido"` se `prox < hoje`; `"vencendo"` se `prox <= hoje + dias`; senão `"em_dia"`. O modelo `EquipamentoCliente` expõe `@property status_calibracao` usando `date.today()`, e `@property cliente_nome` / `equipamento_descricao` via relationships `lazy="joined"`. O filtro por status na lista traduz para SQL sobre `prox_calibragem` (mesmas fronteiras), com `hoje = date.today()`.

### 4.2 Rotas

| Método | Rota | Autorização | Notas |
|---|---|---|---|
| GET | `/equipamentos-cliente?cliente=&status=&q=&offset=&limit=` | qualquer interno | `{items: FrotaListOut[], total}`; `status` ∈ {em_dia,vencendo,vencido,sem_data}; `q` ilike série/patrimônio; `cliente` filtra por FK; limit padrão 25, máx 100 |
| GET | `/equipamentos-cliente/{id}` | qualquer interno | `EquipamentoClienteOut` completo; 404 |
| POST | `/equipamentos-cliente` | Administrador | requer `cliente` e `equipamento`; 201 |
| PATCH | `/equipamentos-cliente/{id}` | Administrador | parcial; só campos editáveis (não `calib_*`/`os_atual`) |
| DELETE | `/equipamentos-cliente/{id}` | Administrador | `excluir_protegido` → 409 se em uso |
| GET | `/equipamentos-cliente/{id}/historico` | qualquer interno | lista `HistoricoOut`; 404 se aparelho não existe |

### 4.3 Schemas

- **`FrotaListOut`** (lista): `id, cliente, cliente_nome, equipamento, equipamento_descricao, serie, patrimonio, prox_calibragem, ativo, status, status_calibracao`.
- **`FrotaPage`**: `{ items: list[FrotaListOut], total: int }`.
- **`EquipamentoClienteOut`** (detalhe): todos os campos editáveis + `cliente_nome`, `equipamento_descricao`, `status_calibracao`, e os campos-espelho `calib_*` + `os_atual` (read).
- **`EquipamentoClienteCreate`**: `cliente: int` (obrig.), `equipamento: int` (obrig.), `modulo` (default 0), `serie?`, `patrimonio?`, `datacompra?`, `ult_calibragem?`, `prox_calibragem?`, `ativo` (default true), `status` (default "A").
- **`EquipamentoClienteUpdate`**: todos opcionais — `equipamento?, modulo?, serie?, patrimonio?, datacompra?, ult_calibragem?, prox_calibragem?, ativo?, status?` (NÃO inclui `cliente`, `calib_*`, `os_atual`).
- **`HistoricoOut`**: `id, equipamento_cliente, datamov, saida, entrada`.

`status` (A/I/M) validado contra o conjunto; `*Out` com `from_attributes=True`.

## 5. Frontend

- **Nav:** item **"Frota"** (sem `adminOnly`) → `/app/frota`, ícone novo. **`ClienteDetailPage`** ganha um link/botão "Ver frota deste cliente" → `/app/frota?cliente=ID` (e o botão "Novo aparelho" leva a `/app/frota/novo?cliente=ID`).
- **`FrotaPage`** (`/app/frota`): filtro de **status** (dropdown: todos / em dia / vencendo / vencido / sem data) + **busca** (série/patrimônio) + paginação (25/pág, "X–Y de N"). Lê `?cliente=ID` da URL; se presente, mostra um chip "Cliente — limpar" e filtra. Tabela: descrição do aparelho, cliente, série/patrimônio, próx. calibração, **`Badge` de status** (em_dia=primary, vencendo=warning, vencido=danger, sem_data=neutral). Linha → `/app/frota/:id`. "Novo aparelho" só admin: se há `?cliente`, vai p/ `/app/frota/novo?cliente=ID`; sem cliente, o botão fica desabilitado com dica "filtre por um cliente".
- **`EquipamentoClienteDetailPage`** (`/app/frota/:id` e `/app/frota/novo`): form com `Select` de equipamento (catálogo), série, patrimônio, módulo, datas (compra/última/próxima calibração), `Select` de status (Ativo/Inativo/Manutenção), ativo; **badge de status calculado**; bloco só-leitura "Última calibração" com os `calib_*` (se houver); **sub-lista de histórico**. Criar: lê `?cliente=ID` (mostra o nome do cliente fixo); sem `?cliente`, exibe aviso "abra a partir da frota de um cliente". Não-admin: campos desabilitados, sem salvar/excluir.
- **API** `app/frota/api.ts`: `equipamentosClienteApi` (`listar({cliente,status,q,offset,limit})`, `obter`, `criar`, `atualizar`, `excluir`, `historico(id)`). Reusa `apiJson`/`apiVoid`.
- Erros (incl. 409) inline; exclusão via `window.confirm`.

## 6. Testes

- **Backend (pytest, SQLite, junto dos atuais):**
  - `status_calibracao` (helper puro): casos vencido/vencendo/em_dia/sem_data e bordas (`prox == hoje` → vencendo; `prox == hoje+90` → vencendo; `prox == hoje+91` → em_dia).
  - Lista: filtro por `cliente`; por `status` (cada faixa retorna os aparelhos certos — montar fixtures com datas relativas a hoje); busca por série/patrimônio; `total` reflete o filtro.
  - Permissão: GET liberado a `usuario_comum` (200); POST/PATCH/DELETE → 403.
  - CRUD; 404; PATCH não altera `calib_*`/`os_atual`; delete-em-uso (com histórico) → 409.
  - Histórico por aparelho; aparelho inexistente → 404.
- **Frontend (Vitest+RTL):** `frota/api.ts` — `listar` monta a query string (`cliente`/`status`/`q`/`offset`/`limit`); `historico` no path certo; propaga `ApiError`. Telas por `tsc -b` + `lint` + E2E manual.

## 7. Critérios de aceite

- Qualquer interno abre "Frota", filtra por status (vê os vencidos), busca por série/patrimônio, abre um aparelho e vê: status calculado (badge), datas, resultados da última OS (se houver, só-leitura) e histórico.
- Do detalhe do cliente, "Ver frota deste cliente" abre `/app/frota?cliente=ID` já filtrado.
- Admin cria um aparelho a partir de um cliente (`/app/frota/novo?cliente=ID`), edita e exclui; excluir com histórico → **409**.
- O filtro de status no backend e o `status_calibracao` exibido concordam (mesmas fronteiras).
- `pytest` e `npm run test` verdes; `tsc -b`, `lint`, `build` limpos; E2E manual contra o banco real (8.548 aparelhos; filtro "vencido" mostra a grande maioria).

## 8. Fora de escopo (reafirmando)
Atalhos para certificados/OS do aparelho; edição dos campos-espelho/`os_atual`; worklist priorizada de cobrança (Fase 4); disparo de avisos; seletor global de clientes para criação (usa contexto via `?cliente`).
