# Só a caixa 100% Módulo pula o Pós-Vendas — Design

**Data:** 2026-09-18
**Área:** backend (`core/fluxo_modulo.py`, `core/os_workflow.py`, `api/caixas.py`, 2 scripts existentes + 1 novo) + frontend (`src/app/ordens/OrdensPage.tsx`)
**Fase:** correção da rota entregue em 18/09/2026, já na `main` (commits `66c2fc0`, `c7c969d`, `5e34f89`, `4fee860`, `11209c7`, `a960f48`, `e0fed4b`). Aquela entrega saiu sem spec própria — o desenho dela está na seção "O ciclo de negócio e o workflow da OS" do [CLAUDE.md](../../../CLAUDE.md). O antecedente do critério de módulo é [2026-07-30-caixa-modulo-sem-integracao-design.md](2026-07-30-caixa-modulo-sem-integracao-design.md), que criou `fluxo_modulo` para a pergunta do card.

## Problema

A rota que pula o Pós-Vendas foi entregue com o critério **errado por ser largo demais**: qualquer caixa que contivesse Phoebus (36) **ou** Módulo (47) desviava do Laboratório(5) direto para o Financeiro(10).

O critério certo é mais estreito. **Só o Módulo sozinho** não passa pelo comercial — é serviço de bancada. Quando o aparelho Phoebus vem junto do módulo dele, a caixa **passa por serviço** e precisa do aceite do Pós-Vendas, igual a qualquer outra.

O erro foi herdar para a rota o mesmo predicado que existia para outra pergunta. `caixa_de_modulo()` nasceu respondendo "esta caixa vira card no TaskHS/GrowthHS?" — para essa pergunta `any(36 ou 47)` está certo, e continua. Ao reaproveitá-lo para "esta caixa pula o Pós-Vendas?", uma função passou a responder duas perguntas cujas respostas não coincidem.

## Evidência (levantada na base em 18/09/2026)

**Composição de todas as 171 caixas que contêm Phoebus ou Módulo:**

| composição | caixas |
|---|---|
| só Módulo (47) | 120 |
| só Phoebus (36) | 27 |
| Phoebus + Módulo | 22 |
| mista (com aparelho normal junto) | 2 |

**As 7 caixas paradas no Financeiro são todas `Phoebus + Módulo`** — `1003, 1011, 1028, 1030, 1043, 1047, 1049` — e as 7 foram postas lá pelo backfill `app.scripts.mover_phoebus_posvendas`, em 18/09/2026 11:31 UTC (`logs_os.texto LIKE '%nao passa por Pos-Vendas%'`). Nenhuma chegou ao Financeiro sozinha.

**O TaskHS é a prova de que elas ainda não passaram por serviço.** As 7 têm card no board `Serviço`, todos **feitos à mão** (`external_source` nulo — o gate de módulo bloqueou o espelhamento automático), e todos parados em **`🔬LIBERADOS DO LABORATÓRIO` (lista 202)**. A lista `Serviços 🪛` é a **203** e `💰Financeiro` a **205**: elas saíram do laboratório e ainda nem entraram no Serviços, enquanto o GestorHS já as tinha no Financeiro.

Reforço pelo outro lado: as duas `Phoebus + Módulo` mais antigas (**639** BATTRE e **692** Fertilizantes Tocantins) têm card em **`Serviços 🪛`**. O par completo gera serviço; o módulo sozinho não.

**Dano colateral:** das 22 `Phoebus + Módulo`, **6** foram encerradas pelo `ENC-ADM-20260918` sem nunca passar pelo Pós-Vendas.

## Decisões

