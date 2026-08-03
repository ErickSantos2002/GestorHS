# Certificado de calibração EPS-LAB-002 (com cálculo de incerteza) — Design

**Data:** 2026-07-31
**Área:** backend (`core/certificado_calculo.py` novo, `core/certificado_gerar.py`, `api/certificados_os.py`, `api/certificados_config.py` novo, `models/`, migração `0024`) + frontend (`app/certificados/`, `app/ordens/`) + testes.
**Tipo:** feature nova com migração. Escopo: **todos os aparelhos**.
**Origem:** `docs/Certificado Iblow.xlsx`, enviada pelo setor de Qualidade.

## Problema

A Qualidade definiu um novo formato de certificado de calibração — documento **EPS-LAB-002, Revisão 02**, duas páginas — que passa a valer para todos os aparelhos. O modelo atual do GestorHS não dá conta de três coisas:

1. **Cinco medições** em vez de três. A OS tem `calib_teste1/2/3`; o novo formato pede `Test 1..Test 5`.
2. **Cálculos metrológicos** que hoje não existem em lugar nenhum: erro por medição, desvio padrão, incerteza combinada (`uc`) e incerteza expandida (`U`) com fator de abrangência k = 2.
3. **Rastreabilidade do padrão** — nº do cilindro de gás, nº do certificado do cilindro e concentração ± incerteza. Nenhum desses dados existe no sistema.

Além disso o documento traz seções novas de texto (método, equipamentos auxiliares, notas metrológicas, garantia) e um técnico responsável assinando, que a OS também não guarda.

## O que a planilha define

### Aba `CERTIFICADO` — o layout

| Seção | Conteúdo | Situação no GestorHS |
|---|---|---|
| 1 – Dados do solicitante | cliente, CNPJ, endereço | já existe (`nomecli`, `cnpj`, `endcli`) |
| 2 – Instrumento calibrado | série, data de venda, OS, data calibração, equipamento, marca, modelo, situação | já existe |
| 3 – Identificação da calibração | data recebimento, local, endereço do laboratório | `dataentr` existe; local/endereço são texto fixo |
| 4 – Condições ambientais | temperatura, pressão, margem padrão (20 ºC ~ 24 ºC) | `calibtemp`/`calibpressao` existem; margem é nova |
| 5 – Método | FLX-LAB-002 / INMETRO NIT-SEFIQ-018 rev 05 | texto fixo no HTML |
| 6 – Comentários e garantia | bloco de texto longo | texto fixo no HTML |
| 7 – Equipamentos auxiliares | TESTO 622, série 39533693, certificados 95239/1, 95239/2, LV06079-33193-22-R0 | **novo** |
| 8 – Padrões utilizados | 100 µmol/mol; certificado 202231419; cilindro CC747704; concentração 100,1 ± 2,00 | **novo** |
| 9 – Resultados | técnico, data, série, cliente, pressão, temperatura, **5 medições**, erro por medição, U, k = 2, limites 0,15 / 0,19 | **novo** (exceto data/série/cliente) |
| Notas | 5 notas metrológicas (GUM, rastreabilidade RBC/Inmetro) | texto fixo no HTML |
| Assinatura | Walbert Santos — Técnico em Metrologia | **novo** |

### Aba `BASE DE CALCULO` — a matemática

```
erro(i)     = medicao(i) − valor_referencia          # valor_referencia = 0,1 na planilha
media       = AVERAGE(medicoes)
u_medicao   = STDEV(medicoes)                        # desvio padrão AMOSTRAL (n−1)
u_i         = componente(i) / sqrt(3)                # distribuição retangular
uc          = sqrt( u_medicao² + Σ u_i² )
U           = uc × k                                 # k = 2, ~95% de confiança
```

Componentes de incerteza da planilha:

| Componente | Valor | Contribuição |
|---|---|---|
| Resolução do instrumento | 0,1 | 0,05773502691896258 |
| Incerteza do padrão de referência ºC | 0,052 | 0,03002221399786054 |
| Resolução do instrumento (pressão) | *vazio* | 0 |
| Incerteza do padrão de referência hPa | *vazio* | 0 |

**Caso de referência da planilha** — 5 medições de 0,16, referência 0,1:
erro = 0,06 em todas · `u_medicao` = 0 · `uc` = **0,06507431649019962** · `U` = **0,13014863298039925**.

