# Job de calibração vencendo: mensal e por cliente — Design

**Data:** 2026-07-27
**Área:** backend (`app/core/growthhs_vencendo.py`, `app/core/agendamento.py`, `app/scripts/enviar_vencendo_growthhs.py`, `app/tarefas/vencendo.py`, `app/core/config.py`) + docs
**Contexto:** ajuste do job dos 50 dias (Etapa 2 da integração com o GrowthHS, v1.20.x, em produção). **Troca a cadência de diária para mensal** e **o card de por-aparelho para por-cliente**.

## Problema

O job cria **um card por aparelho**, todo dia, sobre uma janela rolante de 50 dias. Um cliente com 5 aparelhos vencendo no mesmo mês, em dias diferentes, vira **5 cards em 5 dias diferentes**.

Na prática o comercial cobra **todos os aparelhos do cliente na primeira ligação**. Os cards seguintes chegam depois de o assunto já estar resolvido e obrigam a repetir o mesmo trabalho de fechamento em cada um — ruído puro, e um ruído que cresce com o tamanho do cliente.

## Objetivo

**Um card por cliente por mês de vencimento**, listando todos os aparelhos daquele cliente que vencem naquele mês, criado numa **passada mensal** — no dia 1, às 8h, cobrindo o **mês corrente e o mês seguinte**.

O comercial passa a enxergar sempre **2 meses à frente**, e a primeira rodada sobe 60 dias enquanto as seguintes sobem só o mês novo da ponta.

## Não-objetivos

- **Não mexer na carga de atrasados** (`enviar_atrasados_growthhs`, Etapa 1) — o backlog de vencidos continua sendo dela, e o card mensal **não** inclui vencidos.
- **Não mexer nos cards de OS/caixa** (board Serviços, `growthhs_os.py`, `growthhs_cards.py`).
- **Não atualizar cards já criados.** O endpoint do GrowthHS é *create-or-return*, não upsert; o card continua sendo um retrato do momento em que nasceu.
- **Não migrar os cards antigos** (formato por-aparelho) — a limpeza deles é manual, do lado do GrowthHS.
- **Sem migração de banco.** Nada é persistido no GestorHS: a idempotência mora inteira no `external_id`.

## Por que a idempotência resolve o "60 na primeira, 30 depois"

A chave passa de `{equipamento_cliente_id}:{prox_calibragem}` para **`{cliente_id}:{YYYY-MM}`**. Como toda rodada varre mês corrente + mês seguinte, o mês de trás **já tem card** e volta `created: false`:

```
01/08 → competências 2026-08 + 2026-09
        cliente 123 → cria "123:2026-08" e "123:2026-09"          (2 cards)

01/09 → competências 2026-09 + 2026-10
        "123:2026-09" já existe → created:false, nada acontece
        "123:2026-10" é novo → cria                                (1 card)

01/10 → competências 2026-10 + 2026-11
        "123:2026-10" já existe · "123:2026-11" novo               (1 card)
```

O job continua **burro e sem estado** — não precisa lembrar do que já mandou. Efeitos colaterais bons: a antecedência fica em **31–61 dias** (perto dos 50 de hoje) e um cliente que **não tinha nada** na competência quando ela foi varrida pela primeira vez ainda ganha o card na rodada seguinte, porque a chave dele ainda não existia.

As chaves novas **não colidem** com as antigas: formato diferente (`123:2026-08` vs `77:2026-08-15`).

## Design

### 1. Montagem do card — `app/core/growthhs_vencendo.py` (puro, sem I/O)

`montar_card_vencendo(linhas, competencia, board_id)` — mantém o nome, muda a assinatura: recebe a **lista de linhas de um mesmo cliente** (já ordenada por `prox_calibragem`) e a competência (`date` no dia 1 do mês).

- `source`: `gestorhs.calibracao` (inalterado). Board: `HSGROWTH_BOARD_COBRANCA` (2, inalterado).
- `external_id`: `f"{cliente_id}:{competencia:%Y-%m}"`.
- `title`: `Calibração vencendo · {cliente} · {n} aparelhos · agosto/2026` (singular `1 aparelho` quando n=1).
- `description`: cabeçalho + uma linha por aparelho, na ordem de vencimento:
  ```
  5 aparelhos deste cliente com calibração vencendo em agosto/2026:

  - Phoebus série 12345 (módulo 67890) — vence 03/08/2026
  - Alcoscan série 44821 — vence 09/08/2026
  ```
  Com elo, a linha usa `{elo.descricao} série {elo.serie} (módulo {ec.serie})`; sem elo, `{equipamento_desc} série {ec.serie}` — mesmo critério que `montar_device` já aplica, pelo mesmo motivo (o cliente reconhece o aparelho, não o número do módulo). Série vazia não deixa `série ` órfão na linha.
