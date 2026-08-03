# QR dos certificados auxiliares no certificado de calibração — Design

**Data:** 2026-08-03
**Área:** backend (`core/certificado_qr.py` novo, `core/certificado_config.py`, `core/certificado_gerar.py`, `schemas/certificado_config.py`, migração `0025`) + frontend (`app/certificados/ConfiguracoesTab.tsx`, `api.ts`) + testes.
**Tipo:** feature nova com migração e **dependência nova no backend**.

## Problema

Hoje, toda vez que a Health Safety envia um certificado de calibração ao cliente, envia junto — impressos — mais três documentos: o **certificado do gás**, o do **termohigrômetro digital** e o do **barômetro digital**. São documentos que mudam raramente (uma vez por ano, na recalibração dos padrões) e que vão idênticos em todo envio.

O custo é papel e postagem multiplicados por cada certificado emitido.

Os três documentos **já estão no sistema**, em Certificados › Gerais, que existe exatamente para isso: guarda o PDF e expõe um **link público assinado** (`/publico/certificado-geral/{id}?t=<HMAC>`, sem login) com botões de copiar link e gerar QR na tela. O que falta é levar esse link para dentro do certificado de calibração, para o cliente escanear em vez de receber papel.

## Decisões tomadas

Três, todas do Erick em 03/08/2026:

1. **A legenda de cada QR é um rótulo fixo do instrumento** — "Certificado do Gás", "Certificado do Termohigrômetro Digital", "Certificado do Barômetro Digital" —, não o nome cadastrado do documento. Os nomes cadastrados hoje são `LV09700-06672-26` e `LV09700-07432-26`: números de certificado, que não dizem ao cliente o que ele vai baixar.
2. **Documento não configurado é omitido em silêncio.** Faltando o do barômetro, saem os outros dois. Nunca bloqueia a emissão — mesmo princípio já aplicado no aviso de medição fora da faixa: o certificado de um caso irregular também precisa ser emitido.
3. **Um único token `[qrcertificados]`** monta o bloco inteiro, em vez de três tokens de imagem soltos. Um lugar para colar por template, layout consistente entre aparelhos, e os rótulos não passam a ser digitados à mão em cada modelo.

## Design

### 1. Configuração: três documentos selecionados

`certificado_config` ganha três colunas, todas FK opcionais para `certificado_geral.id`:

| Coluna | Documento |
|---|---|
| `doc_gas_id` | Certificado do Gás |
| `doc_termohigrometro_id` | Certificado do Termohigrômetro Digital |
| `doc_barometro_id` | Certificado do Barômetro Digital |

Guarda-se o **id**, não a URL. A URL é derivada na geração por `link_certificado_geral`, então continua correta se a chave HMAC de assinatura ou a `CERT_PUBLIC_BASE_URL` mudarem. Gravar a URL congelaria um link que pode deixar de resolver.

Migração `0025`, `down_revision = "0024_certificado_config_padroes"`. Sem seed: os três nascem nulos e o Administrador seleciona na tela.

### 2. `core/certificado_qr.py` — geração do QR (módulo puro)

Sem `Session`, sem I/O, sem import de `app.models` — mesma disciplina de `certificado_calculo.py`, e pela mesma razão: é a parte testável isoladamente.

- `qr_data_uri(url: str) -> str` — o QR como **SVG** embutido num `data:` URI.
- `bloco_qr(itens: Sequence[tuple[str, str]]) -> str` — o HTML dos QRs lado a lado, cada um com seu rótulo acima. Lista vazia devolve `""`.

**SVG e não PNG**, deliberadamente: o certificado é impresso. SVG é vetorial e sai nítido em qualquer resolução, enquanto um PNG de 240 px borra no papel — e um QR borrado é um QR que não escaneia. De quebra, dispensa Pillow.

**Dependência nova: `segno`** — Python puro, sem compilação, sem dependências transitivas. Entra em `requirements.txt`.

> ⚠️ **Consequência operacional:** o container de desenvolvimento monta `./backend` com `--reload`, mas as dependências vivem na imagem. Esta é a única mudança desta entrega que **não recarrega sozinha** — exige `docker compose build`. Em produção (Easypanel, via Dockerfile) o deploy já reconstrói.

### 3. Resolução dos documentos

`core/certificado_config.py` ganha `documentos_qr(db, config) -> list[tuple[str, str]]`: lê as três FKs na ordem Gás → Termohigrômetro → Barômetro, busca cada `CertificadoGeral`, monta o link público e devolve os pares `(rótulo, url)`.

