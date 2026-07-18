# Guia de integração — GestorHS cria cards no hsgrowth

Este guia tem tudo que o **GestorHS** precisa para criar cards no hsgrowth
automaticamente, em dois gatilhos: abertura de OS e calibração vencendo. É ao mesmo
tempo o **contrato** da API e o **passo a passo** de integração.

---

## Contrato é diferente do TaskHS — leia isto antes de copiar padrões

Se você já integrou o GestorHS com o TaskHS (`docs/integration.md`), o formato deste
documento vai parecer familiar de propósito — mesma estrutura, mesmo tom. Mas a
**semântica é oposta** num ponto crítico:

> **Aquele contrato é espelho; este é handoff.**
>
> No TaskHS, o GestorHS é dono da verdade: a cada mudança relevante na OS, ele reenvia
> o **estado completo**, e o upsert do TaskHS **sobrescreve** o card (atualiza campos,
> move de lista, tudo). É assim que o card no TaskHS fica sempre igual à OS.
>
> **Aqui não.** O endpoint do hsgrowth é **create-or-return**, não upsert. Depois que o
> card nasce, quem manda é o **vendedor** — o card vive no funil comercial do
> hsgrowth, com etapas e responsável dele. Reenviar o mesmo `(source, external_id)`
> **devolve o card existente e não altera absolutamente nada** nele: nem título, nem
> descrição, nem lista, nem cliente.
>
> Consequência prática: **o GestorHS deve chamar este endpoint UMA vez, no gatilho**
> (abertura da OS; calibração cruzando o limiar de 50 dias) — **não a cada atualização
> da OS**, como faz com o TaskHS. Chamar de novo é inofensivo (é idempotente), mas é
> desperdício de request: não faz nada além de devolver o card que já existe.

---

## 1. Visão geral e direção do fluxo

- **Direção:** `GestorHS → hsgrowth`. O GestorHS é quem sabe que uma OS abriu ou que
  uma calibração está próxima do vencimento; ele **empurra** essa informação como um
  card novo no funil comercial/cobrança do hsgrowth.
- **Gatilhos (só dois):**
  1. Uma **OS é aberta** → cria (ou recupera) um card no board de **Serviços**.
  2. A **calibração de um aparelho está a 50 dias de vencer** → cria (ou recupera) um
     card no board de **Cobrança**.
