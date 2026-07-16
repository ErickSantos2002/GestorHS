# Caixas: remover "Vincular OS" e fechar OS por seleção — Design

**Data:** 2026-07-16
**Área:** frontend (`app/caixas/CaixaDetailPage.tsx`); sem mudança de backend.

## Problema

Duas mudanças pedidas na tela de detalhe de uma Caixa:

1. **Vincular OS existente virou redundante.** Vincular a OS a uma caixa passou a ser
   obrigatório na criação da OS, então o botão "Vincular OS existente" dentro da caixa não faz
   mais sentido.

2. **Fechar OS de dentro da caixa.** Quando as OS de uma caixa chegam em **Preparando Retorno**,
   estão prontas para finalizar — e todas retornam juntas, com basicamente o **mesmo código de
   rastreio**. Hoje é preciso entrar OS por OS para fechar. A equipe quer fechar direto da
   caixa, selecionando quais OS fechar e aplicando um código de retorno a todas de uma vez —
   porque às vezes, de 10 aparelhos, 9 são liberados e 1 fica para manutenção.

## Objetivo

- Remover o botão "Vincular OS existente" (e seu modal) da tela da caixa.
- Permitir **selecionar** as OS que estão em Preparando Retorno e **fechá-las juntas** com um
  único código de retorno, direto da caixa — ou fechar apenas uma, marcando só ela.

## Não-objetivos

- Não mexer no botão "Mover OS para outra caixa" (continua usando `caixasApi.vincularOrdem`).
- Não criar endpoint novo no backend — reusa o `avancar` de OS existente.
- Não fechar OS que não estejam em Preparando Retorno (não são selecionáveis).

## Arquitetura

Tudo no frontend, em `CaixaDetailPage.tsx`. O fechamento reusa o fluxo já existente
(`ordensApi.avancar(osId, { cod_retorno, obs })`), que na fase 7 finaliza a OS (fase 7 → 8),
grava o código de retorno, marca a situação, registra log e espelha no TaskHS — exatamente
como a tela da OS faz hoje.

### Change 1 — remover "Vincular OS existente"

- Remover o botão "Vincular OS existente" do bloco de ações do lote.
- Remover o modal "Vincular OS existente" e o estado/handler só dele
  (`vincularAberto`, `osVincular`, `erroVincular`, `vinculando`, `confirmarVincular`).
- **Manter** `caixasApi.vincularOrdem` — o modal "Mover OS" o utiliza (`confirmarMover`).

### Change 2 — fechar OS por seleção

**Seleção:**
- Coluna de **checkbox** nas linhas da tabela de OS, **apenas** para OS em Preparando Retorno
  (`o.fase === 7`). Linhas em outras fases não têm checkbox (não selecionáveis).
- Estado local `selecionadas: Set<number>` (ids de OS). Um checkbox no cabeçalho "marcar/
  desmarcar todas as elegíveis" é desejável (só age sobre as em fase 7).
- A coluna/checkbox e o botão de fechar só aparecem para `podeEscrever` (Admin/Expedição, que
  é o responsável da fase 7 — o backend valida a função real).

**Ação:**
- Botão **"Fechar OS selecionadas (N)"** no bloco de ações, habilitado quando `N ≥ 1`.
- Abre um modal próprio (`FecharOrdensModal`) com um campo **"Código de retorno"** (obrigatório)
  e uma **observação** opcional — mesma aparência do `AvancarModal`.
- Ao confirmar: para cada OS selecionada, chama `ordensApi.avancar(osId, { cod_retorno, obs })`
  em sequência, aplicando o **mesmo** código. Ao final:
  - conta sucessos e falhas; se houver falha (ex.: 403 de função, ou a OS saiu da fase 7),
    mostra "X fechada(s), Y falharam" com o motivo agregado;
  - recarrega a caixa (`carregar()`) e limpa a seleção.
- Fechar **uma só** é o mesmo fluxo com uma OS marcada.

**Contrato do modal `FecharOrdensModal`** (novo, pequeno):
- Props: `quantidade: number`, `onClose()`, `onConfirmar(cod_retorno: string, obs: string | null) => Promise<void>`.
- Campo código obrigatório (bloqueia confirmar se vazio); repassa o loop ao pai; mostra estado
  "Fechando…" enquanto o pai processa e erro se o pai rejeitar.

### Tolerância a falha parcial

O fechamento é um laço de N chamadas independentes (não atômico). Falha parcial é **esperada e
aceitável** (9 fecham, 1 sem permissão falha) — a UI informa o resultado e recarrega; as que
fecharam permanecem fechadas. Cada `avancar` mantém seu próprio log e espelhamento no TaskHS.

## Segurança / permissões

- Botão e checkboxes atrás de `podeEscrever` (`podeAbrirOS` = Admin/Expedição).
- O backend continua exigindo a função responsável da fase 7 (Expedição) em cada `avancar`
  (`exige_funcao_da_fase`) — a UI é conveniência, a autorização é do servidor.

## Testes

- **Frontend (Vitest):**
  - Só OS em `fase === 7` recebem checkbox; OS de outras fases, não.
  - Marcar OS habilita "Fechar OS selecionadas (N)" com a contagem correta.
  - Confirmar o modal chama `ordensApi.avancar` uma vez por OS selecionada, com o mesmo
    `cod_retorno`.
  - Falha parcial (uma chamada rejeita) é reportada e não impede as demais.
  - O botão "Vincular OS existente" não existe mais; "Mover" continua funcionando.

## Riscos

- **Laço de chamadas**: N requisições em vez de uma. Aceitável para o volume de uma caixa
  (poucas OS). Se no futuro o volume crescer, dá para trocar por um endpoint de fechamento em
  lote — fora de escopo agora.
- **Reaproveitar o `avancar`**: garante mesma regra de negócio/telemetria da tela da OS, sem
  duplicar lógica no backend.
