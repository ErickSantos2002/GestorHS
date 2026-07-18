# Elo Phoebus ↔ Módulo — Design

**Data:** 2026-07-18
**Área:** backend (modelo + migração + script de carga + leitura na API) e frontend (painel somente-leitura na ficha do equipamento)

## Problema

O **Phoebus** é o etilômetro; ele **não** é calibrado e não abre OS de calibração. O que se
calibra é o **Módulo** dentro dele — por isso o módulo foi cadastrado como equipamento próprio
(recebe OS e certificado). Isso deu ótimo controle do módulo, mas **perdeu-se o elo**: hoje não
se sabe qual módulo está dentro de qual Phoebus.

Os módulos **circulam**: o cliente pede calibração, a Health Safety pega um módulo do estoque
sem uso, calibra e envia; o cliente troca o dele e devolve o antigo. O módulo é um **cartucho
intercambiável** — o cliente instala qualquer módulo em qualquer aparelho, sem obrigação. Por
isso a HS **não tem como saber** o par no momento da calibração, e o elo **não pode** ser
derivado do fluxo de OS.

## Objetivo

Registrar o elo aparelho↔módulo a partir de uma planilha (retrato atual), guardá-lo com
histórico, e exibi-lo — **somente leitura** — nas fichas do Phoebus e do módulo. O elo existe
principalmente para alimentar a futura **integração/exportação com o GrowthHS** (CRM), onde os
aparelhos com calibração vencida serão enviados junto do módulo e do aparelho a que ele está
ligado.

## Não-objetivos

- **Não** integrar/exportar para o GrowthHS agora (projeto próprio, depois; vai consumir esta tabela).
- **Não** criar tela de edição do elo — é somente leitura no sistema.
- **Não** amarrar o elo ao fluxo de OS nem obrigar ninguém a informá-lo ao calibrar.
- **Não** alterar cadastro existente de equipamentos/clientes (a carga é aditiva).
- **Não** criar equipamento/cliente que não exista — linha que não casa vira pendência.

## Dados de partida (medidos em 18/07/2026, banco 9998)

- Catálogo: `equipamentos` id **36 = "Phoebus"** (732 na frota) e id **47 = "Módulo de Calibração
  do Bafômetro Automatizado PHOEBUS"** (986 na frota).
- Planilha `docs/Lista de dispositivos.xlsx` (gitignored), aba `devices`, **671 linhas** (1 por
  Phoebus). Colunas usadas: **"Número de Série"** (série do aparelho), **"Número de Série do
  Módulo"**, **"Próxima Calibração"**; há ainda ID/Nome do Dispositivo, Empresa, Firmware.
- Cruzamento: aparelhos **603/671 (89,9%)** casam; módulos **529/580 (91,2%)** casam;
  **504 de 580 elos (86,9%)** têm os dois lados no banco → criáveis direto.
- **322 módulos do banco não estão na planilha** = o estoque/pool (confirma o modelo).
- **143 módulos no banco têm série vazia** (não casáveis).
- Casamento por **série exata** basta — normalizar (maiúsculas/traços) muda quase nada (+6/+2).

## Arquitetura

### Modelo — `instalacoes_modulo`

| coluna | tipo | nota |
|---|---|---|
| `id` | PK | |
| `modulo` | FK `equipamentos_cliente.id` | o módulo |
| `phoebus` | FK `equipamentos_cliente.id` | o aparelho |
| `entrou_em` | Date | quando o módulo entrou nesse aparelho |
| `saiu_em` | Date, nulo | **nulo = instalação aberta = elo atual** |
| `origem` | String | rastro da carga, ex.: `"planilha 2026-07-18"` |

- **Elo atual** = linha com `saiu_em IS NULL`.
- **Integridade:** índices únicos parciais garantindo, entre as instalações abertas, **um módulo
  em no máximo um aparelho** e **um aparelho com no máximo um módulo**.
- Ambos os lados apontam para `equipamentos_cliente` porque Phoebus e Módulo são, os dois,
  linhas dessa tabela.

### Script de carga

`python -m app.scripts.importar_elo_modulos <caminho.xlsx> [--origem "planilha 2026-07-18"] [--dry-run]`

- Lê o `.xlsx` **usando só a biblioteca padrão** (zipfile + ElementTree) — **sem nova dependência**
  no backend. Assim a próxima planilha só precisa ser passada como argumento.
