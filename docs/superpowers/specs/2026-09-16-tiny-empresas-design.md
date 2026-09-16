# Empresa no Tiny ERP — Design

**Data:** 2026-09-16
**Área:** backend (`core/tiny.py`, `integrations/tiny_client.py`, `api/empresas.py`, `core/proposta_servico.py`, script) + frontend (`src/app/empresas/`) + migração Alembic `0031`
**Fase:** 2 de 2. A Fase 1 (Empresas e destinatário da proposta) está em [2026-09-15-empresas-destinatario-proposta-design.md](2026-09-15-empresas-destinatario-proposta-design.md), mergeada na main em 16/09/2026.

## Problema

A filial cadastrada no GestorHS precisa existir também no Tiny ERP, e hoje o comercial digita o mesmo cadastro nos dois sistemas. A Fase 1 tirou a duplicação **dentro** do GestorHS; esta fase tira a duplicação **entre** GestorHS e Tiny.

## Objetivo

1. **Empresa criada no GestorHS nasce no Tiny** — pela página Empresas ou pelo modal da proposta.
2. **Empresa editada aqui atualiza o contato lá**, sem apagar o que só existe no Tiny.
3. **Nada de contato duplicado:** o CNPJ é pesquisado antes; contato que já existe é adotado.
4. **O erro é visível** para quem cadastrou, com um botão para tentar de novo.

## O que a API do Tiny permite (levantado em 16/09/2026)

Documentação: <https://tiny.com.br/api-docs/>. Tudo abaixo foi **verificado na conta da Health & Safety**, com o token real.

- **API v2, token simples.** A Olist diz que a v2 "continuará funcional sem data estimada para descontinuação, mas não receberá mais atualizações". A v3 (OAuth) fica para o futuro.
- **Chamadas:** `POST` form-urlencoded para `https://api.tiny.com.br/api2/<endpoint>.php`, com `token`, `formato=json` e o contato como **JSON dentro do campo `contato`**, na estrutura `{"contatos":[{"contato":{…}}]}`.
- **Endpoints usados:** `contatos.pesquisa.php` (por `cpf_cnpj`), `contato.obter.php` (por `id`), `contato.incluir.php`, `contato.alterar.php`.
- **HTTP é sempre 200**; o que vale é `retorno.status` e `retorno.codigo_erro`.
- **Limite:** 20 chamadas por minuto nesta conta (cabeçalho `x-limit-api` em toda resposta). Operações de contato contam como chamada em lote.
- **Campos obrigatórios do contato:** `sequencia`, `nome` (**50 caracteres**), `situacao`.

**Comportamentos confirmados no teste manual** (contato 610661344, filial da Ibema, criado e alterado de verdade):

| Achado | Consequência no desenho |
|---|---|
| "Não encontrado" volta como **erro 20** ("A consulta não retornou registros"), não como lista vazia | O código trata 20 como ausência, nunca como falha |
| Sem `tipos_contato`, o contato nasce como **"Outro"**; os contatos da empresa são **"Cliente"** | A criação manda `tipos_contato: [{"tipo": "Cliente"}]` |
| `tipos_contato` **acumula** a cada alteração (ficou `[Outro, Cliente]`) | A edição devolve os tipos como vieram do Tiny, sem acrescentar |
| `contato.alterar.php` **apaga o que não for enviado** (limpou endereço, cidade e o `codigo`) | A edição lê o contato antes e reenvia o contato inteiro |
| O Tiny **casa o município pela tabela dele**: aceitou "Araucaria" sem acento e preencheu a UF sozinho | Não normalizamos município; validação errada vira erro visível |
| O `codigo` do contato é numerado pelo Tiny na criação | Nunca enviamos `codigo` na criação; na edição, devolvemos o que veio |
| Campo vazio pode ficar fora do payload | O payload só leva campo com valor |

**Retrato da base em 16/09/2026:** das 10 Empresas cadastradas, **9 já existiam no Tiny** e seriam adotadas; a 10ª (filial da Ibema, `80228885001000`) foi criada no teste manual. Sem a pesquisa prévia, o primeiro uso teria criado 9 contatos duplicados.

## Decisões

| Tema | Decisão |
|---|---|
| Gatilho | Empresa **criada** e **editada** (página Empresas e modal da proposta) |
| Cliente (matriz) | **Não** vai para o Tiny |
| Desativar/reativar | **Não** mexe no Tiny |
| CNPJ já existente lá | Pesquisa antes e **adota** o contato (guarda o `tiny_id`) |
| Edição | **Lê antes de alterar**: sobrepõe só os nossos campos, devolve o resto como está |
| Falha | Nunca derruba o cadastro daqui: envio em segundo plano, estado e motivo na tela, botão de reenviar |
| Bloqueio por limite (6/11) | Vira `pendente`, não `erro` |
| Empresas já cadastradas | Script de acerto, simula por padrão |
| Ligar/desligar | `TINY_TOKEN` vazio = integração desligada (mesmo gating do TaskHS/GrowthHS) |
| Nome acima de 50 caracteres | Cortado no envio, registrado no log; o cadastro daqui fica inteiro |
| Sentido | Só daqui para o Tiny; nada volta |

