# Empresas e destinatário da proposta — Design

**Data:** 2026-09-15
**Área:** backend (`models/`, `schemas/`, `api/empresas.py`, `api/propostas.py`, `core/empresa.py`, `core/proposta_servico.py`, `core/proposta_pdf.py`, script) + frontend (`src/app/empresas/`, `src/app/propostas/`, `src/app/clientes/`, `auth/roles.ts`, `layout/Sidebar.tsx`) + migração Alembic `0030`
**Fase:** 1 de 2. A Fase 2 (cadastro automático no Tiny ERP) tem spec própria.

## Problema

No modal de proposta, o painel "Dados do cliente nesta proposta" grava os dados editados no JSON
`propostas.cliente_override`, que vale **só naquela proposta**. Na prática ele virou o cadastro das
**filiais**: o comercial escolhe o cliente matriz (dono da frota) e digita por cima o CNPJ, a razão
social e o endereço da filial. Na proposta seguinte da mesma filial, digita tudo de novo, porque o dado
não foi salvo em lugar nenhum. Já houve CNPJ de filial perdido nesse override
(`corrigir_cnpj_proposta_99`).

Retrato de produção em 15/09/2026: **258** propostas, **69** com override, **15** com CNPJ diferente do
cliente escolhido (**14** CNPJs distintos) e **6** sem cliente.

## Objetivo

1. Nova tabela e página **Empresas**: filiais com os dados cadastrais e um vínculo **opcional** com o
   Cliente matriz, de onde vêm os aparelhos. Empresa não tem frota própria.
2. A proposta passa a ter como destinatário **um Cliente ou uma Empresa**.
3. **Fim do "dados só nesta proposta".** Editar os dados no modal atualiza o cadastro de origem
   (Cliente ou Empresa). Documento que não existe em lugar nenhum pode virar Empresa nova ali mesmo.
4. Cada proposta guarda uma **cópia congelada** dos dados do destinatário no momento em que foi salva,
   para que um PDF antigo não mude quando o cadastro mudar.

## Não-objetivos

- **Integração com o Tiny ERP** — Fase 2. Nenhuma coluna `tiny_id` nesta entrega.
- **Frota própria da Empresa** — os aparelhos são sempre da matriz.
- **Filial dentro de `clientes`** (coluna `matriz` na própria tabela) — descartado: a filial apareceria
  no portal, em OS, na frota, nas cargas do GrowthHS e no TaskHS.
- **Apagar Empresa** — só desativar, como o Cliente.
- **Unicidade de documento por índice em `clientes`** — duplicata nova ainda aparece lá
  (ver `docs/operacao-unificar-clientes-duplicados.md`), então a trava daquele lado é na aplicação.

## Decisões

| Tema | Decisão |
|---|---|
| Referência na proposta | Duas FKs: `cliente` (matriz/frota, já existe) + `empresa` (nova, opcional) |
| Proposta antiga quando o cadastro muda | Guarda cópia congelada (`propostas.destinatario`); o PDF lê dela |
| Quem edita Empresa e dados do destinatário | Quem faz proposta: Comercial Pós-Vendas, Financeiro, Administrador. Demais internos só visualizam |
| E-mail e telefone | Salvam no cadastro, mas abrem **vazios e obrigatórios** no modal, com o valor do cadastro como sugestão de um clique |
| "Aos cuidados de" | Continua coluna da proposta (`propostas.contato`), nasce vazio |
| Documento entre as tabelas | **Único nas duas**: um CNPJ/CPF existe em `clientes` ou em `empresas`, nunca nos dois |
| Matriz da Empresa | Opcional |
| Documento da Empresa | CNPJ **ou** CPF, como o Cliente |
| Documento de registro existente no modal | **Somente leitura**; correção de documento é feita nas páginas Clientes/Empresas |
| Endereço no modal | Estruturado: endereço, número, complemento, bairro, município, UF, CEP |
| Telefone do Cliente | Grava em `clientes.telefones`; a sugestão lê `telefones` primeiro, depois `celular`/`whatsapp` |
| Filiais escondidas nos overrides | Script `migrar_filiais_propostas` cria as Empresas (simula por padrão) |
| Editar proposta antiga | Abre com o cadastro **atual**; salvar refaz a cópia (a versão anterior segue arquivada) |
| Tela do Cliente | Ganha o bloco "Empresas vinculadas" |

