# GestorHS — Caixas (agrupamento físico de OS)

**Data:** 2026-06-05
**Status:** Aprovado para implementação
**Motivação:** Espelhar o recurso de "Caixas" do sistema legado. Como a OS é aberta **por aparelho**, um cliente que envia 20 aparelhos juntos gera 20 OS. A caixa agrupa fisicamente as OS que chegaram/voltam juntas, num local só, para a equipe organizar o lote. Ao abrir a caixa no sistema, vê-se a lista de todas as OS vinculadas.

## Descoberta de contexto
- A tabela **`caixas` já existe** no banco novo (veio da migração): `id serial PK`, `data date`, `status varchar(1) CHECK (P/A/F) DEFAULT 'P'`, `obs varchar(1000)`.
- A coluna **`ordens.caixa integer` já existe** (preenchida no histórico pela migração), mas **sem FK declarada**.
- Não há modelo SQLAlchemy de `Caixa` nem endpoints/telas ainda — falta o backend e o frontend.

## Decisões-chave
- **Caixa é client-agnostic.** Uma caixa pode conter OS de **vários clientes (CNPJs diferentes)** — o agrupamento é físico (mesma origem/destino), não por cliente. Não há "cliente da caixa".
- **Identificação:** número (`id`) + `data` + `obs` livre (descrição da origem/destino, ex.: "Lote Cuiabá"). Os clientes da caixa são **derivados** das OS dentro dela.
- **Fluxo:** caixa primeiro, depois abre as OS dentro. O operador cria a caixa e vai abrindo/vinculando as OS do lote nela.
- **Status:** `P` Pendente → `A` Aberta → `F` Finalizada, **transições manuais**. Nasce **Pendente**.
- **Vínculo editável:** uma OS pode ser **desvinculada** e **movida** entre caixas.
- **Finalizada trava** novas vinculações (não aceita abrir/vincular/mover OS enquanto `F`).
- **Escopo:** só interna (`/app`). **Sem** portal do cliente.
- **Papéis:** leitura = qualquer usuário interno; escrita = **Expedição** + **Administrador** (mesma regra de abrir OS).

## Banco (migração Alembic `0004_caixas_fk`)
- `ALTER TABLE ordens ADD CONSTRAINT fk_ordens_caixa FOREIGN KEY (caixa) REFERENCES caixas(id) ON DELETE SET NULL`.
  - `ordens.caixa` permanece **nullable** (OS solta = sem caixa).
  - `ON DELETE SET NULL`: apagar uma caixa (quando permitido) solta as OS em vez de quebrar — defensivo; o app ainda bloqueia delete de caixa com OS (ver endpoints).
- **Nenhuma** coluna de cliente em `caixas`; **sem** backfill.
- `caixas` permanece como está (id/data/status/obs).
- Down-revision: a última migração aplicada no banco real (`0003_solicitacoes`). Reversível (downgrade dropa só a constraint).

## Backend

### Modelo `app/models/caixa.py`
```
Caixa(__tablename__ = "caixas")
  id     Integer PK
  data   Date
  status String(1)  # 'P' | 'A' | 'F'
  obs    String(1000) nullable

  ordens = relationship("Ordem", lazy="selectin")  # OS vinculadas

  @property total_os -> len(ordens)
  @property clientes_resumo -> lista de nomes de clientes distintos das OS (derivado)
```
- Em `app/models/ordem.py`: declarar a FK na coluna existente (`caixa = Column(Integer, ForeignKey("caixas.id"), nullable=True)`) + `caixa_rel = relationship("Caixa", lazy="joined")` e `@property caixa_obs`.

### Workflow de status `app/core/caixas_workflow.py` (helper puro)
- Constantes `PENDENTE='P'`, `ABERTA='A'`, `FINALIZADA='F'`.
- `pode_vincular(status) -> status in (P, A)` (Finalizada trava).
- Transições válidas: `P→A`, `A→F`. Função `validar_transicao(atual, novo)` levanta erro para transições inválidas.

### Schemas `app/schemas/caixas.py`
- `CaixaCreate { obs: str | None }`
- `CaixaUpdate { obs: str | None }`
- `CaixaOut { id, data, status, obs, total_os, clientes: list[str] }` (clientes = nomes distintos derivados)
- `OrdemResumoCaixa { id, cliente_nome, equipamento_descricao, equipamento_serie, fase_descricao, fase_cor }`
- `CaixaDetalhe(CaixaOut) { ordens: list[OrdemResumoCaixa] }`
- `VincularOrdemIn { ordem_id: int }`

