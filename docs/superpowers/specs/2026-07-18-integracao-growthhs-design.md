# Integração GestorHS → GrowthHS (cards de serviço e cobrança) — Design

**Data:** 2026-07-18
**Área:** backend (`app/integrations/`, `app/core/`, `app/scripts/`, `app/api/ordens.py`) + infra (cron)
**Contrato:** [docs/integracao-gestorhs.md](../../integracao-gestorhs.md) (idêntico nos dois repositórios)

## Problema

O GrowthHS é o CRM/funil comercial da Health Safety. Hoje nada do GestorHS chega lá: o
time comercial não sabe quais clientes estão com calibração vencida, não sabe quando um
serviço foi concluído no laboratório e não é avisado de vencimentos que se aproximam.
Tudo isso vive só no GestorHS, e a cobrança/contato acontece por memória e planilha.

## Objetivo

Empurrar informação do GestorHS para o funil do GrowthHS em **três frentes**, entregues em
etapas independentes:

1. **Backfill dos atrasados** — carga única, manual, de quem já está com calibração vencida.
2. **Serviço concluído** — quando o laboratório libera uma OS, nasce um card no board de Serviços.
3. **Vencimento se aproximando** — job diário: aparelho a 50 dias de vencer vira card de contato.

## Não-objetivos

- **Nenhum retorno GrowthHS → GestorHS** (callback/webhook). É a fase 2 do contrato.
- **Não atualizar cards já criados.** O endpoint é *create-or-return*: depois do `201`, o card
  pertence ao vendedor e nenhuma chamada posterior altera nada.
- **Não preencher produto/serviço** do catálogo do GrowthHS — é decisão comercial do vendedor
  (catálogos incompatíveis; ver §8 do contrato).
- **Não criar board nem etapa** no GrowthHS.

## Dependência externa (bloqueia só a Etapa 1)

O campo `source` é um `Literal` do Pydantic no GrowthHS
(`backend/app/schemas/integration.py:42`) e hoje aceita só `gestorhs.os` e
`gestorhs.calibracao` — qualquer outro valor devolve `422`. A Etapa 1 exige adicionar
**`gestorhs.atrasados`**. Não precisa de migração: `service_cards.external_source` é
`String(50)` sem enum de banco. As Etapas 2 e 3 usam os dois valores já existentes e **não
dependem** desse ajuste.

---

## Base comum às três etapas

### Cliente HTTP — `app/integrations/hsgrowth_client.py`

Espelha o molde já provado do `taskhs_client.py`:

- **Config:** `HSGROWTH_BASE_URL` (raiz do backend, **sem** `/api/v1`), `HSGROWTH_API_KEY`,
  `HSGROWTH_BOARD_SERVICOS` (=1) e `HSGROWTH_BOARD_COBRANCA` (=2).
- **Gating:** `integracao_ativa()` = ambas as envs preenchidas. Vazio ⇒ **no-op silencioso**
  (nasce desligada; nada quebra em dev/teste).
- **Best-effort:** exceção nunca propaga para o fluxo chamador — loga e segue.
- `POST {base}/api/v1/integration/service-cards`, headers `Content-Type: application/json` e
  `X-API-Key`.
- Trata `201` (criado) e `200` (já existia) como **sucesso**; `4xx` loga como erro de
  configuração/payload; `5xx` loga como transitório (a chamada é idempotente, então repetir
  é seguro).

### Montagem do payload — `app/core/growthhs_payload.py` (puro, sem I/O)

Funções puras, testáveis isoladamente, que transformam entidades do GestorHS no corpo do
contrato:

- `montar_cliente(cliente)` → `client{external_id=str(cliente.id), name, document=cgc or cpf,
  email, phone, address, city, state}`. **`external_id` é sempre `clientes.id`** — nunca o
  documento (CPF/CNPJ não é único no GestorHS).
- `montar_contato(cliente)` → `contact{name, email, phone}` a partir de `cliente.contato`;
  `None` se não houver nome de contato. **Sempre enviar quando existir** — sem `contact`, o
  card nasce sem pessoa vinculada e isso vira mais uma trava para o vendedor avançar.
- `montar_device(equipamento_cliente, elo)` → item de `devices[]`:
  - **Módulo de Phoebus com instalação aberta** (via `instalacoes_modulo`):
    `serial_number` = série do **Phoebus**, `model` = descrição do Phoebus,
    `alcohol_module` = série do **módulo**.
  - **Qualquer outro caso** (inclusive módulo sem elo): `serial_number` = série do próprio
    equipamento, `model` = descrição do catálogo, `alcohol_module` = `None`.
  - `next_recalibration_date` = `prox_calibragem` em `YYYY-MM-DD`.