## Modelo de dados

### Tabela `empresas` (nova)

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | Integer PK | |
| `cliente` | FK `clientes.id`, nullable, `ondelete SET NULL`, index | matriz |
| `nome` | String(100), NOT NULL | razão social |
| `cgc` | String(14), nullable, **unique** | só dígitos |
| `cpf` | String(11), nullable, **unique** | só dígitos |
| `endereco` | String(100) | |
| `numero` | String(20) | texto, para aceitar "S/N" (no Cliente é BigInteger) |
| `complemento` | String(60) | |
| `bairro` | String(100) | |
| `municipio` | String(100) | |
| `estado` | String(2) | |
| `cep` | String(8) | só dígitos |
| `email` | String(100) | |
| `telefone` | String(50) | |
| `insc_est` | String(20) | inscrição estadual |
| `ativo` | Boolean NOT NULL, default true | |
| `created_at` / `updated_at` | DateTime(tz) | |

`CHECK` de exatamente um entre `cgc` e `cpf` preenchido.

### Tabela `propostas` (alterações)

- `empresa` — FK `empresas.id`, nullable, `ondelete SET NULL`, index.
- `destinatario` — JSON, cópia congelada. Escrita **só pelo servidor**; o frontend nunca envia.
- `cliente_override` — **congelada**: continua existindo, nenhum caminho novo escreve nela.

Formato de `destinatario`:

```json
{
  "tipo": "cliente" | "empresa",
  "id": 123,
  "nome": "...", "documento": "...",
  "cep": "...", "endereco": "...", "numero": "...", "complemento": "...",
  "bairro": "...", "municipio": "...", "estado": "..",
  "email": "...", "telefone": "...",
  "matriz_id": 45, "matriz_nome": "..."
}
```

`matriz_*` só quando `tipo = empresa`. No backfill, `tipo` pode ser `cliente` com `id` nulo (as 6
propostas sem cliente), e `endereco` pode vir no formato antigo de texto único, com número e bairro
vazios.

### Migração `0030_empresas`

1. Cria `empresas`.
2. Adiciona `propostas.empresa` e `propostas.destinatario`.
3. **Backfill de `destinatario`** para todas as propostas: dados do cadastro do cliente com o
   `cliente_override` por cima, campo a campo, reproduzindo exatamente o que `proposta_pdf` mostra hoje.
   Assim nenhum PDF muda.
4. Aditiva: não apaga `cliente_override`.

`downgrade` remove as duas colunas e a tabela. Proposta salva depois da `0030` não tem override;
voltar a versão faz o PDF dela sair só com o cadastro do cliente. Isso fica registrado na doc de operação.

### Script `app/scripts/migrar_filiais_propostas`

- Simula por padrão; grava com `--aplicar`. Idempotente.
- Seleciona as propostas cujo `cliente_override.documento` (só dígitos) difere do documento do cliente.
- Para cada documento distinto: se já existe Empresa com ele, reaproveita; se é documento de um
  **Cliente**, **recusa** e lista no resumo; senão cria a Empresa a partir do override (matriz = cliente
  da proposta; campos ausentes no override vêm vazios, não do cadastro da matriz).
- Liga `proposta.empresa` e refaz `proposta.destinatario` com `tipo = empresa`, preservando os valores
  do override.
- Imprime o resumo: Empresas criadas, reaproveitadas, recusadas e propostas ligadas.

## Backend

### Núcleo puro `app/core/empresa.py`

- `normalizar_documento(texto) -> (cgc, cpf)`: só dígitos; 14 dígitos vira CNPJ, 11 vira CPF; outro
  tamanho levanta `DocumentoInvalido`.
- Validação de dígito verificador de CNPJ e CPF (reaproveitar o que já existir em `core/enderecos.py`
  se servir).
- `dados_destinatario(cliente|empresa) -> dict`: monta a cópia congelada. É a única função que conhece o
  formato do JSON.

