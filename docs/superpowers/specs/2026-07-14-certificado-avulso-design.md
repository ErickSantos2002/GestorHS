# Certificado avulso ("em branco")

**Data:** 2026-07-14
**Status:** aprovado (brainstorming)

## Objetivo

Permitir que o **Laboratório** emita um certificado **sem OS, sem cliente e sem
aparelho cadastrados**. O caso real: aparelhos que saem para **POC** — a empresa e o
equipamento não existem no sistema, mas o certificado precisa ser entregue.

O laboratório escolhe um **template** de certificado já cadastrado, digita os dados
(cliente, aparelho, calibração) e gera o PDF. O certificado fica **registrado** no
sistema, mas **sem vínculo com nenhuma empresa ou aparelho**.

## ⚠️ Cuidado de nomenclatura (dois "modelos")

- **Modelo de certificado** (`CertificadoModelo`) = o **template HTML**, cadastrado
  por aparelho + tipo, na aba "Modelos".
- **`[modelo]`** = um **token** do certificado, que significa "modelo do equipamento"
  (texto livre digitado).

No certificado avulso o laboratório **escolhe um template** (de um aparelho que já
tem um cadastrado) e **digita** o modelo/marca/série do aparelho da POC. São coisas
independentes.

## Decisões (aprovadas)

- O avulso **é persistido** (há registro de que foi emitido, por quem e quando) —
  é um documento de calibração entregue a um cliente.
- O formulário tem **os 17 campos que o laboratório já preenche hoje**, **mais 2**
  (ver abaixo) = **19 campos**.
- Permissão para gerar: **Laboratório** ou **Administrador** (igual à geração da OS).

### Os 2 campos extras (`os` e `dataentr`) e seus defaults

Os **12 modelos reais imprimem `[os]` e `[dataentr]`** — e nenhum dos dois vem do
formulário atual (na OS eles saem da própria OS). Sem eles, o certificado avulso sairia
com esses campos **vazios no PDF impresso**. Então o formulário os inclui, **já
preenchidos** e **editáveis**:

| Campo | Default | Por quê |
|---|---|---|
| **Número da OS** (`os`) | **`XXXX`** | O aparelho de POC não tem OS; é o marcador que o laboratório já usa. |
| **Data de recebimento** (`dataentr`) | **hoje** | Na prática o pedido de compra chega no mesmo dia. |

Ambos podem ser alterados se o caso exigir.

## Backend

### Modelo — `app/models/certificado_avulso.py` (novo)

```python
class CertificadoAvulso(Base):
    __tablename__ = "certificados_avulsos"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(1), nullable=False)              # C / M — do template escolhido
    html = Column(Text, nullable=False)                   # o certificado preenchido (auto-contido)
    # Campos soltos apenas para a LISTAGEM/busca (o html ja e auto-contido):
    nomecli = Column(String(200), nullable=True)
    serie = Column(String(50), nullable=True)
    calib_cert = Column(String(50), nullable=True)        # n do certificado
    data_calibracao = Column(Date, nullable=True)
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)   # quem gerou
    data_geracao = Column(DateTime(timezone=True), nullable=True)
```

**Sem nenhuma FK para `clientes` ou `equipamentos_cliente`** — é exatamente o ponto
da feature. (A FK para `usuarios` é segura: usuários agora são desativados, nunca
excluídos.)

### Migração — `0014_certificado_avulso.py`
`down_revision = "0013_nota_fiscal"`. Cria a tabela; `downgrade` a remove.

### Núcleo puro — `app/core/certificado_gerar.py`

#### ⚠️ Fonte única do conjunto de chaves (evita o bug do "literal paralelo")

O contexto real **não tem 23 chaves — tem ~31**: os nomes de `CAMPOS`, os **nomes
legados** (`calibtemp`, `situcalib`, `datacali`, `dataentr`…, usados pelos 12 modelos
migrados) e os **aliases amigáveis** (`temperatura`, `situacao`, `media`…, para
modelos futuros).

**Copiar esse dicionário à mão na versão avulsa criaria duas listas paralelas que
inevitavelmente divergem** — exatamente o padrão que já causou três bugs neste
projeto (as fases, o filtro, o backfill). Então:

**Extrair um construtor compartilhado** (puro), que é a única definição do conjunto de
chaves:

```python
def _montar_contexto(*, nomecli, cnpj, endcli, modelo, marca, serie, patrimonio,
                     datacompra, os_num, calibcert, proxcalibragem, tipocalibragem,
                     datacali, dataentr, temp, pressao, t1, t2, t3, media, situ) -> dict[str, str]
```
- `montar_contexto(db, ordem)` (existente) passa a **extrair os valores da OS** e
  delegar para `_montar_contexto(...)`. **Comportamento idêntico** — os `cert_overrides`
  continuam sendo aplicados depois, como hoje (são específicos da OS).
- `montar_contexto_avulso(valores: dict)` (novo) pega os valores **digitados** e
  delega para o mesmo `_montar_contexto(...)`.

Assim, um token novo adicionado no futuro entra nos dois caminhos de uma vez.