- **Sai o "vence em N dias"** que existe no card atual. Aquele card era lido no dia em que nascia; este vive um mês, e "em 12 dias" envelhece mentindo. A data absoluta não.
- `due_date`: o **menor** `prox_calibragem` do grupo, em datetime completo (`...T00:00:00` — o schema do GrowthHS recusa `YYYY-MM-DD`). É o prazo do aparelho mais urgente, que é quando a cobrança precisa ter acontecido.
- `client` / `contact`: `montar_cliente` / `montar_contato` do primeiro item, inalterados.
- `devices`: **todos** os aparelhos do grupo, via o `montar_device` de hoje (com elo).
- `business_info`: `{origem: "calibracao vencendo", cliente_id, competencia: "2026-08", qtd_aparelhos, equipamento_cliente_ids: [...]}`.

Nomes de mês em PT-BR vêm de uma tupla constante no módulo — **não** de `locale`, que depende do que está instalado na imagem.

### 2. Seleção e laço — `app/scripts/enviar_vencendo_growthhs.py`

- `buscar_vencendo(db, competencia)` — recebe um mês em vez de `dias`. Janela = `[max(hoje, primeiro dia do mês), último dia do mês]` (o `max` só importa quando alguém roda à mão no meio do mês). **Todos os filtros de hoje permanecem idênticos**: `ativo`, `prox_calibragem` não nulo, `os_atual` vazio, sem Phoebus/EBS, sem o cliente de estoque interno da HS. Devolve as mesmas linhas `{cliente_id, cliente, ec, equipamento_desc, elo}`.
- `agrupar_por_cliente(linhas)` — **função pura nova**: `list[list[dict]]`, grupos ordenados por `cliente_id` e, dentro de cada grupo, por `prox_calibragem, ec.id`. Separada da query para poder ser testada sem banco.
- `buscar_excluidos_por_os(db, competencia)` — os aparelhos que vencem na competência e ficaram de fora por `os_atual` preenchido. Só alimenta o relatório; não vira card.
- `processar(db, *, competencias, enviar, limite)` — recebe a **lista** de competências e itera. O best-effort passa a ser **por cliente** (hoje é por aparelho): montar/enviar o card de um cliente que falha vira pendência e o laço segue para o próximo. Retorna `{clientes, aparelhos, criados, existentes, falhas, pendencias, excluidos}`.
- `limite` passa a contar **clientes**, não aparelhos.

### 3. Agendamento — `app/core/agendamento.py` + `app/tarefas/vencendo.py`

- Nova função pura `proxima_execucao_mensal(agora, hora, dia=1)` + `segundos_ate_proxima_mensal(...)`, no mesmo formato das atuais: converte para `TZ_SP`, e se o alvo já passou (ou é exatamente agora) pula para o **mês seguinte** — um restart às 08:00:00 do dia 1 não pode redisparar a rodada.
- `proxima_execucao` / `segundos_ate_proxima` (a versão diária) e seus testes são **removidos**: nada mais os usa depois desta mudança, e o git guarda a versão anterior. O docstring do módulo deixa de falar em "job diário".
- `tarefas/vencendo.py`: `_rodar_job` calcula `[mês corrente, mês seguinte]` a partir de `date.today()` e chama `processar(db, competencias=..., enviar=True)`; o laço dorme com `segundos_ate_proxima_mensal`. O resto do arquivo — task de fundo no lifespan, `asyncio.to_thread`, nunca propagar exceção — fica exatamente como está.
- **Config:** `JOB_VENCENDO_ATIVO` e `JOB_VENCENDO_HORA` continuam. **`JOB_VENCENDO_DIAS` sai** — a janela não é mais medida em dias. O "2 meses à frente" e o "dia 1" ficam como constantes do módulo, sem env nova: quem precisar de outra janela usa `--competencia` na mão.

### 4. CLI

```
python -m app.scripts.enviar_vencendo_growthhs [--competencia YYYY-MM ...] [--dry-run]
                                               [--limite N] [--pendencias CAMINHO.csv]
```