| Pergunta | Decisão | Por quê |
|---|---|---|
| Quem pula o Pós-Vendas? | **Só a caixa cujas OS ativas são TODAS Módulo (47).** | Phoebus sozinho, Phoebus+Módulo e mista geram serviço e precisam do aceite comercial. |
| Phoebus+Módulo vira caixa "Normal"? | **Não.** Só a rota volta ao normal; o bloqueio do card continua. | Tratar como Normal ligaria o espelhamento e o board ganharia um card automático em cima do card manual que a equipe já mantém. |
| O que fazer com o estrago? | **Reverter só as 7 do Financeiro** (10 → 6). | As 6 fechadas pelo `ENC-ADM-20260918` já foram despachadas e o cliente recebeu; reabrir criaria caixa viva sem aparelho dentro. |
| O que o badge da tela significa? | **Composição da caixa**, em qualquer coluna. | "Tem Phoebus/módulo aqui dentro" já é informação útil por si: essa caixa não tem card automático no TaskHS, o card é feito à mão. |

## Desenho

### Núcleo — dois predicados, uma pergunta cada

`core/fluxo_modulo.py` passa a expor **dois** predicados:

| função | quantificador | responde |
|---|---|---|
| `caixa_de_modulo(ordens)` *(existe, inalterada)* | `any(36 ou 47)` | "bloqueia o card do TaskHS/GrowthHS?" |
| `caixa_pula_posvendas(ordens)` *(novo)* | `all(== 47)` | "pula o Pós-Vendas?" |

```python
def caixa_pula_posvendas(ordens) -> bool:
    """A caixa 100% Modulo e' a UNICA que nao passa pelo comercial."""
    ativas = list(ordens)
    return bool(ativas) and all(
        getattr(o, "equipamento_catalogo", None) == settings.EQUIPAMENTO_MODULO_ID
        for o in ativas)
```

O novo é batizado pelo **que decide**, não pela composição. É de propósito: o par `caixa_de_modulo` / `caixa_so_de_modulo` seria uma armadilha, porque em um "módulo" quer dizer *módulo ou Phoebus* e no outro *estritamente 47*. Lista vazia devolve `False` — caixa sem OS ativa não tem para onde desviar.

`caixa_de_modulo` e `rotulo_modulo` ficam com a lógica intacta; só as docstrings mudam, porque as duas deixaram de falar sobre desvio de fase.

Em `core/os_workflow.py`, `PROXIMA_MODULO` vira **`PROXIMA_SO_MODULO`** — o mapa deixou de valer para o Phoebus. O keyword `pula_posvendas` fica: é nome de decisão e continua correto.

### Consumidores

- [api/caixas.py:284](../../../backend/app/api/caixas.py) — `caixa_de_modulo` → `caixa_pula_posvendas`. O comentário perde o "mesmo critério que já tira a caixa do board do TaskHS/GrowthHS", que deixou de ser verdade: agora são dois critérios de propósito.
- [scripts/mover_phoebus_posvendas.py:63](../../../backend/app/scripts/mover_phoebus_posvendas.py) e [scripts/finalizar_caixas_phoebus.py:63](../../../backend/app/scripts/finalizar_caixas_phoebus.py) — `all(fluxo_modulo.os_de_modulo(o) for o in ativas)` vira `fluxo_modulo.caixa_pula_posvendas(ativas)`.
- `api/espelhamento.py`, `api/growthhs_cards.py`, `api/logs_integracao.py` — **não tocados**. Continuam chamando `caixa_de_modulo`, e o `motivo="caixa_de_modulo"` já gravado em log segue válido.

⚠️ **A divergência `any`/`all` documentada ontem deixa de existir.** Ela foi criada porque o backfill precisava de um critério mais estreito que o do avanço em tempo real. Com a regra nova os dois usam **o mesmo predicado**: a caixa mista cai fora por construção, não por uma segunda versão da regra. O aviso sai das docstrings dos dois scripts e do `CLAUDE.md`.

### Frontend

Em [OrdensPage.tsx:126](../../../frontend/src/app/ordens/OrdensPage.tsx), o badge sai de `col.fase === 10 && cx.modulo` para `cx.modulo` — passa a aparecer em qualquer coluna, porque agora fala de composição. A tooltip deixa de dizer "o serviço dele não passa pelo Pós-Vendas, por isso chegou direto ao Financeiro" e passa a dizer o que a caixa carrega e que o card do TaskHS dela é manual.

