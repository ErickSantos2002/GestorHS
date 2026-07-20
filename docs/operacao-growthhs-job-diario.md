# Operação — job diário do GrowthHS (calibração vencendo)

Cria um card no board **Cobrança** (2) do GrowthHS para cada aparelho cuja calibração vence
nos próximos 50 dias. Um card por **aparelho + ciclo**.

## Antes da primeira rodada

A janela já está cheia: a primeira execução cria **409 cards de uma vez** (medido em
20/07/2026), enquanto o regime normal é ~10–13/dia. Confira antes de abrir a torneira:

```bash
docker exec gestorhs-backend python -m app.scripts.enviar_vencendo_growthhs --dry-run
```

Se o comercial não absorver 409 de uma vez, rampe com `--dias`: rode `--dias 7` no primeiro
dia, `--dias 20` alguns dias depois, e só então deixe o cron no padrão de 50. Rodar de novo
**não duplica** — a chave é `{equipamento_cliente_id}:{prox_calibragem}`, que não muda com a
data da execução.

## O agendamento

O job roda **dentro da própria aplicação**: ao subir, o backend cria uma tarefa de fundo
que dorme até as 08:00 (horário de São Paulo), executa e repete. Não há cron, nem
Dockerfile a alterar, nem serviço externo.

Ele nasce **desligado**. Para ativar em produção, no Easypanel:

```
JOB_VENCENDO_ATIVO=true
```

E redeploy. Confirme no log do serviço:

```
INFO app.tarefas.vencendo: job vencendo: LIGADO, disparo diario as 8h (SP)
```

Se aparecer `DESLIGADO (JOB_VENCENDO_ATIVO=false)`, a env não chegou ao container.

> Por que nasce desligado: a máquina de desenvolvimento aponta para o **banco de produção
> com a chave real**. Se o padrão fosse ligado, qualquer `docker compose up` local passaria
> a criar cards de verdade.

Outras envs (opcionais): `JOB_VENCENDO_HORA` (padrão `8`) e `JOB_VENCENDO_DIAS`
(padrão `50`).

### Por que não cron

A escolha original era cron, pelo argumento de rodar uma vez só mesmo com várias réplicas.
Esse argumento caiu: o backend é um serviço único no Easypanel, e a criação de card é
idempotente — a chave `{equipamento_cliente_id}:{prox_calibragem}` não muda com a data da
execução, então mesmo execuções repetidas não duplicariam nada. Em troca, cron custaria
instalar cron na imagem ou depender de um serviço externo. O worker embutido sobe junto
com o deploy, sem passo de infraestrutura.

O script continua executável à mão quando precisar:

```bash
docker exec gestorhs-backend python -m app.scripts.enviar_vencendo_growthhs --dry-run
```

## Flags

| Flag | Para quê |
|---|---|
| `--dias N` | Tamanho da janela (padrão 50). Use para rampar a primeira rodada. |
| `--dry-run` | Monta tudo e mostra o resumo **sem enviar nada**. |
| `--limite N` | Processa só os N primeiros aparelhos — teste controlado. |
| `--pendencias CAMINHO` | Onde gravar o CSV de falhas. |

> ⚠️ Aqui o padrão é **enviar** (`--dry-run` para simular) — o contrário de
> `enviar_atrasados_growthhs`, que exige `--enviar`. É proposital: a chave deste job não
> depende da data da execução, então repetir é inofensivo; e um job de cron que não envia por
> padrão seria um agendamento silenciosamente inútil.

## Quando algo falha

O laço é best-effort **por aparelho**: uma falha num card não derruba a rodada. As falhas vão
para um CSV com o motivo — incluindo o corpo da resposta do GrowthHS, que é onde o 422 diz
qual campo reprovou.

**As falhas saem em dois lugares:**

1. **No stdout** — que o cron redireciona para `/var/log/growthhs-vencendo.log`. Este é o
   canal que **sempre** sobrevive, independente de volume, e é onde olhar primeiro.
2. **Num CSV**, com os mesmos dados em formato de planilha.

O CSV vai para `{UPLOAD_DIR}/relatorios/` — na prática `/data/uploads/relatorios/`, o volume
**persistente** que já existe nos dois ambientes. **Nada a configurar no deploy.**

```bash
docker exec gestorhs-backend ls /data/uploads/relatorios/
```

> Por que não um caminho dentro de `/app`: em produção o Easypanel sobe a imagem pelo
> **Dockerfile, sem bind mount**, então qualquer coisa em `/app` é efêmera e some no
> redeploy — junto com a única diagnose do job. A env `RELATORIOS_DIR` existe para
> sobrescrever o destino, mas não precisa ser preenchida.

Como o job é idempotente, basta corrigir a causa e esperar a próxima execução — ela
reprocessa a janela inteira.

## O que o job NÃO faz

- **Não pega vencidos** (`prox_calibragem < hoje`) — esse backlog foi a carga única da
  Etapa 1, em formato por cliente.
- **Não atualiza** cards existentes. O endpoint do GrowthHS é *create-or-return*, não upsert:
  o card é um retrato do momento em que foi criado.
- **Não pula** aparelho que já tem card de outro ciclo — ciclo novo, card novo, de propósito.
- **Não avisa** aparelho com OS em andamento (`os_atual` preenchido): se o cliente já mandou
  o aparelho, "entre em contato" é ruído.