- `--competencia` é **repetível**; o padrão é mês corrente + mês seguinte. Substitui `--dias`.
- `--dry-run`, `--limite`, `--pendencias` inalterados no propósito. **O padrão continua sendo ENVIAR** — a chave não depende da data de execução, então repetir é inofensivo, e um job agendado que não envia por padrão seria um no-op silencioso.
- Resumo impresso: competências cobertas, clientes, aparelhos, criados / já existentes / falhas, e a contagem de excluídos por OS em andamento.

### 5. Relatório de exclusões

O CSV de pendências ganha as colunas `tipo` (`falha` | `excluido`) e `competencia`, e continua com uma linha **por aparelho**:

```
tipo,competencia,cliente_id,equipamento_cliente_id,serie,prox_calibragem,motivo
falha,2026-08,123,77,SN-9,2026-08-03,GrowthHS respondeu 422: ...
excluido,2026-08,456,88,SN-1,2026-08-19,OS em andamento (os_atual=10902)
```

Numa falha de card, todos os aparelhos daquele cliente saem como linhas `falha` com o mesmo motivo — é o que permite ver exatamente quem não foi comunicado. As linhas `excluido` são informativas: **não** contam como falha e **não** afetam o exit code (1 só quando há falha de verdade), mas saem também no stdout, que é o canal que sobrevive a redeploy.

Isto é o que impede o buraco dos retardatários de ser silencioso: a rodada é uma foto única do dia 1, e quem estava em OS naquele instante fica de fora do mês. O risco real é baixo (quem está em laboratório sai com data +1 ano, deixando a janela sozinho), mas agora aparece no relatório.

## Rollout

Produção, integração já ligada (`JOB_VENCENDO_ATIVO=true`). Sem migração de banco e sem env nova — **`JOB_VENCENDO_DIAS` pode ser removida do Easypanel** (ignorada se ficar).

A primeira rodada automática só acontece no próximo **dia 1**. Para começar antes, à mão:

```bash
docker exec gestorhs-backend python -m app.scripts.enviar_vencendo_growthhs \
  --competencia 2026-08 --competencia 2026-09 --dry-run
```

Confere o resumo e roda sem `--dry-run`. A rodada automática de 01/09 encontra tudo já criado e só sobe outubro.

Fecha como **v1.27.0** (muda o comportamento de uma integração em produção).

## Testes

**`test_growthhs_vencendo.py`** (montagem, reescrito para a nova assinatura): chave é `{cliente}:{competência}` e não muda com a data de execução; título com plural/singular e mês em PT-BR; descrição lista os aparelhos na ordem de vencimento, com e sem elo, e sem série órfã quando a série é vazia; `due_date` é o menor vencimento do grupo, em datetime completo; `devices` traz todos os aparelhos; `business_info` completo; `contact` ausente quando o cliente não tem contato; board repassado.

**`test_enviar_vencendo_growthhs.py`** (seleção e laço): janela é o mês da competência, com as duas bordas; ignora vencidos, fora do mês, inativos, com OS em andamento, Phoebus/EBS e o cliente de estoque; `agrupar_por_cliente` agrupa e ordena; duas competências numa rodada geram um card por cliente **por mês**; `created:false` na competência repetida conta em `existentes` e não em `criados`; falha num cliente não aborta os outros e emite uma linha `falha` por aparelho dele; `--limite` corta em clientes; dry-run monta e não envia; excluídos por OS aparecem no relatório sem virar falha nem mudar o exit code; `main` repassa competências e dry-run.

**`test_agendamento.py`**: `proxima_execucao_mensal` com meses de 28/29/30/31 dias, virada de ano, antes e depois da hora no dia 1, e no dia 1 exatamente na hora (tem que ir para o mês seguinte).

**`test_tarefa_vencendo.py`**: `_rodar_job` monta `[mês corrente, mês seguinte]`; o resto (nasce desligado, task só quando ligado, falha não mata o laço, sessão fechada mesmo com erro, logs em INFO) continua valendo com o agendamento mensal.

## Documentação

- `docs/operacao-growthhs-job-diario.md` → **`docs/operacao-growthhs-job-mensal.md`**, reescrito: nova cadência, o porquê do card por cliente, as flags novas, o relatório de excluídos e a nota de transição.
- `CLAUDE.md`: os dois trechos que descrevem o job (bloco de comandos do backend e o aviso sobre a chave `{equipamento_cliente_id}:{prox_calibragem}`).
- `frontend/src/app/changelog/data.ts`: entrada da v1.27.0.
