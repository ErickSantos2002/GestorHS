# Função "Consulta" e Propostas para a Expedição — design

Data: 11/11/2026

## Por quê

Duas solicitações:

1. **O Comercial Pós-Vendas pediu, em nome da Expedição**, que ela volte a abrir a página **Propostas** para tirar informações dali. O acesso é **só para olhar**. Hoje o item fica escondido na barra lateral para quem não está em `podeGerenciarPropostas`.
2. **Vendedores e SDRs da Health Safety** não têm usuário no Gestor, mas usam a base como fonte de pesquisa para prospectar e vender. Eles precisam responder perguntas como:
   - quantos aparelhos temos cadastrados, e de quais modelos;
   - em quais clientes cada aparelho está;
   - **quais clientes têm um modelo específico (ex.: Phoebus)** e quem são esses clientes (nome, CNPJ, cidade, contato).

O Erick definiu o objetivo: **quem consulta não pode editar nada**. Esconder dado sensível (cobrança, preço) **não** é objetivo.

## Objetivos

- A Expedição vê **Propostas** na barra lateral e usa a página em modo leitura: lista, busca, detalhe, versões e PDF.
- Uma função nova, **`Consulta`**. Quem tem essa função entra no `/app` e só vê, na barra lateral, **Dashboard, Clientes, Empresas, Equipamentos e Produtos**. Nessas páginas não aparece nenhum botão de criar, editar, excluir, transferir, avançar ou gerar.
- **A API recusa qualquer escrita de um usuário `Consulta`**, independentemente do frontend.
- A tela **Equipamentos** passa a filtrar **por modelo** (catálogo `equipamentos`), e a planilha exportada respeita esse filtro.
- A tela **Clientes** passa a filtrar **"tem aparelho do modelo X"**. É isso que responde "quem são os clientes que têm Phoebus" sem repetir o mesmo cliente uma vez por aparelho.
- Uma **visão por modelo**: para cada modelo do catálogo, quantos aparelhos e em quantos clientes distintos. Clicar no modelo leva à lista filtrada.

## Fora do escopo / o que não fazer

- Liberar **Serviços** e **Produtos** para a Expedição. O Erick disse: "só liberar propostas é o suficiente".
- Esconder campos ou páginas por sensibilidade de dado.
- Provisionamento automático: o usuário `Consulta` é criado pelo Administrador na tela Usuários, como qualquer outro. O SSO Microsoft continua exigindo `Usuario` já cadastrado.
- **Anti-objetivo:** a trava de escrita depender só de esconder botão. Se um usuário `Consulta` conseguir gravar qualquer coisa via API, a entrega falhou, mesmo com a tela certa.

## Estado atual (levantado no código)

- **Leitura de propostas já é aberta a qualquer usuário interno** (`GET` em `backend/app/api/propostas.py` usa só `get_current_usuario`). A `PropostasPage` já calcula `podeEscrever = podeGerenciarPropostas(user)` e esconde a escrita. Para o item 1 só falta a visibilidade na `Sidebar.tsx` (linha 31).
- Funções vivem na tabela `funcoes` (`id`, `descricao`). Hoje são 1 a 7 (Administrador, Expedição, Laboratório, Comercial Pós-Vendas, Financeiro, Suporte, Qualidade). A escrita é travada por `require_funcao(...)` em listas de funções permitidas (`GESTOR_CADASTRO`, `EDITOR_CADASTRO` etc. em `deps.py`). Uma função nova, por não estar em nenhuma lista, já fica fora da maioria das escritas.
- **Mas há escritas protegidas só por `get_current_usuario`**, levantadas por varredura dos routers: `POST /caixas/{id}/avancar`, `POST /caixas/{id}/cancelar`, `PATCH /ordens/{id}/observacoes`, `POST /ordens/{id}/avancar`, `POST /ordens/{id}/desfecho-lab` (a checagem de função provavelmente acontece no corpo, mas não está garantida) e `POST /certificado-calculo-previa` (só calcula). Por isso a trava precisa ser **genérica**, não depender de cada rota.
- `_query_frota` (`equipamentos_cliente.py`) filtra por cliente, status, ativo e série/patrimônio. **Não filtra por modelo.** `FrotaListOut` já traz `cliente_nome` e `equipamento_descricao`.
- `_query_clientes` (`clientes.py`) filtra só por texto, e já usa `EXISTS` sobre `EquipamentoCliente` para a busca por série. O filtro por modelo segue o mesmo padrão.
- Listagem e exportação compartilham o mesmo `_query_*`. O filtro novo entra no helper e as duas rotas herdam.

## Decisões de como (minhas, não do Erick, salvo onde indicado)