**Descarta em silêncio** quando: a FK é nula, o documento foi excluído do cadastro, ou `link_certificado_geral` devolve `None` (sem `CERT_PUBLIC_BASE_URL`). Nenhum desses casos levanta exceção — é a decisão 2 implementada no ponto onde ela importa.

### 4. `[qrcertificados]` é um token ESTRUTURAL

Este é o ponto de maior risco do design e merece ser explícito.

`preencher()` escapa **todos** os valores do contexto. Não é detalhe: é o que impede um nome de cliente contendo `<script>` de virar HTML executável no certificado. Um bloco de markup passando por esse laço sairia impresso como texto literal — `&lt;table&gt;…` — no PDF do cliente.

Hoje a única exceção é `[pulapagina]`, tratada fora do laço. Em vez de acrescentar um segundo caso especial, a regra passa a ser declarada:

```python
_TOKENS_ESTRUTURAIS = {"pulapagina", "qrcertificados"}
```

Valores desses tokens são inseridos **sem escapar**; todo o resto continua escapado. Uma regra dita em um lugar, em vez de um `if` por token.

**Os dois tokens estruturais funcionam de formas diferentes, e isso precisa ficar claro:** `pulapagina` não existe no contexto — seu valor é a constante `_PAGE_BREAK`. Já `qrcertificados` **está** no contexto, porque seu valor muda a cada certificado (depende de quais documentos estão configurados). O que `_TOKENS_ESTRUTURAIS` faz é excluir a chave do laço que escapa, não tirá-la do contexto.

**Por que é seguro:** o bloco não contém nenhum dado do usuário. Os rótulos são constantes do código e as URLs são links assinados que o próprio sistema monta a partir de `settings`. Nada que o cliente, o laboratório ou o cadastro digitem entra ali.

O token é emitido pelos **três** caminhos de contexto (OS, avulso, venda) como as demais chaves calculadas. Um caminho que o omita imprime `[qrcertificados]` literalmente no documento do cliente.

**As duas listas de tokens ganham a entrada.** `CAMPOS` em `backend/app/core/certificado_gerar.py` e `CAMPOS_CERTIFICADO` em `frontend/src/app/certificados/api.ts` — a segunda alimenta a paleta do editor de modelos. Token que entra só no backend existe no motor mas fica **invisível** para quem monta o template, e ninguém consegue colá-lo.

### 5. Tela — Configurações

A aba ganha um bloco **Documentos anexos ao certificado**, com três selects (Gás, Termohigrômetro Digital, Barômetro Digital). Cada um lista os Certificados Gerais cadastrados mais uma opção vazia ("— nenhum —"). A lista vem de `GET /certificados-gerais`.

Mesma regra de acesso do resto da aba: qualquer usuário interno lê, só Administrador grava — espelhada em `podeEditarConfigCertificado`.

### 6. Onde o bloco entra no template

`[qrcertificados]` é colado no template do aparelho, **depois da assinatura**, aproveitando o espaço vazio que sobra hoje no fim da página 2. O bloco é dimensionado para caber ali.

Isso é requisito, não preferência: o pedido nasceu de economizar papel. Um bloco que empurre o certificado para uma terceira folha troca três documentos impressos por uma folha a mais em todo certificado — e some parte do ganho.

## Testes

| Onde | O quê |
|---|---|
| `test_certificado_qr.py` | `qr_data_uri` devolve `data:image/svg+xml`; `bloco_qr` com 3, 2, 1 e 0 itens; o rótulo aparece acima do QR |
| `test_certificado_config.py` | `documentos_qr` com os três configurados; com um nulo; com um id apontando para documento excluído; sem `CERT_PUBLIC_BASE_URL` |
| `test_certificado_contexto*.py` | `qrcertificados` presente nos três caminhos; paridade de chaves preservada |
| `test_certificado_gerar.py` | `preencher` NÃO escapa `[qrcertificados]`; continua escapando um valor de dado com `<script>` |
| frontend | os três selects renderizam com as opções; salvar envia os ids; não-admin não vê os controles |
| verificação manual | renderizar o PDF, conferir que **continua em 2 páginas**, e **decodificar o QR gerado** para provar que resolve no link certo — não basta parecer um QR |

## Fora de escopo

- **Tokenizar Dry Gás PPM, técnico e "Situação : APROVADO"** — o Erick decidiu em 03/08 mantê-los fixos no HTML por enquanto.
- **Colar `[qrcertificados]` nos templates de produção** — é trabalho de cadastro. A implementação entrega o token e o aplica no Interlock X6, que é o aparelho de teste.
- **Anexar os PDFs ao e-mail** — a decisão foi substituir o papel pelo QR, não automatizar outro envio.