## Modelo de dados

### `empresas` (migração `0031_empresa_tiny`, aditiva)

| Coluna | Tipo | Observação |
|---|---|---|
| `tiny_id` | Integer, nullable, index | id do contato no Tiny; é a chave da alteração |
| `tiny_status` | String(10), nullable | `pendente`, `enviada`, `erro`. Nulo = nunca entrou na fila |
| `tiny_erro` | String(255), nullable | Última recusa, em texto, para a tela |
| `tiny_em` | DateTime(tz), nullable | Última tentativa |

`downgrade` remove as quatro colunas. Nada mais muda de schema.

### Configuração

`TINY_TOKEN` (vazio = desligada) e `TINY_BASE_URL` (padrão `https://api.tiny.com.br/api2`), já declaradas em `core/config.py` e no `.env.example` (commit `41add21`). Em produção o token vai nas variáveis do EasyPanel.

## Backend

### Núcleo puro `app/core/tiny.py`

Sem I/O, testável isolado:

- `montar_contato(empresa) -> dict` — mapeamento abaixo, sem campo vazio, nome cortado em 50.
- `contato_para_criar(empresa) -> dict` — `montar_contato` + `sequencia: 1` + `situacao: "A"` + `tipos_contato: [{"tipo": "Cliente"}]`.
- `contato_para_alterar(empresa, atual: dict) -> dict` — mescla: parte do `atual` (como veio do `contato.obter.php`), sobrepõe os campos do mapeamento, mantém `id`, `sequencia: 1` e `situacao: "A"`.
- `ler_resposta(corpo: dict) -> Resultado` — traduz o `retorno` do Tiny (dataclass com `ok`, `id`, `codigo_erro`, `mensagem` e `deve_tentar_de_novo`).
- `NAO_ENCONTRADO = 20`, `DUPLICIDADE = 30`, `VALIDACAO = 31`, `LIMITE = (6, 11)`, `TOKEN_INVALIDO = 2`.

**Mapeamento GestorHS → Tiny**

| Tiny | GestorHS |
|---|---|
| `nome` | `nome` (cortado em 50) |
| `cpf_cnpj` | `cgc` ou `cpf` |
| `tipo_pessoa` | `J` com CNPJ, `F` com CPF |
| `ie` | `insc_est` |
| `endereco`, `numero`, `complemento`, `bairro`, `cep` | os mesmos |
| `cidade` | `municipio` |
| `uf` | `estado` |
| `email` | `email` |
| `fone` | `telefone` |

**Preservados na edição** (vêm do `obter` e voltam como estavam): `codigo`, `tipos_contato`, `fantasia`, `pessoas_contato`, `email_nfe`, `obs`, `id_vendedor`/`nome_vendedor`, `limite_credito`, `id_lista_preco`, endereço de cobrança e qualquer outra chave que o Tiny devolver.

### Cliente HTTP `app/integrations/tiny_client.py`

Segue `taskhs_client.py`:

- `integracao_ativa() -> bool` = `bool(settings.TINY_TOKEN)`.
- `pesquisar_contato(documento) -> int | None`, `obter_contato(tiny_id) -> dict | None`, `incluir_contato(contato) -> Resultado`, `alterar_contato(contato) -> Resultado`.
- `sincronizar_empresa(empresa_id)` — o alvo do `BackgroundTasks`: abre sessão própria, executa o fluxo, grava `tiny_id`/`tiny_status`/`tiny_erro`/`tiny_em` e registra em `log_integracao` (`integracao="tiny"`, status `sucesso`/`erro`/`pulado`). **Nunca propaga exceção.**
- `timeout=20`. Desligada, é no-op e não marca nada.

### Fluxo

**Criar** (sem `tiny_id`): `pesquisar_contato(documento)` → achou: grava o id, `enviada` · não achou (erro 20): `incluir_contato` → grava o id devolvido.
**Editar** (com `tiny_id`): `obter_contato(tiny_id)` → `contato_para_alterar` → `alterar_contato`.
**Contato sumiu do Tiny** (obter falha): cai no fluxo de criação.
**Duplicidade (30) na inclusão:** pesquisa de novo e adota.

### Rotas

