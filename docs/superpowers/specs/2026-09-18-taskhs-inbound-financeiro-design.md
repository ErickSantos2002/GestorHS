# Card no Financeiro do TaskHS avança a caixa no GestorHS — Design

**Data:** 2026-09-18
**Área:** **dois repos.** GestorHS: `core/fluxo_modulo.py`, `api/espelhamento.py`, `api/deps.py`, `core/config.py`, novo `api/integracao_taskhs.py`, novo `core/avanco_inbound.py`, script SQL de adoção. TaskHS: `app/automations.py`, `app/core/config.py`, e uma opção na tela de automações (`frontend/src/pages/BoardPage.tsx`).
**Fase:** continuação de [2026-09-18-so-modulo-pula-posvendas-design.md](2026-09-18-so-modulo-pula-posvendas-design.md), que devolveu as caixas de Phoebus+Módulo ao Pós-Vendas (v1.55.0, na `main`).

⚠️ **O TaskHS é outro repositório.** Este documento especifica os dois lados para que o desenho se entenda inteiro, mas a implementação lá é feita numa sessão aberta dentro de `~/github/TaskHS`. A regra de território vale: nada de editar repo de fora.

## Problema

A v1.55.0 pôs a caixa de Phoebus+Módulo de volta no Pós-Vendas(6), que é o lugar certo dela — o serviço do aparelho passa pelo comercial. Mas isso criou trabalho: alguém tem que entrar no GestorHS e avançar a caixa à mão quando o serviço termina.

O setor de Serviços não trabalha no GestorHS. Ele trabalha no board `Serviço` do TaskHS, movendo o card de lista em lista. Pedir que passe a abrir o GestorHS para avançar caixa é trocar um problema de sistema por trabalho manual recorrente.

A caixa normal não tem esse problema: o avanço 6 → 10 dela é disparado pelo GrowthHS quando a proposta é marcada como "Ganho" (`POST /integracao/growthhs/caixas/{id}/ganho`). **Phoebus não tem proposta no GrowthHS**, então não existe gatilho equivalente.

## Evidência (levantada em 18/09/2026)

**O mapa fase → lista já faz a correspondência.** `core/taskhs.py:FASE_PARA_LIST_ID` mapeia a fase 6 para a lista **202** (`🔬LIBERADOS DO LABORATÓRIO`) e a fase 10 para a **205** (`💰Financeiro`). "Card entrou na 205" já significa, no vocabulário do GestorHS, "caixa entrou no Financeiro".

**Os 7 cards das caixas revertidas hoje estão na 202** — a mesma lista que o GestorHS usaria. O setor os criou à mão e, sem saber, na lista certa.

**O TaskHS já tem motor de automação.** `app/automations.py` executa `run_card_moved_automations(db, card, from_list_id, to_list_id)` com `trigger_type = "card_moved_to_list"` e `trigger_list_id`. Hoje existe uma ação só: `mark_due_complete`. O ponto de extensão é um `elif` no laço de ações.

**Polling está descartado por um fato, não por preferência.** O router `/integration` do TaskHS — o único que aceita `X-API-Key` — expõe apenas `POST /cards` (upsert) e `DELETE /cards`. **Não há leitura.** Ler card exige `get_current_user` (JWT) mais acesso ao quadro. O GestorHS não consegue consultar o TaskHS com a credencial que tem, e criar endpoint de leitura lá seria mudança maior que a da automação.

**`action_config` é coluna morta.** Existe em `models/automation.py:16` e em **nenhum outro lugar**: nem em `AutomationCreate`/`AutomationUpdate`/`AutomationOut`, nem no router, nem no frontend. Uma ação genérica com URL configurável obrigaria a levar esse campo por toda a pilha do TaskHS — por isso o desenho usa ação específica, com a URL no `.env`.

**Cards manuais vivos de caixa de Phoebus/Módulo em fase ativa: 12**, em dois grupos de tratamento oposto:

| grupo | caixas | lista do card | fase no GestorHS | tratamento |
|---|---|---|---|---|
| **A** | 1003, 1011, 1028, 1030, 1041, 1043, 1047, 1049 | 202 (todas) | 6 | **adotar** — a 202 já é a lista da fase 6, então adotar não move nada |
| **B** | 639, 670, 685, 692 | 203 / 204 | 4 | **não tocar** — adotar arrastaria o card para a 196 (Expedição), desfazendo trabalho |

**Nenhum dos 12 é de caixa 100% Módulo.** O setor nunca criou card para essas — só para as que têm Phoebus dentro. É o dado que sustenta a decisão de estreitar o bloqueio do espelhamento.

