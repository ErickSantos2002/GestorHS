# Múltiplas notas fiscais por caixa — design

**Data:** 04/09/2026
**Origem:** pedido do Financeiro. Duas necessidades no mesmo lugar:

1. Algumas caixas precisam de **mais de uma nota fiscal** — além da nota do serviço, vai junto a nota de envio/remessa. Não é toda caixa: umas levam uma, outras duas, outras três ou quatro.
2. Às vezes ele **anexa a nota errada e avança a caixa**. Hoje não existe correção: o botão de anexar só aparece na fase Financeiro e não há como remover o que já foi anexado.

## Como está hoje

A nota fiscal são **três colunas em `ordens`**:

```python
nota_fiscal = Column(String(50))          # basename do PDF em disco
nota_fiscal_xml = Column(String(50))      # basename do XML
nota_fiscal_numero = Column(String(50))   # numero da NF
```

Uma nota por OS, e só uma. O `POST /caixas/{id}/nota-fiscal` recebe o par PDF+XML mais o número e grava uma **cópia física dos dois arquivos no subdir de cada OS ativa** da caixa (`notas-fiscais/{ordem_id}`), setando as três colunas em todas. `_gravar_par` apaga os arquivos anteriores antes de gravar os novos — anexar de novo hoje **substitui**, não acumula.

O modal por OS não existe mais: `frontend/src/app/ordens/OrdemDetailPage.tsx` só exibe e baixa, com o comentário dizendo que o anexo é no nível da caixa. Ou seja, **"a nota é da caixa" já é a realidade do fluxo — só não é a realidade do banco.**

Quem depende dessas colunas:

| Consumidor | O que faz |
|---|---|
| `GET /ordens/{id}/nota-fiscal` e `.../xml` | download autenticado, por OS |
| `/publico/nota-fiscal/{ordem_id}` e `.../xml` | download sem login, token HMAC `nf:{ordem_id}` |
| `core/taskhs.py::_sec_financeiro` | obs4 do card: `Nota fiscal: N`, `NF em PDF: url`, `NF em XML: url` |
| `api/caixas.py::executar_avanco_caixa` | guard: `if not o.nota_fiscal` → 409 ao sair do Financeiro |
| `core/exportacoes.py` | coluna "Nota fiscal" da planilha de OS |
| `OrdemDetailPage.tsx` | seção de exibição/download |

O comentário em `core/nota_fiscal_link.py` é explícito: **não mudar o formato da mensagem do PDF**, há links já publicados nos cards do TaskHS.

## Decisões tomadas no brainstorm

| Pergunta | Decisão |
|---|---|
| A nota extra é da caixa ou de um aparelho? | **Da caixa.** O lote é o que vai; a nota de remessa cobre o pacote todo. |
| Como a expedição distingue nota de serviço da de remessa? | **Só pelo número**, na ordem em que foram anexadas. Sem campo de tipo nem descrição. |
| XML obrigatório nas extras? | **Sim, sempre o par.** Mantém a regra que já existe. |
| Até onde vai a correção? | **Fases 10 (Financeiro) e 7 (Preparando Retorno).** Não alcança caixa finalizada nem cancelada. |
| Teto de notas? | **Nenhum.** "Até 3 ou 4" foi exemplo, não limite. |

## O modelo de dados

Tabela nova, ligada à caixa:

```python
class NotaFiscal(Base):
    __tablename__ = "notas_fiscais"
    id = Column(Integer, primary_key=True, index=True)
    caixa = Column(Integer, ForeignKey("caixas.id"), nullable=False, index=True)
    numero = Column(String(50), nullable=False)
    arquivo_pdf = Column(String(50), nullable=False)
    arquivo_xml = Column(String(50), nullable=False)
    ordem = Column(Integer, ForeignKey("ordens.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False)
    criado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
```

`ordem` é **só do backfill**: marca que os arquivos daquela nota estão no subdir antigo, o da OS. Nota nova nasce com `ordem = NULL`.

O subdir vira função pura, em `core/nota_fiscal.py`, que já é a fonte única da convenção:

```python
def subdir_caixa(caixa_id: int) -> str:
    return f"notas-fiscais/caixa/{caixa_id}"

def subdir_nota(nota) -> str:
    # nota do backfill aponta para o subdir da OS onde o arquivo ja esta;
    # nota nova vive no subdir da caixa. Nenhum arquivo e movido de lugar.
    return subdir(nota.ordem) if nota.ordem else subdir_caixa(nota.caixa)
```

### Por que não replicar por OS

A alternativa era manter a réplica de hoje: N linhas por OS, cópia física em cada subdir. Uma caixa de 4 aparelhos com 4 notas viraria 32 arquivos idênticos no disco, e remover uma nota viraria "remover em todas as OS". Só compensaria se a nota um dia passasse a ser por aparelho — e a decisão foi que não é.