- `POST /empresas` e `PUT /empresas/{id}` agendam `sincronizar_empresa` **depois do commit**, via `BackgroundTasks`, e marcam `tiny_status = "pendente"` na mesma transação do cadastro.
- **Modal da proposta:** o agendamento acontece depois do commit da proposta, nunca dentro da transação — uma falha do Tiny não pode derrubar o salvamento.
- `POST /empresas/{id}/tiny` — reenvio manual. Mesmas funções de escrita de Empresa (Comercial Pós-Vendas, Financeiro, Administrador). Devolve `EmpresaOut`.
- `GET /empresas?tiny_status=erro` — filtro novo na listagem.
- `EmpresaOut` ganha `tiny_id`, `tiny_status`, `tiny_erro`, `tiny_em`.

### Script `app/scripts/enviar_empresas_tiny`

- Simula por padrão; grava com `--aplicar`; `--limite N` para processar aos poucos.
- Percorre as Empresas **ativas sem `tiny_id`**, em ordem de id, com pausa entre elas (o limite é de 20 chamadas por minuto e cada empresa gasta duas).
- Resumo: quantas seriam **adotadas**, quantas **criadas**, e a lista de erros com o motivo.
- Para sozinho ao levar bloqueio por limite (6/11), dizendo quantas faltaram.
- Idempotente: empresa com `tiny_id` não é tocada de novo.

## Frontend

- **Coluna "Tiny"** na página Empresas: `Enviada` (com o id), `Pendente`, `Erro` (vermelho, motivo no title) ou vazio.
- **Botão "Reenviar ao Tiny"** na linha, só em `erro` e `pendente`, e só com `podeGerenciarEmpresas`.
- **Modal da Empresa:** mesmo estado no rodapé, com o id do contato.
- **Filtro** "Só com erro no Tiny" na listagem.
- `empresasApi` ganha `reenviarTiny(id)` e o parâmetro `tiny_status`.

## Erros e bordas

| Situação | Resposta |
|---|---|
| Integração desligada | Nada enviado, nada marcado |
| Tiny fora do ar / timeout | `pendente` + log; botão e script tentam de novo |
| Limite estourado (6/11) | `pendente`, sem marcar erro |
| Validação (31), ex.: município fora da tabela | `erro` com a mensagem do Tiny na tela |
| Token inválido (2) | `erro` com aviso de configuração |
| Nome > 50 caracteres | Cortado no envio, anotado no log |
| Duas edições em sequência | A última vence; cada uma lê antes de escrever |
| Contato apagado no Tiny | A alteração falha e o reenvio recria |

## Testes

**Backend** (SQLite in-memory; nenhuma chamada real ao Tiny):

- `test_tiny_core.py` — mapeamento, corte do nome, campo vazio fora do payload, `tipos_contato` só na criação, mesclagem da edição (código, tipos, pessoas de contato e e-mail de NFe preservados), `ler_resposta` para sucesso, 20, 30, 31, 6, 11 e 2.
- `test_tiny_client.py` — `httpx.MockTransport`: desligado sem token; pesquisa que acha e que não acha; inclusão; alteração; erro não propaga; grava em `log_integracao`; monta o form com `token`, `formato` e `contato` JSON.
- `test_empresas_tiny.py` — criar e editar Empresa agendam o envio; `POST /empresas/{id}/tiny` exige função e responde 404 para empresa inexistente; filtro `tiny_status`; a criação pela proposta agenda depois do commit e a proposta não falha se o Tiny falhar.
- `test_enviar_empresas_tiny.py` — simulação não grava; `--aplicar` adota e cria; `--limite`; para no bloqueio; idempotente.

**Frontend** (Vitest): coluna com os quatro estados, botão só em erro e pendente, gate por função, filtro.

**Verificação:** `pytest -q` contra a baseline das 4 falhas conhecidas; `npm run lint && npx tsc -b --noEmit && npm run build && npm test`.

## Entrega

- Branch `feat/tiny-empresas`; commits backend → frontend; `docs(changelog): v1.54.0 — …`; merge na `main`.
- **Produção:** deploy + `alembic upgrade head` (`0031`, aditiva) → com `TINY_TOKEN` vazio nada acontece → Erick põe o token no EasyPanel → `enviar_empresas_tiny` simulando → `--aplicar`.
- **Ensaio local antes:** o ambiente de `~/projetos/gestorhs-local/` tem cópia do banco de produção; o script roda lá primeiro. Atenção: o Tiny **não tem ambiente de teste**, então mesmo o ensaio local fala com o Tiny de verdade — o esperado é adotar as 10 e não criar nenhuma.
- Doc de operação `docs/operacao-tiny-empresas.md` com os passos, os códigos de erro e o que fazer em cada um.
- `CLAUDE.md`: seção curta sobre a integração, o gating por token e o "ler antes de alterar".

## Não-objetivos

- Cliente (matriz) no Tiny; desativar/reativar espelhado; qualquer leitura do Tiny para cá; fila persistente com worker; API v3; pessoas de contato e e-mail de NFe geridos daqui.
