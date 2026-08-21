# Relatório de Manutenção — design

**Data:** 21/08/2026
**Origem:** `docs/certificado-manutencao/` — formulário padrão `FORM-LAB-010` (docx) e três relatórios preenchidos em PDF.

## O problema

A Health Safety emite relatório de manutenção à mão, fora do sistema. O GestorHS não tem onde registrar o que foi feito na bancada: existem os campos de calibração na OS, mas nada equivalente para manutenção.

O motor de certificados já prevê o tipo `"M"` — `tipos_para()` devolve `["C", "M"]` quando o serviço é Manutenção ou Ambas, e `certificados.tipo` aceita `M` —, mas nenhum modelo desse tipo foi cadastrado e não há de onde tirar os dados do documento.

Até 21/08/2026 só existiam **9 OS** com tipo Manutenção ou Ambas, porque a Expedição registrava o tipo na entrada e ninguém mais podia corrigir. A v1.42.0 (Laboratório corrige o tipo de serviço na fase dele) é pré-requisito deste trabalho e já está em produção.

## O que o formulário pede

Campos do FORM-LAB-010, com a origem de cada um:

| Campo | Origem |
|---|---|
| Nº | digitado pelo Laboratório |
| Cliente, CNPJ, Endereço | cadastro do cliente (tokens existentes) |
| Equipamento (fixo "Bafômetro"), Marca, Nº Série, Modelo | cadastro do aparelho (tokens existentes) |
| Ordem Serviço | a própria OS (token existente) |
| Data de venda | `datacompra` do aparelho (token existente) |
| Data da Manutenção | **novo** |
| Local de Manutenção e Endereço da H&S | fixos no modelo |
| Tipo do Problema | **novo** — composto dos serviços escolhidos |
| Resumo do Serviço | **novo** — composto e editável |
| Comentários e assinatura | fixos no modelo |

### Numeração

Os três exemplos usam `HF00711`, `HF00712` e `HF00714`. Esses mesmos números já existem como número de **certificado de calibração** em OS de junho (10535, 10533, 10537), e a série de calibração está em `HF02558`. Ou seja: a manutenção tem série própria, controlada à mão pelo Laboratório, que por coincidência usa o mesmo prefixo.

**Decisão:** o número é campo livre, digitado. O sistema não gera nem valida sequência — não vai brigar com o controle que já existe fora dele.

### Divergências nos arquivos de origem

Duas, a confirmar com a Qualidade — não bloqueiam a implementação:

- O docx se chama "REV 02", mas o cabeçalho dos três PDFs diz "Revisão: 00".
- O texto de "Comentários" do docx é mais antigo. Os PDFs trazem dois parágrafos (política de peças + observação de que a calibração não é sistemática) que o docx não tem.

**O modelo segue os PDFs**, que são o que está em uso.

## Modelo de dados

Três tabelas novas.

### `manutencoes` — uma por OS

```
id
os              FK ordens, ÚNICO
numero          texto livre (ex.: "HF00715")
data_manutencao data
resumo          texto — o "Resumo do Serviço" já composto
criado_por      texto (nome do usuário)
criado_em, atualizado_em
```

A unicidade em `os` espelha `os_certificados`, que já tem unicidade em `(os, tipo)`: **um relatório de manutenção por OS**. Dentro dele cabem vários serviços — que é como a Health Safety trabalha (o relatório de 10301681 cobre troca de pilha interna *e* troca do Bluetooth).

`Local de Manutenção` e o endereço da empresa **não** viram coluna: são fixos no modelo do documento, seguindo o precedente do `Técnico: Walbert Santos`, que já é fixo no certificado de calibração. Vira campo no dia em que houver manutenção em campo.

### `manutencao_servicos` — o catálogo

```
id
descricao     texto, ÚNICO  → vai para "Tipo do Problema"
resumo_padrao texto         → frase pronta que compõe o "Resumo do Serviço"
ativo         booleano
```

Lista **fechada**: o técnico escolhe daqui, não digita serviço livre. Padroniza a escrita no documento e permite responder depois "qual defeito mais aparece no iBlow10?".

Aposentar um serviço é desativar, nunca apagar — apagar faria relatórios antigos perderem o registro do que foi feito.