### Endpoints `app/api/caixas.py`
Leitura: `get_current_usuario` (qualquer interno). Escrita: `require_funcao("Expedição", "Administrador")`.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/caixas?status=&q=&offset=&limit=` | Lista paginada `{items,total}`. `q` numérico = id; texto = `obs ilike`. Ordena por id desc. |
| GET | `/caixas/{id}` | Detalhe com a lista de OS vinculadas. 404 se não existe. |
| POST | `/caixas` | Cria caixa **Pendente**, `data = hoje`, `obs` opcional. Retorna `CaixaOut`. |
| PATCH | `/caixas/{id}` | Edita `obs`. |
| POST | `/caixas/{id}/abrir` | Transição `P→A`. 409 se não estiver Pendente. |
| POST | `/caixas/{id}/finalizar` | Transição `A→F`. 409 se não estiver Aberta. |
| DELETE | `/caixas/{id}` | `excluir_protegido` → 409 se houver OS vinculada. |
| POST | `/caixas/{id}/ordens` `{ordem_id}` | Vincula/**move** a OS para esta caixa (seta `ordem.caixa`). 404 OS/caixa; 409 se a caixa estiver Finalizada. **Sem** validação de cliente. Log em `logs_os`. |
| DELETE | `/caixas/{id}/ordens/{ordem_id}` | Desvincula a OS (`caixa = null`). 404 se a OS não está nesta caixa; 409 se Finalizada. Log em `logs_os`. |

### Abrir OS dentro da caixa
- `OrdemAbrirIn` ganha campo opcional `caixa: int | None`.
- O endpoint `POST /ordens` (`abrir`) passa a: se `caixa` informado, validar que a caixa existe e **não está Finalizada** (409 senão), e setar `ordem.caixa` ao criar. Sem caixa = comportamento atual intacto.
- O cliente continua derivado do `equipamento_cliente` (uma caixa pode acumular OS de clientes diferentes).

## Frontend

### Módulo `frontend/src/app/caixas/`
- **`api.ts`** (`caixasApi`): `listar({status,q,offset,limit})`, `obter(id)`, `criar({obs})`, `atualizar(id,{obs})`, `abrir(id)`, `finalizar(id)`, `excluir(id)`, `vincularOrdem(id, ordem_id)`, `desvincularOrdem(id, ordem_id)`. Tipos `CaixaListItem`, `CaixaPage`, `CaixaDetalhe`, `OrdemResumoCaixa`. Mapa `STATUS_CAIXA` (`P`→{label:'Pendente',tone:'warning'}, `A`→{label:'Aberta',tone:'info'}, `F`→{label:'Finalizada',tone:'success'}). `formatData` pt-BR.
- **`CaixasPage`** (`/app/caixas`): filtro de status + busca (id/obs) + paginação; cada linha mostra nº, data, status (badge), nº de OS, clientes resumidos, obs. Botão **Nova caixa** → modal com campo **descrição/origem** (opcional) → cria e navega ao detalhe.
- **`CaixaDetailPage`** (`/app/caixas/:id`):
  - Cabeçalho: nº da caixa, data, **badge de status**, `obs` editável (PATCH); botões de transição **Abrir caixa** (P→A) / **Finalizar** (A→F), gated Expedição/Admin e pelo status atual.
  - Lista das OS vinculadas: por linha — nº da OS (link p/ `/app/ordens/:id`), cliente, equipamento+série, badge de fase; ação **Remover** (desvincular) e **Mover** (escolher caixa destino).
  - Ações do lote (gated Expedição/Admin, desabilitadas se Finalizada):
    - **Abrir OS**: picker de aparelho buscando a frota de **qualquer cliente** (reusa `GET /equipamentos-cliente?q=`) → abre `AbrirOSModal` com a caixa pré-vinculada.
    - **Vincular OS existente**: busca OS (preferencialmente sem caixa) → vincula/move.

### Componentes existentes reaproveitados/alterados
- **`AbrirOSModal`**: aceita prop opcional `caixa?: number`; quando presente, manda `caixa` no payload de abrir. O fluxo da Frota (`EquipamentoClienteDetailPage`) continua chamando sem caixa.
- **`OrdemDetailPage`**: novo bloco/linha "Caixa" mostrando a caixa da OS (link p/ `/app/caixas/:id`) quando `ordem.caixa` existir.
- **`Sidebar`**: nova entrada de nav **"Caixas"** (visível a todos os internos; ações de escrita gated dentro das telas).
- **`roles.ts`**: reusar `podeAbrirOS` (Expedição/Admin) como guard das ações de escrita de caixa.

## Testes / verificação
- **Backend (pytest):** criar caixa (Pendente, data=hoje); transições válidas (P→A→F) e inválidas (409); `pode_vincular` trava em Finalizada; vincular OS (seta caixa, sem checar cliente); **mover** OS entre caixas; desvincular; abrir OS com `caixa` (seta) e com caixa Finalizada (409); delete protegido (409 com OS, 204 vazia); permissões (403 para função não-Expedição nas rotas de escrita); GET lista/detalhe (200 p/ qualquer interno). Helper de workflow testado isolado.
- **Frontend (vitest):** query strings/payloads do `caixasApi` (listar com filtros, criar, abrir/finalizar, vincular/desvincular). Telas via `tsc -b` + lint + build.
- **E2E manual no navegador:** criar caixa → abrir 2 OS de clientes diferentes dentro → ver os dois clientes no detalhe → mover uma OS p/ outra caixa → desvincular → finalizar (trava novas vinculações) → tentar excluir caixa com OS (409). Limpar dados de teste ao final.

## Critérios de aceite
- Existe nav "Caixas"; é possível criar uma caixa (Pendente, com descrição opcional), abrir/vincular OS de **clientes diferentes** dentro dela, ver a lista de OS com seus clientes, mover/remover OS, e percorrer Pendente→Aberta→Finalizada.
- Finalizada bloqueia novas vinculações; excluir caixa com OS dá 409.
- A FK `ordens.caixa → caixas.id` existe no banco; o detalhe da OS mostra sua caixa.
- Escrita restrita a Expedição/Admin; leitura para qualquer interno.
- pytest/vitest/tsc/lint/build verdes; E2E manual ok.

## Fora do v1 (deferidos)
- Reabrir caixa finalizada (F→A/P).
- Etiqueta/impressão da caixa.
- Caixa visível no portal do cliente.
- Fechamento automático (quando todas as OS finalizam).
- Campo de origem estruturado/buscável separado da `obs`.