### As colunas legadas congelam

`ordens.nota_fiscal`, `nota_fiscal_xml` e `nota_fiscal_numero` **não são apagadas e não recebem escrita nova**. Existem para uma coisa só: continuar servindo as rotas antigas — `GET /ordens/{id}/nota-fiscal` e o link público `nf:{ordem_id}` —, para que os links já publicados nos cards do TaskHS não quebrem. Nenhum caminho novo escreve nelas.

Não fazer dual-write é deliberado: manter a coluna espelhando "a primeira nota da caixa" pareceria conveniente, mas criaria duas fontes de verdade para o mesmo dado, e a divergência apareceria sem aviso — exatamente o que aconteceu com o modelo de relatório de manutenção colado à mão na tela.

### Migração `0029_notas_fiscais`

Cria a tabela e faz o backfill. Para cada caixa que tem ao menos uma OS com `nota_fiscal` preenchido, insere **uma** linha:

- `caixa` = a caixa
- `numero` = `nota_fiscal_numero` da OS representante
- `arquivo_pdf` / `arquivo_xml` = os basenames dessa OS
- `ordem` = o id da OS representante (é onde os arquivos estão)

Representante = a primeira OS da caixa (por id) com `nota_fiscal` **e** `nota_fiscal_xml` preenchidos, espelhando o `rep_nf` que `api/espelhamento.py` já usa hoje para escolher de qual OS sai o link do card. **Nenhum arquivo é movido no disco.**

O backfill importa por dois motivos concretos: sem ele, uma caixa hoje na fase 10 ou 7 apareceria como "sem nota" depois do deploy, e o guard de avanço a travaria. Cobrir só as caixas ativas resolveria isso, mas deixaria a tela da OS e a planilha lendo de dois lugares — o backfill vai em todas.

**OS antiga com PDF e sem XML** (existem, o XML nasceu na migração 0026): `arquivo_xml` é `NOT NULL`, então essas caixas não entram no backfill como nota. Ficam com o comportamento de hoje, servido pelas colunas legadas — a tela da OS cai no bloco legado quando a caixa não tem nenhuma nota na tabela (ver "Frontend"). O guard de avanço aceita as duas fontes (ver abaixo), então caixa antiga não trava.

**OS sem caixa** não entra no backfill; suas colunas legadas continuam servindo a própria tela.

## API

### Anexar — `POST /caixas/{id}/notas-fiscais`

Recebe **listas paralelas**, para que o "+" da tela mande as N notas num envio só:

```
numeros: list[str] = Form(...)
arquivos_pdf: list[UploadFile] = File(...)
arquivos_xml: list[UploadFile] = File(...)
```

Validações, antes de gravar qualquer arquivo:

- as três listas têm o mesmo comprimento e ao menos um item → senão 422
- cada número passa por `_validar_numero` (não vazio, ≤ 50) → senão 422
- caixa existe → senão 404
- `caixa.fase` ∈ (10, 7) → senão 409
- caixa tem OS ativa → senão 409 (regra que já existe)

Grava as N notas numa transação só. Ou entram todas, ou nenhuma — anexar em lote não pode deixar metade das notas gravadas se a quarta for um XML inválido. **Acumula**: as notas já anexadas continuam lá.

Responde `CaixaDetalhe` (como o endpoint atual) e re-espelha a caixa no TaskHS.

### Remover — `DELETE /caixas/{id}/notas-fiscais/{nota_id}`

Apaga o registro **e os arquivos do disco**. Mesmos guards de função e de fase do anexar; 404 se a nota não é daquela caixa. Re-espelha a caixa.

Remover uma nota do backfill apaga o arquivo que a rota pública antiga (`nf:{ordem_id}`) ainda nomeia — aquele link passa a devolver 404. É o comportamento certo: nota removida é nota que não deve mais ser baixada por ninguém.

Anexar e remover **registram log na OS** (`registrar_log`), uma linha por OS ativa da caixa: `Nota fiscal 12345 anexada` / `Nota fiscal 12345 removida`. A correção precisa deixar rastro — é a pergunta que o Financeiro vai fazer daqui a um mês.

### Download — `GET /caixas/{id}/notas-fiscais/{nota_id}/pdf` e `/xml`

Autenticado (`get_current_usuario`, como as rotas de OS). Resolve o subdir por `subdir_nota`, e reusa `media_type`/`nome_download` que já existem — o XML continua saindo como `application/octet-stream` com `X-Content-Type-Options: nosniff`, pela mesma razão de sempre (XML de usuário servido inline executaria `<script>`).

### Rotas antigas

Saem duas rotas de **escrita**:

- `POST /caixas/{id}/nota-fiscal` (singular) — substituída pela plural. O único chamador é o modal, que é reescrito.
- `POST /ordens/{ordem_id}/nota-fiscal` — resquício do modal por OS, que já não existe. `ordensApi.enviarNotaFiscal` no frontend só é chamado pelo próprio teste (`api.notaFiscal.test.ts`); os dois saem junto. É o último caminho que ainda escreveria nas colunas congeladas, e deixá-lo de pé transformaria "congeladas" em promessa vazia.

Vários testes de backend usam esse `POST` por OS como **setup** para ter uma nota fiscal em cena (`test_nota_fiscal.py`, `test_publico_nota_fiscal.py`, `test_caixa_avancar.py`, `test_ordens_taskhs.py`, `test_taskhs_bloqueio_modulo.py`). Eles passam a montar o cenário direto: as colunas legadas gravadas na fixture quando o teste é sobre o comportamento legado, e o endpoint novo da caixa quando é sobre o comportamento novo.

Ficam como estão, servindo as colunas legadas e sem lógica nova, as rotas de **leitura**: `GET /ordens/{id}/nota-fiscal`, `.../xml` e as duas públicas `nf:{ordem_id}`.

### Guard de avanço

Em `executar_avanco_caixa`, a saída do Financeiro deixa de olhar `o.nota_fiscal` por OS e passa a perguntar da caixa:

```python
elif origem == 10:
    if not tem_nota_fiscal and not sem_nota_fiscal:
        raise HTTPException(409, "anexe a nota fiscal da caixa antes de confirmar o pagamento")
```

`tem_nota_fiscal` é calculado uma vez, antes do laço: existe linha em `notas_fiscais` para a caixa **ou** alguma OS ativa tem `nota_fiscal` preenchido. O segundo termo é o que impede caixa antiga (PDF sem XML, fora do backfill) de travar.

O `sem_nota_fiscal` do Administrador segue com a mesma semântica, mas a linha de log dele também deixa de olhar a coluna: `if sem_nota_fiscal and origem == 10 and not tem_nota_fiscal`. Senão a caixa que tem nota nova na tabela ganharia o carimbo "(sem nota fiscal, dispensada pelo Administrador)" mesmo tendo nota.

## Link público e TaskHS

### Link por nota

Formato novo em `core/nota_fiscal_link.py`, ao lado do antigo, sem tocar nele:

```python
def _mensagem_nota(nota_id: int, tipo: str = PDF) -> str:
    return f"nf:n:{nota_id}" if tipo == PDF else f"nf:n:{nota_id}:{tipo}"
```

Rotas em `api/publico.py`: `/publico/nota-fiscal/nota/{nota_id}` e `/publico/nota-fiscal/nota/{nota_id}/xml`. PDF e XML continuam com **tokens distintos** — assinar os dois com a mesma mensagem faria um link antigo de PDF baixar o XML.

### obs4 do card

`_sec_financeiro` passa a receber uma **lista de notas** já resolvidas em `(numero, url_pdf, url_xml)`, montada em `api/espelhamento.py`, e escreve uma linha por nota:

```
Pagamento: confirmado em 04/09/2026
NF 12345 — PDF: <link> · XML: <link>
NF 12346 — PDF: <link> · XML: <link>
```

Quando a caixa não tem nenhuma nota na tabela, cai no formato de hoje, alimentado pelas colunas legadas do `rep_nf` — é o que mantém o card de caixa antiga igual ao que a expedição já conhece.

`taskhs.py` continua puro: quem consulta o banco e assina os links é `_montar_payload_caixa`, como já faz para certificados e proposta.

Como anexar e remover re-espelham a caixa, **corrigir a nota atualiza o card sozinho** — que é a metade do pedido do Financeiro.

## Frontend

### Modal de anexar

`NotaFiscalCaixaModal.tsx` passa a ter uma **lista dinâmica de blocos**. Cada bloco: número + PDF + XML. Abaixo, `+ Adicionar nota`; cada bloco além do primeiro tem um X para tirá-lo antes de enviar. Abre com um bloco só — a caixa de uma nota, que é a maioria, não fica mais trabalhosa do que é hoje.

Validação por bloco, antes de enviar: número não vazio, PDF escolhido, XML escolhido. A mensagem de erro diz **qual** bloco está incompleto ("Nota 2: escolha o XML"), senão o usuário com quatro blocos não sabe onde olhar.

Envia tudo num `POST` só, com as três listas no `FormData`.

### Tela da caixa

`CaixaDetailPage.tsx` ganha uma seção **"Notas fiscais"**, visível quando a caixa está em 10 ou 7 (ou tem notas), listando cada nota com número, baixar PDF, baixar XML e remover. Remover pede confirmação inline (o padrão da tela, sem `window.confirm` — diálogo de browser trava a automação e não é o estilo do resto).

