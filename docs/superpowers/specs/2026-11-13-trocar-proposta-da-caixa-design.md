# Trocar a proposta da caixa pela tela

## Por que

`caixas.numero_proposta` só é escrita pelo "Ganho" do GrowthHS, e o número vem digitado à
mão no card de lá. Erro de digitação (caixa 1212: #474 no lugar de #476, 13/11/2026) só se
corrigia com `app.scripts.corrigir_proposta_caixa` + `sincronizar_taskhs_caixas`, rodados
por quem tem acesso à máquina — e o segundo nem roda daqui (o `.env` local aponta para um
TaskHS local).

## O que

Botão **"Trocar proposta"** no bloco da proposta da tela da caixa. Informa o número novo,
o servidor confere, grava e reespelha o card da caixa no TaskHS (a obs3 mostra
"Proposta #N").

- **Quem:** Comercial Pós-Vendas e Administrador (`require_funcao` no backend,
  `podeTrocarPropostaCaixa` em `roles.ts`).
- **Quando:** caixa em fase ativa até Preparando Retorno — 4, 5, 6, 10, 7, por
  `posicao()`. Finalizada, cancelada ou arquivada → 409. Motivo: depois da 7 o card pode
  estar em lista que o GestorHS não conhece (209/210) e reespelhar o arrastaria de volta.
- **Trava:** a mesma do script — proposta existe, não está desabilitada, tem cliente, e o
  cliente é o da caixa (principal ou de alguma OS, canceladas inclusive). A regra sai do
  script para `app/core/proposta_caixa.py` e o script passa a importar de lá.
- **Rastro:** uma linha no log de cada OS ativa da caixa: `Caixa #N: proposta #A -> #B`.
- **Número igual ao atual:** devolve a caixa sem gravar nem reespelhar.

## Endpoint

`PUT /caixas/{caixa_id}/proposta` com `{"numero": int}` → `CaixaDetalhe`.
404 caixa/proposta inexistente · 409 fase fora da janela · 422 proposta recusada pela trava.
Fora do catálogo do agente (Guardi): não entra em `ESCRITAS_AGENTE`.

## Fora do escopo

- Não desfaz faturamento da proposta anterior (`--desfaturar-anterior` segue no script).
- Não corrige o `proposal_number` no card do GrowthHS. A tela avisa que um novo "Ganho"
  regrava o número de lá.
- Caixa sem número, ou com número só do CRM antigo, não mostra o bloco — logo, não mostra
  o botão. Esses casos continuam no script.

## Abordagens

1. **Endpoint dedicado + botão no bloco da proposta** (escolhida): regra e permissão
   próprias, sem abrir o `PATCH /caixas` genérico, que é da Expedição.
2. Abrir `numero_proposta` no `PATCH /caixas/{id}`: mistura permissões (Expedição) e
   pularia trava e reespelhamento.
3. Só uma tela que roda o script: não resolve o card e depende da máquina.