Para comparação de escala: há 365 cards manuais com `CX <n>` no título no board (legado anterior ao espelhamento), dos quais 32 são de caixa normal em fase ativa. **Este desenho não toca em nenhum deles.**

## Decisões

| Pergunta | Decisão | Por quê |
|---|---|---|
| Quem cria o card de caixa com Phoebus? | **O GestorHS**, de agora em diante. | O card nasce com `external_id = id da caixa`, o elo fica robusto sem adivinhar título, e o setor para de criar card à mão. |
| O que fica fora do board do TaskHS? | **Só a caixa 100% Módulo.** | Nenhum dos 12 cards manuais é de caixa 100% Módulo: o próprio setor já revelou onde está a linha. |
| E o board do GrowthHS? | **Continua com o critério largo** (`caixa_de_modulo`, `any`). | Aquele board é comercial e Phoebus não tem proposta nele. A divergência entre os dois boards passa a ser intencional. |
| Cards manuais que já existem? | **Adotar os 8 do grupo A; não tocar nos 4 do grupo B.** | Sem adoção, o espelhamento criaria um segundo card por caixa — o estrago dos 28 cards órfãos de jul–set. O grupo B tem drift e adotar andaria para trás. |
| Que caixa a automação pode avançar? | **Só caixa com Phoebus dentro.** Sem Phoebus → 409. | Sair da fase 6 grava `aceite`/`data_aceite`. Na caixa normal esse aval vem do "Ganho" no GrowthHS; deixar o TaskHS gravá-lo seria forjar aprovação comercial. |
| Ação genérica ou específica no TaskHS? | **Específica** (`avisar_gestorhs`), URL no `.env` do TaskHS. | `action_config` é coluna morta; a genérica custaria schema + router + tela num repo que não editamos daqui. Também elimina a superfície de SSRF de uma URL digitável na tela. |
| Chave de API | **Chave própria** (`TASKHS_INBOUND_API_KEY`), não a do GrowthHS. | Um vazamento derruba uma integração, não duas, e a rotação é independente. |

## Desenho — lado GestorHS

### Um núcleo para "é caixa 100% Módulo"

O mesmo `all(== 47)` passa a responder **duas** perguntas: "pula o Pós-Vendas?" e "fica fora do board do TaskHS?". Para não ter o predicado copiado, `core/fluxo_modulo.py` ganha o núcleo e `caixa_pula_posvendas` delega:

```python
def caixa_so_de_modulo(ordens) -> bool:
    """True SO se todas as OS sao Modulo (47). Nucleo de DUAS decisoes:
    pular o Pos-Vendas e ficar fora do board do TaskHS.

    ⚠️ "modulo" aqui e' ESTRITAMENTE o catalogo 47. Em `caixa_de_modulo`, logo
    acima, "modulo" quer dizer "modulo OU phoebus" (`any`) — nomes parecidos,
    conjuntos diferentes. `caixa_de_modulo` segue valendo para o GrowthHS.
    """
    ativas = list(ordens)
    return bool(ativas) and all(
        getattr(o, "equipamento_catalogo", None) == settings.EQUIPAMENTO_MODULO_ID
        for o in ativas)


def caixa_pula_posvendas(ordens) -> bool:
    """A caixa 100% Modulo e' a unica que nao passa pelo comercial."""
    return caixa_so_de_modulo(ordens)
```

`caixa_pula_posvendas` sobrevive como nome porque é lido no `api/caixas.py`, onde "pula o Pós-Vendas" é a frase que descreve a decisão.

### O espelhamento passa ao critério estreito

`api/espelhamento.py` troca `fluxo_modulo.caixa_de_modulo` por `fluxo_modulo.caixa_so_de_modulo` nos **três** pontos (`espelhar_caixa_sync` e os dois de `agendar_espelhamento_caixa`), e o `motivo` do log de integração vira `"caixa_so_de_modulo"`. `api/growthhs_cards.py` e `api/logs_integracao.py` **não mudam**.

Efeito colateral a esperar: caixa com Phoebus passa a virar card automático. Nas 12 caixas do levantamento isso é o desejado para o grupo A (já adotado) e **indesejado** para o grupo B — ver "Ordem de implantação".

### O avanço 6 → 10 sai de dentro do endpoint do GrowthHS

Hoje a lógica vive em `api/integracao_growthhs.py`, com um `FASE_POSVENDAS = 6` local que duplica a constante. Ela vai para `core/avanco_inbound.py`, puro quanto a regra e recebendo a sessão:

```python
FASES_JA_AVANCADAS = (wf.FASE_FINANCEIRO, wf.FASE_PREPARANDO, wf.FASE_FINALIZADA)


def estado_para_avanco(caixa) -> str:
    """'avancar' | 'no_op' | 'fase_errada'. Decide sem tocar no banco.

    `no_op` e' fase JA avancada: quem chama nao sabe se ja mandou este mesmo
    evento antes, e repetir nao pode virar erro.
    """
```

Os dois endpoints (GrowthHS e TaskHS) usam esse núcleo e continuam donos do que é só deles: a chave, a obs do log e as validações próprias.

### O endpoint novo

`api/integracao_taskhs.py`, registrado em `main.py`:

```
POST /integracao/taskhs/caixas/{caixa_id}/financeiro
  auth: X-API-Key == settings.TASKHS_INBOUND_API_KEY  (require_taskhs_inbound)
  body: {"card_id": int | None, "observacao": str | None}
  200:  {"movida": bool, "caixa_id": int, "fase": int}
  404:  caixa nao encontrada
  409:  caixa nao esta em Pos-Vendas
  409:  caixa sem Phoebus  -> detail "caixa sem Phoebus: avanco pelo TaskHS nao se aplica"
  503:  integracao desligada (chave nao configurada)
```

`require_taskhs_inbound` é gêmeo de `require_growthhs_inbound` em `api/deps.py`, incluindo o `secrets.compare_digest` dentro de `try/except TypeError` — Starlette decodifica header como latin-1 e caractere não-ASCII levantaria `TypeError`, que sem o guard vira 500 em vez de 401.

A trava de escopo é **positiva**, não a negação do predicado de módulo:

```python
tem_phoebus = any(o.equipamento_catalogo == settings.EQUIPAMENTO_PHOEBUS_ID
                  for o in ativas)
```

Escrever `not fluxo_modulo.caixa_so_de_modulo(ativas)` deixaria passar caixa **normal** (sem Phoebus e sem módulo), que é justamente o caso que a decisão do `aceite` quer barrar.

`card_id` entra só no log — serve para rastrear qual card disparou, e nunca para resolver a caixa.

A obs gravada é `"via TaskHS"`, ou `"via TaskHS: <observacao>"` quando vier texto, espelhando o formato do GrowthHS.

### Configuração

`core/config.py` ganha `TASKHS_INBOUND_API_KEY: str = ""`. **Vazio = integração desligada** (503), pelo mesmo motivo do `JOB_VENCENDO_ATIVO`: a máquina de desenvolvimento aponta para o banco de produção.

## Desenho — lado TaskHS (especificação para a sessão de lá)

### A ação nova

Em `app/automations.py`, dentro do laço que hoje só trata `mark_due_complete`:

```python
elif auto.action_type == "avisar_gestorhs":
    await _avisar_gestorhs(card)
```

```python
async def _avisar_gestorhs(card) -> None:
    """POST no GestorHS avisando que o card entrou na lista do Financeiro.

    NO-OP silencioso se o card nao for espelhado do GestorHS: card criado a mao
    nao tem external_id, e o GestorHS nao teria como saber de que caixa se trata.
    E' isso que mantem os 4 cards manuais do "grupo B" inertes sem caso especial.

    BEST-EFFORT: excecao aqui NAO pode derrubar o movimento do card que o
    usuario acabou de fazer. `run_card_moved_automations` ja envolve cada acao
    num try/except proprio, entao basta nao reintroduzir raise.
    """
    if card.external_source != "gestorhs" or not card.external_id:
        return
    if not settings.GESTORHS_BASE_URL or not settings.GESTORHS_INBOUND_API_KEY:
        return
    url = f"{settings.GESTORHS_BASE_URL}/integracao/taskhs/caixas/{card.external_id}/financeiro"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(url, json={"card_id": card.id},
                         headers={"X-API-Key": settings.GESTORHS_INBOUND_API_KEY})
    if r.status_code >= 400:
        logger.warning("GestorHS respondeu %s para card %s (caixa %s)",
                       r.status_code, card.id, card.external_id)
```

⚠️ **O `external_id` é `String(100)`** no `models/card.py`, não inteiro — interpolar direto na URL está correto, mas nada de assumir `int`.

⚠️ **A chamada HTTP acontece dentro da transação do movimento do card.** `run_card_moved_automations` roda depois do `flush` e antes do commit do router. Um GestorHS lento seguraria a transação pelo timeout inteiro — daí o `timeout=10`. Se isso incomodar na prática, o caminho é a mesma solução que o GestorHS usa: jogar em background e não bloquear o request.

