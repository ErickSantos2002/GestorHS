# Integração inbound — GrowthHS chama o GestorHS ao dar "ganho"

Endpoint para o **GrowthHS** chamar o **GestorHS** quando o pós-vendas marca uma
proposta como "Ganho" no board de negociação. A chamada move a caixa correspondente de
**Pós-Vendas(6)** para **Financeiro(10)** no GestorHS, sem depender de um humano abrir o
sistema para adiantar a fase.

## Objetivo

Hoje a caixa fica parada em Pós-Vendas até alguém no GestorHS avançá-la manualmente para
Financeiro. Quando o negócio já foi fechado no GrowthHS (proposta aceita, OC recebida),
essa confirmação deve refletir automaticamente no GestorHS — é isso que este endpoint
faz.

## Ligar a integração

Nasce **desligada**. No GestorHS, defina a env:

```
GROWTHHS_INBOUND_API_KEY=<segredo forte>
```

Vazio (padrão) = a integração responde `503` para qualquer chamada. Gere um segredo
aleatório longo (ex.: `openssl rand -hex 32`) e combine com a equipe do GrowthHS fora de
banda — essa é a chave que vai no header de cada chamada.

## Endpoint

```
POST {BASE_URL_GESTORHS}/integracao/growthhs/caixas/{caixa_id}/ganho
```

`{BASE_URL_GESTORHS}` é a URL da API do GestorHS no ambiente (produção ou homologação).

## Autenticação

Header fixo, não é JWT — quem chama é o GrowthHS, não um usuário logado:

```
X-API-Key: <a chave configurada em GROWTHHS_INBOUND_API_KEY>
```

- Chave ausente ou errada → `401`.
- Integração desligada (env vazia) → `503`, antes mesmo de checar a chave enviada.

## O que é `caixa_id`

É o **`external_id`** que o próprio GestorHS já manda no card do TaskHS/GrowthHS quando
cria ou espelha a caixa (`external_id = caixa.id`). Não é preciso descobrir esse valor por
outro caminho: o card do negócio no GrowthHS já carrega esse identificador desde que foi
criado pelo GestorHS. Basta ler o `external_id` do card e usá-lo como `{caixa_id}` na URL.

## Corpo (JSON)

```json
{
  "observacao": "Negócio fechado — Proposta #123, OC 456, R$ 18.500,00"
}
```

Campo `observacao` é **opcional** (texto livre) e vai para o histórico da caixa no
GestorHS — valor do negócio, número de proposta, número de OC, o que for útil para quem
olhar o histórico depois. Se omitido ou vazio, o histórico registra apenas `via
GrowthHS`; se preenchido, registra `via GrowthHS: <observacao>`.

## Respostas

| HTTP | Corpo / detalhe | Quando |
|---|---|---|
| `200` | `{"movida": true, "caixa_id": 42, "fase": 10}` | Caixa estava em Pós-Vendas(6) e foi movida agora para Financeiro(10). |
| `200` | `{"movida": false, "caixa_id": 42, "fase": 10}` | Caixa **já estava** em Financeiro(10) ou além (fase 7/Finalizada). Repetir a chamada é seguro — não é erro. |
| `409` | `{"detail": "caixa nao esta em Pos-Vendas"}` | Caixa existe, mas está em uma fase anterior a Pós-Vendas (ainda não chegou lá) — chamada fora de ordem. |
| `404` | `{"detail": "caixa nao encontrada"}` | `caixa_id` não corresponde a nenhuma caixa no GestorHS. |
| `401` | `{"detail": "api key invalida"}` | Header `X-API-Key` ausente ou não bate com a chave configurada. |
| `503` | `{"detail": "integracao inbound do GrowthHS desligada"}` | `GROWTHHS_INBOUND_API_KEY` está vazia no GestorHS — integração não está ligada neste ambiente. |

## Idempotência

A chamada pode ser **repetida com segurança**. Se a caixa já foi movida (fase Financeiro
ou além), a resposta é `200 {"movida": false, ...}` — não há duplicação de histórico nem
erro. Isso cobre o caso comum de retry automático do lado do GrowthHS (timeout, falha de
rede) sem exigir controle de "já enviei essa chamada antes" em nenhum dos dois lados.

O único caso que dá erro é chamar **antes da hora** — caixa ainda não chegou em
Pós-Vendas (`409`). Isso não é idempotência quebrada, é a integração recusando avançar uma
fase que o fluxo normal (Recebido → Laboratório → Pós-Vendas) ainda não alcançou.

## Exemplo `curl`

```bash
curl -X POST "https://api.gestorhs.com.br/integracao/growthhs/caixas/42/ganho" \
  -H "X-API-Key: $GESTORHS_INBOUND_KEY" \
  -H "Content-Type: application/json" \
  -d '{"observacao": "Negocio fechado - Proposta #123, OC 456, R$ 18.500,00"}'
```

Resposta esperada (caixa 42 estava em Pós-Vendas):

```json
{"movida": true, "caixa_id": 42, "fase": 10}
```

## Segurança

- A chave `GROWTHHS_INBOUND_API_KEY` autoriza **só esta transição** (Pós-Vendas →
  Financeiro) — não abre nenhum outro endpoint do GestorHS e não representa um usuário
  interno.
- A chave **não expira** e **não tem escopo por caixa/cliente** — qualquer caixa em
  Pós-Vendas pode ser movida por quem a possuir.
- **Revogar** é trocar (ou zerar) a env `GROWTHHS_INBOUND_API_KEY` e reiniciar o serviço.
  Zerar desliga a integração inteira (toda chamada volta `503`) até uma nova chave ser
  configurada.
- A comparação da chave usa `secrets.compare_digest` (tempo constante) para evitar
  vazamento por timing; um header `X-API-Key` malformado (ex.: caractere não-ASCII)
  é tratado como chave inválida (`401`), nunca derruba a chamada com `500`.
- Toda chamada gera uma linha de log no GestorHS — aceita ou recusada (`401`, `404`,
  `409`), com o resultado e o `caixa_id`, nunca o valor da chave. A gravação no
  **histórico da caixa** (a `observação` do corpo) só acontece quando a chamada é
  aceita e move a fase (`200 {"movida": true, ...}`).
