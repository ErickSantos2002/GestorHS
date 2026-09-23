# Cliente de proposta no Tiny ERP — Design

**Data:** 2026-09-23
**Área:** backend (`core/tiny.py`, `integrations/tiny_client.py`, `api/propostas.py`, `tarefas/tiny_pendentes.py`, script novo) + frontend (`src/app/clientes/`) + migração Alembic `0032`
**Antecede:** [2026-09-16-tiny-empresas-design.md](2026-09-16-tiny-empresas-design.md) — o espelhamento da **Empresa** no Tiny, de onde vem todo o comportamento da API citado aqui.

## Problema

Proposta para **Empresa** (filial) já espelha a filial no Tiny ao salvar (`_agendar_empresa_no_tiny`). Proposta para **Cliente** não faz nada — e o Financeiro fatura no Tiny quem recebeu a proposta. Em 22/09/2026 o cliente 692 (IMETAME, CNPJ 31790710000196) teve proposta e não existia no Tiny; foi criado à mão (contato **610662219**) com as funções da Empresa por um script avulso.

Na base de 23/09/2026: 324 propostas, **306 para Cliente**, **212 clientes distintos**.

## Objetivo

1. **Todo Cliente que recebe proposta tem contato no Tiny** — ao criar, editar ou duplicar a proposta.
2. **Se já existe lá, ignora:** adota o `tiny_id` e **não altera nada** no Tiny.
3. **Se não existe, cria.** Sem contato duplicado: pesquisa pelo documento antes.
4. **Não cadastrar a base inteira** — só quem tem proposta.
5. **Os 212 de hoje entram por script de carga**, simulado por padrão.

## Fora de escopo

- **Atualizar** contato de Cliente no Tiny. O cadastro de Cliente veio do legado (complemento `"-"`, `numero` numérico, `telefones` com várias linhas) e o do Tiny tende a estar melhor. Diferente da Empresa, **não existe caminho de alteração** para Cliente.
- Espelhar Cliente criado/editado na página de Clientes. O gatilho é **só** a proposta.
- Botão "Reenviar" na tela de Clientes (o worker e o script cobrem; é uma rota pequena se fizer falta).
- Unificar o estado de Empresa e Cliente numa tabela só.

## Decisões

| Decisão | Motivo |
|---|---|
| Estado em colunas de `clientes` (`tiny_id`, `tiny_status`, `tiny_erro`, `tiny_em`), iguais às da Empresa | Cliente com `tiny_id` não gasta chamada (limite de 20/min); `pendente` fica visível ao worker; o script sabe quem já foi feito |
| **Cliente inativo também entra** (tempo real, worker e script) | Teve proposta, então pode ser faturado. Pedido do Erick em 23/09/2026. A criação de proposta nova continua recusando cliente inativo (`DestinatarioInativo`); isso afeta propostas antigas, edições e o script |
| O gatilho olha `proposta.empresa is None and proposta.cliente` **na rota**, não um marcador no serviço | Cobre criar, editar **e duplicar** do mesmo jeito. A Empresa usa `empresa_para_tiny` porque só o bloco `destinatario` a edita; o Cliente só precisa existir lá, e `duplicar` não passa bloco |
| Cliente com `tiny_id` preenchido **não agenda nada** | É o "se já existe, ignora". Zero chamada ao Tiny |
| Nunca chamar `contato.alterar.php` para Cliente | Objetivo 2; e `alterar` apaga o que não for enviado |

## Desenho

### 1. Contato a partir do Cliente (`core/tiny.py`, puro)

`montar_contato` lê atributos por nome da Empresa. Entra um adaptador puro `contato_do_cliente(cliente) -> dict` que traduz para os mesmos campos e reaproveita `montar_contato`/`contato_para_criar`:

| Cliente | Contato Tiny | Tratamento |
|---|---|---|
| `nome` | `nome` | corte em 50 (`_MAX_NOME`, já existe) |
| `cgc` / `cpf` | `cpf_cnpj`, `tipo_pessoa` | como na Empresa |
| `numero` (BigInteger) | `numero` | vira texto |
| `complemento` | `complemento` | `"-"` (e só traços/espaços) vira vazio e sai do payload |
| `telefones` | `fone` | como está (o Tiny aceita texto livre) |
| `insc_est`, `endereco`, `bairro`, `municipio`, `estado`, `cep`, `email` | idem Empresa | idem |

Criação sempre com `tipos_contato: [{"tipo": "Cliente"}]` e `situacao: "A"` (já é o `contato_para_criar`).

### 2. Sincronização (`integrations/tiny_client.py`)

`sincronizar_cliente(cliente_id, *, db=None) -> None` — best-effort, nunca levanta, no molde de `sincronizar_empresa` mas **só com o caminho de criação**:

1. `integracao_ativa()` falsa → retorna sem tocar em nada.
2. Trava a linha com `stmt_travar_cliente(cliente_id)` = `select(Cliente)...with_for_update(of=Cliente)` (mesma lição do `FOR UPDATE OF empresas`; função separada para o teste compilar o SQL no dialeto do Postgres).
3. Cliente com `tiny_id` → retorna (outro sync chegou antes).
4. Sem `cgc` nem `cpf` → `erro` com "cliente sem CNPJ/CPF", sem chamar o Tiny.
5. `pesquisar_contato(documento)`:
   - achou (documento bate, `escolher_contato`) → grava `tiny_id`, `enviada`. **Nada é enviado ao Tiny.**
   - `deve_tentar_de_novo` → `pendente`.
   - qualquer falha que não seja erro 20 → `pendente` (não dá para afirmar que não existe; criar geraria duplicado).
   - erro 20 → `incluir_contato(contato_para_criar(...))`; `duplicidade` → pesquisa de novo e adota.