### Configuração e tela

`app/core/config.py`: `GESTORHS_BASE_URL: str = ""` e `GESTORHS_INBOUND_API_KEY: str = ""`. Vazio = no-op, igual ao lado de cá.

Na tela de automações (`frontend/src/pages/BoardPage.tsx`), `avisar_gestorhs` entra como opção de `action_type`. **Nenhuma mudança de schema** — `AutomationCreate`/`Update`/`Out` já carregam `action_type` como string livre, e `action_config` continua sem uso.

### A automação a cadastrar em produção

Uma linha, pela tela ou por `POST /boards/{id}/automations`:

| campo | valor |
|---|---|
| `board_id` | o board `Serviço` |
| `trigger_type` | `card_moved_to_list` |
| `trigger_list_id` | **205** (`💰Financeiro`) |
| `action_type` | `avisar_gestorhs` |
| `enabled` | `true` |

## Adoção dos 8 cards do grupo A

`CardUpdate` não expõe `external_id`/`external_source`, então é SQL no banco do TaskHS — script para o Erick rodar no Konsole, no padrão do combinado de `sudo`/`admin.toml`.

```sql
-- Adota os 8 cards manuais das caixas de Phoebus+Modulo paradas no Pos-Vendas.
-- Os cards NAO saem de lugar: a lista 202 ja e' a que o GestorHS usa para a fase 6.
-- Depois disso o upsert do GestorHS encontra estes cards em vez de criar duplicata.
BEGIN;
UPDATE cards SET external_source = 'gestorhs', external_id = '1003' WHERE id = 1935;
UPDATE cards SET external_source = 'gestorhs', external_id = '1011' WHERE id = 1964;
UPDATE cards SET external_source = 'gestorhs', external_id = '1028' WHERE id = 1982;
UPDATE cards SET external_source = 'gestorhs', external_id = '1030' WHERE id = 1984;
UPDATE cards SET external_source = 'gestorhs', external_id = '1041' WHERE id = 2010;
UPDATE cards SET external_source = 'gestorhs', external_id = '1043' WHERE id = 2012;
UPDATE cards SET external_source = 'gestorhs', external_id = '1047' WHERE id = 2016;
UPDATE cards SET external_source = 'gestorhs', external_id = '1049' WHERE id = 2018;
-- Confira 8 linhas e nenhuma violacao de uq_card_external antes do COMMIT:
--   select id, title, list_id, external_source, external_id from cards
--    where id in (1935,1964,1982,1984,2010,2012,2016,2018);
COMMIT;
```

⚠️ **`uq_card_external` é `UniqueConstraint("external_source", "external_id")`.** Se alguma dessas caixas já tiver um card espelhado (não deveria — o gate bloqueou desde sempre), o `UPDATE` falha. O script roda em transação justamente para abortar inteiro nesse caso; confirmar antes com a consulta do comentário.

O par card↔caixa acima é o levantamento de 18/09/2026. **Reconferir antes de rodar**, porque card pode ser arquivado ou caixa pode andar de fase nesse meio-tempo.

## O laço que se fecha sozinho

Quando o GestorHS avança a caixa 6 → 10, o espelhamento move o card para a 205 — o que dispara a automação, que chama o GestorHS de volta. **Não é loop infinito:** a caixa já está na fase 10, `estado_para_avanco` devolve `no_op`, o endpoint responde `movida: false` e a corrente morre no segundo salto. É o mesmo mecanismo que já protege o inbound do GrowthHS e tem teste próprio nesta spec.

## Testes

**GestorHS**