Não confundir com a tabela `servicos` já existente, que é o catálogo **comercial** das propostas (nome, SKU, preço). Daí o prefixo `manutencao_`, e o rótulo "Serviços de manutenção" na tela.

### `manutencao_itens` — os serviços daquela manutenção

```
id
manutencao  FK manutencoes
servico     FK manutencao_servicos
ordem       inteiro — posição escolhida, define a ordem no texto
ÚNICO (manutencao, servico)
```

## Composição dos textos

Puro, sem I/O, em `app/core/manutencao.py`.

**Tipo do Problema** — os `descricao` dos serviços, em português:

| Serviços | Saída |
|---|---|
| 1 | `Troca da placa mãe.` |
| 2 | `Troca de Pilha interna e Troca do Bluetooth Mercury.` |
| 3+ | `A, B e C.` |

**Resumo do Serviço** — os `resumo_padrao` dos serviços escolhidos, juntados na ordem, e **editável antes de gerar**.

O que fica gravado em `manutencoes.resumo` é o **texto final**, não a receita. Recompor na hora de imprimir faria a edição do catálogo reescrever relatórios antigos em silêncio, e relatório emitido é documento — não muda sozinho.

**Quando o técnico muda os serviços depois de já ter mexido no resumo:** o resumo é recomposto enquanto o texto ainda for exatamente a composição anterior. A partir do momento em que o técnico edita, mudar a seleção de serviços não sobrescreve mais o que ele escreveu — a tela avisa que o resumo não acompanha mais os serviços. Sem essa regra, acrescentar um serviço no fim apagaria um texto trabalhado.

## Geração do documento

Mesma construção do certificado de calibração: modelo HTML no banco com tokens `[campo]`, substituição por `preencher()`, PDF pelo Playwright.

### Modelo único

Um HTML de manutenção gravado em `certificados` com `equipamento` nulo, editável na tela de Modelos. Os três PDFs são idênticos entre si — só mudam marca, modelo e série, que são dados. Um modelo por aparelho seriam 17 cópias iguais e 17 lugares para corrigir a cada revisão da Qualidade.

A busca do modelo ganha fallback: sem modelo específico do aparelho, usa o genérico.

⚠️ **O fallback vale SÓ para o tipo `M`.** Já existe um registro com `equipamento` nulo do tipo `C` — o modelo "legado" mantido em julho. Um fallback para qualquer tipo faria todo aparelho sem modelo de calibração passar a gerar certificado com aquele modelo de teste, sem aviso. Para `C`, modelo por aparelho continua obrigatório e a falta continua sendo aviso na tela.

`CertificadoModelo.equipamento` está declarado `nullable=False` no modelo, mas a coluna aceita nulo no banco (o registro legado prova). O modelo passa a refletir o banco.

### Tokens

Reaproveitados: `[nomecli]`, `[cnpj]`, `[endcli]`, `[marca]`, `[serie]`, `[modelo]`, `[os]`, `[datacompra]`.

Novos, quatro:

```
[manutnumero]     número digitado
[manutdata]       data da manutenção
[manutproblema]   serviços compostos
[manutresumo]     resumo final
```

### `tipos_para` passa a respeitar o tipo de serviço

| `tipo_servico` | Documentos |
|---|---|
| `C` | só Calibração |
| `M` | só Manutenção |
| `A` | Calibração e Manutenção |
| vazio (OS antigas) | só Calibração |

Hoje `M` ainda pede o certificado de calibração, o que faria o técnico emitir um documento de calibração que não realizou. Os próprios PDFs registram que *"a calibração não é realizada de forma sistemática em todas as manutenções"*.

### O que já funciona sem código novo

- **PDF, download com escolha de pasta e link público assinado** — todos indexados por `(os, tipo)`, genéricos.
- **Card do TaskHS** — `espelhamento` busca todos os `OSCertificado` da OS e monta um link por tipo; `TIPO_SERVICO_LABEL` já traduz `M` para "Manutenção". Assim que o documento existir, o card mostra "Certificado de Manutenção: link" sozinho.

## Telas

### OS — duas seções no lugar de uma

A seção "Certificados" vira duas, uma abaixo da outra:

- **Certificado de calibração** — gerar, baixar, regerar
- **Certificado de manutenção** — gerar, baixar, regerar

Aparecem conforme o tipo de serviço da OS: `C` mostra só a primeira, `M` só a segunda, `A` mostra as duas. Deixa explícito qual documento está sendo feito e onde.

### Modal de manutenção

Espelha o modal de certificado. Abre com **todos** os campos:

- Cliente, CNPJ, endereço, marca, modelo, série e data de venda vêm preenchidos do cadastro; o que não existir vem vazio; **tudo é editável**, inclusive o que veio preenchido.
- Número, data, serviços (múltipla escolha do catálogo) e resumo são próprios da manutenção.

Os campos compartilhados gravam em `ordens.cert_overrides` — a mesma coluna do certificado de calibração —, então numa OS "Ambas" a correção de endereço feita num documento vale para o outro. Os campos próprios gravam em `manutencoes`.

### Endpoints

| Método e rota | O que faz |
|---|---|
| `GET /ordens/{id}/manutencao-campos` | devolve os campos já preenchidos, espelhando `certificado-campos` |
| `PUT /ordens/{id}/manutencao` | cria ou atualiza a manutenção da OS (idempotente pela unicidade em `os`) |
| `POST /ordens/{id}/gerar-certificado` | já existe; passa a gerar o tipo `M` quando o tipo de serviço pedir |
| `GET/POST/PUT/DELETE /manutencao-servicos` | o catálogo |

Gerar o relatório **exige a manutenção registrada** — sem número, data e ao menos um serviço, o endpoint recusa com 409 e mensagem explícita, no mesmo padrão da recusa por falta de modelo. Documento em branco não deve sair.

### Cadastros — Serviços de manutenção

Painel novo em Cadastros, ao lado de Categorias, Equipamentos e Fases. Lista descrição, resumo padrão e ativo.

## Permissões

| Ação | Quem | Quando |
|---|---|---|
| Registrar/editar manutenção | Laboratório, Administrador | fases 5–8 |
| Gerar/regerar o relatório | Laboratório, Administrador | fases 5–8 |
| Cadastrar/editar serviço | Laboratório, Administrador | sempre |
| Excluir serviço | Administrador | sempre |

A janela 5–8 é a mesma do certificado de calibração, que permite regerar OS antiga sob demanda. Excluir só com Administrador espelha a decisão dos cilindros de gás (03/08/2026): quem opera não deve apagar sem querer.

As regras vivem em `app/api/deps.py` (backend) e `frontend/src/auth/roles.ts` (espelho) — os dois lados sempre juntos.

## Testes

**Backend, núcleo puro:**
- "Tipo do Problema" com 1, 2 e 3+ serviços
- composição do resumo a partir dos `resumo_padrao`, na ordem escolhida
- `tipos_para` nos quatro casos: `C`, `M`, `A`, vazio

**Backend, integração:**
- fallback do modelo genérico vale para `M` **e não** para `C` — o registro legado não pode virar padrão de calibração
- permissão por função e por fase (403 e 409)
- uma manutenção por OS: a segunda tentativa atualiza, não duplica
- gerar sem manutenção registrada recusa com 409, e não cria `os_certificados` pela metade
- gerar grava `os_certificados` com `tipo="M"` e não toca no `C`

**Frontend:**
- as duas seções aparecendo conforme `tipo_servico`
- modal preenchendo do cadastro e aceitando edição
- resumo composto ao escolher serviços, e preservado quando editado à mão

## Fora de escopo

- Geração automática do número (decidido: digitado)
- Peças substituídas como cadastro próprio — os "Comentários" fixos já cobrem a política, e nenhum dos exemplos lista peças
- Manutenção sem OS — os três exemplos têm OS; entra quando houver atendimento em campo
- Estatística de defeitos por aparelho — o catálogo fechado deixa o dado pronto, mas a tela é outro trabalho

## Notas relacionadas

- [Certificado EPS-LAB-002](2026-07-31-certificado-eps-lab-002-design.md) — o motor de certificado que este trabalho reaproveita
- [QR dos certificados auxiliares](2026-08-03-qr-certificados-auxiliares-design.md) — link público e card do TaskHS