- **O hsgrowth nunca chama de volta nesta fase.** Não há callback nem webhook do
  hsgrowth para o GestorHS. (Isso está planejado para uma fase 2 — ver "Fora de
  escopo" no fim deste documento.)
- **Regra de negócio de calendário fica no GestorHS.** O hsgrowth não sabe o que é uma
  "OS" ou uma "calibração"; ele só sabe criar cards num board, numa etapa de entrada
  fixa. Cabe ao GestorHS decidir quando disparar.
- **Depois de criado, o card é do vendedor.** Ver o destaque acima — isto não é um
  espelho que se mantém sincronizado; é uma entrega única.

---

## 2. Base URL e autenticação

### Base URL

`HSGROWTH_BASE_URL` é a **raiz do backend**, **sem** `/api/v1` no final:

- **Local/dev:** `http://localhost:8000`
- **Produção:** `https://<dominio-do-backend-hsgrowth>`

Todo caminho deste documento é montado como `$HSGROWTH_BASE_URL/api/v1/...` — o
`/api/v1` **não** faz parte da env, aparece explícito em cada exemplo de `curl` (ex.:
`POST $HSGROWTH_BASE_URL/api/v1/integration/service-cards`). É a mesma convenção que o
GestorHS já usaria para qualquer outro endpoint do hsgrowth: uma env com a raiz, e o
path completo (incluindo `/api/v1`) visível em cada chamada. **Não** configure
`HSGROWTH_BASE_URL` já terminando em `/api/v1` — os exemplos deste documento
duplicariam o prefixo (`/api/v1/api/v1/...`) e todo `curl` bateria em `404`. **HTTPS
obrigatório em produção** — a chave viaja no header.

### Autenticação — API key

Toda requisição exige o header:

```
X-API-Key: <a chave>
```

- A chave é gerada **uma única vez** no hsgrowth, rodando (no backend do hsgrowth):

  ```bash
  cd backend && python -m scripts.provisionar_integracao_gestorhs
  ```

  A saída imprime a chave em texto puro **apenas na primeira execução**. Rodar de
  novo não reemite — imprime "já provisionado". Se perder a chave, não tem como
  recuperá-la (só é guardado o hash); é preciso desativar o client de integração e
  provisionar de novo.
- No lado do GestorHS, guarde a chave em env — **mesmo gating do `taskhs_client.py`**:
  env vazia (`HSGROWTH_BASE_URL` ou `HSGROWTH_API_KEY` ausente) = integração
  **desligada**, sem fallback inseguro, sem exceção estourando no fluxo principal.
  ```python
  def integracao_ativa() -> bool:
      return bool(settings.HSGROWTH_BASE_URL and settings.HSGROWTH_API_KEY)
  ```
- No lado do hsgrowth, a chave está associada a um `IntegrationClient` com escopo
  `service_cards:create` e a um usuário de impersonação
  (`gestorhs@integracao.local`) — é esse usuário que aparece como autor do evento
  "card criado pela integração" no histórico do card.
- Chave ausente, inválida ou de client inativo → `401`. Chave válida mas sem o
  escopo `service_cards:create` → `403`. Não existe fallback: sem chave configurada e
  correta, nenhum card é criado.
- **Rotacionar** (trocar a chave mantendo o mesmo `client_id`): no backend do
  hsgrowth, rode

  ```bash
  cd backend && python -m scripts.provisionar_integracao_gestorhs --rotate
  ```

  Isso gera uma chave nova, grava o hash dela no `IntegrationClient` existente
  (`client_id=hsg_gestorhs`) e reativa o client caso estivesse desativado. A saída
  imprime a chave nova em texto puro — copie na hora, ela não é exibida de novo.

  **A chave antiga para de autenticar no mesmo instante** — não há período de
  coexistência entre as duas. Isso significa que a troca precisa ser **coordenada**:
  rode a rotação e atualize a env `HSGROWTH_API_KEY` do GestorHS o quanto antes depois
  disso, porque qualquer requisição do GestorHS feita com a chave antiga nesse
  intervalo recebe `401`.
- **Revogar sem substituir** (parar a integração sem emitir chave nova): chame
  `POST /integration-clients/{id}/deactivate` (só admin; `{id}` é o id numérico do
  `IntegrationClient`, não o `client_id` de texto `hsg_gestorhs` — confira em
  `GET /integration-clients`) ou marque `is_active = False` direto no banco. Toda
  requisição com a chave atual passa a receber `401`, e a integração fica parada até
  alguém rodar `--rotate` (que também reativa o client) ou reativar manualmente via
  `POST /integration-clients/{id}/activate`.

---

## 3. Referência do endpoint

### `POST /integration/service-cards` — criar (ou recuperar) um card

Cria o card se `(source, external_id)` ainda não existe; se já existe, **devolve o
card existente sem alterar nada** (ver destaque no topo do documento).

**Headers:** `Content-Type: application/json`, `X-API-Key: <chave>`.

**Corpo — campos de topo:**

| Campo | Tipo | Obrigatório | Descrição |
|---|---|:---:|---|
| `source` | string, um de `"gestorhs.os"` \| `"gestorhs.calibracao"` \| `"gestorhs.atrasados"` | ✅ | Qual gatilho originou o card (ver seção 4). |
| `external_id` | string (1–100 caracteres) | ✅ | Id da entidade no GestorHS. Junto com `source`, forma a chave de idempotência. |
| `board_id` | int | ✅ | Board do hsgrowth onde o card deve nascer. O card sempre entra na etapa marcada como `is_entry_stage=true` desse board — **não há como escolher a lista diretamente**. Se o board não existir ou não tiver etapa de entrada configurada → `404`. |
| `title` | string (1–500 caracteres) | ✅ | Título do card. |
| `description` | string \| null | — | Texto livre, sem limite de tamanho. |
| `due_date` | string ISO 8601 **com hora** — `"YYYY-MM-DDTHH:MM:SS"` \| null | — | Data de vencimento do card. ⚠️ **Data pura (`"YYYY-MM-DD"`) NÃO é aceita**: o campo é `Optional[datetime]` e o Pydantic v2 recusa com *"invalid datetime separator, expected `T`"* (confirmado com um `422` real em 18/07/2026). Use `"2026-07-30T00:00:00"`. |
| `client` | objeto `IntegrationCardClient` | ✅ | Ver tabela abaixo. |
| `contact` | objeto `IntegrationCardContact` \| null | — | Pessoa de contato. Se omitido, o card não fica vinculado a nenhuma pessoa. |
| `devices` | array de `IntegrationCardDevice` \| null | — | Lista de aparelhos. Vira `business_info.equipamentos` no card (mesmo formato usado internamente pelo campo `aparelhos` do produto do card). |
| `business_info` | objeto livre (dict) \| null | — | Qualquer metadado extra que o GestorHS queira anexar ao card (ex.: id da OS, id do `equipamento_cliente`). Não tem schema fixo do lado do hsgrowth. |

**`client` (objeto, obrigatório):**

| Campo | Tipo | Obrigatório | Descrição |
|---|---|:---:|---|
| `external_id` | string (1–100) | ✅ | O `clientes.id` do GestorHS, como string. É a chave de deduplicação do cliente — **nunca** o documento (CPF/CNPJ no GestorHS é livre, sem unicidade). |
| `name` | string (1–255) | ✅ | Razão social / nome do cliente. |
| `document` | string (até 20) \| null | — | CPF ou CNPJ. |
| `email` | string (até 255) \| null | — | |
| `phone` | string (até 20) \| null | — | |
| `address` | string, sem limite \| null | — | |
| `city` | string (até 100) \| null | — | |
| `state` | string (até 2, UF) \| null | — | |

**`contact` (objeto, opcional):**

| Campo | Tipo | Obrigatório | Descrição |
|---|---|:---:|---|
| `name` | string (1–200) | ✅ (dentro do objeto) | O GestorHS só tem um contato por cliente — mande esse. |
| `email` | string (até 255) \| null | — | |
| `phone` | string (até 50) \| null | — | O GestorHS já escolhe qual telefone mandar (o hsgrowth não recebe uma lista de telefones para escolher). |

**`devices[]` (itens do array, todos os campos opcionais e sem limite de tamanho):**

| Campo | Tipo | Descrição |
|---|---|---|
| `serial_number` | string \| null | Número de série do aparelho. |
| `model` | string \| null | Modelo. |
| `alcohol_module` | string \| null | Módulo/sensor. |
| `next_recalibration_date` | string \| null | Próxima data de calibração — string livre, não validada como data pelo hsgrowth; recomenda-se `YYYY-MM-DD` por consistência. |

**Resposta — `201 Created` (card criado agora) ou `200 OK` (já existia):**

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | int | Id do card no hsgrowth. |
| `list_id` | int | Etapa (lista) atual do card. No `201` (criação), é a etapa de entrada do board. No `200` (`created: false`), é a etapa **atual** do card já existente — pode não ser mais a de entrada, se o vendedor já tiver movido o card. |
| `title` | string | |
| `external_source` | string \| null | Eco de `source`. |
| `external_id` | string \| null | Eco de `external_id`. |
| `client_id` | int \| null | Id do cliente no hsgrowth (novo ou reaproveitado). |
| `person_id` | int \| null | Id do contato no hsgrowth, se `contact` foi enviado. |
| `created` | bool | `true` = card criado agora; `false` = já existia, nada foi alterado. |

### 3.1 Exemplo — board de Serviços (`gestorhs.os`)

Disparado quando a OS é aberta.

```bash
curl -X POST "$HSGROWTH_BASE_URL/api/v1/integration/service-cards" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $HSGROWTH_API_KEY" \
  -d '{
    "source": "gestorhs.os",
    "external_id": "8842",
    "board_id": 3,
    "title": "OS #8842 · Auto Posto Bela Vista · Bafômetro SN-4471",
    "description": "Calibração periódica — equipamento chegou em 17/07.",
    "due_date": "2026-07-30T00:00:00",
    "client": {
      "external_id": "512",
      "name": "Auto Posto Bela Vista Ltda",
      "document": "12345678000199",
      "email": "financeiro@belavista.com.br",
      "phone": "11987654321",
      "address": "Rua das Palmeiras, 220",
      "city": "São Paulo",
      "state": "SP"
    },
    "contact": {
      "name": "Marcos Oliveira",
      "email": "marcos@belavista.com.br",
      "phone": "11987654321"
    },
    "devices": [
      {
        "serial_number": "SN-4471",
        "model": "Alcotest 7110",
        "alcohol_module": "M-2231",
        "next_recalibration_date": "2027-07-30"
      }
    ],
    "business_info": {
      "os_id": 8842,
      "tipo_servico": "calibracao"
    }
  }'
```

`board_id` aqui é o board de **Serviços** do hsgrowth (anote o id real — ver checklist,
seção 9).

### 3.2 Exemplo — board de Cobrança (`gestorhs.calibracao`)

Disparado pelo job diário quando `prox_calibragem` de um `equipamento_cliente` está a
50 dias de vencer.

```bash
curl -X POST "$HSGROWTH_BASE_URL/api/v1/integration/service-cards" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $HSGROWTH_API_KEY" \
  -d '{
    "source": "gestorhs.calibracao",
    "external_id": "7310:2026-09-08",
    "board_id": 5,
    "title": "Calibração vencendo · Auto Posto Bela Vista · Bafômetro SN-4471",
    "description": "Próxima calibração em 2026-09-08 (faltam 50 dias). Sem OS aberta ainda.",
    "due_date": "2026-09-08T00:00:00",
    "client": {
      "external_id": "512",
      "name": "Auto Posto Bela Vista Ltda",
      "document": "12345678000199",
      "email": "financeiro@belavista.com.br",
      "phone": "11987654321",
      "address": "Rua das Palmeiras, 220",
      "city": "São Paulo",
      "state": "SP"
    },
    "contact": {
      "name": "Marcos Oliveira",
      "email": "marcos@belavista.com.br",
      "phone": "11987654321"
    },
    "devices": [
      {
        "serial_number": "SN-4471",
        "model": "Alcotest 7110",
        "alcohol_module": "M-2231",
        "next_recalibration_date": "2026-09-08"
      }
    ],
    "business_info": {
      "equipamento_cliente_id": 7310
    }
  }'
```

`board_id` aqui é o board de **Cobrança** — um id diferente do exemplo anterior (ver
checklist, seção 9).

Os dois `curl` acima usam `due_date` **com hora**. A versão anterior deste documento
mostrava data pura (`"2026-07-30"`) e afirmava que ambos passavam — **não passavam**:
uma chamada real em 18/07/2026 devolveu `422` em `due_date`. Corrigido.

---

## 4. Os dois `source` e a formação do `external_id`

| Gatilho | Board | `source` | `external_id` |
|---|---|---|---|
| OS **liberada do laboratório** (fase 5→6) | Serviços | `gestorhs.os` | `str(ordem.id)` |
| Calibração vencendo em 50 dias | Cobrança | `gestorhs.calibracao` | `f"{equipamento_cliente.id}:{prox_calibragem:%Y-%m-%d}"` |
| **Carga única de vencidos** (backfill) | Cobrança | `gestorhs.atrasados` | `f"{cliente.id}:{data_da_carga:%Y-%m-%d}"` |

### A carga de vencidos (`gestorhs.atrasados`) é por CLIENTE, não por aparelho

As outras duas origens criam **um card por entidade** (uma OS, um aparelho). Esta cria
**um card por cliente**, com todos os aparelhos vencidos dele em `devices[]` — porque o
objetivo é *ligar uma vez* para o cliente e resolver os 20 aparelhos dele, não abrir 20
conversas. É uma carga **manual e única**, disparada por script.

A data da carga entra na chave pelo mesmo motivo da seção anterior: permitir uma segunda
leva no futuro. O efeito colateral é que **rodar a carga em duas datas diferentes cria um
card duplicado por cliente** — por isso o script do GestorHS não envia nada por padrão e
exige a flag `--enviar`.

### Por que a cobrança leva a data na chave

Calibração é **cíclica**: o mesmo aparelho (`equipamento_cliente.id`) vence de novo a
cada ciclo, e cada vencimento merece seu próprio card de cobrança — o hsgrowth precisa
poder cobrar o cliente este ano e cobrar de novo no ano que vem, como duas
oportunidades distintas.

Se o `external_id` fosse só `str(equipamento_cliente.id)` (sem a data), o card criado
para o vencimento deste ano ficaria permanentemente "ocupando" aquele par
`(source, external_id)`. No ano seguinte, quando o mesmo aparelho voltar a cruzar o
limiar de 50 dias, o job diário chamaria o endpoint de novo com o **mesmo**
`external_id` de sempre — e por ser create-or-return, o hsgrowth simplesmente
devolveria o card antigo (`created: false`, `200 OK`), sem criar nada novo. Não haveria
erro, não haveria log de falha: a chamada teria sucesso, silenciosamente, sem que
ninguém percebesse que o card novo nunca nasceu. Na prática: o cliente do ano seguinte
não entra no funil de cobrança, ninguém liga para ele, e a calibração vence sem
ninguém saber — até o cliente reclamar.

Colocar a data (`prox_calibragem`) dentro do `external_id` resolve isso: cada
vencimento gera uma chave diferente, então cada ciclo de calibração ganha o seu
próprio card, mesmo que seja sempre o mesmo aparelho e o mesmo cliente. A idempotência
continua funcionando dentro do mesmo ciclo — rodar o job diário todo dia durante os 50
dias antes do vencimento não duplica o card, porque `external_id` não muda enquanto
`prox_calibragem` não mudar.

---

## 5. Códigos de status

| Código | Quando | O que fazer |
|---|---|---|
| `201` | Card criado agora. | Seguir. Opcionalmente guardar `id`/`client_id`/`person_id` retornados, mas não é necessário — a próxima chamada usa de novo `(source, external_id)`. |
| `200` | `(source, external_id)` já existia. **Nada foi alterado.** | **Este é o caso normal de um retry idempotente — não é erro.** Seguir normalmente; não tente "corrigir" nada reenviando com dados diferentes, pois não vai ter efeito (ver destaque no topo do documento). |
| `401` | Header `X-API-Key` ausente, ou chave inválida/de client inativo. | Conferir a env `HSGROWTH_API_KEY` e se o header está sendo enviado. Não é um erro transitório — não adianta repetir sem corrigir a chave. |
| `403` | Chave válida, mas sem o escopo `service_cards:create` (ou client de integração sem usuário de impersonação associado). | Erro de configuração do lado do hsgrowth — falar com quem administra o `IntegrationClient` lá. |
| `404` | `board_id` não existe, ou existe mas nenhuma lista dele tem `is_entry_stage=true`. | Erro de configuração: conferir o `board_id` enviado e se a etapa de entrada do board foi marcada (seção 9, checklist). |
| `422` | Payload inválido — campo obrigatório faltando, string além do `max_length`, `source` fora do enum, `due_date` em formato que o parser não reconhece. | Corrigir o payload. Um `curl` deste documento que devolva `422` é bug do documento, não do seu código — reporte. |
| `5xx` | Erro transitório no hsgrowth. | Repetir depois — a chamada é idempotente, então repetir é seguro; não gera card duplicado nem sobrescreve nada. |

---

## 6. Semântica — create-or-return, não upsert

- **Identidade do card:** o par `(source, external_id)`, com restrição de unicidade no
  banco do hsgrowth (`unique_service_card_external_ref`). Não é possível ter dois
  cards com o mesmo par.
- **Create-or-return:** se o par já existe, o hsgrowth devolve o card existente
  (`200`, `created: false`) e **não toca em nada** — nem título, nem descrição, nem
  `due_date`, nem lista/etapa atual, nem cliente, nem contato. Isso vale mesmo que o
  payload da segunda chamada seja diferente do da primeira.
- **Cliente:** deduplicado por `client.external_id` (o `clientes.id` do GestorHS),
  nunca por documento — o GestorHS tem duplicatas de CPF/CNPJ no legado, e casar por
  documento juntaria clientes errados. Se o `client.external_id` já tem um cliente
  vinculado no hsgrowth, ele é reaproveitado (os dados enviados no payload **não**
  atualizam o cliente existente); senão, um cliente novo é criado.
- **Contato:** se `contact` for enviado, o hsgrowth tenta reaproveitar uma pessoa já
  existente daquele cliente (por email, senão por nome sem email cadastrado) antes de
  criar uma nova — evita duplicar contato a cada chamada. Ver docstring de
  `_resolve_person` em `integration_card_service.py` para os detalhes da regra de
  dedup, incluindo o trade-off aceito conscientemente para homônimos sem email.
- **Corrida:** duas chamadas simultâneas com o mesmo `(source, external_id)` não geram
  dois cards — a restrição de unicidade do banco resolve a corrida, e a chamada que
  perde a corrida devolve o card do vencedor (`200`, `created: false`).
- **Evento:** quando um card é criado pela integração, um evento
  `card_created` fica registrado no histórico do card, com o usuário de
  impersonação da chave como autor.

---

## 7. Onde plugar no GestorHS

### 7.1 OS liberada do laboratório → board de Serviços

> **Mudou em 18/07/2026.** Este documento dizia originalmente "na abertura da OS". O gatilho
> passou a ser a **saída do laboratório** (transição de fase 5→6), por dois motivos: a etapa
> de entrada configurada no Board 1 é "Liberados do Laboratório", e o comercial quer ver o
> serviço **pronto** (calibração feita, certificado gerado), não o trabalho entrando. O
> princípio do contrato — **uma única chamada, num gatilho só** — continua valendo.

Gatilho na transição de fase 5→6, dentro da rota `avancar`. Siga exatamente o padrão que já existe
para o TaskHS em `app/api/espelhamento.py` e é usado em `app/api/ordens.py` (função
`abrir`, hoje já chama `_agendar_espelhamento(...)` depois do commit da OS):

- **Depois do commit** da OS (nunca antes — não quer criar card para uma OS que acabou
  não sendo persistida).
- Via **`BackgroundTasks`** (o mesmo parâmetro que a rota já recebe para o TaskHS) —
  não bloqueia a resposta HTTP da abertura da OS.
- **Best-effort**: se a chamada falhar (rede, `5xx`, hsgrowth fora do ar), **logar e
  seguir** — nunca travar ou reverter a abertura da OS por causa disso. Siga o mesmo
  molde de `taskhs_client.enviar_card`:
  ```python
  def enviar_card_hsgrowth(payload: dict) -> None:
      if not integracao_ativa():
          return
      try:
          _post(payload)
      except Exception:
          logger.exception(
              "falha ao criar card no hsgrowth (external_id=%s)", payload.get("external_id")
          )
  ```
- Diferente do TaskHS: aqui só existe **um** gatilho por OS (a abertura). Não plugar em
  `avancar` nem em `cancelar` — reenviar não faz nada mesmo (seção 6), então chamar de
  novo nesses pontos seria só overhead de rede sem efeito nenhum no hsgrowth.

### 7.2 Job diário dos 50 dias → board de Cobrança

Isto **é infraestrutura nova**. Hoje o GestorHS **não tem agendador**: não há Celery,
não há APScheduler, não há cron configurado — o único mecanismo de "rodar algo fora de
uma requisição HTTP" é `BackgroundTasks` (para tarefas pós-commit, como o
espelhamento acima) e scripts manuais como `app/scripts/sincronizar_taskhs.py`
(`python -m app.scripts.sincronizar_taskhs`, disparado à mão).

