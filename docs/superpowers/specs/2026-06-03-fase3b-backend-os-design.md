# GestorHS — Fase 3B (Backend de Ordens de Serviço)

**Data:** 2026-06-03
**Status:** Aprovado para implementação
**Parte de:** Fase 3 (Ordens de Serviço), sub-projeto 2 de 5 (3A schema/migração ✅ → **3B backend OS + avanço + config função→fase** → 3C kanban → 3D formulários-portão → 3E calibração/certificado).
**Depende de:** Migração `0002_os_schema` aplicada no banco real (colunas novas de `ordens`, `fotos.os`, `fases.funcao_responsavel`; fases 4–9 redefinidas). Funções seed: Administrador(1), Expedição(2), Laboratório(3), Comercial Pós-Vendas(4).

---

## 1. Objetivo

Construir o backend da Ordem de Serviço: o motor que conduz um aparelho pelas fases Recebido → Laboratório → Pós-Vendas → Preparando Retorno → Finalizada (e Cancelada como saída lateral), com **avanço por formulário-portão** validado pela **função responsável** de cada fase. É o coração operacional do sistema. Entrega modelos, endpoints REST e regras de workflow — **sem frontend** (kanban e formulários vêm em 3C/3D). Inclui a configuração do mapa função→fase e o CRUD de funções (adiado da 1A).

## 2. Escopo

**Dentro:**
- Modelos SQLAlchemy `Ordem`, `Fase`, `LogOS`.
- Endpoints de OS: lista paginada, quadro de ativas, detalhe, abrir, avançar, cancelar, logs.
- Motor de avanço linear com portões por transição e validação por função.
- Config função→fase (`GET /fases`, `PATCH /fases/{id}`) e CRUD de `funcoes`.
- Cobertura pytest (SQLite), junto da suíte atual (74 testes).

**Fora (com a fase/destino):**
- Resultados ricos de calibração (`calib_temp/pressao/teste1-3/media/situacao`), certificado (nº/PDF), cálculo de `prox_calibragem` e espelhamento no `equipamentos_cliente` → **Fase 3E**. Na 3B a transição Laboratório→Pós-Vendas só grava `data_calibracao` + notas.
- Upload de fotos do recebimento (armazenamento de imagem ainda indefinido) → **adiado**.
- Financeiro (`valor`, `frete_envio`, `frete_retorno`, `pago`) → fora do v1 (campos mapeados, intocados).
- Todo o frontend (kanban → **3C**; formulários-portão → **3D**).
- Tabela `solicitacoes` (recalibração via portal) → **Fase 5**.

## 3. Contexto do código atual

- Backend FastAPI + SQLAlchemy 2 + Pydantic v2. Deps em `app/api/deps.py`: `get_current_usuario` (qualquer interno; 401 sem token) e `require_funcao(*descricoes)` (403 se a função do usuário não estiver na lista; 403 se sem função). `app/api/cadastros_common.py` → `excluir_protegido(db, obj)` (IntegrityError → 409 "registro em uso").
- Modelos um-por-arquivo em `app/models/`, registrados em `app/models/__init__.py`; PK Integer (mapeia o serial/bigserial do Postgres e auto-incrementa no SQLite). Routers registrados em `app/main.py`. Já existe `app/api/funcoes.py` com `GET /funcoes` (qualquer interno).
- Padrão de lista paginada server-side: `{items, total}`, `offset`/`limit` com `limit=Query(25, ge=1, le=100)`, busca `ilike`.
- Testes: SQLite in-memory com `PRAGMA foreign_keys=ON`; fixtures `client`, `db_session`, `usuario_admin`, `usuario_comum` (login/senha123). A suíte usa `create_all` dos modelos (não Alembic).

### Tabelas (já existentes no banco, pós-0002)

