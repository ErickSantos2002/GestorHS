# Exportação para Excel nas listas — Design

**Data:** 2026-08-19
**Área:** backend (`core/planilha.py` novo, `api/clientes.py`, `api/equipamentos_cliente.py`, `api/ordens.py`, `api/certificados_emitidos.py` novo) + frontend (`components/ui/BotaoExportar.tsx` novo, `lib/download.ts`, páginas de Clientes/Frota/Ordens/Certificados) + testes.
**Tipo:** feature nova, sem migração. Nova dependência: `openpyxl`.
**Origem:** pedido do Erick — a equipe precisa tirar planilha de aparelhos, clientes e afins de tempos em tempos, e hoje não há nenhuma forma de fazer isso pelo sistema.

## Problema

O GestorHS não exporta nada. Não existe CSV, não existe xlsx, não existe botão de download de lista em lugar nenhum do app interno. Quando alguém precisa de uma planilha — para mandar a um cliente, para conferir a base, para trabalhar em cima dos dados — a saída hoje é pedir para alguém consultar o banco direto ou copiar da tela de 25 em 25 linhas.

Três consequências práticas:

1. **A tela mostra menos do que o banco tem.** A lista de aparelhos exibe cinco colunas; o cadastro tem série, patrimônio, data de compra, última calibração, número do certificado e situação. Quem copia da tela perde tudo isso.
2. **A paginação limita a 25 linhas.** Uma base de milhares de aparelhos não sai da tela por copiar e colar.
3. **O trabalho volta para o banco.** Toda planilha vira um pedido de consulta SQL para quem tem acesso, o que não escala e não é o que o sistema deveria exigir.

## O que exportar

Quatro exportações, decididas com o Erick:

| Exportação | Origem | Situação |
|---|---|---|
| **Clientes** | `/app/clientes` | lista já existe |
| **Equipamentos (frota)** | `/app/equipamentos` | lista já existe |
| **Ordens de serviço** | `/app/ordens` | lista já existe |
| **Certificados emitidos** | — | **não existe** — ver abaixo |

### O caso dos certificados

A tela `/app/certificados` **não é uma lista de certificados**. São cinco abas de administração: Modelos, Imagens, Em branco (avulsos), Gerais e Configurações. Nenhuma delas é dado que alguém queira em planilha.

Os certificados de fato emitidos vivem em duas tabelas separadas e só aparecem picados no detalhe da OS e no detalhe do aparelho:

- `os_certificados` — gerados a partir de uma OS (`os`, `tipo` C/M, `data_geracao`)
- `certificados_venda` — gerados na venda de um aparelho, sem OS (`equipamento_cliente`, `calib_cert`, `data_calibracao`, `usuario`, `data_geracao`)

Portanto esta parte **não é adicionar um botão**: é um relatório novo, com uma query que une as duas origens num conjunto só. Ele nasce **apenas como exportação**, sem tela de listagem — uma aba "Emitidos" na página de Certificados com filtros de período e cliente e o botão.

Limitação aceita conscientemente: o usuário exporta sem ver antes o que vai sair. Se incomodar no uso, o caminho é acrescentar a tabela paginada nessa aba depois — o endpoint de query já estará pronto.

## Decisões

| Questão | Decisão | Por quê |
|---|---|---|
| Onde o arquivo é gerado | **Backend** | Precisa de todas as linhas do filtro e de colunas que a tela não mostra; o backend já tem os dois. |
| Escopo das linhas | **Tudo que bate com os filtros atuais**, não só a página | É o que a equipe quer; exportar 25 linhas não resolve nada. |
| Colunas | **Mais do que a tela mostra** | A planilha é para trabalhar em cima, não para espelhar a tela. |
| Quem pode | **Qualquer usuário interno logado** (`get_current_usuario`) | A exportação não revela nada que a tela já não mostre para o mesmo usuário. Sem regra de função nova. |
| Portal do cliente | **Fora de escopo** | Dobraria o trabalho (endpoints do portal, isolamento de tenant). Entra depois, se for pedido. |
| Formato | **`.xlsx` com acabamento** | Ver seção "Acabamento". |
| Biblioteca | **`openpyxl`** | Escrever xlsx à mão com `zipfile`+XML (como `importar_elo_modulos.py` faz para *ler*) é muito mais difícil para escrever do que para ler: estilo de célula, autofiltro, painel congelado e tipo data exigem montar `styles.xml`/`sheet.xml` no braço. Não vale economizar uma lib madura. |
| Geração | **Síncrona**, com teto de 50.000 linhas | Nesse volume são segundos. Job em background só se a base crescer muito. |

