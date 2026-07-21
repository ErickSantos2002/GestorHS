# Logs de Integração — design

**Data:** 2026-07-21
**Status:** aprovado (brainstorming)

## Problema

As integrações de saída do GestorHS (espelhamento no TaskHS e cards no GrowthHS)
são *best-effort* e disparam em background. Quando dão certo, ninguém vê; quando
falham — ou quando nem rodam (no-op por integração desligada) — o único rastro é
um `logger.exception` no stdout do container, que no Easypanel é efêmero, sem
busca boa e misturado a todo o resto.

Foi exatamente esse o modo de falha do incidente de 21/07/2026: a OS 10853 saiu do
laboratório mas não gerou card no GrowthHS porque as variáveis `HSGROWTH_*` não
estavam configuradas em produção — um **no-op silencioso**, invisível até alguém
reparar na ausência do card. Falta um lugar para ver o que subiu, o que falhou e o
que foi pulado.

## Objetivo

Uma **página interna separada** ("Logs de Integração") onde o Administrador vê,
filtra e reenvia os eventos de integração — sucesso, erro e pulado —, cobrindo
GrowthHS e TaskHS num só lugar.

## Decisões (brainstorming)

- **Escopo:** todas as integrações de saída — card de OS do GrowthHS, jobs de
  vencendo/atrasados do GrowthHS e espelhamento de OS no TaskHS.
- **Eventos registrados:** `sucesso`, `erro` e `pulado` — inclusive o pulo por
  integração desligada (completude total, aceitando o ruído de linhas repetidas
  enquanto uma chave não estiver configurada).
- **Reenviar:** já no v1, botão por linha.
- **Acesso:** só função `Administrador` (ver e reenviar).
- **Retenção:** guardar tudo por ora — sem expurgo automático no v1.

## Abordagem escolhida (1 de 3)

Registrar no **choke point dos clientes** (`taskhs_client` / `hsgrowth_client`),
que são o funil por onde passa *todo* envio — avanço de OS, jobs, backfill e
reenvio manual. Um helper único grava a linha; a linha **guarda o payload
enviado**, e o reenviar apenas **re-posta esse payload** pelo cliente
correspondente — uniforme, à prova de tipo de card e idempotente (GrowthHS é
create-or-return, TaskHS é upsert).

Alternativas descartadas:
- **Instrumentar em cada gatilho (orquestração):** mais contexto, porém
  espalhado por vários call sites (fácil esquecer um) e reenvio precisaria
  re-derivar o card por tipo.
- **Não guardar payload, re-derivar no reenviar:** menos armazenamento e sem PII
  na tabela, mas exige uma função de "remontar" por tipo de card — mais escopo e
  o ponto mais frágil.

Contrapartida aceita: o `payload` guardado contém PII do cliente (nome/telefone/
documento). É uma tabela interna, acesso só Admin — aceitável. O reenvio usa o
payload da época (não re-deriva dados novos), o que é benigno porque os endpoints
são upsert / create-or-return.

## Seção 1 — Modelo de dados + ponto de captura

**Tabela `log_integracao`** (migração Alembic `0018`):

| Campo | Tipo | Papel |
|---|---|---|
| `id` | PK | |
| `criado_em` | datetime (index, default agora) | ordenação/filtro por data |
| `integracao` | str | `taskhs` \| `growthhs` |
| `tipo` | str | `os_card`, `os_espelho`, `vencendo`, `atrasados` — derivado do `source` do payload |
| `external_id` | str, nulo | chave do card (ex.: `"10853"`) |
| `referencia_os` | int, nulo | id da OS quando houver (linka pra OS na tela) |
| `status` | str | `sucesso` \| `erro` \| `pulado` |
| `motivo` | str, nulo | quando pulado/erro: `desligado`, `sem_equipamento`, etc. |
| `http_status` | int, nulo | código HTTP da resposta |
| `resposta` | text, nulo | corpo da resposta ou mensagem de erro (truncado) |
| `payload` | JSON, nulo | o payload enviado — é o que permite o reenviar |

**Ponto de captura:** helper único `registrar_log_integracao(...)` que **abre
sessão própria** (`SessionLocal`) e grava a linha — *best-effort absoluto*, num
`try/except` que nunca propaga. Chamado:

- **Dentro do `enviar_card` / `enviar_card_sync`** dos dois clientes — cobre
  `sucesso`, `erro` e `pulado(desligado)` de forma uniforme, sem mudar a
  assinatura pública (a `integracao` vem do módulo; o `tipo` é derivado de
  `payload["source"]`). Para isso, o `_post` passa a capturar status HTTP + corpo
  da resposta.
- **Nos pontos de pulo-por-dado** (ex.: `agendar_card_os` quando a OS não tem
  equipamento vinculado) — chamada explícita com `status=pulado`,
  `motivo=sem_equipamento`, `payload=None`.