- Identifica Phoebus e Módulo pelos ids de catálogo (36/47), **parametrizáveis** por argumento
  para não ficarem cravados no código.
- Casa por **série exata** contra `equipamentos_cliente.serie`.
- **Regras (decididas com o Erick):**
  1. Linha cujo aparelho **ou** módulo não casa → **pulada**, entra no relatório de pendências.
  2. Mesma série de módulo em mais de um aparelho → **vence a linha com a maior "Próxima
     Calibração"**; as demais viram pendência. (Validado: as perdedoras são visivelmente
     obsoletas — datas de 2000, "Desativado", "DEFEITO em CONSERTO".)
  3. Módulos com série vazia no banco → **ignorados** (não há como casar).
- **Aditivo:** só insere em `instalacoes_modulo`; **não altera** equipamento, cliente nem OS.
- **Reexecução:** ao rodar de novo, fecha (`saiu_em`) as instalações abertas que mudaram e abre
  as novas — o histórico se acumula. Rodar com a mesma planilha duas vezes não deve duplicar
  (idempotente para o mesmo par já aberto).
- **Saídas:** um **CSV de pendências** em `docs/` (já coberto pelo `.gitignore`) com linha,
  série do aparelho, série do módulo, empresa e **motivo**; e um resumo no terminal
  (criados / fechados / pulados por motivo). `--dry-run` roda sem gravar.

### Leitura na API

O retorno de `GET /equipamentos-cliente/{id}` ganha o elo **conforme o papel** do equipamento,
resolvido pela própria tabela (sem o backend precisar saber ids de catálogo na leitura):

- `modulo_instalado`: consultando `instalacoes_modulo` por `phoebus = id` e `saiu_em IS NULL`
  → `{ id, serie }` do módulo, ou `null`.
- `instalado_em`: consultando por `modulo = id` e `saiu_em IS NULL` → `{ id, serie, cliente_nome }`
  do Phoebus, ou `null`.

### Frontend (somente leitura)

Como Phoebus e Módulo compartilham a **mesma tela de detalhe**
(`EquipamentoClienteDetailPage`), a tela renderiza **o painel que tiver dado** — sem números
mágicos de catálogo:

- Se `modulo_instalado` → seção **"Módulo instalado"** com a série e link para a ficha do módulo.
- Se `instalado_em` → seção **"Instalado em"** com a série do Phoebus, o cliente e link para a ficha.
- Se o equipamento é um módulo e não há instalação aberta → **"No estoque"**.
- Nenhum botão de editar/vincular: é informativo.

## Segurança / permissões

- Leitura do elo segue a permissão já existente da ficha do equipamento (usuário interno logado).
- O script roda por linha de comando (operador com acesso ao servidor) — não há endpoint de escrita.

## Testes

- **Script (puro, sem I/O):** as regras de decisão viram funções testáveis —
  (a) casar série; (b) escolher a linha vencedora entre duplicados pela maior "Próxima
  Calibração"; (c) classificar o motivo da pendência. Testes com amostras representativas,
  incluindo os casos reais (`F000876` com data de 2000, `F003014` "Desativado").
- **Backend API:** `GET /equipamentos-cliente/{id}` devolve `modulo_instalado` para um Phoebus
  com instalação aberta, `instalado_em` para o módulo correspondente, e `null`/estoque quando
  não há instalação aberta; instalação fechada (`saiu_em` preenchido) **não** aparece.
- **Integridade:** não é possível ter duas instalações abertas para o mesmo módulo, nem para o
  mesmo Phoebus.
- **Frontend:** a ficha mostra "Módulo instalado" quando vem `modulo_instalado`; mostra
  "Instalado em" quando vem `instalado_em`; mostra "No estoque" quando módulo sem instalação.

## Riscos

- **O elo envelhece.** Os módulos trocam ~anualmente e o elo só é atualizado quando um novo
  script rodar. Mitigação: exibir a **data da carga** (`entrou_em`/`origem`) junto do elo, para
  quem lê saber de quando é aquele retrato. Isso é intencional — o Erick sabe e aceita.
- **~13% das linhas não casam.** Tratado como pendência (não bloqueia a carga).
- **Ler .xlsx sem biblioteca** é mais frágil que usar openpyxl; mitigado por o formato ser
  simples (uma aba, células de texto) e já ter sido validado contra o arquivo real.