## Arquitetura

### `backend/app/core/planilha.py` (novo)

Módulo **puro** — sem I/O, sem SQLAlchemy, sem FastAPI. É a única coisa no sistema que sabe como um xlsx bonito se parece.

```python
@dataclass(frozen=True)
class Coluna:
    titulo: str
    campo: str
    largura: int
    formato: Literal["texto", "data", "datahora", "numero", "inteiro", "sim_nao"] = "texto"

LIMITE_LINHAS = 50_000

class PlanilhaGrandeDemais(Exception): ...

def gerar_xlsx(
    titulo_aba: str,
    colunas: Sequence[Coluna],
    linhas: Sequence[dict],
    filtros_aplicados: str,
) -> bytes: ...
```

`gerar_xlsx` levanta `PlanilhaGrandeDemais` se `len(linhas) > LIMITE_LINHAS`.

Estar em `core/` e ser puro segue a convenção do projeto (lógica de negócio sem I/O, testável isolada) e garante que as quatro exportações — e as futuras — saiam idênticas.

### Endpoints

Um por lista, dentro do router que já existe:

```
GET /clientes/exportar
GET /equipamentos-cliente/exportar
GET /ordens/exportar
GET /certificados-emitidos/exportar
```

Cada um aceita **exatamente os mesmos parâmetros de filtro do `listar()` correspondente**, menos `offset` e `limit`. Autorização idêntica à da listagem: `Depends(get_current_usuario)`.

Os três primeiros entram no router que já existe. O de certificados emitidos é um router novo,
`api/certificados_emitidos.py` com prefixo `/certificados-emitidos` (segue o padrão dos vizinhos:
`/certificados-avulsos`, `/certificados-gerais`), registrado com `include_router` em `main.py` —
o projeto não registra routers automaticamente.

**Cuidado com a ordem das rotas.** Em `clientes.py` o `@router.get("/{cliente_id}")` está declarado
logo depois da listagem. FastAPI casa na ordem de registro, então `/exportar` declarado *depois*
seria capturado por `/{cliente_id}`, o `"exportar"` falharia na conversão para `int` e a resposta
viria 422 em vez do arquivo. **`/exportar` tem que ser declarado antes de qualquer rota
`/{id}` do mesmo router** — vale para clientes, ordens e equipamentos-cliente. É o tipo de erro que
só aparece em runtime, então cada endpoint ganha um teste de rota que o pegaria.

Resposta:

```
200 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="equipamentos-2026-08-19.xlsx"
```

`PlanilhaGrandeDemais` vira `400` com mensagem pedindo para refinar os filtros.

### Extração dos filtros (mudança em código existente)

Hoje a lógica de filtro está escrita **dentro do corpo** de cada `listar()`. Exemplo em `equipamentos_cliente.py`: os `if cliente`, `if ativo`, `if status`, `if q` vivem no endpoint.

Se `exportar()` reescrever esses mesmos filtros, os dois divergem no primeiro filtro novo que alguém adicionar na tela — e a planilha passa a ignorar o filtro em silêncio, que é o pior tipo de bug: ninguém percebe, e a planilha errada já foi mandada para o cliente.

Por isso, para cada um dos três recursos existentes, a montagem da query sai para um helper no mesmo arquivo:

```python
def _query_frota(db, cliente=None, status=None, ativo=None, q=None):
    """Filtros da frota. Usado por listar() e por exportar() — mantém os dois em sincronia."""
```

`listar()` chama o helper e aplica `offset`/`limit`; `exportar()` chama o mesmo helper e leva tudo. Isso é um `refactor` de comportamento inalterado — os testes existentes de listagem devem continuar passando sem alteração, e isso é a prova de que a extração está correta.

### Colunas

**Clientes** — Código, Nome, CNPJ, CPF, Inscr. estadual, Endereço, Número, Complemento, Bairro, Município, UF, CEP, Contato, E-mail, Telefones, Celular, WhatsApp, Cadastrado em, Ativo.

**Equipamentos** — Código, Cliente, CNPJ do cliente, Aparelho, Marca, Série, Patrimônio, Data da compra, Última calibração, Próxima calibração, Status, Nº do certificado, Situação da calibração, OS atual, Ativo.

O Status é o de `core/calibracao.py::status_calibracao()` (`em_dia`/`vencendo`/`vencido`/`sem_data`), reaproveitado e escrito por extenso na planilha — não recalculado.

**Ordens** — OS, Cliente, CNPJ do cliente, Aparelho, Série, Fase, Tipo de serviço, Chegada, Calibração, Retorno, Entrega, Próxima calibração, Nº do certificado, Situação, Nota fiscal, Valor, Frete envio, Frete retorno, Pago, Caixa, Garantia.

**Certificados emitidos** — Cliente, CNPJ, Aparelho, Série, Origem (OS/Venda), OS, Tipo (Calibração/Manutenção), Nº do certificado, Data da calibração, Gerado em, Gerado por.

Fora, de propósito:

- **Campos de teste da calibração** (`calib_teste1..5`, média): são `String` no banco. Em planilha viram texto e não somam, o que engana mais do que ajuda. Entram depois se a equipe pedir, convertidos para número.
- **Textos longos das OS** (`obs`, `desfecho_lab_obs`, `condicao_chegada`, `acessorios`): deixam a planilha impraticável de ler.

**Ponto confirmado na revisão — "Marca":** existe. `Equipamento.marca` é FK para `marcas.id`, e o nome
está em `Marca.descricao`. Não há property no modelo expondo isso (diferente de `equipamento_descricao`,
que já existe), então a exportação faz o join explicitamente na query, sem adicionar property nova ao modelo.

**Ponto confirmado na revisão — "Gerado por":** `os_certificados` **não tem** coluna de usuário; só
`certificados_venda` tem (`usuario` → `usuarios.id`). Portanto a coluna sai preenchida apenas nas linhas de
origem "Venda" e vazia nas de origem "OS". Isso é o dado real do sistema, não uma falha da exportação —
mas quem receber a planilha precisa saber, então o rodapé de filtros registra a observação.

### Acabamento da planilha

Tudo resolvido dentro de `gerar_xlsx`, igual para as quatro:

- Cabeçalho em negrito, com cor de fundo e texto claro
- Painel congelado abaixo do cabeçalho (`freeze_panes="A2"`) — rola mil linhas e o cabeçalho fica
- Autofiltro em toda a faixa de dados
- Largura por coluna, definida na `Coluna`
- **Datas como data de verdade** (`dd/mm/aaaa`, `dd/mm/aaaa hh:mm`) e **números como número** — dá para ordenar e somar na planilha
- Valor nulo vira **célula vazia**, nunca o `—` que a tela usa
- Booleano vira "Sim"/"Não"
- Uma linha após os dados registrando **quais filtros geraram o arquivo** e a data/hora da geração — para quem receber a planilha saber o que está olhando

## Frontend

### `components/ui/BotaoExportar.tsx` (novo)

Um componente, quatro usos:

```tsx
<BotaoExportar
  caminho="/equipamentos-cliente/exportar"
  params={{ cliente: clienteId, status: statusFiltro, ativo: ativoFiltro, q: busca }}
  nome="equipamentos"
/>
```