**Não incluir `pulapagina` no contexto** (nem hoje ele está): `preencher()` já o trata
**fora do laço**, substituindo-o pela quebra de página **sem escapar** (é HTML
estrutural, não é dado). Se entrar no contexto como valor comum, seria escapado e a
quebra de página deixaria de funcionar.

#### Por que o conjunto completo de chaves importa (verificado, não suposto)

`preencher()` substitui **apenas as chaves presentes no contexto** — um token ausente
fica **literalmente escrito no PDF**. Comprovado rodando o código real:

```python
preencher("<p>[nomecli] / [proxcalibragem]</p>", {"nomecli": "ACME"})
# -> "<p>ACME / [proxcalibragem]</p>"   <-- o token VAZOU para o certificado
```

Daí a exigência do construtor compartilhado acima: ele garante que o avulso emita
**exatamente o mesmo conjunto de chaves** que o fluxo da OS.

Valores não informados viram `""`. Formatação: datas em `DD/MM/AAAA` (reusar `_fmt`);
`dataemissao` = hoje. No avulso, `proxcalibragem` e `tipocalibragem` saem vazios
(nenhum dos 12 modelos reais os usa).

`preencher()` e `html_para_pdf()` são reaproveitados **sem alteração** — o escape de
valores (proteção contra injeção de HTML/script no certificado) já vem de graça.

### Endpoints — `app/api/certificados_avulsos.py` (router novo, registrado em `main.py`)

- **`POST /certificados-avulsos`** — corpo: `equipamento` (o aparelho **do template**),
  `tipo` (`C`/`M`) e os 17 campos digitados.
  Permissão: `require_funcao("Laboratório", "Administrador")`.
  Busca o `CertificadoModelo(equipamento, tipo)`; **não existe → 409** com mensagem
  clara (mesmo padrão do fix recém-feito na OS). Preenche o HTML, grava o registro
  (com `usuario` = quem gerou e `data_geracao` = agora) e devolve o registro criado.

- **`GET /certificados-avulsos`** — lista para a tela (id, tipo, nomecli, serie,
  calib_cert, data_calibracao, data_geracao, nome de quem gerou), mais recentes
  primeiro. Qualquer usuário logado.

- **`GET /certificados-avulsos/{id}/pdf`** — renderiza o `html` guardado e devolve o
  PDF (`html_para_pdf`). Qualquer usuário logado. Inexistente → 404.

### Schemas — `app/schemas/certificado_avulso.py`
`CertificadoAvulsoIn` (equipamento, tipo + os 17 campos, todos opcionais exceto
`equipamento`/`tipo`) e `CertificadoAvulsoOut` (os campos da listagem +
`usuario_nome`).

## Frontend

### Página Certificados — terceira aba **"Em branco"**
A página hoje tem as abas **Modelos** e **Imagens** (`CertificadosPage.tsx`). Ganha
uma terceira, contendo:

- Botão **"Gerar certificado em branco"** (só para Laboratório/Admin) → abre o modal.
- **Lista** dos avulsos emitidos: nº do certificado, cliente, série, data da
  calibração, quem gerou, quando — com ação **Baixar PDF**.

### Modal `CertificadoAvulsoModal.tsx`
- **Seletor de template**: lista os `CertificadoModelo` existentes como
  `Aparelho — Calibração/Manutenção`.
- **Os mesmos 17 campos** do formulário que o laboratório já conhece, **todos vazios**:
  cliente (nome, CNPJ/CPF, endereço), aparelho (modelo, marca, série, patrimônio, data
  de compra) e calibração (nº do certificado, temperatura, pressão, testes 1/2/3 +
  média, situação, data da calibração).
- Ao salvar: chama o `POST`, fecha e recarrega a lista.

### `roles.ts`
`podeGerarCertificado(user)` = Admin ou função `Laboratório` (espelho do
`require_funcao` do backend). Reusar se já existir regra equivalente.

## Testes

- **`montar_contexto_avulso`** (puro): devolve **todas as 23 chaves de `CAMPOS`**;
  campos não informados viram `""`; datas formatadas `DD/MM/AAAA`; `dataemissao` = hoje.
- **Regressão de token**: o HTML gerado a partir de um template que usa **todos** os
  tokens **não contém nenhum `[token]` literal** (prova que nada vaza pro PDF).
- **Geração**: salva o registro com o HTML preenchido, `usuario` e `data_geracao`;
  os valores digitados aparecem no HTML; template inexistente → **409**.
- **Permissão**: Laboratório gera (200); Admin gera (200); Comercial → **403**.
- **Listagem**: devolve os avulsos, mais recentes primeiro, com o nome de quem gerou.
- **PDF**: baixa com `application/pdf`; id inexistente → 404.
- **Isolamento**: gerar um avulso **não cria nem altera** nenhuma OS, cliente ou
  equipamento (o ponto da feature).

## Aplicação em produção

1. `alembic upgrade head` (migração **0014** — só **cria uma tabela nova**;
   **retrocompatível**, não toca em nada existente).
2. Deploy normal (sem rebuild — nenhuma dependência nova).

## Fora de escopo

- Editar/regerar um avulso (basta gerar outro).
- Excluir um avulso.
- A reformulação do formulário de calibração (o Erick mencionou que virá depois).
- Vincular um avulso a uma OS/cliente posteriormente.
- Busca/filtro na lista de avulsos.
