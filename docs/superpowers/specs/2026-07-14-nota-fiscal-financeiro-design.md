# Nota fiscal obrigatória para sair do Financeiro

**Data:** 2026-07-14
**Status:** aprovado (brainstorming)
**Depende de:** etapa Financeiro (v1.11.0) e correção da fase 10 no frontend (v1.12.1).

## Objetivo

O setor **Financeiro** só pode avançar a OS para **Preparando Retorno** depois de
**anexar a nota fiscal de serviço** e informar o **número da NF**. O anexo fica
disponível para download no GestorHS e no cartão do TaskHS.

## Decisões (aprovadas)

- **Um arquivo por OS**, podendo ser **PDF ou XML** (a NFS-e vem num dos dois).
- **Número da NF obrigatório** no momento do upload (sem registro pela metade).
- **Bloqueio no avanço**: sair do Financeiro (10 → 7) sem nota fiscal → **409**.
- **No cartão do TaskHS**: a seção `💰 Financeiro` ganha o número da NF e um **link
  público de download** (mesmo mecanismo de token do certificado).

## Backend

### Modelo — `app/models/ordem.py`
Duas colunas novas (espelham o padrão de `pdf_certificado`):
```python
    nota_fiscal = Column(String(50), nullable=True)          # basename do arquivo em disco
    nota_fiscal_numero = Column(String(50), nullable=True)   # numero da NF
```

### Migração — `0013_nota_fiscal.py`
`down_revision = "0012_usuario_email_credencial"`. `upgrade` adiciona as duas colunas
(nullable); `downgrade` as remove.

### Storage — `app/core/storage.py`
Liberar XML:
```python
TIPOS_XML = {"application/xml", "text/xml"}
TIPOS_NOTA_FISCAL = TIPOS_PDF | TIPOS_XML
```
e acrescentar as extensões ao mapa `_EXT` (`application/xml` → `.xml`, `text/xml` → `.xml`).
O limite de 10 MB, o nome aleatório e a proteção de path traversal já existem e são
reaproveitados sem mudança.

### Endpoints — `app/api/notas_fiscais.py` (router novo, registrado em `main.py`)

- **`POST /ordens/{ordem_id}/nota-fiscal`** — `multipart/form-data` com:
  - `file`: UploadFile (PDF ou XML; fora disso → **415**)
  - `numero`: str **obrigatório** (`Form(...)`; ausente → **422**; em branco após `strip()` → **422**)

  Permissão: `require_funcao("Financeiro", "Administrador")`.
  Salva em `notas-fiscais/{ordem_id}`; se já havia um anexo, **remove o arquivo anterior**.
  Grava `ordem.nota_fiscal` e `ordem.nota_fiscal_numero`. Responde
  `{"nota_fiscal": basename, "nota_fiscal_numero": numero}`.

- **`GET /ordens/{ordem_id}/nota-fiscal`** — download autenticado (qualquer usuário
  logado, como o certificado). Sem anexo → **404**. `media_type` conforme a extensão
  (`application/pdf` ou `application/xml`).

### Bloqueio do avanço — `app/api/ordens.py` (`avancar`)
No ramo `origem == 10` (Financeiro → Preparando Retorno), **antes** de marcar como pago:
```python
    elif origem == 10:                    # Financeiro -> Preparando Retorno
        if not ordem.nota_fiscal:
            raise HTTPException(status_code=409, detail="anexe a nota fiscal antes de confirmar o pagamento")
        ordem.pago = True
        ordem.data_pagamento = agora()
        texto = "Pagamento confirmado"
```
Espelha exatamente o gate já existente do laboratório (`origem == 5` exige certificado).

### Schema — `app/schemas/ordens.py`
`OrdemOut` passa a expor `nota_fiscal: str | None` e `nota_fiscal_numero: str | None`.

### Link público assinado

⚠️ **Restrição crítica:** os links de certificado **já publicados nos cartões do TaskHS**
são assinados com `hmac_sha256(JWT_SECRET_KEY, "cert:{ordem_id}:{tipo}")`. O formato
dessa mensagem **não pode mudar**, senão todos os links existentes passam a dar 403.

- **`app/core/assinatura.py`** (novo, puro): extrai o HMAC compartilhado.
  ```python
  def assinar(mensagem: str) -> str            # hmac_sha256(JWT_SECRET_KEY, mensagem).hexdigest()
  def verificar(mensagem: str, token: str) -> bool   # hmac.compare_digest
  ```
- **`app/core/certificado_link.py`**: passa a delegar para `assinatura`, **mantendo a
  mensagem `f"cert:{ordem_id}:{tipo_codigo}"` byte-a-byte** (os tokens continuam idênticos).