### Constantes de domínio

`EQUIPAMENTO_PHOEBUS_ID = 36` e `EQUIPAMENTO_EBS_ID = 37` (hospedeiros, não calibram) e
`CLIENTE_ESTOQUE_HS_ID = 2` (o pool interno) passam a viver em config, junto do
`EQUIPAMENTO_MODULO_ID` que já existe — fonte única, sem número mágico espalhado.

---

## Etapa 1 — Backfill dos atrasados (script manual)

**Entrega:** `python -m app.scripts.enviar_atrasados_growthhs [--dry-run] [--pendencias CSV]`

- **Alvo:** `equipamento_cliente` com `ativo = true` e `prox_calibragem < hoje`.
- **Exclui:** `equipamento in (36, 37)` (Phoebus e EBS) e `cliente = 2` (estoque da HS).
- **Agrupamento:** **um card por cliente**, com todos os aparelhos vencidos dele em `devices[]`.
- **Volume medido (18/07/2026):** 3.007 equipamentos → **969 cards**, em 969 clientes.
- **Board:** `HSGROWTH_BOARD_COBRANCA` (2) → entra em "Oportunidade Existente".
- **Chave:** `source = "gestorhs.atrasados"`, `external_id = f"{cliente.id}:{data_da_carga:%Y-%m-%d}"`.
  A data na chave permite uma segunda leva no futuro sem cair no *create-or-return* silencioso.
- **Título:** `Calibração vencida · {cliente.nome} · {N} aparelho(s)`.
- **Descrição:** resumo — quantidade e a data do vencimento mais antigo.
- **`due_date`:** a **calibração mais antiga vencida** daquele cliente (dá urgência real no funil).
- **`business_info`:** `{"origem": "backfill atrasados", "cliente_id": …, "qtd_equipamentos": N}`.
- **Mecânica:** `--dry-run` (não envia nada), best-effort por cliente (falha em um não
  interrompe os demais), resumo no terminal e **CSV de pendências** em `docs/` (gitignored).
- **O relatório deve contar:** clientes **sem contato** (trava extra para o vendedor) e
  módulos **sem elo** (mandamos a série do módulo em vez da do aparelho).

---

## Etapa 2 — OS liberada do laboratório → board de Serviços

**Gatilho:** transição de fase **5 → 6** (Laboratório concluído) em
`POST /ordens/{id}/avancar`.

- **Onde:** em `app/api/ordens.py::avancar`, **depois do commit**, via `BackgroundTasks`,
  exatamente como o espelhamento do TaskHS já faz. Best-effort: se o GrowthHS estiver fora,
  a OS avança normalmente.
- **Escopo:** **toda** OS, inclusive de Phoebus/EBS — o gatilho aqui é "serviço entregue",
  não "calibração vencendo".
- **Board:** `HSGROWTH_BOARD_SERVICOS` (1) → entra em "Liberados do Laboratório".
- **Chave:** `source = "gestorhs.os"`, `external_id = str(ordem.id)`.
- **Título:** `OS #{id} · {cliente} · {equipamento} {série}`.
- **Descrição:** resultado do laboratório — situação da calibração, nº do certificado e
  próxima calibração.
- **`due_date`:** data da liberação **+ 2 dias** (prazo para o setor de serviços agir; sem
  prazo, ninguém corre atrás).
- **`devices[]`:** o aparelho da OS, com a regra do elo.
- **Uma chamada só por OS.** Não plugar em `abrir`, `cancelar` nem nas demais transições.

> **Desvio consciente do contrato:** o §7.1 do `integracao-gestorhs.md` manda plugar na
> **abertura** da OS. Mudamos para a **saída do laboratório** porque a etapa de entrada
> configurada no Board 1 é "Liberados do Laboratório" e porque o comercial quer ver o serviço
> **pronto** (com calibração feita e certificado gerado), não o trabalho entrando. O espírito
> do contrato — **uma única chamada, num gatilho só** — continua respeitado. O documento
> precisa ser atualizado nos dois repositórios.

---

## Etapa 3 — Job diário dos 50 dias → board de Cobrança

**Entrega:** `python -m app.scripts.enviar_vencendo_growthhs [--dias 50] [--dry-run]`,
agendado por **cron** (Easypanel/host) rodando `docker exec gestorhs-backend python -m …`
uma vez por dia.

- **Por que cron e não APScheduler:** zero dependência nova, segue a convenção que já existe
  (`criar_usuario`, `sincronizar_taskhs`, `importar_elo_modulos`), roda **uma vez** mesmo com
  várias réplicas do backend, e o job continua executável à mão quando necessário.