Para o gatilho dos 50 dias, alguém precisa decidir e montar **um agendador de verdade**
— cron do sistema operacional/Easypanel chamando um script, um systemd timer, ou a
introdução de algo como APScheduler no processo do backend. Esse é o item de infra que
falta; não está coberto por este documento nem pelo hsgrowth.

O que **já pode ser dito com segurança sobre o job em si**: ele pode ser burro. Não
precisa de estado ("já mandei este?", "mudou desde a última vez?") nem de controle de
duplicidade do seu lado, porque a criação no hsgrowth já é idempotente (seção 6). O job
pode simplesmente:

1. Rodar uma vez por dia.
2. Varrer todos os `equipamento_cliente` ativos com `prox_calibragem` a **50 dias ou
   menos** do vencimento (ou seja: dispara todo dia enquanto o aparelho estiver dentro
   da janela, não só no dia exato em que cruza o limiar — perder o dia exato por
   qualquer motivo não é um problema).
3. Para cada um, montar o payload (seção 3.2) e chamar o endpoint.
4. Se a chamada falhar para um aparelho, logar e seguir para o próximo — o próximo
   ciclo do job tenta de novo.

Como o `external_id` já inclui a data de vencimento (seção 4), chamar todo dia durante
a janela de 50 dias não cria cards repetidos — todas as chamadas dentro do mesmo ciclo
resolvem para o mesmo `(source, external_id)` e devolvem `200`/`created: false` depois
da primeira.