`ROTULO_MODULO` e o contrato `'phoebus' | 'modulo' | 'ambos' | null` de [caixas/api.ts:87](../../../frontend/src/app/caixas/api.ts) **não mudam**. `roles.ts` não é tocado: não é regra de função.

### Correção de produção

Script novo `app/scripts/reverter_posvendas_phoebus_modulo.py`, de uso único, **simula por padrão** (`--aplicar` grava), no padrão dos demais.

- **Alvo, tríplice e auto-limitante:** caixa em fase 10 **e** com o log do backfill (`Caixa #N: 6 -> 10 (fluxo do Phoebus/Modulo...`) **e** `not caixa_pula_posvendas(ativas)`.
- **Ação:** OS ativas e caixa voltam para a fase 6, com log `Caixa #N: 10 -> 6`.
- **Recusa** se achar `aceite`, `pago` ou nota fiscal (linha em `notas_fiscais` ou coluna legada) em qualquer caixa do lote. Conferido em 18/09/2026: as 7 estão zeradas nos cinco campos. A trava existe para o que possa mudar entre agora e a execução.
- **Não fala com TaskHS nem GrowthHS.** As 7 nunca tiveram card espelhado — os cards são manuais.
- **Esperado:** 7 caixas / 17 OS.

## Testes

- `test_fluxo_modulo.py` — `test_rotulo_concorda_com_caixa_de_modulo` muda de alvo: vira **implicação** (`caixa_pula_posvendas(x) ⟹ rotulo_modulo(x) == 'modulo'`), não mais equivalência. Casos novos para `caixa_pula_posvendas` nas cinco composições: só módulo `True`; Phoebus+Módulo, só Phoebus, mista e vazia `False`.
- `test_caixa_pula_posvendas.py` — muda de premissa, não de caso. O módulo do arquivo hoje afirma "o criterio e' UM so: `fluxo_modulo.caixa_de_modulo`", e `test_caixa_de_modulo_vai_do_lab_direto_ao_financeiro` é **parametrizado sobre `[PHOEBUS_ID, MODULO_ID]`**, esperando fase 10 nos dois. O parametrize se desfaz: Módulo sozinho continua indo para 10; Phoebus sozinho passa a ir para **6**. Os outros quatro testes do arquivo (sem aceite, fluxo do Financeiro em diante, travado no lab, controle positivo) passam a montar a caixa só com Módulo. Entra um caso novo para o par Phoebus+Módulo na mesma caixa, que é o bug desta spec.
- `test_mover_phoebus_posvendas.py`, `test_finalizar_caixas_phoebus.py`, `test_os_workflow.py` — casos que hoje esperam o desvio com Phoebus **invertem**, e o nome do mapa renomeado acompanha.
- `test_reverter_posvendas_phoebus_modulo.py` — novo: seleção pelo critério tríplice, recusa com aceite/pago/nota, idempotência.
- `test_taskhs_bloqueio_modulo.py` e `test_growthhs_bloqueio_modulo.py` — **não mudam**, e é justamente isso que trava a decisão de que Phoebus+Módulo não virou "Normal".
- Frontend: `OrdensPage.modulo.test.tsx` tem um teste *"nao mostra aviso fora do Financeiro"* que **inverte** — o badge passa a aparecer fora do Financeiro.

Baseline desta máquina: **4 falhas pré-existentes** (`PermissionError` em `test_certificados_gerais.py` e `test_publico_certificado_geral.py`). Verde é bater a baseline, não zero.

## Fora do escopo

- **As 6 caixas fechadas pelo `ENC-ADM-20260918` ficam como estão.** Já despachadas; reabrir criaria caixa viva sem aparelho dentro. O rollback em `~/projetos/gestorhs-backups/rollback-ENC-ADM-20260918.sql` continua disponível se a decisão mudar.
- **Changelog e bump de versão** seguem pendentes em `frontend/src/app/changelog/data.ts`, agora cobrindo a rota e esta correção numa entrada só.
