# Caixa de módulo/phoebus não vai para as integrações — Design

**Data:** 2026-07-30
**Área:** backend (novo `core/fluxo_modulo.py`, `models/ordem.py`, `api/espelhamento.py`, `api/growthhs_cards.py`, `scripts/reenviar_os_taskhs.py`) + testes.
**Tipo:** gate de integração (bloqueio); nenhuma migração, nenhuma mudança de frontend.

## Problema

Módulo e Phoebus seguem um fluxo de serviço diferente do resto dos equipamentos. Hoje a caixa deles é espelhada como card no TaskHS e vira card de caixa no GrowthHS igual a qualquer outra, poluindo os dois boards com trabalho que não é acompanhado por lá. Queremos que **caixa com módulo ou phoebus não gere card em nenhuma das duas integrações**, e que o resto continue funcionando exatamente como hoje.

Em produção: **140** caixas exclusivamente de módulo/phoebus, **2** mistas, 727 sem nenhum (869 caixas no total).

## Regra

**Vale daqui pra frente.** O que já foi enviado fica onde está — nada de mexer, arquivar ou limpar card antigo (ver *Fora do escopo*).

Uma caixa não gera card quando **qualquer** uma de suas OS não canceladas é de um destes equipamentos de catálogo:

| id | descrição |
|---|---|
| 36 | Phoebus |
| 47 | Módulo de Calibração do Bafômetro Automatizado PHOEBUS |

- **Só 36 e 47.** O catálogo tem também `49` (Módulo de Calibração para EBS) e `37` (EBS); ficam de fora — se um dia entrarem, é uma linha no conjunto.
- **Qualquer OS contamina a caixa.** Caixa mista (módulo + comum) não gera card. São 2 em 869, provável erro de montagem; a alternativa (bloquear só caixa 100% módulo) deixaria uma porta silenciosa.
- **OS cancelada não conta.** Vale o mesmo conjunto que o payload da caixa já usa hoje: fase ≠ 9, com fallback para a lista completa quando toda a caixa está cancelada. OS de módulo cancelada não bloqueia; qualquer OS de módulo viva bloqueia.
- **OS sem equipamento vinculado não bloqueia.** `equipamento_cliente` é nullable; sem equipamento não há como afirmar que é módulo.

## Contexto (o que existe hoje)

- **Ids de catálogo:** `config.py` já tem `EQUIPAMENTO_PHOEBUS_ID = 36` e `EQUIPAMENTO_MODULO_ID = 47` como fonte única (vêm do elo Phoebus↔Módulo, v1.19.0).
- **TaskHS:** `api/espelhamento.py` é o ponto de estrangulamento — `agendar_espelhamento_caixa` (chamado em `caixas.py` no avançar e no cancelar, em `ordens.py` e em `notas_fiscais.py`), `agendar_espelhamento` (por OS, no upload de NF) e `espelhar_os_sync` (backfill). Os gates de hoje: `list_id is None` e `taskhs_client.integracao_ativa()`.
- **TaskHS, fora da camada:** `scripts/reenviar_os_taskhs.py` monta o payload com `espelhamento._montar_payload_os` e chama `taskhs_client.enviar_card_sync` **direto** — não passa pelos gates de `espelhamento.py`.
- **GrowthHS:** `api/growthhs_cards.py` — `agendar_card_caixa` é chamado em `caixas.py:216` na saída do Laboratório; `agendar_card_os` não tem call site em produção (só testes o exercitam).
- **`Ordem`** expõe `equipamento_serie` e `equipamento_descricao`, mas **não** o id de catálogo.
- **Log de integração:** `registrar_log_integracao(..., status="pulado", motivo=...)` já é usado para `"desligado"` (TaskHS) e `"sem_equipamento"` (GrowthHS), e aparece na tela de logs de integração.

## Design

### 1. Predicado puro — `core/fluxo_modulo.py` (novo)

O predicado é consumido pelas duas integrações, então não pode morar em `core/taskhs.py`. Módulo novo, pequeno, sem I/O:

```python
EQUIPAMENTOS_DE_MODULO = {settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_MODULO_ID}

def os_de_modulo(ordem) -> bool      # a OS é de módulo/phoebus
def caixa_de_modulo(ordens) -> bool  # qualquer OS da lista é de módulo/phoebus
```

`caixa_de_modulo` recebe a **lista de ordens já filtrada** pelo chamador, não a caixa — mantém o módulo puro e deixa o critério de "quais ordens contam" visível no ponto de uso.

