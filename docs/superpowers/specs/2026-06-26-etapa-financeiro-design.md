# Nova etapa "Financeiro" na Ordem de Serviço

**Data:** 2026-06-26
**Status:** aprovado (brainstorming)

## Objetivo

Inserir uma etapa **Financeiro** no workflow da OS, **entre Pós-Vendas e
Preparando Retorno**, responsável por confirmar o pagamento antes de liberar o
envio. Avançar a etapa marca a OS como paga.

Fluxo novo:

```
Recebido(4) → Laboratório(5) → Pós-Vendas(6) → Financeiro(10) → Preparando Retorno(7) → Finalizada(8)
```
`Cancelada(9)` segue como saída a qualquer momento.

## Decisões (aprovadas)

- **ID da fase:** `10` (IDs não são sequenciais; a ordem vem do mapa `PROXIMA`).
- **Função responsável:** nova função **`Financeiro`**. (Operacional: após a
  migração, é preciso criar/atribuir um usuário com essa função; Admin sempre pode.)
- **Ação ao avançar (10 → 7):** marca `ordens.pago = True` e grava
  `ordens.data_pagamento` (coluna nova), espelhando o par `aceite`/`data_aceite`.
- **Rótulo do botão (fase 10):** `Confirmar pagamento`.
- **Cor da fase:** `a855f7` (roxo).
- **Lista no TaskHS:** `💰 Financeiro` (coluna nova no board `Serviço`).

## Backend

### Workflow — `app/core/os_workflow.py`
- `FASE_FINANCEIRO = 10`.
- `PROXIMA = {4: 5, 5: 6, 6: 10, 10: 7, 7: 8}`.
- `ATIVAS = (4, 5, 6, 10, 7)` (ordem reflete a sequência lógica — usada pelo kanban).
- **Ordem lógica das fases** (nova), para qualquer comparação de "antes/depois"
  que hoje usa o ID numérico cru (o ID 10 quebra `>=`):
  ```python
  ORDEM_FASES = {4: 0, 5: 1, 6: 2, 10: 3, 7: 4, 8: 5}
  def posicao(fase: int) -> int:
      return ORDEM_FASES.get(fase, 99)  # desconhecida/cancelada -> fim
  ```

### Transição — `app/api/ordens.py` (`avancar`)
Nova ramificação por fase de origem:
- origem `5` (Laboratório → Pós-Vendas): inalterado (exige certificado, espelha calibração).
- origem `6` (Pós-Vendas → **Financeiro**): inalterado — registra aceite
  (`aceite=True`, `data_aceite=agora()`). Só muda o destino (10 em vez de 7), o que
  já é automático via `PROXIMA`.
- origem `10` (**Financeiro** → Preparando Retorno): **novo** — `ordem.pago = True`,
  `ordem.data_pagamento = agora()`, texto de log `"Pagamento confirmado"`.
- origem `7` (Preparando Retorno → Finalizada): inalterado (exige `cod_retorno`).
- origem `4` (Recebido → Laboratório): inalterado.

Autorização: `exige_funcao_da_fase` já lê `fases.funcao_responsavel`; com a fase 10
apontando para a função `Financeiro`, o gate funciona sem código novo.

### Migração — `0010_etapa_financeiro.py`
1. `op.add_column("ordens", sa.Column("data_pagamento", sa.DateTime(timezone=True), nullable=True))`.
2. Inserir a função: `INSERT INTO funcoes (descricao) VALUES ('Financeiro') ON CONFLICT DO NOTHING`
   (ou equivalente que respeite o schema de `funcoes`), e obter seu id.
3. Inserir a fase: `INSERT INTO fases (id, descricao, cor, funcao_responsavel)
   VALUES (10, 'Financeiro', 'a855f7', <id_financeiro>) ON CONFLICT (id) DO NOTHING`.
- `downgrade`: remover a fase 10, a função `Financeiro` (se sem uso) e a coluna
  `data_pagamento`.

### Modelo — `app/models/ordem.py`
- Adicionar `data_pagamento = Column(DateTime(timezone=True), nullable=True)`.

## TaskHS

### Mapa — `app/core/taskhs.py`
- `FASE_PARA_LISTA[10] = "💰 Financeiro"`.

### Descrição do card — `app/core/taskhs.py` (`montar_descricao`)
- **Trocar as comparações numéricas de fase por `os_workflow.posicao(...)`** nas
  seções que dependem de ordem:
  - 🤝 Pós-Vendas: aparece quando `posicao(fase) >= posicao(6)`.
  - 🚚 Preparando Retorno: aparece quando `posicao(fase) >= posicao(7)`.
  (📋 Recebido continua a partir do recebimento; 📮 Finalizada continua por `cod_retorno`.)
- **Nova seção `💰 Financeiro`**, entre Pós-Vendas e Preparando Retorno, quando
  `posicao(fase) >= posicao(10)`:
  - `Pagamento: confirmado em {data_pagamento:DD/MM/AAAA}` quando `pago` é true
    (sem data → `Pagamento: confirmado`);
  - `Pagamento: pendente` caso contrário.

## Frontend

### `src/app/ordens/api.ts`
- `TRANSICOES[10] = { rotulo: 'Confirmar pagamento' }` (o `TRANSICOES[6]` continua
  `'Registrar aceite'`).
- `FASES_ATIVAS = [4, 5, 6, 10, 7]`.

### `src/auth/roles.ts`
- `export const FUNCAO_FINANCEIRO = 'Financeiro'` (espelho do nome usado no backend).

### Kanban
- O `quadro` (backend) já deriva as colunas de `wf.ATIVAS`; o frontend renderiza as
  colunas que a API devolve. Com a fase 10 em `ATIVAS`, a coluna **Financeiro**
  aparece sozinha entre Pós-Vendas e Preparando Retorno — sem mudança estrutural no
  componente. (Verificar apenas que o componente não tem fases hard-coded.)

## Testes

- **Workflow** (`test_os_workflow*` / unit): `proxima_fase(6)==10`, `proxima_fase(10)==7`;
  `eh_ativa(10)` true; `posicao` ordena `4<5<6<10<7<8` e devolve fim para 9/desconhecida.
- **`avancar`** (`test_ordens_avancar.py`): 6→10 registra aceite; 10→7 marca
  `pago=True` + `data_pagamento` setado + log "Pagamento confirmado"; o fluxo
  completo 4→5→6→10→7→8 funciona.
- **Autorização** (`test_ordens_*`): usuário com função `Financeiro` avança a fase 10;
  outra função (não-admin) recebe 403; Admin avança.
- **TaskHS** (`test_taskhs*`): `lista_da_fase(10) == "💰 Financeiro"`; `montar_descricao`
  mostra a seção 💰 Financeiro (pendente vs confirmado) e **não** mostra Preparando
  Retorno enquanto em Financeiro (graças à `posicao`).
- **Fixtures** (`conftest.py`): `fases_seed` ganha a fase 10 + função `Financeiro`;
  nova fixture `usuario_financeiro`.

## Changelog

- `frontend/src/app/changelog/data.ts`: entrada **v1.11.0** — nova etapa Financeiro
  entre Pós-Vendas e Preparando Retorno (confirma pagamento antes de liberar o envio).

## Fora de escopo

- Captura de valor cobrado / forma de pagamento (decidido: só marca `pago` + data).
- Tela/relatório financeiro dedicado.
- Renumeração de fases existentes.
- Backfill de OS antigas para a nova fase (as que estão em Pós-Vendas seguem o fluxo
  normal e passarão pelo Financeiro no próximo avanço).