---

## 8. O que a integração **não** faz

- **Não preenche produto nem serviço do catálogo do card.** O card nasce sem produto e
  sem serviço vinculado, mesmo que `devices[]` traga aparelhos. Isso é proposital, não
  uma lacuna a preencher depois: os catálogos são **incompatíveis** entre os dois
  sistemas —
  - o hsgrowth tem serviços de "Calibração 1", "Calibração 2", "Calibração 3",
    "Calibração 4", sem nenhuma regra documentada que diga qual delas corresponde a
    qual situação vinda do GestorHS;
  - não existe, hoje, nenhum serviço de **Manutenção** cadastrado no catálogo do
    hsgrowth, então uma OS de manutenção não teria para onde mapear;
  - o `Equipamento` do GestorHS não tem SKU, então não há chave de correspondência
    direta com produto do hsgrowth.

  **Consequência que a equipe precisa internalizar:** todo card criado por esta
  integração **fica travado na etapa de entrada do board** até que o vendedor preencha,
  à mão, tudo que a etapa de entrada exige para avançar (`_validate_advance` em
  `service_board_service.py`, seção "Marcar a etapa de entrada" do checklist §9) —
  produto e serviço são só parte da trava, não a trava inteira:
  - **Board de Serviços** (etapa "Dados Preenchidos"): ao menos 1 produto, ao menos 1
    serviço, `client_id` vinculado, `person_id` vinculado, e `business_info.service_type`
    preenchido (Recalibração e/ou Manutenção).
  - **Board de Cobrança** (etapa "Oportunidade Existente"): os mesmos quatro primeiros
    itens, mais `business_info.collection_type` preenchido (Tipo de cobrança — Aparelhos
    a vencer ou atrasados) no lugar de `service_type`.

  Produto/serviço são sempre manuais (ver acima). `client_id` sempre vem preenchido,
  porque `client` é obrigatório no payload (seção 3). Mas **`person_id` só vem
  preenchido se o GestorHS mandar o objeto `contact`** — se ele for omitido, o card nasce
  sem contato vinculado, e essa é mais uma trava que o vendedor precisa destravar na mão
  antes de avançar. **Recomendação: o GestorHS deve sempre mandar `contact` quando tiver
  o dado**, para não adicionar um bloqueio evitável ao que já é intencional.

  Tudo isso é proposital — decidir qual produto/serviço vender é uma decisão comercial
  (inclusive de preço) que pertence ao vendedor, não uma inferência automática que o
  sistema deveria adivinhar a partir de dados do GestorHS.