6. Resultado da inclusão pelo mesmo `_aplicar` da Empresa: ok com id → `enviada`; limite/rede → `pendente`; recusa → `erro` com a mensagem.

`_marcar`/`_aplicar` já recebem o registro por parâmetro e só mexem nas quatro colunas, então servem aos dois modelos sem mudança de assinatura.

### 3. Gatilho na proposta (`api/propostas.py`)

Novo `_agendar_cliente_no_tiny(db, background_tasks, proposta)`, chamado em `criar`, `atualizar` e `duplicar` (este hoje não agenda nem a Empresa — continua não agendando Empresa, que não foi editada; passa a agendar Cliente):

- sai sem nada se integração desligada, `proposta.empresa` preenchida, `proposta.cliente` nulo, ou cliente com `tiny_id`;
- senão marca `tiny_status = 'pendente'` e `tiny_erro = NULL`, commita (falha aqui é logada e engolida, como na Empresa) e agenda `sincronizar_cliente` num wrapper `_tiny_cliente_seguro`.

Proposta nunca falha por causa do Tiny.

### 4. Worker de reenvio (`tarefas/tiny_pendentes.py`)

A volta passa a pegar **Empresas ativas** `pendente` (como hoje) e **Clientes** `pendente` (sem filtro de `ativo`), dividindo o mesmo teto `JOB_TINY_LIMITE`: primeiro as Empresas, o que sobrar do teto vai para Clientes, ambos pela `tiny_em` mais antiga. Mesma pausa de 7s entre itens. Continua nascendo desligado (`JOB_TINY_ATIVO`) e não sobe sem `TINY_TOKEN`. `erro` e status nulo continuam de fora.

### 5. Script de carga (`app/scripts/enviar_clientes_tiny.py`)

```
python -m app.scripts.enviar_clientes_tiny                 # simula
python -m app.scripts.enviar_clientes_tiny --aplicar       # grava
python -m app.scripts.enviar_clientes_tiny --aplicar --limite 20
```

- **Fila:** clientes (ativos **ou não**) com `tiny_id IS NULL` e pelo menos uma proposta com `propostas.cliente = clientes.id AND propostas.empresa IS NULL`, em ordem de id.
- **Simulação:** faz a pesquisa de verdade (leitura) e **não grava nada no banco nem cria nada no Tiny**. Resumo: já existem lá / seriam criados / sem documento / inconclusivos, e um CSV com os que pedem atenção (sem documento, inconclusivo, erro).
- **`--aplicar`:** chama `sincronizar_cliente` por cliente, 7s entre eles. Levando bloqueio (código 6/11) **para** e diz quantos faltaram, como o `enviar_empresas_tiny`.
- **Idempotente:** quem tem `tiny_id` sai da fila; parar e repetir não duplica.
- A IMETAME (692) cai na fila (sem `tiny_id` no banco) e é **adotada** pelo contato 610662219.

### 6. Migração `0032_cliente_tiny.py`

Aditiva, espelho da `0031`: `clientes.tiny_id` (Integer, index), `tiny_status` (String 10), `tiny_erro` (String 255), `tiny_em` (DateTime tz), todas nulas. Model `Cliente` ganha as quatro colunas.

### 7. Tela de Clientes

- `ClienteOut` (detalhe) e `ClienteListOut` (listagem) expõem `tiny_id`, `tiny_status`, `tiny_erro`.
- Na listagem (`ClientesPage.tsx`) e no cabeçalho do detalhe (`ClienteLayout.tsx`), um selo com o status do Tiny no mesmo visual da página Empresas: `enviada` (com o `tiny_id` em texto miúdo), `pendente`, `erro` (destacado, mensagem no `title`). Status nulo não mostra nada.
- Sem botão de reenviar e sem filtro por status nesta versão.

## Testes

Todos com `httpx` mockado — o Tiny não tem ambiente de teste e o token vale para a empresa toda.

- `core/tiny`: `contato_do_cliente` com `numero` inteiro, complemento `"-"`, `telefones`, CPF vs CNPJ, nome longo.
- `sincronizar_cliente`: adota (sem inclusão nem alteração); cria no erro 20; `pendente` em rede/limite/pesquisa inconclusiva; `erro` em recusa; sem documento não chama; cliente com `tiny_id` não chama; duplicidade adota; **nenhum caminho chama `contato.alterar.php`**; cliente inativo é sincronizado.
- `stmt_travar_cliente` compilada no dialeto do Postgres contém `FOR UPDATE OF clientes`.
- Rotas: criar/editar/duplicar proposta para Cliente sem `tiny_id` marca `pendente` e agenda; com `tiny_id` não chama o Tiny; proposta para Empresa segue agendando só a Empresa; integração desligada não marca nada.
- Worker: pega Cliente `pendente` (inclusive inativo), respeita o teto somando Empresas + Clientes, ignora `erro`.
- Script: fila só com clientes que têm proposta própria e sem `tiny_id`, inclui inativos; simulação não grava; `--aplicar` para no bloqueio.
- Frontend: selo por status na listagem.

## Operação (ordem de deploy)

1. Deploy do código + `alembic upgrade head` (`0032`).
2. `python -m app.scripts.enviar_clientes_tiny` — conferir resumo e CSV.
3. `python -m app.scripts.enviar_clientes_tiny --aplicar` (~25 min para 212).
4. Documentar em `docs/operacao-tiny-empresas.md` (seção de Clientes), CLAUDE.md (bloco do Tiny e lista de migrações) e changelog.