Monta a query com os filtros que estão na tela **naquele momento**, mostra `Spinner` + "Gerando planilha…" enquanto o backend trabalha (o botão fica desabilitado), e exibe o erro inline se a API recusar. Chaves com valor `undefined`/`''` não entram na query. Fica ao lado do título da página, variante `secondary`.

### `lib/download.ts` (mudança)

O arquivo já tem toda a lógica delicada da janela nativa de "salvar como": abrir a janela **antes** de buscar o arquivo (o crédito do clique expira e o Chrome barra a janela se ela vier depois), tratar cancelamento sem lançar erro, e cair no `<a download>` em navegador sem a API.

Os helpers internos (`janelaSalvar`, `salvarDireto`, `cancelado`) são extraídos e passa a existir:

```ts
export async function baixarPlanilha(nomeSugerido: string, obterBlob: () => Promise<Blob>): Promise<void>
```

Mesma janela nativa, `accept` de xlsx, **sem** a parte de reabrir numa aba — o navegador não renderiza xlsx, e essa parte existe porque o laboratório abre o PDF do certificado para imprimir. `baixarPdfComEscolhaDePasta` fica intocada no comportamento.

### Onde o botão entra

| Página | Filtros que vão junto |
|---|---|
| `ClientesPage` | busca (`q`) — a lista de clientes não tem outro filtro |
| `FrotaPage` | cliente, status, ativo, busca |
| `OrdensPage` | fase, cliente, tipo de serviço, busca, chegada de/até |
| `CertificadosPage` → aba "Emitidos" (nova) | período, cliente |

A aba "Emitidos" é a única UI nova: dois filtros e o botão.

## Testes

TDD, conforme o `CLAUDE.md` do projeto.

**Backend** (`pytest`, SQLite in-memory):

- `tests/test_planilha.py` — o módulo puro: cada formato de célula produz o tipo certo; nulo vira célula vazia; booleano vira Sim/Não; cabeçalho presente e congelado; autofiltro na faixa certa; rodapé com os filtros; `PlanilhaGrandeDemais` acima do teto.
- `tests/test_exportar.py` — os quatro endpoints: recusa sem token; **respeita cada filtro** (registro que não bate com o filtro não aparece na planilha); `Content-Type` e `Content-Disposition` corretos; 400 acima do teto.

O teste de filtro é o que importa mais: é ele que impede a planilha de sair com dados a mais.

**Frontend** (Vitest + Testing Library):

- `BotaoExportar.test.tsx` — chama o caminho certo com os filtros certos; omite filtro vazio da query; mostra estado de carregando; mostra erro quando a API falha.

Os testes existentes de listagem (`test_frota.py`, `test_clientes.py`, `test_ordens*.py`) passam **sem alteração** — é a prova de que a extração dos filtros não mudou comportamento.

## Riscos e pontos em aberto

- **`openpyxl` no deploy.** Entra no `requirements.txt`, mas a imagem Docker precisa ser reconstruída — não é uma mudança que sobe só com pull de código.
- **Coluna "Marca".** Depende do vínculo em `equipamentos`; a confirmar na implementação. Não bloqueia.
- **Geração síncrona.** Segura no teto de 50k linhas. Se a base crescer muito, o caminho é job em background — fora de escopo.
- **Portal do cliente sem exportação.** Decisão consciente. Cliente que pedir planilha continua dependendo da equipe interna.

## Ordem de entrega

1. `docs(spec)` — este documento
2. `docs(plan)` — plano de implementação
3. `refactor(export)` — extração dos filtros para helpers, testes de listagem verdes sem mudança
4. `feat(export)` — `core/planilha.py` + testes
5. `feat(export)` — os quatro endpoints + testes
6. `feat(export)` — `BotaoExportar`, `baixarPlanilha`, aba "Emitidos" + testes
7. `docs(changelog)` — bump da versão em `frontend/src/app/changelog/data.ts`
