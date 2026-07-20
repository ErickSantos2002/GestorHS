# Certificado de venda (primeiro certificado, sem OS)

**Data:** 2026-07-20
**Status:** aprovado (brainstorming)

## Objetivo

Emitir o **primeiro certificado da vida de um aparelho** — o certificado que acompanha
a **venda** — sem precisar abrir uma OS.

Hoje o certificado só nasce de dois lugares:

| Caminho | Vínculo | Onde |
|---|---|---|
| Dentro da OS | OS + cliente + aparelho | `POST /ordens/{id}/gerar-certificado` |
| Avulso ("em branco") | **nenhum** (feito para POC) | `POST /certificados-avulsos` |

Nenhum dos dois serve: o aparelho vendido **já está cadastrado na frota do cliente**,
mas ainda **não tem OS**. O certificado de venda é o terceiro caso — **vinculado ao
aparelho, sem OS**.

## ⚠️ Por que NÃO reusar `CertificadoAvulso`

Foi a alternativa mais tentadora (reusaria tabela, POST e endpoint de PDF), e foi
**descartada**. O docstring do modelo diz literalmente:

> *"Nao ha FK para clientes nem equipamentos_cliente — e exatamente o ponto da feature."*

O avulso existe para ser **sem vínculo**; o de venda **é vinculado**. São conceitos
opostos, e juntá-los na mesma tabela faria os certificados de venda vazarem para a aba
"Em branco" em `/certificados`. O reuso que interessa (`_montar_contexto`, `preencher`,
`html_para_pdf`, o JSX do modal) é obtido sem herdar essa ambiguidade.

Também foi descartado tornar `OSCertificado.os` nullable: o unique `(os, tipo)`, o JOIN
do card da frota, o download por OS e o portal todos assumem `os` não-nulo. Risco de
regressão alto no miolo do fluxo de OS, para ganho baixo.

## Decisões (aprovadas)

- O certificado de venda **é persistido e vinculado ao aparelho** da frota.
- Aparece no card **Certificados** da tela do aparelho **e no portal do cliente**.
- **Um por aparelho**, mas **regerável** — gerar de novo sobrescreve (corrige erro de
  digitação sem duplicar histórico).
- Tipo é sempre **Calibração** (`C`) — não há certificado de venda de manutenção.
- Permissão: **Laboratório** ou **Administrador** (igual à geração da OS).
- Situação default: **"Aparelho inicial"** (é o caso de um aparelho recém-vendido).

### O campo extra: "Próxima calibração"

O pedido original foi "exatamente igual ao modal da OS". Há **um desvio deliberado**.

`prox_calibragem` **não é calculada em lugar nenhum do sistema** — o laboratório digita
à mão no `AvancarModal`, e o modal de certificado da OS não tem esse campo (na OS o
valor já foi preenchido antes, ao avançar de fase).

Sem OS, não há esse "antes". Se o certificado de venda não gravar `prox_calibragem`, o
aparelho recém-vendido entra na frota como `sem_data` em `status_calibracao()` e
**nunca dispara alerta de calibração vencendo** — justamente o aparelho que mais
deveria estar no radar. Por isso o modal de venda inclui **"Próxima calibração"**.

## Backend

### Modelo — `app/models/certificado_venda.py` (novo)

```python
class CertificadoVenda(Base):
    """Primeiro certificado do aparelho, emitido na VENDA — sem OS.

    Diferente de CertificadoAvulso (que e sem vinculo nenhum, para POC), este e
    ancorado no aparelho da frota do cliente. Unique em equipamento_cliente: um por
    aparelho, regeravel por upsert.
    """
    __tablename__ = "certificados_venda"
    __table_args__ = (UniqueConstraint("equipamento_cliente",
                                       name="uq_certificados_venda_equip"),)

    id = Column(Integer, primary_key=True, index=True)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id"),
                                 nullable=False)
    html = Column(Text, nullable=False)          # certificado preenchido, auto-contido
    calib_cert = Column(String(50), nullable=True)      # para a listagem
    data_calibracao = Column(Date, nullable=True)       # para a listagem
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_geracao = Column(DateTime(timezone=True), nullable=True)
```

O `unique` garante "um por aparelho" **no banco**, não só na tela. `tipo` não é coluna:
é sempre `C`.

### Migração — `0017_certificado_venda.py`