O filtro em si (fase ≠ 9 com fallback) vira `ordens_do_card(caixa)` em `core/caixa.py`, hoje embutido dentro de `_montar_payload_caixa`. Sem essa extração o mesmo critério apareceria escrito três vezes — no gate do TaskHS, no gate do GrowthHS e na montagem do payload — e as três acabariam divergindo.

### 2. Id de catálogo na OS — `models/ordem.py`

Property nova, no padrão das vizinhas:

```python
@property
def equipamento_catalogo(self):
    return self.equipamento_rel.equipamento if self.equipamento_rel else None
```

### 3. Gates — 5 pontos

**`api/espelhamento.py` (TaskHS):**
- `agendar_espelhamento_caixa` → `caixa_de_modulo(ordens não canceladas)`, antes de montar o payload.
- `agendar_espelhamento` → `os_de_modulo(ordem)`.
- `espelhar_os_sync` → `os_de_modulo(ordem)`; passa a devolver `bool` (enviado/pulado) para `sincronizar_taskhs` contar pulados em vez de contá-los como enviados.

**`scripts/reenviar_os_taskhs.py` (TaskHS):** check próprio, imprimindo `PULA` no mesmo formato já usado para fase sem lista.

**`api/growthhs_cards.py` (GrowthHS):** `agendar_card_caixa` e `agendar_card_os`. O segundo não tem call site em produção, mas é gateado junto para não voltar já furado.

O bloqueio é **no-op silencioso** para o usuário: nenhum erro, nenhuma mensagem na tela, o avanço/cancelamento da caixa segue normal.

### 4. Observabilidade

Cada bloqueio grava `registrar_log_integracao(integracao=..., status="pulado", motivo="caixa_de_modulo")`, reusando o mecanismo existente. Aparece na tela de logs de integração sem UI nova.

## Fora do escopo (decidido, não esquecido)

- **Cards que já existem nos boards congelam onde estão.** O gate cobre criar, mover de lista e arquivar — é o mesmo caminho. Card de caixa de módulo que hoje está no TaskHS para de se mexer e fica parado na lista atual; a equipe arquiva a mão se incomodar. Sem script de limpeza em massa, sem exceção para arquivar.
- **Cargas de frota do GrowthHS não mudam.** `enviar_atrasados_growthhs` e `enviar_vencendo_growthhs` são agregados **por cliente** sobre a frota, não nascem de caixa. Continuam avisando calibração vencida/vencendo de módulo, com o elo do Phoebus no payload — o módulo é o item que de fato calibra, e o elo foi construído para aparecer ali.
- **Integração inbound do GrowthHS** (mover caixa Pós-Vendas → Financeiro) não muda.
- **Frontend não muda.** Nenhuma regra de função, nenhuma tela envolvida.

## Testes

**Puros — `tests/test_fluxo_modulo.py` (novo):** OS de módulo (47) bloqueia; OS de phoebus (36) bloqueia; equipamento comum não bloqueia; OS sem `equipamento_cliente` não bloqueia; caixa mista bloqueia; caixa só de comuns não bloqueia; lista vazia não bloqueia; equipamento 49 (Módulo EBS) **não** bloqueia (trava a decisão de escopo).

**De endpoint:** avançar caixa de módulo saindo do Laboratório não chama `taskhs_client` nem `hsgrowth_client`; caixa comum saindo do Laboratório continua chamando os dois; cancelar caixa de módulo não envia arquivamento ao TaskHS; caixa cuja única OS de módulo está cancelada volta a gerar card; upload de NF em OS de módulo não espelha card.

**Baseline:** esta máquina tem 5 falhas de teste pré-existentes — conferir o baseline antes de atribuir qualquer falha a esta mudança.

## Arquivos

Backend: `core/fluxo_modulo.py` (novo), `core/caixa.py`, `models/ordem.py`, `api/espelhamento.py`, `api/growthhs_cards.py`, `scripts/sincronizar_taskhs.py`, `scripts/reenviar_os_taskhs.py`. Testes: `test_fluxo_modulo.py`, `test_taskhs_bloqueio_modulo.py`, `test_growthhs_bloqueio_modulo.py`, `test_reenviar_os_taskhs.py` (novos) + `test_caixa_core.py` e `test_sincronizar_taskhs.py` (acrescentam casos). Frontend: só o changelog (v1.33.0).