- `test_avanco_inbound.py` (novo, núcleo puro): `estado_para_avanco` devolve `avancar` na fase 6; `no_op` nas fases 10, 7 e 8; `fase_errada` nas fases 4 e 5 e em caixa arquivada (`fase is None`).
- `test_integracao_taskhs.py` (novo): caixa Phoebus+Módulo na 6 avança para a 10 e as OS acompanham; caixa só Phoebus avança; **caixa normal na 6 responde 409 e NÃO ganha aceite**; caixa 100% Módulo na 6 responde 409 (não tem card no board, não deveria chegar aqui); segunda chamada na mesma caixa responde 200 com `movida: false`; chamada na fase 4 responde 409; sem chave configurada responde 503; chave errada responde 401; header com caractere não-ASCII responde 401 e **não** 500.
- `test_growthhs_inbound`: a suíte existente continua passando sem alteração — é o que trava que a extração para `core/` não mudou comportamento.
- `test_taskhs_bloqueio_modulo.py`: dos 8 testes, **2 invertem e 1 muda de texto**; os outros 5 montam a caixa com `EQUIPAMENTO_MODULO_ID` puro e continuam valendo como estão. Invertem: `test_avancar_caixa_de_phoebus_nao_espelha` (passa a **esperar** espelhamento, e o nome muda) e `test_avancar_caixa_mista_nao_espelha` (mista é Módulo + aparelho comum, que sob o critério estreito espelha). Muda de texto: `test_bloqueio_registra_log_pulado`, cujo `motivo` esperado vira `"caixa_so_de_modulo"`. Ficam intactos `test_avancar_caixa_de_modulo_nao_espelha`, `test_avancar_caixa_comum_continua_espelhando`, `test_caixa_cujo_modulo_esta_cancelado_volta_a_espelhar`, `test_cancelar_caixa_de_modulo_nao_arquiva_card` e `test_anexar_nota_fiscal_em_caixa_de_modulo_nao_espelha`. Entra um caso novo para Phoebus+Módulo, que é a composição das 7 caixas reais.
- `test_growthhs_bloqueio_modulo.py`: **não muda**, e é isso que trava a decisão de que o board comercial mantém o critério largo.
- `test_fluxo_modulo.py`: `caixa_so_de_modulo` com as cinco composições, mais um caso travando que `caixa_pula_posvendas` e `caixa_so_de_modulo` concordam em todas elas.

**TaskHS** (a sessão de lá escreve)

- `_avisar_gestorhs` é no-op para card com `external_source` nulo, para `external_source` diferente de `gestorhs` e para `external_id` vazio.
- Sem `GESTORHS_BASE_URL` ou sem chave, não há chamada HTTP.
- Erro HTTP e timeout **não** propagam: o movimento do card continua válido.
- `httpx` mockado sempre; o teste nunca chama o GestorHS de verdade.

## Ordem de implantação

A ordem importa, pelo mesmo motivo que importou hoje de manhã — o código em produção precisa poder lidar com o estado que se cria.

1. **GestorHS:** implementar, mergear e **deployar**, com `TASKHS_INBOUND_API_KEY` vazia. Nada muda de comportamento externo: a chave vazia devolve 503 e o endpoint fica inerte.
2. **Adoção:** rodar o SQL dos 8 cards. Fazer isto **depois** do deploy e **antes** de qualquer avanço dessas caixas, para que o primeiro espelhamento encontre o card adotado em vez de criar duplicata.
3. **Grupo B:** decidir o que fazer com 639, 670, 685 e 692 **antes** que algo toque essas caixas. Com o critério estreito no ar, o próximo avanço delas cria um card novo na lista 196, ao lado do card manual em `Serviços`/`Pendências`. Está **fora do escopo** deste desenho — ver abaixo.
4. **TaskHS:** implementar a ação, configurar `GESTORHS_BASE_URL` e `GESTORHS_INBOUND_API_KEY`, deployar.
5. **Ligar:** gerar a chave, pôr o mesmo valor nos dois lados (`TASKHS_INBOUND_API_KEY` aqui, `GESTORHS_INBOUND_API_KEY` lá) e cadastrar a automação na lista 205.
6. **Validar com uma caixa só**, movendo o card à mão de 202 para 205 e conferindo a fase no GestorHS antes de contar ao setor.

## Fora do escopo

- **Os 4 cards do grupo B** (639, 670, 685, 692). Têm drift real entre os dois sistemas — o GestorHS diz fase 4, o TaskHS diz `Serviços`/`Pendências` — e resolver isso é decidir qual dos dois está certo, caixa por caixa. Merece conversa própria. O item 3 da ordem de implantação registra o risco de card duplicado até essa conversa acontecer.
- **Os 365 cards manuais legados** e as 32 caixas normais em fase ativa com card manual. Nada aqui os toca.
- **O board do GrowthHS.** Segue com `caixa_de_modulo` (`any`): Phoebus não tem proposta lá.
- **Avanço em qualquer outra transição.** A automação cobre só 6 → 10. Nada de "card na lista 208 finaliza a caixa": sair da 10 exige nota fiscal e sair da 7 exige `cod_retorno`, validações que o card não tem como satisfazer.
- **Changelog e versão.** A entrega é invisível ao usuário do GestorHS (nenhuma tela muda); fica a critério do Erick se merece entrada.