A checagem de unicidade entre as tabelas precisa de sessão, então fica num helper em
`app/api/empresas.py` (ou módulo de serviço), chamado pelas rotas de Empresa, pelo salvamento da
proposta e pela criação/edição de Cliente.

### Rotas `app/api/empresas.py` (registrar no `main.py`)

| Rota | Autorização |
|---|---|
| `GET /empresas?q=&cliente=&ativo=&skip=&limit=` | `get_current_usuario` |
| `GET /empresas/{id}` | `get_current_usuario` |
| `POST /empresas` | `require_funcao("Comercial Pós-Vendas", "Financeiro", "Administrador")` |
| `PUT /empresas/{id}` | idem |
| `POST /empresas/{id}/desativar` · `POST /empresas/{id}/reativar` | idem |

- Documento inválido → 422.
- Documento já existente em `empresas` ou `clientes` → **409** com `{"detail": "...", "tipo": "cliente"|"empresa", "id": N, "nome": "..."}`.
  Condição de corrida entre dois POST simultâneos: o `IntegrityError` do índice único vira o mesmo 409.
- `PUT` pode trocar o documento (é a página própria), sujeito às mesmas validações.
- `GET /clientes/{id}` não muda; a tela do Cliente busca `GET /empresas?cliente={id}`.

### Unicidade do lado de `clientes`

Criar ou editar Cliente com documento que já é de uma Empresa → 409, com o mesmo corpo.

### Busca de destinatário: `GET /propostas/destinatarios?q=`

- `get_current_usuario`. Busca por nome ou documento em Clientes **e** Empresas **ativos**.
- Resposta: `[{tipo, id, nome, documento, municipio, estado, matriz_id?, matriz_nome?}]`, limite 20.
- Sem resultado → lista vazia. O modal decide oferecer "Cadastrar empresa" quando `q` é documento
  completo (11 ou 14 dígitos).

### Salvar proposta (`POST /propostas`, `PUT /propostas/{id}`)

`PropostaBase`/`PropostaUpdate`: sai `cliente_override`, sai `cliente`, entra `destinatario`:

```python
class DestinatarioIn(BaseModel):
    tipo: Literal["cliente", "empresa", "nova_empresa"]
    id: int | None = None          # obrigatório em cliente/empresa
    matriz: int | None = None      # só em nova_empresa
    nome: str
    documento: str | None = None   # obrigatório em nova_empresa; ignorado nos demais
    cep: str | None = None
    endereco: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    municipio: str | None = None
    estado: str | None = None
    email: str                     # obrigatório
    telefone: str                  # obrigatório
```

No `PUT`, `destinatario` é opcional: ausente não mexe no destinatário. `POST` exige `destinatario`.

`core/proposta_servico.py`, **numa transação só**:

1. **Aplica ao cadastro.**
   - `cliente`: atualiza **só** `nome, endereco, numero, complemento, bairro, municipio, estado, cep,
     email, telefones`. Os demais campos (`obs`, WhatsApp, inscrições, `contato` etc.) ficam intactos.
     `numero` do Cliente é BigInteger: valor não numérico (ex.: "S/N") grava nulo e vai para a cópia como
     texto.
   - `empresa`: atualiza os campos equivalentes da Empresa.
   - `nova_empresa`: cria a Empresa com as mesmas validações de `POST /empresas` (409 incluído).
   - `documento` enviado com `tipo` `cliente`/`empresa` é **ignorado**.
   - Cliente ou Empresa **desativado** → 409 (só em proposta nova ou troca de destinatário; salvar uma
     proposta antiga cujo destinatário foi desativado depois continua permitido).
2. **Acerta as FKs.** Cliente: `proposta.cliente = id`, `proposta.empresa = None`. Empresa:
   `proposta.empresa = id`, `proposta.cliente = empresa.cliente` (pode ser nulo).
3. **Valida aparelhos.** Com `proposta.cliente` nulo, `aparelhos` precisa vir vazio (422). Todo
   `equipamento_cliente` informado precisa pertencer a `proposta.cliente` (422).