Esse é o teste de aceitação do módulo de cálculo.

### Pontos levantados para a Qualidade (não bloqueiam a implementação)

Todos os números moram na Configuração, editáveis pelo Administrador — então a implementação não depende das respostas. Ficam registrados porque, se entrarem errados, viram documento errado na mão do cliente:

1. **`valor_referencia = 0,1`** parece inconsistente com o resto da planilha. O cilindro é 100,1 µmol/mol (≈ 0,17 mg/L), os limites impressos são 0,15–0,19 e a medição do exemplo é 0,16 — mas o erro é calculado contra 0,1, resultando em 0,06 (erro de ~37 % num aparelho aprovado). Ou o valor deveria ser ≈ 0,17, ou o campo "erro" não significa o que o nome sugere.
2. **`U = 0,1301` é maior que a largura da faixa de tolerância** (0,19 − 0,15 = 0,04). Metrologicamente isso inviabilizaria qualquer declaração de conformidade. Vem de `resolucao_instrumento = 0,1`; convém confirmar se a resolução do iBlow10 é 0,1 mg/L ou 0,01.
3. **`B2 = 0,2002` ("Incerteza do padrão de referência")** está na planilha mas não entra em nenhuma fórmula. As linhas de pressão (`B12`/`B13`) estão vazias — confirmar se serão preenchidas ou são placeholders.

## Design

### 1. `certificado_config` — a aba Configurações (linha única)

Tabela nova, **singleton**: uma linha, sem listagem. Guarda tudo que é global do laboratório.

| Campo | Tipo | Valor inicial (da planilha) |
|---|---|---|
| `valor_referencia` | Numeric(10,4) | 0,1 |
| `limite_minimo` | Numeric(10,4) | 0,15 |
| `limite_maximo` | Numeric(10,4) | 0,19 |
| `resolucao_instrumento` | Numeric(10,4) | 0,1 |
| `incerteza_padrao_temp` | Numeric(10,4) | 0,052 |
| `resolucao_pressao` | Numeric(10,4), nulo | *vazio* |
| `incerteza_padrao_pressao` | Numeric(10,4), nulo | *vazio* |
| `fator_k` | Numeric(4,2) | 2 |
| `tecnico_nome` | String(100) | Walbert Santos |
| `tecnico_cargo` | String(100) | Técnico em Metrologia |
| `equipamentos_auxiliares` | Text | TESTO 622 … (seção 7 completa) |
| `margem_temperatura` | String(50) | 20 ºC ~ 24 ºC |

`equipamentos_auxiliares` e `margem_temperatura` ficam aqui — e não no HTML do modelo — porque mudam sozinhas: o TESTO 622 é recalibrado periodicamente e os nºs de certificado mudam. Com um template por aparelho, deixá-las no HTML significa reeditar todos os modelos a cada recalibração do termo-higrômetro.

`tecnico_nome`/`tecnico_cargo` são fixos aqui por decisão do Erick (não vêm do usuário logado).

### 2. `certificado_padrao` — os cilindros de gás, com vigência

| Campo | Tipo |
|---|---|
| `id` | Integer PK |
| `numero_cilindro` | String(50) — ex. `CC747704` |
| `numero_certificado` | String(50) — ex. `202231419` |
| `concentracao` | Numeric(10,4) — ex. 100,1 |
| `incerteza_concentracao` | Numeric(10,4) — ex. 2,00 |
| `unidade` | String(20) — ex. `µmol/mol` |
| `vigencia_inicio` | Date |
| `vigencia_fim` | Date, nulo = vigente |
| `ativo` | Boolean |

Resolução do padrão: dada uma data, retorna o registro `ativo` cuja vigência contém a data (`vigencia_inicio <= data` e `vigencia_fim` nulo ou `>= data`). Sem correspondência → `None`, sem erro.

### 3. Colunas novas em `ordens`

- `calib_teste4`, `calib_teste5` — `String(50)`, iguais às três existentes. Colunas simples em vez de JSON porque o número de medições foi fixado em 5 para todos os aparelhos.
- `padrao_id` — FK para `certificado_padrao`, nulo.