1. **Item 1:** a linha `Propostas` da `Sidebar` passa a usar um helper novo, `podeVerPropostas` (= `podeGerenciarPropostas` **ou** Expedição), em `roles.ts`, com teste em `roles.test.ts`. Serviços e Produtos continuam em `podeGerenciarPropostas`. Nada muda no backend.
2. **A função nasce por migração Alembic `0033_funcao_consulta.py`**, que insere `funcoes(descricao='Consulta')` de forma idempotente (não insere se já existir) e cujo `downgrade` apaga a função se nenhum usuário a usar. Assim o deploy cria a função junto, e a tela Usuários a oferece sem mais nada.
3. **A trava de escrita é central**, em `get_current_usuario` (`deps.py`). Ela passa a receber o `Request`: se a função do usuário for `Consulta` e o método não for `GET`/`HEAD`/`OPTIONS`, responde **403 "Função Consulta é somente leitura"**. Exceção explícita, numa lista nomeada: a rota `/auth/trocar-senha`, porque o usuário precisa poder trocar a própria senha. `/auth/definir-senha`, `/auth/refresh`, os logins, o SSO e os inbounds não passam por `get_current_usuario`, então não precisam de exceção. Pelo mesmo motivo, o teste de "toda escrita dá 403" se limita às rotas que dependem de `get_current_usuario`. A varredura confirmou que nenhum `GET` grava no banco, então a trava por método não deixa brecha. Constante `FUNCAO_CONSULTA = "Consulta"` em `deps.py`, espelhada em `roles.ts`.
   - Testes: para **toda** rota de escrita registrada no app (varrer `app.routes` por método ≠ GET), um usuário `Consulta` recebe 403. Esse teste é a garantia de que nenhuma rota nova escapa. Para cada `GET` usado pelas telas permitidas, recebe 200. Trocar a própria senha funciona.
4. **Frontend do `Consulta`:** helper `isConsulta(user)`. Na `Sidebar`, quando `isConsulta`, só aparecem Dashboard, Clientes, Empresas, Equipamentos e Produtos. A página Produtos (`CatalogoProdutosPage`, que hoje usa `podeGerenciarPropostas`) abre em modo leitura para ele. Nas páginas permitidas, os botões de escrita já são guardados por helpers (`podeGerenciarCadastros`, `podeEditarCadastros`, `podeGerenciarEmpresas`, `isAdmin`…) que **não** incluem `Consulta`, então devem sumir sozinhos. O builder confere tela a tela e corrige o botão que estiver sem guarda. **Sem guarda de rota:** se o `Consulta` digitar a URL de Ordens, a página abre em leitura, e o Erick disse que isso não preocupa.
5. **Filtro por modelo na frota:** parâmetro `equipamento: int | None` em `_query_frota` (e, por consequência, em `listar` e `exportar`). Na `FrotaPage`, um `Select` "Modelo" ao lado de Status/Aparelhos, alimentado pelo catálogo, com estado na URL (`?equipamento=36`), para o link da visão por modelo funcionar.
6. **Filtro na lista de clientes:** parâmetro `equipamento: int | None` em `_query_clientes` (`EXISTS` com `EquipamentoCliente.equipamento == X`). **Minha escolha:** contar só aparelho **ativo** (`ativo = true`), porque a pergunta comercial é "quem tem hoje". `Select` "Tem aparelho" na `ClientesPage`, também na URL, e a exportação respeita.
7. **Visão por modelo:** endpoint `GET /equipamentos-cliente/resumo-por-modelo` → `[{equipamento, descricao, aparelhos, clientes}]` (só aparelhos ativos, ordenado por `aparelhos` desc, modelos com zero de fora). Mostrada como um bloco recolhível "Por modelo" no topo da `FrotaPage`. Cada linha tem dois links: "ver aparelhos" (`/app/equipamentos?equipamento=X`) e "ver clientes" (`/app/clientes?equipamento=X`). Visível a todos os usuários internos, não só ao `Consulta`.
8. **Estoque da HS fora da contagem (decisão do Erick, 11/11):** o estoque próprio fica cadastrado como cliente (`settings.CLIENTE_ESTOQUE_HS_ID = 2`, "HS LTDA", 61 aparelhos ativos hoje). Ele fica **fora** de `resumo-por-modelo` (não soma em `aparelhos` nem em `clientes`) e do filtro "tem aparelho" da lista de Clientes, igual às cargas do GrowthHS (`cliente != CLIENTE_ESTOQUE_HS_ID`). O cliente continua aparecendo normalmente na lista de Clientes sem esse filtro. **Na lista de Equipamentos ele continua aparecendo**, inclusive com o filtro de modelo e na exportação, porque ali a visão é aparelho por aparelho. Os testes afirmam as três coisas.
9. **Changelog:** uma entrada nova em `data.ts` (versão minor) cobrindo as duas mudanças.

## Deixado para o builder

- Os nomes exatos dos componentes, o layout do bloco "Por modelo" e o texto dos rótulos (manter o PT-BR e o design system de `components/ui/`).
- Se `get_current_usuario` resolve a função via `usuario.funcao_rel` (já `lazy="joined"`) ou por consulta. A preferência é `funcao_rel`, para não custar uma query a mais por request.
- A ordem dos commits, seguindo o fluxo do `CLAUDE.md` (spec → plan → backend → frontend → changelog).

## Para o Erick depois do deploy

- Aplicar a `0033` em produção antes ou junto com o deploy.
- Criar os usuários dos vendedores e SDRs na tela Usuários com a função **Consulta**.