- **`app/core/nota_fiscal_link.py`** (novo): mensagem `f"nf:{ordem_id}"`; expõe
  `link_nota_fiscal(ordem_id) -> str | None` →
  `{CERT_PUBLIC_BASE_URL}/publico/nota-fiscal/{ordem_id}?t={token}`, ou `None` se a base
  estiver vazia (mesma degradação graciosa do certificado).
- **`app/api/publico.py`**: novo `GET /publico/nota-fiscal/{ordem_id}?t=<token>` — sem
  autenticação; token inválido → **403**; sem anexo → **404**; serve o arquivo com o
  `media_type` correto.

### TaskHS — `app/core/taskhs.py`
A seção `💰 Financeiro` (função `_sec_financeiro`) ganha uma linha quando houver NF:
```
- Nota fiscal: {numero} — {url}
```
(a linha do pagamento continua como está).

O módulo continua **puro**: a URL chega pronta, resolvida pelo wiring. Isso muda a
assinatura de `montar_descricao`, que ganha um parâmetro nomeado:
```python
def montar_descricao(ordem, *, certificados: list[dict], nota_fiscal_url: str | None = None) -> str | None
```
O default `None` mantém as chamadas existentes válidas. `_sec_financeiro(ordem, nota_fiscal_url)`
emite a linha da NF quando `ordem.nota_fiscal_numero` existir; se a `url` for `None`
(base pública não configurada), mostra só o número, sem link.

O wiring (`_agendar_espelhamento` em `ordens.py`) resolve
`nota_fiscal_link.link_nota_fiscal(ordem.id)` quando `ordem.nota_fiscal` existir e passa
o resultado adiante.

## Frontend

### Detalhe da OS — seção "Nota fiscal"
- Aparece **a partir da fase Financeiro** (usar `posicaoFase`, **nunca** comparação
  numérica — o id 10 é maior que 7/8).
- **Sem anexo**: para Financeiro/Admin, um formulário com **arquivo** (PDF/XML) +
  **número** e o botão "Anexar nota fiscal". Para os demais, um aviso de que a nota
  ainda não foi anexada.
- **Com anexo**: mostra o **número da NF** e um botão de **download**; Financeiro/Admin
  podem **substituir** (reenviar).
- O bloqueio do avanço segue o padrão existente: o backend devolve 409 e o
  `AvancarModal` exibe a mensagem (não desabilitamos o botão — é como o gate do
  certificado já funciona).

### `roles.ts`
Nova regra `podeAnexarNotaFiscal(user)` = Admin ou função `Financeiro` (espelho do
`require_funcao` do backend).

## Testes

- **Avanço**: OS na fase 10 sem NF → **409** com a mensagem; com NF → **200**, `pago=True`
  e `data_pagamento` setado; o fluxo completo 4→5→6→10→7→8 (com NF) continua passando.
- **Upload**: PDF ok; XML ok; tipo inválido (ex.: imagem) → **415**; sem `numero` → **422**;
  `numero` em branco → **422**; substituir o anexo **remove o arquivo anterior** do disco;
  função sem permissão (ex.: Laboratório) → **403**.
- **Download**: com anexo → 200 e `content-type` correto; sem anexo → 404.
- **Link público**: token válido → 200; token adulterado → 403; OS sem NF → 404; sem
  autenticação (não exige login).
- **Regressão crítica**: um teste travando que `certificado_link.assinar(1234, "C")`
  continua produzindo **exatamente o mesmo token** de antes do refactor (os links já
  publicados no TaskHS não podem quebrar).
- **Card**: `montar_descricao` inclui `Nota fiscal: {numero} — {url}` na seção Financeiro
  quando há NF, e omite a linha quando não há.
- **Frontend**: `posicaoFase` continua sendo a fonte da ordem (sem comparação numérica);
  a seção só aparece a partir do Financeiro.

## Aplicação em produção

1. `alembic upgrade head` (migração **0013** — só adiciona colunas; **retrocompatível**,
   não quebra o código antigo).
2. Deploy do código novo (backend + frontend). Não requer rebuild por dependência nova.
3. Sem backfill: OS que já estão no Financeiro passam a exigir a NF para avançar.

## Fora de escopo

- PDF **e** XML simultâneos (é um arquivo, de um dos dois formatos).
- Relatório fiscal, busca/filtro por número de NF.
- Validação do conteúdo do XML (schema da NFS-e) ou do número contra a prefeitura.
- Exigir NF em qualquer outra fase.