- **Alvo:** `equipamento_cliente` com `ativo = true` e
  `prox_calibragem BETWEEN hoje AND hoje + 50 dias`.
  **Não inclui vencidos** (`prox_calibragem < hoje`) — esse backlog é da Etapa 1; incluí-los
  aqui geraria milhares de cards por aparelho, em formato diferente do que a Etapa 1 já criou.
- **Exclui:** `equipamento in (36, 37)`, `cliente = 2` e **aparelhos com OS em andamento**
  (`os_atual` preenchido) — se o cliente já mandou o aparelho, "entre em contato" é ruído.
- **Agrupamento:** **um card por aparelho + ciclo** (≠ Etapa 1, de propósito — ver abaixo).
- **Board:** `HSGROWTH_BOARD_COBRANCA` (2).
- **Chave:** `source = "gestorhs.calibracao"`,
  `external_id = f"{equipamento_cliente.id}:{prox_calibragem:%Y-%m-%d}"`.
- **Título:** `Calibração vencendo · {cliente} · {equipamento} {série}`.
- **`due_date`:** a própria `prox_calibragem`.
- **Volume medido:** ~9 cards/dia (120–377 aparelhos/mês).
- **Job burro, sem estado:** roda todo dia sobre a janela inteira; não precisa lembrar o que
  já mandou, porque a criação é idempotente. Falha num aparelho → loga e segue para o próximo.

> **Por que aqui é por aparelho e na Etapa 1 é por cliente:** a Etapa 1 é um **retrato único**
> — agrupar por cliente é seguro porque a foto é tirada uma vez. A Etapa 3 tem **janela
> rolante**: se a chave fosse por cliente, o segundo aparelho a entrar na janela depois do
> card já existir devolveria o card antigo (`created: false`) e **nunca apareceria**, sem erro
> nenhum. Chave por aparelho+ciclo é o único formato provadamente correto aqui.

---

## Segurança

- Chave em env, **nunca** no código; HTTPS obrigatório em produção (a chave viaja no header).
- Sem env configurada, a integração fica **desligada** — sem fallback inseguro.
- Nenhum dado do GrowthHS entra no GestorHS (fluxo é só de saída), então não há superfície
  de injeção vinda de lá nesta fase.
- O payload leva dados de cliente (nome, documento, endereço, contato) para um sistema
  interno da própria empresa — mesma titularidade, sem compartilhamento com terceiros.

## Testes

- **Payload (puro):** `montar_cliente`/`montar_contato`/`montar_device` — inclusive a regra do
  elo (módulo com instalação aberta → série do Phoebus + `alcohol_module`; sem elo → série do
  módulo) e ausência de contato.
- **Cliente HTTP:** desligado sem env (não faz request); `201` e `200` tratados como sucesso;
  exceção de rede não propaga.
- **Etapa 1:** seleção respeita os três filtros (ativo, vencido, exclusões); agrupa por
  cliente; `external_id` no formato certo; `due_date` = vencimento mais antigo; `--dry-run`
  não envia nada.
- **Etapa 2:** dispara **apenas** na transição 5→6 (não em 4→5, 6→10, 10→7, 7→8 nem no
  cancelar); usa `str(ordem.id)`; falha do cliente HTTP não impede a OS de avançar.
- **Etapa 3:** janela `[hoje, hoje+50]` (não pega vencidos); pula `os_atual` preenchido; pula
  exclusões; `external_id` inclui a data do ciclo.

## Riscos

- **Volume da Etapa 1 (969 cards de uma vez).** É a escolha consciente do Erick (cobertura
  total). O `--dry-run` e o CSV existem justamente para conferir antes de abrir a torneira.
- **Card congelado.** Nada que aconteça depois na OS reflete no card. É a natureza do
  contrato; o time precisa saber disso.
- **Cards travados na etapa de entrada** até o vendedor preencher produto/serviço à mão
  (§8 do contrato). Esperado, não é bug.
- **Etapa 3 depende de infraestrutura nova (cron).** É o único item que não é código.
- **`tipo_servico` está `NULL` nas 10.598 OS legadas** (a migração não trouxe o campo). Não
  afeta a Etapa 2 (que só vale para OS novas), mas convém saber ao montar a descrição do card.

## Ordem de entrega

As três etapas são **independentes** e podem ser entregues em sequência: a base comum
(cliente HTTP + payload) sai junto com a Etapa 1; a Etapa 2 só acrescenta o gatilho no
`avancar`; a Etapa 3 acrescenta o script e o agendamento. A Etapa 1 é a única bloqueada pelo
ajuste do enum no GrowthHS.
