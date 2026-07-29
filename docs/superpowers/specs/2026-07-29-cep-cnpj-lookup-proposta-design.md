# Campo CEP na proposta + busca automática por CEP e CNPJ — Design

**Data:** 2026-07-29
**Área:** backend (novo `api/integracoes_externas.py`, novo `core/enderecos.py`, novo `integrations/enderecos_client.py`, `core/proposta_pdf.py`) + frontend (`app/propostas/PropostaModal.tsx`, `clienteOverride.ts`, novo `app/propostas/buscaEndereco.ts`).
**Tipo:** feature — novo campo no override da proposta + consulta a APIs públicas.

## Problema

Os dados do cliente numa proposta (o override "Editar dados nesta proposta") não têm **CEP** — nem o PDF imprime o CEP do cadastro. E preencher Razão social, Endereço, Município e Estado é digitação manual, sujeita a erro, quando esses dados são públicos e consultáveis pelo CNPJ ou pelo CEP.

Queremos: (1) o campo CEP nos dados do cliente da proposta; (2) uma lupa ao lado do CEP e outra ao lado do CNPJ que consultam APIs públicas e preenchem os campos automaticamente.

## Contexto (padrões a espelhar)

- **Integração externa:** `integrations/taskhs_client.py` faz o I/O com `httpx` (já é dependência), `core/taskhs.py` é puro e testável. Mesma separação aqui.
- **Override da proposta:** `cliente_override` é JSON (sem migração para novos campos). A lista canônica de campos, rótulos e a comparação com o cadastro vivem em `frontend/src/app/propostas/clienteOverride.ts`; o backend consome as mesmas chaves em `core/proposta_pdf.py`.
- **Bloco de endereço no PDF:** `proposta_pdf` monta `cliente_endereco` e `cliente_cidade_estado` do cadastro e aplica o override por cima. O bloco de **entrega** do mesmo PDF já usa o formato `Município/UF — CEP: NNNNN-NNN`.

## Design

### 1. Backend — dois endpoints internos

Dois GETs autenticados por usuário interno (`get_current_usuario`), timeout de 5s, registrados em `main.py`:

```
GET /integracoes/cep/{cep}    → { cep, endereco, municipio, estado }
GET /integracoes/cnpj/{cnpj}  → { documento, nome, endereco, municipio,
                                  estado, cep, situacao }
```

O payload carrega só o que a tela consome. `bairro` e `nome_fantasia` existem nos provedores mas não têm campo correspondente na proposta — o bloco de endereço do PDF nunca mostrou bairro, nem para dados vindos do cadastro — então ficam de fora em vez de trafegar sem uso.

**`core/enderecos.py` (puro, sem I/O):** validação de formato (8 dígitos / 14 dígitos) e um mapeador por provedor, do JSON cru para o nosso formato. É onde mora a normalização — inclusive o *capitalize* descrito em §3.

**`integrations/enderecos_client.py` (I/O):**
- **CEP:** BrasilAPI `https://brasilapi.com.br/api/cep/v2/{cep}` como primária; **ViaCEP** `https://viacep.com.br/ws/{cep}/json/` como fallback quando a primária falha ou devolve 404. Os formatos diferem (`street`/`city`/`state` vs `logradouro`/`localidade`/`uf`), daí um mapeador para cada. A ViaCEP sinaliza CEP inexistente com `{"erro": true}` e HTTP 200 — tratar como não encontrado.
- **CNPJ:** BrasilAPI `https://brasilapi.com.br/api/cnpj/v1/{cnpj}`, sem fallback. A ReceitaWS limita a 3 req/min, o que geraria mais erro do que ajuda.

**Erros traduzidos para o frontend:** `400` formato inválido (validado antes de sair para a rede) · `404` não encontrado · `502` provedor indisponível.

Diferente do TaskHS, esta integração **não é best-effort e não é gateada por env**: é síncrona, o usuário está esperando o resultado, e o erro precisa chegar na tela.

### 2. O que cada lupa preenche

| Lupa | Preenche | Não toca |
|---|---|---|
| **CEP** | Endereço (logradouro), Município, Estado | Nome, Documento, Telefone, E-mail, Contato |
| **CNPJ** | Razão social, Endereço, Município, Estado, **CEP** | Telefone, E-mail, Contato |

O CNPJ devolve endereço completo (`logradouro` + `numero` + `complemento`) e é montado numa string só, que é o formato do campo Endereço. O CEP chega apenas no nível da rua — o número continua sendo digitado à mão.

**Telefone e E-mail ficam de fora de propósito:** na Receita esses campos costumam estar desatualizados, e são justamente os que a Health Safety mantém bons no cadastro.

**Situação cadastral:** a busca por CNPJ exibe `situacao` ao lado da mensagem de preenchimento (*"Situação na Receita: ATIVA"*), em âmbar quando for diferente de ATIVA. É informação para quem está montando a proposta — não bloqueia nada e não vai para o PDF.

**Conflito com o que já está preenchido:** a busca **sobrescreve** os campos que ela retorna. Preencher só o que está vazio não funcionaria aqui — o painel de override abre pré-preenchido com o cadastro, então quase nada está vazio e a lupa pareceria quebrada. Para tornar isso reversível, depois de cada busca aparece a linha *"Preenchido pelo CNPJ: Razão social, Endereço, Município, Estado, CEP"* com um **Desfazer** que restaura o snapshot do painel inteiro tirado imediatamente antes da busca.

### 3. Normalização: MAIÚSCULAS da Receita