4. **Escreve `proposta.destinatario`** com `dados_destinatario()` sobre o cadastro já salvo (flush antes).
5. Versão + PDF, como hoje.

Falha em qualquer passo desfaz tudo: nem Empresa órfã, nem Cliente alterado sem proposta.

### Leitura

- `montar_saida`: `cliente_nome`/`cliente_documento` vêm de `destinatario`. Novos campos de saída:
  `empresa`, `destinatario`.
- Listagem: a busca textual passa a olhar `destinatario->>'nome'` e `destinatario->>'documento'`.
  Como o SQLite dos testes não tem `->>`, usar o operador JSON do SQLAlchemy (`Proposta.destinatario["nome"].as_string()`),
  que compila para os dois dialetos.
- `snapshot_proposta` (versões) inclui `empresa` e `destinatario`.
- **Duplicar** copia `cliente`, `empresa` e `destinatario`; a cópia é refeita no próximo salvamento.
- `proposta_pdf.py` lê **só** `destinatario`, montando o endereço a partir das partes estruturadas ou,
  quando só houver o texto antigo, usando o texto como está.

## Frontend

### Permissão

`roles.ts`: `podeGerenciarEmpresas(user)` = Administrador, Comercial Pós-Vendas ou Financeiro (igual a
`podeGerenciarPropostas`, mas com nome próprio para as duas regras poderem divergir).

### `DadosEmpresaForm` (componente compartilhado)

Em `src/app/empresas/DadosEmpresaForm.tsx`, usado na página Empresas e no modal da proposta.

- Campos: nome, documento (com lupa de CNPJ), CEP (com lupa), endereço, número, complemento, bairro,
  município, UF, e-mail, telefone. Na página Empresas, também inscrição estadual e matriz.
- `documentoTravado`: documento em modo leitura.
- `sugestoes`: para e-mail e telefone, mostra "Usar do cadastro: …" e preenche com um clique.
- Lupas: reaproveitam `propostas/buscaEndereco.ts`, preenchendo agora número e bairro separados.
- `somenteLeitura` para quem não tem permissão.

### Página Empresas (`src/app/empresas/`)

- Rota `/app/empresas` em `routes.tsx`; item "Empresas" no `Sidebar.tsx` logo abaixo de Clientes,
  visível a todo usuário interno.
- Tabela: nome, documento, matriz (link para o Cliente), município/UF, ativo. Busca e filtro por matriz.
- Criar/editar em modal com `DadosEmpresaForm` + seletor de matriz (busca em Clientes); desativar e
  reativar. Botões só com `podeGerenciarEmpresas`.
- 409 de documento: mensagem com link para o cadastro existente.

### Tela do Cliente

Bloco "Empresas vinculadas": lista `GET /empresas?cliente={id}` com link para cada Empresa. Vazio, some.

### Modal da proposta (`PropostaModal.tsx`)

1. Campo **Destinatário**: busca única em `/propostas/destinatarios`; cada resultado marcado
   **Cliente** ou **Empresa · matriz X**.
2. Ao escolher: `DadosEmpresaForm` com documento travado, e-mail/telefone vazios com sugestão; frota do
   Cliente ou da matriz da Empresa.
3. Documento completo sem resultado: botão **"Cadastrar empresa com este documento"**. Abre o
   formulário com o documento preenchido e editável, seletor de matriz sugerindo o último Cliente
   buscado, e dispara a lupa de CNPJ. Trocar a matriz recarrega a frota e limpa os aparelhos marcados.
   Enquanto a proposta não é salva, a Empresa não existe.
