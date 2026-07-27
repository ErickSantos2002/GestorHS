# Operação — job mensal do GrowthHS (calibração vencendo)

Cria um card no board **Cobrança** (2) do GrowthHS para cada **cliente** com aparelhos
cuja calibração vence no mês. Um card por **cliente + mês de vencimento**, com todos os
aparelhos daquele cliente que vencem naquele mês.

## A cadência

Roda **todo dia 1, às 08:00 (São Paulo)**, sobre **duas competências: o mês corrente e o
mês seguinte**.

```
01/08 → competências agosto + setembro
        cliente 123 → cria "123:2026-08" e "123:2026-09"        (2 cards)

01/09 → competências setembro + outubro
        "123:2026-09" já existe → created:false, nada acontece
        "123:2026-10" é novo → cria                              (1 card)
```

A primeira rodada sobe **60 dias**; as seguintes, só o mês novo da ponta. Isso não é
uma regra no código — é consequência da chave `{cliente_id}:{YYYY-MM}`, que não muda com
a data da execução. O comercial fica sempre com **2 meses à frente** à vista, e cada
aparelho é avisado com **31 a 61 dias** de antecedência.

O job é **burro e sem estado**: não guarda o que já mandou. Rodar de novo é inofensivo.

## Por que um card por cliente

O comercial cobra todos os aparelhos do cliente **na primeira ligação**. Com um card por
aparelho, os cards seguintes chegavam depois de o assunto já estar resolvido e obrigavam
a repetir o mesmo fechamento N vezes.

O agrupamento só é seguro porque a varredura é **mensal**. Na janela rolante diária de
antes, o segundo aparelho a entrar na janela depois de o card do cliente já existir
voltaria `created: false` e sumiria sem erro nenhum.

## Ligar em produção

Nasce **desligado**. No Easypanel:

```
JOB_VENCENDO_ATIVO=true
```

E redeploy. Confirme no log do serviço:

```
INFO app.tarefas.vencendo: job vencendo: LIGADO, disparo todo dia 1 as 8h (SP)
```

Se aparecer `DESLIGADO (JOB_VENCENDO_ATIVO=false)`, a env não chegou ao container.

> Por que nasce desligado: a máquina de desenvolvimento aponta para o **banco de produção
> com a chave real**. Se o padrão fosse ligado, qualquer `docker compose up` local passaria
> a criar cards de verdade.

Outras envs (opcionais): `JOB_VENCENDO_HORA` (padrão `8`) e `RELATORIOS_DIR`.
**`JOB_VENCENDO_DIAS` não existe mais** — a janela não é medida em dias; pode ser
removida do Easypanel.

### Por que não cron

O backend é um serviço único no Easypanel e a criação de card é idempotente, então
execuções repetidas não duplicam nada. Cron custaria instalar cron na imagem ou depender
de um serviço externo; o worker embutido sobe junto com o deploy, sem passo de
infraestrutura.

## Rodar à mão

```bash
docker exec gestorhs-backend python -m app.scripts.enviar_vencendo_growthhs --dry-run
```

| Flag | Para quê |
|---|---|
| `--competencia YYYY-MM` | Mês a cobrir; **repetível**. Padrão: mês corrente + seguinte. |
| `--dry-run` | Monta tudo e mostra o resumo **sem enviar nada**. |
| `--limite N` | Processa só os N primeiros **clientes** — teste controlado. |
| `--pendencias CAMINHO` | Onde gravar o CSV do relatório. |

> ⚠️ Aqui o padrão é **enviar** (`--dry-run` para simular) — o contrário de
> `enviar_atrasados_growthhs`, que exige `--enviar`. É proposital: a chave deste job não
> depende da data da execução, então repetir é inofensivo; e um job agendado que não
> envia por padrão seria um agendamento silenciosamente inútil.

Adiantar a primeira rodada, sem esperar o dia 1:

```bash
docker exec gestorhs-backend python -m app.scripts.enviar_vencendo_growthhs \
  --competencia 2026-08 --competencia 2026-09 --dry-run
```

Confira o resumo e rode de novo sem `--dry-run`. A rodada automática do dia 1 seguinte
encontra tudo criado e só sobe o mês da ponta.

## Quando algo falha

O laço é best-effort **por cliente**: uma falha num card não derruba a rodada. O relatório
sai em **dois lugares** — no **stdout** (log do serviço, o canal que sempre sobrevive) e
num **CSV**:

```
tipo,competencia,cliente_id,equipamento_cliente_id,serie,prox_calibragem,motivo
falha,2026-08,123,77,SN-9,2026-08-03,GrowthHS respondeu 422: ...
excluido,2026-08,456,88,SN-1,2026-08-19,OS em andamento (os_atual=10902)
```

- **`falha`** — o card do cliente não foi criado. Uma linha por aparelho dele, com o
  corpo da resposta do GrowthHS, que é onde o 422 diz qual campo reprovou. O processo
  sai com código 1.
- **`excluido`** — o aparelho vence na competência mas tem **OS em andamento**, então
  não virou card ("entre em contato" é ruído para quem já mandou o aparelho). **Não é
  falha** e não afeta o código de saída; está no relatório porque a rodada é uma foto
  única do dia 1 e a omissão não pode ser silenciosa.

O CSV vai para `{UPLOAD_DIR}/relatorios/` — na prática `/data/uploads/relatorios/`, o
volume **persistente** que já existe nos dois ambientes. **Nada a configurar no deploy.**

```bash
docker exec gestorhs-backend ls /data/uploads/relatorios/
```

Como o job é idempotente, basta corrigir a causa e rodar de novo — ou esperar o próximo
dia 1, que reprocessa as competências inteiras.

## O que o job NÃO faz

- **Não pega vencidos** (`prox_calibragem < hoje`) — esse backlog foi a carga única da
  Etapa 1, em formato por cliente.
- **Não atualiza** cards existentes. O endpoint do GrowthHS é *create-or-return*, não
  upsert: o card é um retrato do momento em que foi criado. Se a data de calibração de um
  aparelho mudar depois, o card do mês não muda junto.
- **Não avisa** aparelho com OS em andamento no dia da rodada — sai no relatório como
  `excluido`.
- **Não pega quem entra na janela depois da rodada.** Aparelho cujo cliente já tem card
  daquele mês não é acrescentado a ele. Na prática o risco é baixo: quem está em
  laboratório sai com data +1 ano e deixa a janela sozinho.
