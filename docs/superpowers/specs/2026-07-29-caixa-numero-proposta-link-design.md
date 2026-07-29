# Caixa: número da proposta (via GrowthHS) + link no card do TaskHS — Design

**Data:** 2026-07-29
**Área:** backend (config/migração/model, `api/integracao_growthhs.py`, novo `core/proposta_link.py`, `api/publico.py`, `core/taskhs.py`, `api/espelhamento.py`) + doc.
**Tipo:** extensão da integração inbound + link público (espelha o padrão do certificado).

## Problema

Quando o GrowthHS dá ganho e move a caixa pra Financeiro (endpoint inbound `ganho`), ele também sabe **o número da proposta** (o mesmo `#N` da tela de Propostas do GestorHS). Queremos: (1) guardar esse número na caixa; (2) no card do TaskHS, na etapa de Pós-Vendas, um **link público pra baixar o PDF da proposta** — igual ao link de certificado que já existe no card.

## Contexto (padrões a espelhar)

- **Link público de certificado:** `core/certificado_link.py` assina um token HMAC (`core/assinatura.assinar/verificar`) e monta `{CERT_PUBLIC_BASE_URL}/publico/certificado/{ordem_id}/{tipo}?t=...`; `api/publico.py` valida o token e serve o PDF sem login.
- **PDF da proposta:** `proposta_pdf.gerar_pdf(db, proposta_id)` devolve os bytes (usado pelo endpoint autenticado `/propostas/{id}/pdf`).
- **Card do TaskHS:** `taskhs.montar_obs_caixa(...)` monta as seções obs1..obs6; **obs3 = Pós-Vendas** (`_sec_posvendas(rep)`); os links (certificado/NF) são resolvidos em `espelhamento._montar_payload_caixa` e passados como `..._url`.

## Design

### 1. Guardar o número — migração 0023 + endpoint ganho
- **Migração 0023** (down_revision `0022_proposta_faturada`): coluna `caixas.numero_proposta` (Integer, nullable).
- **`GanhoIn`** ganha `numero_proposta: int | None = None`.
- No `ganho`: quando presente, gravar `cx.numero_proposta = dados.numero_proposta` — tanto no caminho de avanço (fase 6) quanto no no-op (já avançada), pra capturar o número mesmo em reenvio. (Rejeição 409/404 não grava.)

### 2. Link público da proposta — novo módulo + endpoint
- **`core/proposta_link.py`** (espelha `certificado_link`): mensagem `f"proposta:{proposta_id}"`; `assinar/verificar`; `link_proposta(proposta_id) -> {CERT_PUBLIC_BASE_URL}/publico/proposta/{proposta_id}?t=<token>` (None se base vazia).
- **`api/publico.py`:** `GET /publico/proposta/{proposta_id}` — valida o token (`proposta_link.verificar`), gera o PDF com `proposta_pdf.gerar_pdf(db, proposta_id)`, devolve `Response` inline (404 se a proposta/`ValueError`).

### 3. Link no card do TaskHS (seção Pós-Vendas)
- **`espelhamento._montar_payload_caixa`:** resolve `proposta_url` — se `caixa.numero_proposta`, achar a `Proposta` por `numero`; se existir, `proposta_link.link_proposta(proposta.id)`; passa `proposta_url` (e o número) para `montar_obs_caixa`.
- **`taskhs.montar_obs_caixa(..., proposta_url=None)`** → `_sec_posvendas(rep, *, numero_proposta=caixa.numero_proposta, proposta_url=proposta_url)`.
- **`_sec_posvendas`:** quando há `numero_proposta`, acrescenta uma linha `Proposta #{numero}: {url}` (ou só `Proposta #{numero}` se a proposta não for achada / base pública vazia).

## Fora de escopo
- Auto-marcar a proposta como Faturada (Financeiro faz manual — feature de ontem).
- Versionar/travar qual versão do PDF (serve o PDF atual, como o endpoint autenticado).
- Lado do GrowthHS (mandar o campo) — feito por eles, guiado pelo doc.
- Proposta soft-deletada ainda pode ser baixada por um token já emitido (o link só é gerado para propostas não deletadas, mas tokens antigos em cards antigos continuam válidos) — comportamento consistente com os links de certificado/nota fiscal, aceito de propósito.

## Segurança
Link público = mesmo esquema HMAC do certificado (token assinado, sem login, só leitura do PDF). `numero_proposta` é um inteiro; a resolução por `numero` é interna (o link usa o id).

## Rollout
Backend, **migração 0023** (aplicar em prod após deploy). Versão **v1.30.0**. Atualizar o doc de integração inbound (`docs/integracao-growthhs-inbound.md`) com o campo `numero_proposta`.

## Testes
- **Endpoint ganho:** com `numero_proposta`, grava em `caixas.numero_proposta` (no avanço e no no-op); sem ele, fica NULL; presente no `PropostaOut`/detalhe da caixa se exposto (opcional).
- **Link público:** token válido → 200 PDF (`gerar_pdf` chamado); token inválido → 403; proposta inexistente → 404; base pública vazia → `link_proposta` devolve None.
- **Card:** caixa com `numero_proposta` e proposta existente → a seção Pós-Vendas do card contém `Proposta #N` e a URL pública; sem número → sem a linha.

## Arquivos
Backend: `models/caixa.py`, `alembic/versions/0023_*.py`, `api/integracao_growthhs.py`, `core/proposta_link.py` (novo), `api/publico.py`, `core/taskhs.py`, `api/espelhamento.py`, testes. Doc `docs/integracao-growthhs-inbound.md`. Changelog v1.30.0.