A Receita devolve tudo em caixa alta e sem acento (`"BR 101"`, `"ZONA RURAL"`, `"JOAO NEIVA"`). Gravar assim destoaria do resto do documento comercial, então `core/enderecos.py` capitaliza Razão social, Endereço e Município (Estado permanece a sigla em caixa alta).

Limitação assumida e explícita: **a acentuação não é restaurada** — a fonte já veio sem ela, e inventar acento seria adivinhar. Resultado: `"Joao Neiva"`. O usuário corrige no campo se quiser.

Preposições e conectivos ficam minúsculos (`de`, `da`, `do`, `dos`, `das`, `e`) exceto na primeira palavra, e tokens que não são palavras normais são preservados como vieram: siglas de rodovia (`BR`, `PE`), `S/N`, `KM`, e qualquer token com dígito. `"BR 101"` continua `"BR 101"`, não vira `"Br 101"`.

### 4. O campo CEP

Novo campo no painel "Editar dados nesta proposta". As duas lupas ficam lado a lado na mesma linha, por serem as duas chaves de busca:

```
Razão social / Nome                    (linha inteira)
CNPJ / Documento 🔍  |  CEP 🔍
Endereço                               (linha inteira)
Município            |  Estado
Telefone             |  E-mail
Contato                                (linha inteira)
```

`cep` entra em `CAMPOS_OVERRIDE`/`ROTULOS_OVERRIDE` e ganha seu caso em `valorDoCadastro` (lendo `Cliente.cep`) — assim o comparativo "Dados editados" já criado cobre o campo novo de graça. O input usa máscara progressiva de CEP, no mesmo espírito de `mascararCNPJ`/`mascararCPF` em `lib/documento.ts`; o armazenamento é só dígitos, a formatação fica nas pontas.

**No PDF:** `proposta_pdf` passa a ler `cliente.cep`, com o override por cima, e a emitir o CEP junto da linha de cidade/UF — `Recife - PE — CEP: 50.030-230` — que é a convenção que o bloco de Endereço de Entrega do mesmo PDF já usa. Sem migração: `cliente_override` é JSON e `Cliente.cep` já existe.

### 5. Override passa a gravar só o que diverge

Hoje o painel abre pré-preenchido com o cadastro inteiro, então **Aplicar grava os 8 campos** mesmo sem nenhuma alteração — e a proposta ganha o selo "Dados editados" à toa. Com o CEP entrando nesse mesmo painel, o problema fica mais frequente: quem quer só informar um CEP acabaria marcando a proposta como editada.

Correção: ao Aplicar, campos cujo valor é idêntico ao do cadastro **não entram** no override. O selo passa a significar de fato "tem coisa diferente do cadastro".

Isso muda uma semântica e a mudança é intencional: campos não gravados voltam a acompanhar o cadastro se ele mudar depois, em vez de ficarem congelados no valor do momento da edição. Propostas antigas não são migradas — seus overrides continuam como estão, e o comparativo segue mostrando `(igual ao cadastro)` nos campos redundantes.

## Fora de escopo

- Lupas no cadastro do cliente (aba Dados) — mesmos campos, mas decidido manter a superfície pequena. A busca fica num módulo reutilizável para essa extensão ser barata depois.
- Busca de CEP no **Endereço de entrega** da proposta, que segue texto livre.
- Cache/rate-limit dos endpoints: são autenticados e de uso interno esporádico.
- Preenchimento automático ao digitar (debounce). A busca é só no clique da lupa — consistente com a decisão recente de que Enter não dispara ação nesse formulário.
- Bloquear proposta para CNPJ com situação cadastral baixada/inapta — a `situacao` é só exibida (§2), sem travar nada.

## Consequência a registrar

O PDF nunca imprimiu CEP do cliente. Com esta mudança, **toda proposta existente passa a mostrar o CEP do cadastro** quando o PDF for baixado de novo. As versões já arquivadas não mudam — elas têm o PDF salvo em disco (`proposta_versao.pdf_path`); só o PDF corrente é gerado na hora.

## Segurança

Endpoints exigem usuário interno — não são expostos ao portal do cliente. O `{cep}`/`{cnpj}` do path é validado como dígitos antes de compor a URL do provedor, então não há como injetar caminho na chamada externa. Nenhum dado do GestorHS é enviado para fora: sai apenas o CEP ou o CNPJ consultado.

## Testes

**Backend**
- `core/enderecos.py`: mapeadores BrasilAPI e ViaCEP → nosso formato; `{"erro": true}` da ViaCEP como não encontrado; validação de 8/14 dígitos; capitalização (preposições minúsculas, `BR 101` e `S/N` preservados, primeira palavra sempre maiúscula).
- `integrations/enderecos_client.py`: `httpx` monkeypatched — fallback para ViaCEP quando a BrasilAPI dá erro e quando dá 404; erro de rede vira 502. **Nenhum teste toca a internet.**
- `core/proposta_pdf.py`: CEP do cadastro no bloco do cliente; override de `cep` sobrepondo; proposta sem CEP nenhum não emite a linha.

**Frontend**
- Lupa do CNPJ preenche os campos esperados e **não** altera Telefone/E-mail/Contato.
- Lupa do CEP preenche Endereço/Município/Estado e não toca em Nome/Documento.
- Desfazer restaura exatamente o estado anterior à busca.
- CNPJ não encontrado e provedor fora do ar mostram mensagem e não alteram campo nenhum.
- Aplicar sem mudar nada **não** grava override (nem marca a proposta como editada).
- `cep` aparece no comparativo "Dados editados" quando diverge do cadastro.

## Rollout

Backend + frontend, **sem migração**. Versão **v1.31.0**, entrada no changelog (`frontend/src/app/changelog/data.ts`) citando o campo CEP e as buscas automáticas.