- **Não atualiza cards já criados.** Depois do `201` inicial, nenhuma chamada
  subsequente muda título, descrição, `due_date`, cliente, contato ou aparelhos do
  card. Ver o destaque no topo do documento.
- **Não move card de volta.** Se o vendedor mover o card para outra etapa, arquivar,
  ganhar ou perder, a integração nunca desfaz isso nem interfere. O hsgrowth não recebe
  nenhum sinal do GestorHS depois da criação, então não há como ele tentar mover nada.
- **Não cria board nem etapa.** `board_id` tem que apontar para um board que já existe,
  com uma lista já marcada como `is_entry_stage=true` — senão `404` (seção 5). A
  integração nunca cria board/lista sozinha.
- **Não notifica o GestorHS de volta.** Sem callback, sem webhook — pelo menos nesta
  fase (ver "Fora de escopo" no fim do documento).

---

## 9. Checklist de configuração — ponta a ponta

1. **Provisionar a chave no hsgrowth:**
   ```bash
   cd backend && python -m scripts.provisionar_integracao_gestorhs
   ```
   Copie a chave exibida — **é a única vez que ela aparece em texto puro**. Rodar de
   novo sem ter desativado o client anterior só confirma "já provisionado", sem
   reemitir.
2. **Marcar a etapa de entrada de cada board** (Serviços e Cobrança) no hsgrowth, uma
   lista por board — e tem que ser **exatamente esta lista**, não qualquer uma:
   - No board de **Serviços** (board 1): a etapa **"Liberados do Laboratório"** (`list_id=1`).
     *(Este documento dizia "Dados Preenchidos"; a configuração real, verificada em 18/07/2026, é "Liberados do Laboratório" — que vem ANTES dela no funil, então o card ainda passa pelas travas de avanço.)*
   - No board de **Cobrança** (board 2): a etapa **"Oportunidade Existente"** (`list_id=14`).
   ```bash
   curl -X PUT "$HSGROWTH_BASE_URL/api/v1/service-boards/{board_id}/lists/{list_id}" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TOKEN_DE_USUARIO_HSGROWTH" \
     -d '{"is_entry_stage": true}'
   ```
   (Esta chamada usa o **token de usuário normal** do hsgrowth — login JWT — não a
   `X-API-Key` da integração; é uma operação de configuração de board, restrita a
   quem tem acesso ao módulo de Serviços — roles `admin`, `manager` ou `service`
   [`require_service_access()`] — não pela integração.)

   **Por que o nome importa:** as regras de avanço (`_validate_advance` em
   `service_board_service.py`) reconhecem a etapa de origem **pelo nome** — "dados
   preenchidos" no board 1, "oportunidade existente" no board 2 — e é só a partir
   dessa etapa que as travas de produto/serviço/cliente/contato entram em vigor (ver
   seção 8). Marcar `is_entry_stage` numa lista **posterior** a essas (ou num board
   fora de `{1, 2}`, que não tem regras de avanço) faz o card de integração nascer
   **depois** das travas, sem nenhum erro — ele simplesmente pula a etapa em que
   ficaria parado esperando o vendedor preencher os dados.