```
fases(id, descricao, cor char6, funcao_responsavel → funcoes)        -- 6 linhas (ids 4-9)
ordens(id, cliente → clientes NOT NULL, equipamento_cliente → equipamentos_cliente,
       fase → fases, tipo_calibragem → tipos_calibragem, caixa, checklist,
       data_solicitacao, data_envio, data_chegada, data_calibracao, data_retorno,
       data_entrega, prox_calibragem, cod_envio, cod_retorno, etiqueta,
       calib_cert, calib_temp, calib_pressao, calib_teste1, calib_teste2, calib_teste3,
       calib_teste_media, calib_situacao, pdf_certificado, certificado,
       valor NOT NULL DEFAULT 0, frete_envio NOT NULL DEFAULT 0, frete_retorno NOT NULL DEFAULT 0,
       pago bool NOT NULL DEFAULT false, recebido bool NOT NULL DEFAULT false,
       garantia bool NOT NULL DEFAULT true, situacao varchar(1) NOT NULL DEFAULT 'E' CHECK (E/C/F),
       chave, pilhas, sopradores, arquivo, obs,
       -- adicionadas em 0002:
       tipo_servico varchar(1) CHECK (C/M/A), condicao_chegada text, acessorios text,
       aceite bool NOT NULL DEFAULT false, data_aceite timestamptz)
logs_os(id, os → ordens NOT NULL, usuario → usuarios, datalog, autor varchar(1) DEFAULT '0', texto)
equipamentos_cliente(..., os_atual → ordens)   -- FK para a OS corrente
```

Fases pós-0002: 4 Recebido (Expedição), 5 Laboratório (Laboratório), 6 Pós-Vendas (Comercial Pós-Vendas), 7 Preparando Retorno (Expedição), 8 Finalizada (sem responsável), 9 Cancelada (sem responsável).

## 4. Modelos

Um arquivo por modelo em `app/models/`, registrados em `__init__.py`.

- **`Fase`** (`fases`): `id`, `descricao`, `cor`, `funcao_responsavel` (FK `funcoes.id`, nullable). `funcao_rel = relationship("Funcao", lazy="joined")`; `@property funcao_nome`.
- **`LogOS`** (`logs_os`): `id`, `os` (FK `ordens.id`), `usuario` (FK `usuarios.id`, nullable), `datalog` (DateTime tz), `autor` (String(1), default `'1'`), `texto` (Text).
- **`Ordem`** (`ordens`): mapeia a tabela inteira. Campos NOT NULL com default (`valor`/`frete_envio`/`frete_retorno`=0, `pago`/`recebido`=False, `garantia`=True, `situacao`='E', `aceite`=False) declarados com `default=` no modelo para o `create_all`/insert do SQLite funcionar. Relationships `lazy="joined"`: `cliente_rel` (Cliente), `equipamento_rel` (EquipamentoCliente), `fase_rel` (Fase). Propriedades: `cliente_nome`, `equipamento_serie`, `equipamento_descricao` (via `equipamento_rel.equipamento_descricao`), `fase_descricao`, `fase_cor`.

`fase` é a fonte da verdade do estado do workflow; `situacao` (legado) é mantido em sincronia pelo motor de avanço.

## 5. Motor de avanço

Constante de transições em `app/core/os_workflow.py` (puro e testável), mapeando fase atual → próxima fase e os efeitos do portão:

```
ABERTURA      → 4 Recebido            (Expedição/Admin)
4 Recebido    → 5 Laboratório         (Expedição/Admin)
5 Laboratório → 6 Pós-Vendas          (Laboratório/Admin)
6 Pós-Vendas  → 7 Preparando Retorno  (Comercial Pós-Vendas/Admin)
7 Prep.Retorno→ 8 Finalizada          (Expedição/Admin)
qualquer 4-7  → 9 Cancelada           (função responsável da fase atual/Admin)
```

### 5.1 Abrir (`POST /ordens`)
- Body `OrdemAbrirIn`: `equipamento_cliente` (obrig.), `tipo_servico` ∈ {C,M,A} (obrig.), `condicao_chegada?`, `acessorios?`.
- Valida que o `equipamento_cliente` existe (404 se não) e que **não há OS ativa** para ele (fase ∈ {4,5,6,7}) → senão **409** "aparelho já possui OS ativa".
- Deriva `cliente` do equipamento; cria a OS em `fase=4`, `data_chegada`=agora, `recebido`=True, `situacao`='E'.
- Após `flush`/`commit`, atualiza `equipamentos_cliente.os_atual` = id da nova OS.
- Grava `LogOS` ("OS aberta — Recebido"). Retorna 201 `OrdemOut`.