O botão "Anexar nota fiscal" passa a aparecer nas fases **10 e 7**, para quem tem `podeAnexarNotaFiscal` — o espelho de `roles.ts` já cobre a função (Financeiro/Administrador); o que muda é a condição de fase, que hoje é `caixa.fase === 10` cru. Usar `posicaoFase`, não comparação de ID solta.

`CaixaDetalhe` ganha `notas_fiscais: NotaFiscalOut[]`, com `id`, `numero`, `criado_em`. Basenames não vão para o schema: o download é por rota dedicada, o front não precisa saber o nome do arquivo em disco.

### Tela da OS

A seção "Nota fiscal" lista as notas **da caixa** da OS (número + baixar PDF/XML), sem botão de anexar nem de remover — segue sendo tela de leitura. Se a caixa não tiver nenhuma nota na tabela, cai no bloco de hoje, com as colunas legadas da própria OS. É o que mantém OS antiga (e OS sem caixa) exibindo o que sempre exibiu.

### Planilha

A coluna "Nota fiscal" passa a trazer os números das notas da caixa separados por vírgula (`12345, 12346`), caindo em `nota_fiscal_numero` quando a caixa não tem notas na tabela. O `_query_*` da listagem é o mesmo — só muda como a célula é montada em `core/exportacoes.py`.

## Testes

**Backend** (`tests/test_notas_fiscais_caixa.py`, mais ajustes nos existentes):

- anexar 3 notas numa chamada → 3 linhas, arquivos no subdir da caixa
- anexar de novo → acumula, não substitui (é a inversão do comportamento atual, merece teste próprio)
- listas de tamanhos diferentes → 422, e **nenhum arquivo gravado**
- XML inválido no terceiro bloco → 415 e nenhuma das três notas gravada (atomicidade) — 415 e não 422 porque quem recusa é `storage.ArquivoInvalido` (`app/core/storage.py`), a convenção já usada no resto do sistema para tipo de mídia não suportado
- anexar/remover com caixa em 7 → 200; em 8 → 409; em 6 → 409
- anexar sem ser Financeiro/Administrador → 403
- remover nota de outra caixa → 404
- remover apaga o arquivo do disco
- guard de avanço: caixa sem nota → 409; com nota na tabela → passa; caixa antiga só com coluna legada → passa
- link público por nota: token do PDF não abre o XML; token de outra nota não abre esta
- `_sec_financeiro` com 0, 1 e 3 notas; caixa antiga cai no formato legado
- migração: backfill escolhe a OS representante certa, ignora OS sem XML

**Frontend:**

- o `+` adiciona bloco; o X remove; o primeiro bloco não tem X
- erro nomeia o bloco incompleto
- envio manda as três listas paralelas
- lista de notas na tela da caixa renderiza e o remover chama a API
- botão "Anexar nota fiscal" aparece em 10 e 7, some em 8

**Regressão a vigiar:** as 5 falhas pré-existentes desta máquina são baseline verde — conferir antes de acusar regressão.

## Fora de escopo

- Tipo ou descrição da nota (serviço/remessa) — decidido: só o número.
- Editar uma nota já anexada. Corrigir é remover e anexar de novo.
- Nota fiscal por aparelho.
- Correção em caixa finalizada ou cancelada.
- Migrar arquivos de lugar no disco.
- Remover as colunas legadas de `ordens`.

## Armadilhas conhecidas do repo que valem aqui

- **O ID 10 (Financeiro) é maior que o 7 e o 8, mas vem antes deles.** A janela de correção é "Financeiro e Preparando Retorno" — escrever isso como `fase >= 7` ou como lista literal `(7, 8)` erra. Usar `posicao()` no backend e `posicaoFase()` no frontend.
- **Um card por CAIXA, nunca por OS.** Anexar e remover chamam `agendar_espelhamento_caixa`, nunca um caminho por OS — espelhar a OS abriria um segundo card para a mesma caixa.
- **Levantar FK por `pg_constraint`**, se a migração precisar conferir dependências. O `information_schema` devolve vazio e engana.

## Sequência de commits

1. `docs(spec)` — este documento
2. `docs(plan)` — plano de implementação
3. `feat(nf)` — model, migração `0029` com backfill e `core/nota_fiscal.py` + testes
4. `feat(nf)` — endpoints de anexar/remover/baixar, guard de avanço + testes
5. `feat(nf)` — link público por nota e obs4 do TaskHS + testes
6. `feat(nf)` — modal com `+`, seção de notas na tela da caixa, tela da OS, planilha + testes
7. `docs(changelog)` — bump da versão em `frontend/src/app/changelog/data.ts`