Consequência: linhas com `payload=None` (pulo por dado) **não** têm botão de
reenviar — precisam corrigir o dado e re-disparar. As demais (erro /
pulado-desligado, que têm payload) são reenviáveis.

## Seção 2 — API (backend)

Router novo `logs_integracao.py`, registrado em `main.py`, **todo gateado por
`require_funcao("Administrador")`**.

**`GET /logs-integracao`** — lista paginada (`offset`/`limit`,
`LogsPage{items,total}`), ordem decrescente por `criado_em`. Filtros por query
string:
- `integracao` (`taskhs`/`growthhs`), `status` (`sucesso`/`erro`/`pulado`),
  `tipo`, `os` (referencia_os) e `q` (busca em external_id/resposta).

A resposta inclui um **cabeçalho de estado da config** —
`{ taskhs_ativo: bool, growthhs_ativo: bool }`, calculado de `integracao_ativa()`
de cada cliente. É o que materializa na tela o aviso "integração desligada" sem
depender de linha nenhuma.

**`POST /logs-integracao/{id}/reenviar`** — reenvio:
1. Carrega a linha. Sem `payload` → **409** ("linha sem payload, não é reenviável").
2. Re-posta via `enviar_card_sync(payload)` do cliente correspondente (propaga
   erro, diferente do best-effort).
3. **Grava uma nova linha de log** com o resultado do reenvio (o próprio reenvio
   fica auditado, inclusive se falhar de novo).
4. Retorna a nova linha (status/erro), para a tela atualizar na hora.

Idempotência: GrowthHS é create-or-return e TaskHS é upsert — reenviar nunca
duplica; no pior caso reescreve/retorna o mesmo card.

Schemas em `schemas/` (`LogIntegracaoOut`, `LogsPage`, `ReenvioOut`). Nenhuma
lógica de negócio nova em `core/` além do helper de registro.

## Seção 3 — Frontend

Módulo novo `src/app/integracao/` com a página **"Logs de Integração"**, sob a
árvore `/app`, **só para Administrador**:

- **Rota + sidebar:** entrada nova em `routes.tsx`/`App.tsx` (lazy) e item no
  menu, visível só para Admin. O espelho da regra vai em `auth/roles.ts` (ex.:
  `podeVerLogsIntegracao`), mantendo os dois lados em sincronia (CLAUDE.md).
- **Topo — faixa de estado:** dois selos vindos do cabeçalho do endpoint —
  `GrowthHS: ativo/desligado` e `TaskHS: ativo/desligado`.
- **Filtros:** barra reusando os componentes de UI existentes (`SearchBar`,
  selects) — integração, status, tipo e busca por OS/external_id.
- **Tabela:** data/hora · integração · tipo · OS (link para `/app/ordens/:id`
  quando houver) · **status como badge** (verde sucesso / vermelho erro / cinza
  pulado) · motivo/erro resumido.
- **Linha expansível:** abre para ver `payload` e `resposta` completos (o detalhe
  técnico para diagnóstico).
- **Botão "Reenviar":** só nas linhas elegíveis (erro / pulado-desligado com
  payload). Chama `POST .../reenviar`, mostra o resultado e recarrega a lista.
  Escondido/desabilitado nas linhas sem payload.
- **Cliente HTTP:** métodos novos seguindo o padrão do projeto (ex.: `api.ts` do
  módulo, como a frota): `listar(filtros)` e `reenviar(id)`.

## Seção 4 — Tratamento de erro + testes

**Tratamento de erro:**
- O helper de log é *best-effort absoluto*: sessão própria + `try/except` que
  engole tudo. Falha ao gravar log não afeta envio nem avanço de OS.
- Sessão isolada (`SessionLocal` novo) evita sujar a transação da request/
  BackgroundTask (o avanço da OS já foi commitado antes do envio best-effort).
- No reenviar, o `enviar_card_sync` propaga de propósito; o endpoint captura,
  grava a linha do resultado e devolve — o erro vira dado, não 500.

**Testes (TDD, SQLite in-memory como o resto do backend):**
- **Helper:** grava linha com os campos certos; falha de escrita não propaga.
- **Clientes:** `enviar_card` loga `sucesso` (mock 2xx), `erro` (mock 4xx/rede,
  com http_status+corpo) e `pulado(desligado)` (`integracao_ativa=False`) — para
  os dois clientes.
- **Pulo-por-dado:** `agendar_card_os` sem equipamento grava `pulado/
  sem_equipamento` com `payload=None`.
- **Endpoint lista:** filtros (integracao/status/tipo/os), cabeçalho de estado
  ativo/desligado, e gating Admin (403 para não-admin).
- **Endpoint reenviar:** re-posta e grava nova linha; linha sem payload → 409;
  gating Admin; idempotência (mock create-or-return).
- **Frontend (Vitest):** badges por status, faixa de estado, botão reenviar só em
  linha elegível e chamando a API.

## Fora de escopo (YAGNI)

Expurgo automático de logs, métricas/gráficos, alertas, reenvio em lote.