**E também em `equipamentos_cliente`:** `calib_teste4`, `calib_teste5`. Ao concluir o laboratório, os resultados são espelhados no registro da frota do cliente (`_CAMPOS_CALIB` em `api/ordens_acoes.py`). Sem as duas colunas lá, a frota ficaria com 3 das 5 medições e o histórico do aparelho divergiria do certificado emitido.

**Não vão para o banco:** erro, média, `uc` e `U`. São derivados, recalculados na geração e congelados no `os_certificados.html`, que já é o snapshot do documento emitido. Persistir valor calculado criaria uma segunda verdade capaz de divergir da fórmula.

**Trade-off assumido:** `padrao_id` fica gravado na OS, então regerar um certificado antigo mantém o cilindro correto. Os parâmetros da Configuração **não são versionados** — se a Qualidade alterar a resolução e alguém regerar uma OS antiga, a incerteza sai com o valor novo. Versionar a config é possível depois; é cedo para pagar esse custo agora.

### 4. `core/certificado_calculo.py` — módulo puro

Sem I/O, sem `Session` — segue `os_workflow.py` e `calibracao.py`. Recebe as medições e os parâmetros, devolve os resultados.

Três detalhes que a planilha esconde e o código trata de propósito:

- **`STDEV` do Excel é amostral (n−1).** `statistics.stdev`, não `pstdev`. Com 0 ou 1 medição, `statistics.stdev` levanta exceção — retornar `0` nesses casos, que é o que o Excel faz com célula vazia.
- **Componente vazio contribui 0**, não erro. `B12`/`B13` entram como zero na `SUMSQ`.
- **Arredondamento só na apresentação.** O cálculo roda com precisão cheia; a formatação para o HTML é o último passo. Arredondar no meio altera o `U` na terceira casa.

Medições em branco (OS antiga com 3 valores) são **ignoradas** no cálculo, não tratadas como zero — e o erro correspondente sai em branco no certificado, não como `-0,1`. Média, `u_medicao` e `U` são calculados sobre as medições que existirem.

### 5. Endpoint de prévia — uma fórmula, um lugar

`POST /certificados/calculo-previa` recebe a lista de medições e devolve erro por medição, média, `uc` e `U`, usando a Configuração vigente.

Existe para que o modal mostre os valores ao vivo **sem reimplementar a fórmula em TypeScript**. Duplicar o cálculo no frontend é o caminho para a tela exibir um `U` e o PDF sair com outro.

### 6. Tokens novos em `certificado_gerar.py`

Adicionados a `CAMPOS` e emitidos por `_montar_contexto` — a fonte única das chaves, que é o que impede um `[token]` de sair literal no PDF:

`calibteste4` · `calibteste5` · `erro1`…`erro5` · `mediamedicoes` · `incertezaexpandida` · `fatork` · `drygasppm` · `limitemin` · `limitemax` · `padraocilindro` · `padraocertificado` · `padraoconcentracao` · `padraoincerteza` · `tecnico` · `tecnicocargo` · `equipamentosauxiliares` · `margemtemp`

Origem dos que não são óbvios:

| Token | Origem |
|---|---|
| `drygasppm` | `certificado_padrao.concentracao` — na planilha, `A82` é `=$D$72`, ou seja o mesmo valor da seção 8 |
| `padraoconcentracao` / `padraoincerteza` | `concentracao` e `incerteza_concentracao` do padrão vigente na OS |
| `limitemin` / `limitemax` | `certificado_config.limite_minimo` / `limite_maximo` |
| `fatork` | `certificado_config.fator_k` |
| `mediamedicoes` | média calculada — distinto de `calibtestemedia`, que é o campo digitado hoje e continua existindo |

Os outros três caminhos que passam por `_montar_contexto` — `montar_contexto_avulso`, `montar_contexto_venda` e o certificado geral — recebem as mesmas chaves vazias. Nenhum deles tem medição de calibração, então saem em branco, que é o comportamento correto.

**A lista de tokens é duplicada no frontend.** `CAMPOS_CERTIFICADO`, em `frontend/src/app/certificados/api.ts`, alimenta a paleta do editor em Certificados › Modelos e espelha à mão o `CAMPOS` do backend. Token que entrar só no backend existe no motor mas fica **invisível** para quem monta o modelo — as duas listas têm de ser atualizadas juntas.