### 5.2 Avançar (`POST /ordens/{id}/avancar`)
- Body `AvancarIn`: `obs?`, `cod_retorno?`.
- 404 se OS não existe. **409** se `fase` ∉ {4,5,6,7} ("OS já encerrada").
- Autorização: a função do usuário deve ser a `funcao_responsavel` da fase **atual**, ou Administrador → senão **403**.
- Efeitos por fase atual:
  - **4→5:** (sem campos obrigatórios). Log "Encaminhado ao laboratório" (+`obs`).
  - **5→6:** `data_calibracao`=agora. Log "Calibração/manutenção concluída" (+`obs`). *(resultados ricos → 3E)*
  - **6→7:** `aceite`=True, `data_aceite`=agora. Log "Aceite registrado".
  - **7→8:** `cod_retorno` **obrigatório** (422 se ausente/vazio); `data_retorno`=agora; `situacao`='F'. Log "Postado para retorno — Finalizada (rastreio: …)".
- Cada avanço grava um `LogOS` (usuario=quem avançou, datalog=agora). Retorna `OrdemOut`.

### 5.3 Cancelar (`POST /ordens/{id}/cancelar`)
- Body `CancelarIn`: `motivo` (obrig., não-vazio → 422 se vazio).
- 404 se não existe; **409** se já em {8,9}.
- Autorização: função responsável da fase **atual** ou Administrador → senão 403.
- `fase`=9, `situacao`='C'. Grava `LogOS` ("OS cancelada: {motivo}"). Retorna `OrdemOut`.

## 6. Superfície de API

### 6.1 OS (`app/api/ordens.py`, prefix `/ordens`)

| Método | Rota | Auth | Notas |
|---|---|---|---|
| GET | `/ordens?fase=&cliente=&tipo=&q=&offset=&limit=` | interno | `{items, total}`; ordem `id desc`; `fase` filtra por id; `tipo`=tipo_servico; `q` ilike em `etiqueta`/nome do cliente **e** match exato se `q` é numérico (id); `limit`=Query(25, ge=1, le=100) |
| GET | `/ordens/quadro?cliente=` | interno | só fases 4–7, agrupadas: `list[QuadroColuna]` na ordem 4,5,6,7; sem paginação |
| GET | `/ordens/{id}` | interno | `OrdemOut`; 404 |
| GET | `/ordens/{id}/logs` | interno | `list[LogOut]` ordenado por id; 404 se OS não existe |
| POST | `/ordens` | Expedição/Admin | abrir (§5.1); 201; 404 equip.; 409 OS ativa |
| POST | `/ordens/{id}/avancar` | função fase atual/Admin | §5.2; 403/404/409/422 |
| POST | `/ordens/{id}/cancelar` | função fase atual/Admin | §5.3; 403/404/409/422 |

`q` numérico → filtra `Ordem.id == int(q)`. `q` texto → `or_(Ordem.etiqueta.ilike, Cliente.nome.ilike)` (join em Cliente).

### 6.2 Fases (`app/api/fases.py`, prefix `/fases`)

| Método | Rota | Auth | Notas |
|---|---|---|---|
| GET | `/fases` | interno | `list[FaseOut]` ordenado por id (as 6 fases) |
| PATCH | `/fases/{id}` | Admin | `FaseUpdate` `{funcao_responsavel: int|None}`; valida que a função existe (404 se não); 404 fase |

### 6.3 Funções (estende `app/api/funcoes.py`, prefix `/funcoes`)

| Método | Rota | Auth | Notas |
|---|---|---|---|
| GET | `/funcoes` | interno | (já existe) |
| POST | `/funcoes` | Admin | `FuncaoCreate` `{descricao}`; 201; 409 se descrição duplicada |
| PATCH | `/funcoes/{id}` | Admin | `FuncaoUpdate` `{descricao}`; 404; 409 duplicada |
| DELETE | `/funcoes/{id}` | Admin | `excluir_protegido` → 409 se em uso (usuário com `funcao_id` ou fase com `funcao_responsavel`); 404 |

Autorização de avanço/cancelamento: helper interno que resolve a `funcao_responsavel` da fase atual e compara com a função do usuário (ou Administrador). Não usa `require_funcao` fixo (a função exigida é dinâmica por fase).

## 7. Schemas

