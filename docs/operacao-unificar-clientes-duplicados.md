# Operação — cadastro de cliente duplicado

O mesmo CNPJ cadastrado duas vezes. A frota do cliente fica partida entre os dois
cadastros: a tela mostra cinco aparelhos quando ele tem dez, o alerta de vencimento sai
pela metade e o portal do cliente esconde metade do histórico dele.

Aconteceu com a **FERTILIZANTES TOCANTINS** (`05.571.228/0011-27`, ids 1059 e 1064) em
08/09/2026, com a **ROYAL FIC** (`01.349.764/0016-36`, ids 528 e 1581) e com a **CMOC
BRASIL** (`26.108.898/0007-03`, ids 138 e 1186) em 09/09/2026. Um rollback do banco desfez
essas três, e a Royal FIC voltou a aparecer como "quarto caso" — foi o sinal de que o
problema era comum, e em **11/09/2026 os 17 pares da base foram unificados de uma vez**
(ver [a rodada de 11/09](#a-rodada-de-11092026-todos-de-uma-vez)). Restam **0**, mas
cadastro novo duplicado continua nascendo: rode a consulta abaixo de vez em quando.

## Duplicado não é filial

Matriz e filial têm CNPJs **diferentes** — mesma raiz de oito dígitos, ordem diferente. A
Fertilizantes Tocantins tem **sete** cadastros com a raiz `05571228` (TO, MA, PA, MT, MG)
e todos são clientes legítimos; só o `0011-27` estava repetido.

**Compare o CNPJ inteiro, nunca a raiz.** Unificar por raiz juntaria unidades que pedem
calibração separado, emitem nota separado e recebem a caixa em endereços diferentes.

Para achar os pares de verdade:

```sql
SELECT cgc, count(*), string_agg(id::text, ',' ORDER BY id), min(nome)
FROM clientes WHERE coalesce(cgc,'') <> ''
GROUP BY cgc HAVING count(*) > 1 ORDER BY 2 DESC;
```

## O procedimento

```bash
cd ~/github/GestorHS/backend && source .venv/bin/activate

python -m app.scripts.unificar_clientes --cgc 05571228001127                         # simula
python -m app.scripts.unificar_clientes --cgc 05571228001127 --renumerar-patrimonios --aplicar
```

Sem `--aplicar` ele só descreve o plano. Um par por rodada; para escolher o sobrevivente
à mão, `--manter 1059 --absorver 1064`.

### Quem sobrevive

Decidido por peso, nesta ordem: **caixa viva**, depois **número de OS**, depois **id
menor**.

Caixa pesa mais porque caixa em andamento já é um card publicado no TaskHS e no GrowthHS
**pelo id do cliente**. Mover o cliente principal de uma caixa que a expedição está
olhando agora troca o dado embaixo do card. OS antiga é histórico — ninguém está com ela
na mão. No caso da Fertilizantes, o 1059 tinha a caixa 649 no Laboratório e ficou, mesmo
com os dois cadastros sendo idênticos campo a campo.

### O que o script move

**Treze colunas** apontam para `clientes.id`:

```
caixas.cliente_principal          ordens.cliente
equipamentos_cliente.cliente      propostas.cliente
fotos.cliente                     solicitacoes.cliente
funcionarios.cliente              transferencias_equipamento.de_cliente
mensagens.cliente                 transferencias_equipamento.para_cliente
testes.cliente                    usuarios_cliente.cliente
testes_detalhes.cliente
```

`mensagens`, `testes` e `testes_detalhes` são **legadas** do sistema antigo: têm FK de
verdade no Postgres mas não têm model no GestorHS, e por isso nem existem no SQLite dos
testes. O script pula o que não existe.

⚠️ **Levante FK sempre por `pg_constraint`.** Uma consulta ao `information_schema`
juntando `constraint_column_usage` devolve vazio aqui e dá a falsa impressão de que não
existe FK nenhuma. O script refaz esse levantamento no banco real a cada rodada e
**recusa** se achar coluna fora da lista dele — é a rede contra uma tabela nova.

O cadastro absorvido é **apagado**, não desativado: um cliente inativo com CNPJ igual ao
ativo é exatamente a ambiguidade que se está tirando do caminho. Nada se perde — tudo é
reapontado antes do `DELETE`.

### Quando ele recusa

Nada é gravado se:

- os dois cadastros **divergem** em algum campo (`--aceitar-divergencia` manda ficar com
  os do sobrevivente, e a divergência aparece no plano);
- os dois têm usuário de portal com o **mesmo login** — a única de `usuarios_cliente` é
  `(cliente, login)` e só estouraria no meio do `UPDATE`, com metade das linhas movidas;
- o banco tem FK para `clientes` fora de `REFERENCIAS`.

Espere recusa por divergência nos pares que sobraram: os dois cadastros da Fertilizantes
eram byte a byte iguais, mas isso é a exceção, não a regra. Divergência não quer dizer
"não unifique" — quer dizer **confira se é mesmo o mesmo cliente** antes.

### O segundo caso: divergência que não é dúvida

A ROYAL FIC recusou de primeira — o `528` (2019) tinha contato, telefones e obs; o `1581`
(2024) só tinha um e-mail diferente. Mesmo nome, mesmo CNPJ, mesmo endereço: um cadastro
novo aberto sem ninguém ver que o cliente já existia. O `528` ficou pela regra do número
de OS (15 contra 1) — nenhum dos dois tinha caixa, e todas as OS estavam finalizadas.

`--aceitar-divergencia` fica com os campos do sobrevivente, então a única informação que
sumiria era o e-mail do cadastro novo. **Divergência assim resolve-se fora do script:**
antes de aplicar, decida onde o dado do absorvido vai parar. Aqui o e-mail foi anotado na
obs do `528` depois da unificação — o script não tem por que adivinhar isso.

Do lado da frota, o aparelho absorvido (`166971`) tinha patrimônio 1 igual ao 1136 do
sobrevivente e virou **8**, continuando do maior ocupado.

### O terceiro caso: a caixa viva era de outra filial

A CMOC BRASIL tem **três** cadastros na raiz `26108898` — `...000452` (#866), `...000533`
(#1091) e o `...000703`, este último repetido nos ids `138` (2020) e `1186` (2022). Só o
par do `0007-03` era duplicidade; as outras duas são filiais de verdade e mandam aparelho
na mesma caixa.

Nenhum dos dois tinha caixa **como `cliente_principal`**, mas os dois tinham OS na caixa
**993**, viva no Pós-Vendas, cujo principal é o `#866`. Isso é seguro: o card do TaskHS é
chaveado pela caixa e o principal dela não mudou. **Confira o principal da caixa antes de
aplicar** — se ele fosse o cadastro absorvido, o card publicado passaria a apontar para um
id apagado.

O `138` ficou pela regra do número de OS (25 contra 9) — que aqui também é o id menor. A
divergência era de contato: o `138` trazia "Marcela Dias Carlos De Jesus" com um e-mail de
outra pessoa (`iramaia.barreto@`) e um telefone de DDD 13; o `1186`, "Rick"
(`rick.santos@`) com celular de DDD 62, que é o de Catalão/GO, onde fica o endereço. Como
na ROYAL FIC, o contato do absorvido foi **anotado na obs do sobrevivente** em vez de
descartado — a obs do `138` estava vazia.

Do lado da frota, os quatro aparelhos absorvidos tinham patrimônio 1–4 contra os 1–15 do
sobrevivente e viraram **16–19**.

## A rodada de 11/09/2026: todos de uma vez

Os 17 pares foram simulados juntos, sem nenhuma recusa (nem login de portal repetido, nem FK
fora da lista), e gravados **um por transação**, com um `.sql` de rollback por par em
`~/projetos/gestorhs-operacoes/rollback-unificacao-<fica>-<vai>-2026-09-11.sql` gerado
antes de aplicar. O sobrevivente saiu da regra de sempre em todos os pares.

**A regra da divergência virou padrão:** antes de apagar, o que o absorvido perderia é
anotado na obs do sobrevivente, num bloco `--- Do cadastro #X (unificado em 11/09/2026) ---`
com razão social, endereço, contato, e-mail, telefones e as linhas de obs que o sobrevivente
não tinha. Diferença só de grafia (caixa alta, acento, pontuação, um valor truncado do
outro) é descartada. Três pares tinham divergência de identidade, e foram unificados mesmo
assim porque CNPJ inteiro igual é a mesma pessoa jurídica: Consita ← "SUMA BRASIL" (mesmo
grupo, outro endereço em BH), Madero ← outro endereço em Ponta Grossa e Aço Verde ← "Gusa
Nordeste S/A", a razão social antiga.

**Caixa viva dos dois lados.** Na Rumo (697 ← 1108) e na Univale (788 ← 789) os dois
cadastros tinham caixa em andamento, então uma delas mudou de `cliente_principal` de
qualquer jeito: **978** (Laboratório) e **980** (Pós-Vendas). O card do TaskHS dessas duas
precisa de `sincronizar_taskhs_caixas --caixas 978,980 --aplicar`, rodado **dentro do
container** — o `.env` local aponta para o TaskHS de desenvolvimento.

⚠️ **O mesmo aparelho pode estar nos dois cadastros.** Na Aço Verde, cinco bafômetros do
`#617` tinham a **mesma série** dos patrimônios 1–5 do `#1538`: o cadastro novo tinha
recadastrado a frota em vez de herdar. Depois da junção a frota mostrava os cinco em dobro,
e as linhas velhas (0 OS, próxima calibração parada em 2024) acusavam vencido no alerta.
As cinco foram mescladas nas linhas com OS — só `documentos_equipamento_cliente` apontava
para elas — e apagadas, com rollback em
`rollback-mesclar-aparelhos-aco-verde-2026-09-11.sql`. Nos outros 16 pares não houve série
repetida. **Depois de unificar, confira:**

```sql
SELECT cliente, upper(trim(serie)), count(*) FROM equipamentos_cliente
WHERE coalesce(trim(serie),'') <> '' GROUP BY 1, 2 HAVING count(*) > 1;
```

Em 11/09/2026 ela devolvia **dois casos antigos**, sem relação com a unificação: `F000856`
na HS LTDA (#2, com OS nas duas linhas) e `TBK8S0109` na SALUM CONSTRUÇÕES (#794, uma linha
com 0 OS e calibração parada em 2022). Ficaram como estavam.

`equipamentos_cliente` tem **dez** FKs apontando para ela (`ordens`, `historico_equipamentos`,
`documentos_equipamento_cliente`, `transferencias_equipamento`, `proposta_aparelhos`,
`solicitacoes`, `certificados_venda`, `testes_detalhes` e as duas de `instalacoes_modulo`).
Levante por `pg_constraint` antes de apagar qualquer linha.

Na mesma frota, a renumeração levou os absorvidos para **371–377**, não para 8 em diante:
os patrimônios 50–55 e 366–370 são **Módulos de Calibração Phoebus** (equipamento 47) e o
script continua do maior ocupado, como manda a regra.

## O patrimônio depois da junção

As duas numerações começavam em 1, então o cliente unificado fica com dois aparelhos "1",
dois "2" e assim por diante. `--renumerar-patrimonios` resolve no mesmo passo; para um
cliente já unificado sem a flag, o conserto é:

```bash
python -m app.scripts.renumerar_patrimonios --cliente 1059 --aparelhos 4153,5067,5068,5699,6824
```

`--aparelhos` são os ids de `equipamentos_cliente` que **cedem** o número — os que vieram
do cadastro absorvido. Quem não está na lista nunca anda: a etiqueta que o cliente já
conhece no cadastro que fica não muda. Sem a lista, cede quem entrou depois (id maior).

A numeração nova continua do **maior ocupado** e não preenche buraco — reusar um número
aposentado confundiria quem conhece a etiqueta antiga. Na Fertilizantes: 1–5 ficaram
parados e os cinco absorvidos viraram 6–10.

Valor **não numérico fica intocado**. Em 203 aparelhos da base o campo virou recado
(`SEM CONSERTO`, uma data) — renumerar isso apagaria a informação.

⚠️ **Repetição de patrimônio não é sinal de duplicidade.** 83 clientes já tinham o número
repetido dentro da própria frota antes de qualquer unificação. Renumerar é limpeza local:
faça no cliente que você acabou de unificar, não numa varredura geral.

`patrimonio` sai no certificado pelo token `[patrimonio]`, mas documento já emitido fica
congelado em `os_certificados` — renumerar **não** reescreve o passado.

## O que fica de fora

- **GrowthHS.** Os cards são chaveados por `{cliente_id}:{...}`. Card já criado com o id
  do cadastro absorvido continua lá, órfão, e o GrowthHS não expõe leitura para o script
  detectar isso. Os próximos nascem com o id do sobrevivente.
- **TaskHS.** O card é da **caixa**, não do cliente, então unificar não mexe nele. Só
  encoste em `sincronizar_taskhs_caixas` se a caixa tiver mudado de cliente principal —
  o que não acontece quando o sobrevivente é escolhido pela regra da caixa viva, **a menos
  que os dois cadastros tenham caixa viva** (Rumo e Univale em 11/09).
- **Rollback.** Não existe automático. Antes de aplicar, guarde o `INSERT` do cadastro que
  vai sumir e os ids das linhas que vão mudar de dono; desfazer é recriar a linha e rodar
  o `UPDATE` inverso.

## Ver também

[operacao-growthhs-job-mensal.md](operacao-growthhs-job-mensal.md) — o job que dispara
pelos vencimentos e que enxergava metade da frota enquanto o cadastro estava partido.