`down_revision = "0016_instalacao_modulo"`. Cria a tabela; `downgrade` a remove.
Retrocompatível: só acrescenta tabela, não toca em nada existente.

### Contexto — `app/core/certificado_gerar.py`

Adicionar `montar_contexto_venda(db, ec, valores) -> dict[str, str]`, que **delega ao
mesmo `_montar_contexto`** usado pela OS e pelo avulso.

**Isto não é opcional.** `_montar_contexto` é a fonte única do conjunto de chaves, e
`preencher()` substitui **apenas as chaves presentes no contexto** — um token ausente
sai **literalmente escrito no PDF**:

```python
preencher("<p>[nomecli] / [proxcalibragem]</p>", {"nomecli": "ACME"})
# -> "<p>ACME / [proxcalibragem]</p>"   <-- vazou para o certificado
```

Montar um dicionário próprio criaria a terceira lista paralela — o padrão que já causou
bugs neste projeto. Origem dos valores:

| Token | Origem |
|---|---|
| `nomecli`, `cnpj`, `endcli` | cadastro do **cliente** dono do aparelho |
| `modelo`, `marca` | `modelo_marca(db, ec.equipamento)` — catálogo, nunca digitado |
| `serie`, `patrimonio`, `datacompra` | cadastro do **aparelho** (editáveis no modal) |
| `os_num` | **`"XXXX"`** — mesma convenção já usada no avulso |
| `dataentr` | `datacompra` do cadastro; se vazia, hoje |
| `proxcalibragem` | o campo novo do modal |
| calibração (`calibcert`, `datacali`, `temp`, `pressao`, `t1..t3`, `media`, `situ`) | digitados no modal |

### Espelhamento — `app/api/ordens_acoes.py`

`espelhar_calibracao(db, ordem)` hoje lê os campos **de uma OS**. Extrair o miolo para
uma função que aceita os **valores soltos** (`espelhar_calibracao_valores(db, ec,
valores, ult, prox)`); `espelhar_calibracao` passa a ser um wrapper que extrai da OS e
delega. **Comportamento idêntico** para o fluxo de OS.

O fluxo de venda chama a nova função. É o que grava `calib_*`, `ult_calibragem` e
`prox_calibragem` na frota — e é isso que faz o aparelho aparecer no **portal** e nos
**alertas**.

### Endpoints — `app/api/certificados_venda.py` (router novo, registrado em `main.py`)

Permissão de escrita: `require_funcao("Laboratório", "Administrador")`.

- **`GET /equipamentos-cliente/{id}/certificado-venda-campos`** — devolve os campos
  pré-preenchidos do cadastro (cliente + aparelho), `calib_situacao="Aparelho inicial"`,
  `data_calibracao=hoje`, e os valores já gravados se o certificado existir (caso de
  regeração). Qualquer usuário logado.

- **`POST /equipamentos-cliente/{id}/certificado-venda`** — gera.
  Busca `CertificadoModelo(equipamento=ec.equipamento, tipo="C")`; **não existe → 409**
  com mensagem clara (mesmo padrão da OS e do avulso). Preenche o HTML, faz **upsert**
  pelo unique (regerar sobrescreve `html`, `calib_cert`, `data_calibracao`, `usuario`,
  `data_geracao`), espelha na frota e devolve o registro.

- **`GET /equipamentos-cliente/{id}/certificado-venda/pdf`** — renderiza o `html`
  guardado via `html_para_pdf`. Qualquer usuário logado. Inexistente → 404.

### Card de certificados da frota — `app/api/equipamentos_cliente.py`

`GET /{item_id}/certificados` hoje devolve só `OSCertificado`, via JOIN com `Ordem`.
Passa a **unir as duas fontes**. `EquipCertItem` (`app/schemas/frota.py:107`) tem hoje
`os: int` não-nulo; passa a `os: int | None` (nulo no de venda) e ganha
`origem: "os" | "venda"`, para o front montar o link e o rótulo.

Ordenação: o de venda vem **por último** na lista, mantendo a ordem atual (OS mais
recente primeiro) — ele é cronologicamente o primeiro da vida do aparelho, então fica
no fim da lista decrescente.

### Portal — `app/api/portal.py`

Dois ajustes, ambos necessários para o cliente conseguir baixar:

1. **`GET /portal/certificados`** — a listagem filtra por
   `EquipamentoCliente.calib_cert`, que o espelhamento preenche, e o join com `Ordem` já
   é `outerjoin`; o aparelho vendido portanto **já aparece sem alteração nenhuma**. O
   problema é só o campo `pdf`, que vem de `Ordem.pdf_certificado` via `os_atual` e sai
   **nulo** sem OS. Ajustar: sem `os_atual`, sinalizar o certificado de venda como fonte
   do PDF.

2. **`GET /portal/certificados/{ordem_id}`** — só serve certificado de OS. Acrescentar
   caminho para o de venda, **validando o tenant pelo token** (`cli.cliente` ==
   `ec.cliente`), nunca por parâmetro de URL.

Sem esses dois ajustes a feature nasce com um **link quebrado na cara do cliente**.

## Frontend

### Botão — `frota/EquipamentoClienteDetailPage.tsx`

Botão **"Gerar certificado de venda"** no card **Certificados**, visível só para quem
pode. Rótulo vira **"Regerar certificado de venda"** quando já existe.

Um botão só atende **as duas rotas** (`/app/frota/equipamentos/:id` e
`/app/clientes/:id/equipamentos/:aparelho`), porque as duas montam o mesmo componente —
a segunda com `embutido` (`routes.tsx:42`).

Na tabela, a linha do certificado de venda mostra **`— Venda`** na coluna OS (sem link,
já que não há ordem) e baixa pelo endpoint novo.

### Modal — extração de componente compartilhado

O corpo do formulário do `GerarCertificadoModal` (seções Cliente / Aparelho /
Calibração, incluindo o cálculo automático da média por `mediaTestes`) sai para um
componente compartilhado `CamposCertificado.tsx`. Os dois modais passam a consumi-lo,
mudando só a origem dos dados e o submit.

`CertificadoVendaModal.tsx` = `CamposCertificado` + o campo **"Próxima calibração"** +
submit no endpoint novo.

Isso evita a quarta cópia do mesmo formulário (OS, avulso, venda) divergindo com o
tempo — mesmo risco de lista paralela que a spec do avulso já apontou.

### `roles.ts`

`podeGerarCertificadoVenda(user)` = Admin ou `Laboratório`, espelhando o
`require_funcao` do backend. Reusar helper equivalente se já houver.

## Testes

**Backend**
- `montar_contexto_venda`: emite **o mesmo conjunto de chaves** que o fluxo da OS;
  regressão de token — HTML gerado de um template que usa todos os tokens **não contém
  nenhum `[token]` literal**.
- Geração: grava o registro com HTML preenchido, `usuario` e `data_geracao`; os valores
  do cadastro aparecem no HTML.
- **Upsert**: gerar duas vezes deixa **um** registro, com os dados da segunda.
- Aparelho sem `CertificadoModelo` de calibração → **409**.
- Permissão: Laboratório 200, Admin 200, Comercial Pós-Vendas → **403**.
- **Espelhamento**: após gerar, o `equipamento_cliente` tem `calib_cert`,
  `ult_calibragem` e `prox_calibragem` preenchidos.
- **Regressão**: `espelhar_calibracao` a partir de uma OS continua idêntica.
- Card da frota: devolve certificados de OS **e** o de venda, com `origem` correta.
- **Portal**: aparelho sem OS mas com certificado de venda aparece na listagem **e
  baixa o PDF**; cliente de outro tenant → **404/403** (isolamento pelo token).
- PDF: `application/pdf`; aparelho sem certificado → 404.

**Frontend**
- Botão só aparece para quem tem função; alterna "Gerar"/"Regerar".
- Modal pré-preenche cliente e aparelho a partir do cadastro.
- Linha de venda mostra `— Venda` na coluna OS, sem link.
- Regressão: `GerarCertificadoModal` segue funcionando após a extração de
  `CamposCertificado`.

## Aplicação em produção

1. `alembic upgrade head` (migração **0017** — só cria tabela nova; retrocompatível).
2. Deploy normal (nenhuma dependência nova).

## Fora de escopo

- Certificado de venda de **manutenção** (só calibração).
- Excluir um certificado de venda (regerar cobre a correção).
- Converter um certificado de venda em OS depois.
- Gerar certificado de venda **em lote** para vários aparelhos.
- Reformulação do formulário de calibração (mencionada pelo Erick para depois).