3. **Anotar os dois `board_id`** — o do board de Serviços e o do board de Cobrança.
   São valores diferentes; confirme qual é qual antes de configurar o GestorHS.
4. **Configurar as envs no GestorHS:**
   - `HSGROWTH_BASE_URL` — base URL do backend do hsgrowth (seção 2).
   - `HSGROWTH_API_KEY` — a chave do passo 1.
   - Os dois `board_id` do passo 3, guardados em config (constantes ou env, como
     `FASE_PARA_LIST_ID` é guardado hoje para o TaskHS).
5. **Testar com `curl`** os dois exemplos da seção 3 contra o hsgrowth de
   desenvolvimento antes de ligar no fluxo real — confirme `201` na primeira chamada e
   `200`/`created: false` ao repetir a mesma chamada.
6. **Ligar no fluxo real:**
   - Plugar a chamada de `gestorhs.os` na abertura da OS (seção 7.1).
   - Montar e agendar o job diário de `gestorhs.calibracao` (seção 7.2) — lembrando
     que isto exige infraestrutura de agendamento que ainda não existe no GestorHS.

---

## Fora de escopo (fase 2)

Retorno `hsgrowth → GestorHS` quando o card é finalizado (por exemplo, para o GestorHS
saber que o orçamento foi fechado). Não implementado nesta fase. O que fica pronto
desde já para viabilizar essa fase futura: todo card criado por esta integração carrega
`external_source`/`external_id`, que é o vínculo de volta com a OS ou o
`equipamento_cliente` de origem.