`app/schemas/ordens.py`:
- **`OrdemListOut`**: `id, cliente, cliente_nome, equipamento_cliente, equipamento_descricao, equipamento_serie, fase, fase_descricao, fase_cor, tipo_servico, data_chegada, prox_calibragem, situacao`.
- **`OrdemPage`**: `{items: list[OrdemListOut], total: int}`.
- **`QuadroColuna`**: `{fase: int, descricao: str, cor: str, ordens: list[OrdemListOut]}`.
- **`OrdemOut`** (detalhe): campos identificadores + datas do ciclo (`data_chegada/calibracao/retorno/aceite/prox_calibragem`) + `tipo_servico, condicao_chegada, acessorios, aceite, cod_retorno, etiqueta, recebido, situacao, obs` + nomes (`cliente_nome, equipamento_descricao, equipamento_serie, fase_descricao, fase_cor`) + campos-espelho `calib_*`/`pdf_certificado` **só-leitura** (preenchidos na 3E). `from_attributes=True`.
- **`OrdemAbrirIn`**: `equipamento_cliente: int`, `tipo_servico: Literal['C','M','A']`, `condicao_chegada: str | None`, `acessorios: str | None`.
- **`AvancarIn`**: `obs: str | None = None`, `cod_retorno: str | None = None`.
- **`CancelarIn`**: `motivo: str` (min_length=1).
- **`LogOut`**: `id, os, usuario, autor, datalog, texto`.

`app/schemas/fases.py`:
- **`FaseOut`**: `id, descricao, cor, funcao_responsavel, funcao_nome`.
- **`FaseUpdate`**: `funcao_responsavel: int | None`.
- **`FuncaoCreate`**: `descricao: str` (min_length=1); **`FuncaoUpdate`**: `descricao: str`.

`tipo_servico` validado pelo `Literal`; `*Out` com `from_attributes=True`.

## 8. Testes (pytest, SQLite, junto dos 74 atuais)

- **Fixtures:** seed das 6 fases com `funcao_responsavel` (4→Expedição, 5→Laboratório, 6→Comercial Pós-Vendas, 7→Expedição, 8/9→null); usuários por função (`usuario_expedicao`, `usuario_lab`, `usuario_comercial`) além de admin/comum; um `cliente` e um `equipamento_cliente` base; helper para criar OS em fase arbitrária.
- **Workflow puro** (`os_workflow`): mapa de próxima-fase e função exigida por fase (incl. terminais sem próxima).
- **Abrir:** sucesso → fase 4, `os_atual` setado, `cliente` derivado, log criado; 409 ao abrir 2ª OS ativa do mesmo aparelho; 404 equipamento inexistente; 403 para usuário Laboratório/comum; 201 para Expedição e Admin.
- **Avançar — cadeia feliz:** 4→5 (Expedição), 5→6 (Laboratório, seta `data_calibracao`), 6→7 (Comercial, `aceite`=True), 7→8 (Expedição, exige `cod_retorno`, `situacao`='F').
- **Avançar — erros:** 403 com função errada em cada passo; **admin override** (admin avança qualquer fase); 409 ao avançar OS em 8 ou 9; 422 sem `cod_retorno` em 7→8.
- **Cancelar:** de fases 4/5/6/7 pela função responsável e por admin (`situacao`='C', fase=9); 403 função errada; 409 se já 8/9; 422 motivo vazio.
- **Lista/quadro:** filtro por `fase`, `cliente`, `tipo`; `q` por id numérico e por nome de cliente; paginação e `total`; quadro retorna só ativas agrupadas nas 4 colunas na ordem certa.
- **Fases:** GET lista 6; PATCH `funcao_responsavel` (admin) ok, 403 não-admin, 404 função inexistente.
- **Funções:** POST/PATCH (409 duplicada), DELETE normal e **409 em uso** (usuário ou fase referenciando), 403 não-admin.
- **Logs:** listagem ordenada; 404 OS inexistente.

Meta aproximada: suíte sobe de 74 para ~110+ testes, todos verdes.

## 9. Critérios de aceite

- Abrir uma OS a partir de um `equipamento_cliente` cria em Recebido, trava duplicidade (409) e seta `os_atual`.
- A OS avança Recebido→Finalizada com a função certa em cada portão, gravando log e os campos da transição; função errada → 403; admin sempre pode; OS encerrada não avança (409).
- Cancelar leva à fase 9 com motivo logado e `situacao`='C'.
- Lista paginada com filtros e quadro de ativas agrupado funcionam.
- Admin configura `funcao_responsavel` por fase e gerencia funções (CRUD com proteção de exclusão).
- `pytest` verde (suíte ampliada); nada do frontend nem dos campos de 3E/financeiro é tocado.

## 10. Fora de escopo (reafirmando)
Resultados ricos de calibração/certificado/espelhamento (3E); upload de fotos; financeiro; frontend (3C/3D); `solicitacoes` (Fase 5).