4. **"Trocar destinatário"** substitui "Remover empresa": limpa seleção, formulário e aparelhos.
5. Aviso acima do formulário: "Alterações nestes dados atualizam o cadastro de NOME" (ou "criam a
   empresa NOME").
6. 409 de documento ao salvar `nova_empresa`: o modal mostra o cadastro encontrado e oferece **"Usar
   este cadastro"**, que troca o destinatário para ele sem perder o resto da proposta.
7. Editar proposta existente: carrega o Cliente/Empresa **atual** pelo `empresa`/`cliente` da
   proposta. Proposta antiga sem nenhum dos dois (as 6 sem cliente) abre sem destinatário e exige
   escolher um para salvar.
8. `validacao.ts`: destinatário obrigatório; nome, e-mail, telefone e "aos cuidados de" obrigatórios;
   documento obrigatório em `nova_empresa`.

### Remoções

`clienteOverride.ts`, `OverrideDetalhe.tsx`, o painel "Dados do cliente nesta proposta" e o selo
"Dados editados" da listagem. O detalhe da proposta passa a mostrar a cópia congelada.

## Erros e bordas

| Situação | Resposta |
|---|---|
| Documento inválido | 422 |
| Documento já em Clientes/Empresas | 409 com `tipo`, `id`, `nome`; modal oferece "Usar este cadastro" |
| POST simultâneo da mesma Empresa | Índice único → mesmo 409 |
| Destinatário desativado em proposta nova ou troca | 409 |
| Aparelhos com `proposta.cliente` nulo | 422 |
| Aparelho fora da frota da matriz/Cliente | 422 |
| Trocar a matriz na página Empresas | Não altera propostas existentes |
| Sem permissão | UI somente leitura; 403 no backend |

## Testes

**Backend** (SQLite in-memory):

- `test_empresa_core.py` — normalização, dígito verificador, `dados_destinatario`.
- `test_empresas.py` — CRUD, permissões por função, 409 nas duas direções (Empresa↔Cliente),
  desativar/reativar, filtro por matriz.
- `test_clientes.py` — 409 ao criar/editar Cliente com documento de Empresa.
- `test_propostas_destinatario.py` — os três `tipo`; rollback quando a proposta falha (nenhuma Empresa
  criada, Cliente inalterado); `destinatario` enviado pelo cliente HTTP é ignorado; documento ignorado
  em registro existente; campos do Cliente fora da lista intactos; FKs; Empresa sem matriz com
  aparelhos → 422; aparelho de outra frota → 422; destinatário desativado → 409; busca
  `/propostas/destinatarios` mista.
- Backfill da `0030` — cópia gerada igual ao que o PDF mostrava (cadastro + override), incluindo
  proposta sem cliente. Testar a função de backfill isolada, chamada pela migração.
- `test_migrar_filiais_propostas.py` — simulação não grava; `--aplicar` cria e liga; documento repetido
  reaproveita; documento de Cliente é recusado; segunda execução não duplica.
- `test_proposta_pdf.py` — PDF lê `destinatario`; endereço estruturado e texto antigo.

**Frontend** (Vitest): `DadosEmpresaForm` (trava, sugestões, lupas), busca de destinatário e botão
"Cadastrar empresa", fluxo do 409 "Usar este cadastro", `EmpresasPage` com gate por função,
`podeGerenciarEmpresas`, `validacao.ts`.

**Verificação:** `pytest -q` contra a baseline das falhas pré-existentes; `npm run lint && npx tsc -b
--noEmit && npm run build && npm test`.

## Entrega

- Branch `feat/empresas`; commits backend → frontend; `docs(changelog): v1.53.0 — ...`; merge na
  `main`.
- Produção, em ordem:
  1. Deploy + `alembic upgrade head` (`0030`: tabela, colunas e backfill das cópias).
  2. `python -m app.scripts.migrar_filiais_propostas` — conferir o resumo e os recusados.
  3. `python -m app.scripts.migrar_filiais_propostas --aplicar`.
- Doc de operação `docs/operacao-empresas-migracao.md` com os passos, o resumo esperado e o aviso do
  `downgrade`.
- `CLAUDE.md`: seção curta sobre Empresas, a cópia congelada e `cliente_override` congelado.

## Fase 2 (fora desta spec)

Cadastro automático no Tiny ERP a cada Empresa nova. Começa pela documentação da API. Perguntas em
aberto: v2 (token) ou v3 (OAuth); só Empresa ou também Cliente novo; CNPJ que já existe no Tiny;
síncrono ou em segundo plano (padrão TaskHS/GrowthHS com `log_integracao`); edição da Empresa também
atualiza no Tiny. Nada da Fase 1 depende das respostas.
