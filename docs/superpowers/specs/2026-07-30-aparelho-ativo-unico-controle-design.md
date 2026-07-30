# Aparelho: um único controle de ativo/inativo — Design

**Data:** 2026-07-30
**Área:** frontend (`app/frota/EquipamentoClienteDetailPage.tsx`, `app/frota/api.ts`) + backend (`schemas/frota.py`) + testes.
**Tipo:** remoção de campo morto (sem migração, sem mudança de comportamento).

## Problema

A tela do aparelho tem **dois** controles para a mesma ideia:

| controle | campo | valores |
|---|---|---|
| Select "Situação" | `equipamentos_cliente.status` | `A` Ativo / `I` Inativo / `M` Manutenção |
| Checkbox "Ativo" | `equipamentos_cliente.ativo` | true / false |

São colunas independentes e podem se contradizer. Só o checkbox faz alguma coisa: `EquipamentoCliente.status` **não é lido em lugar nenhum do backend** — nenhum filtro, nenhuma regra. Quem manda é `ativo`, em cinco pontos:

- `api/portal.py:39,64` — o que o cliente enxerga da própria frota
- `api/dashboard.py:25,41` — os números do painel
- `api/alertas.py:40,85` — os alertas de calibração
- `scripts/enviar_vencendo_growthhs.py:90` e `scripts/enviar_atrasados_growthhs.py:94` — as cargas de cobrança no GrowthHS

Quem marca **Situação = Inativo** achando que aposentou o aparelho não aposenta nada: ele segue no portal do cliente, no dashboard, gerando alerta e indo pro GrowthHS como vencido/vencendo — virando cobrança de aparelho que o cliente pode nem ter mais.

## Evidência (produção, 30/07/2026)

| `status` | `ativo` | aparelhos |
|---|---|---|
| A | **false** | **1.624** |
| A | true | 7.102 |
| I | true | **1** |
| M | — | **0** |

Leitura: 1.624 aparelhos estão desativados de verdade e a tela mostra "Situação: Ativo" para todos — a contradição já é massiva hoje. O dropdown foi usado **uma vez** (aparelho 7939, Cofco, Módulo PHOEBUS F000472), e nem ali surtiu efeito: o aparelho continua `ativo`, com OS 10868 aberta. "Manutenção" nunca foi usada.

O `status` A/I/M também não é renderizado em nenhum outro lugar — nem na lista da Frota, nem na aba do cliente, nem no portal. Existe só naquele Select. (Cuidado com o homônimo: o parâmetro `status` da listagem de frota é o filtro de **calibração** — `vencido`/`vencendo`/`em_dia`/`sem_data` — e não tem relação com este campo.)

## Decisão

Fica o `ativo`; sai o `status`. É o campo que funciona, o que carrega os 1.624 valores reais e o que as regras de negócio leem.

"Manutenção" **não** vira estado de verdade: zero registros em 8.727 aparelhos, e aparelho em manutenção já é visível pelo fluxo da OS.

## Design

### 1. Tela do aparelho — `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`

O Select "Situação" (linhas 198-202) sai. O checkbox "Ativo" (linhas 204-207) ocupa o lugar dele, dentro do mesmo `grid` de duas colunas ao lado do campo "Módulo", para a linha não ficar com um buraco. `status` sai do estado do formulário e do payload.

### 2. API — `backend/app/schemas/frota.py`

`status` sai dos quatro schemas onde aparece — leitura em `FrotaListOut:16` e `EquipamentoClienteOut:56`, escrita em `EquipamentoClienteCreate:83` e `EquipamentoClienteUpdate:95`. Nada mais lê nem grava o campo.

**Não confundir com `status_calibracao`**, que fica nos dois schemas de leitura logo abaixo do campo removido: é o classificador de calibração (`vencido`/`vencendo`/`em_dia`/`sem_data`) e nada tem a ver com este trabalho.

A coluna `equipamentos_cliente.status` **fica no banco**, com os dados de hoje, congelada. Sem migração: nada de perder histórico, e nada que possa ser desfeito errado. O modelo já tem `default="A"`, então aparelho novo continua nascendo com `'A'` sem ninguém informar.

O tipo espelho no frontend (`app/frota/api.ts`) perde o campo junto.

### 3. Dados

Nada a corrigir. Os 1.624 aparelhos com `ativo = false` já estão desativados de verdade e continuam assim. O aparelho 7939 fica **ativo** — decisão explícita: o "Inativo" do dropdown nunca teve efeito, e ele está com OS aberta e calibração vencendo; desativá-lo agora o faria sumir do portal no meio do atendimento.

## Fora do escopo

- **Nenhuma migração.** A coluna não é dropada.
- **Nenhuma mudança de comportamento em produção.** Nenhuma das cinco regras que leem `ativo` é tocada. O que muda é só a tela deixar de oferecer um controle que enganava.
- **Manutenção como estado real** — descartado acima.

## Testes

**Backend:** criar aparelho sem `status` no payload funciona e persiste `'A'` por default; editar aparelho sem `status` funciona e não altera o valor gravado; a resposta da frota (lista e detalhe) não traz mais `status`.

**Frontend:** a tela do aparelho não renderiza mais o Select "Situação"; o checkbox "Ativo" continua presente e salva `ativo` corretamente (marcar e desmarcar).

**Baseline:** esta máquina tem 4 falhas pré-existentes no backend e 1 no frontend — conferir antes de atribuir qualquer falha a esta mudança.

## Arquivos

Frontend: `app/frota/EquipamentoClienteDetailPage.tsx`, `app/frota/api.ts`, testes ao lado. Backend: `schemas/frota.py`, `tests/test_frota*.py`. Changelog: entrada de release ao fechar.