### 7. Frontend — aba Configurações

Nova aba em `CertificadosPage.tsx`, ao lado de Modelos / Imagens / Avulsos / Gerais. Duas partes:

1. **Parâmetros** — form único com os campos da `certificado_config`. Sem listagem: é linha única.
2. **Padrões (cilindros)** — tabela dos cilindros cadastrados, indicando o vigente. Cadastrar um novo é o que se faz quando o gás troca.

**Acesso: Administrador apenas**, nos dois lados — `require_funcao("Administrador")` no backend e a regra correspondente em `auth/roles.ts`. São os números que definem a incerteza de todo certificado emitido; não é operação diária de laboratório.

### 8. Frontend — modal de gerar certificado

Em `app/certificados/CamposCertificado.tsx`:

- Os 3 campos de medição passam a **5**.
- Medição fora de `[limite_minimo, limite_maximo]` fica **destacada em vermelho com aviso**, e o botão Gerar **continua liberado** — o certificado de um aparelho reprovado também precisa ser emitido. Bloquear criaria um beco sem saída no laboratório.
- Painel read-only abaixo das medições: erro de cada uma, média e `U` com o `k`, vindos do endpoint de prévia.
- Linha exibindo o **cilindro vigente** que será gravado (nº, certificado, concentração), sem edição.

### 9. Geração e OS antigas

Ao gerar, o backend resolve o padrão vigente na `data_calibracao` da OS e grava `padrao_id`.

**OS antigas geram com o que têm, campos faltantes em branco.** Uma OS de 2024 tem 3 medições e nenhum cilindro cadastrado para aquela data: as medições 4 e 5 e os campos do padrão saem vazios. O sistema não preenche com a configuração ou o cilindro atuais — isso afirmaria que um aparelho calibrado em 2024 usou o cilindro de 2026, uma rastreabilidade falsa num documento da Qualidade. Também não bloqueia a regeração, para não deixar sem 2ª via o cliente que pedir uma calibração antiga.

O cálculo de `U` para uma OS antiga usa as medições que existirem.

### 10. Migração `0024_certificado_config_padroes.py`

- Cria `certificado_config` e `certificado_padrao`.
- Adiciona `calib_teste4`, `calib_teste5` e `padrao_id` em `ordens`.
- Insere a linha única de `certificado_config` com os valores da planilha como ponto de partida.

Não insere cilindro nenhum: o `CC747704` é cadastrado pela tela, com a vigência que a Qualidade informar.

## Testes

| Onde | O quê |
|---|---|
| `test_certificado_calculo.py` | o caso da planilha batendo casa por casa (`uc` = 0,06507431649019962, `U` = 0,13014863298039925); stdev com 0 e 1 medição; componente vazio contribuindo 0; medição em branco ignorada |
| `test_certificado_config.py` | singleton (não cria segunda linha); leitura e escrita; 403 para não-Administrador |
| `test_certificado_padrao.py` | resolução por vigência; data sem padrão → `None`; padrão inativo ignorado |
| `test_certificados_os.py` (ampliado) | OS antiga com 3 medições gera com os campos novos vazios; OS nova grava `padrao_id`; todos os tokens novos presentes no contexto (nenhum `[token]` literal no HTML) |
| frontend | destaque de medição fora de faixa com o botão Gerar ainda habilitado; prévia renderizando o `U` devolvido pelo backend |

## Fora de escopo

- **Certificado de Manutenção (tipo `M`)** não muda — a planilha trata só de calibração.
- **O HTML EPS-LAB-002 em si** é conteúdo da Qualidade. A implementação entrega os tokens e monta o template do iBlow10 como referência; colar o novo layout nos demais aparelhos é trabalho de cadastro, não de código.
- **Versionamento dos parâmetros de configuração** — ver o trade-off na seção 3.

## Consequência conhecida da decisão de manter um modelo por aparelho

O Erick optou por manter a estrutura atual (`certificados`: um HTML por aparelho + tipo) em vez de um modelo único compartilhado. Isso significa que **toda revisão do documento pela Qualidade** (Revisão 03 e seguintes) exige reeditar o template de cada aparelho, e os modelos tendem a divergir com o tempo. Fica registrado como custo aceito, não como problema a resolver agora.
