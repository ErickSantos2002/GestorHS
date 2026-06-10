# GestorHS — Regerar certificado com valores corrigidos (inclusive OS finalizada)

**Data:** 2026-06-10
**Status:** Aprovado para implementação
**Motivação:** Os certificados são preenchidos manualmente e saem com valores errados com frequência. É preciso poder **corrigir os valores e regerar o certificado mesmo com a OS finalizada**, incluindo corrigir a data de calibração.

**Contexto:** continuação dos certificados (v1.4.x). O endpoint `POST /ordens/{id}/gerar-certificado` já regenera a partir dos campos `calib_*` da própria OS e já é liberado para Laboratório/Admin sem checar fase; o certificado é montado de `ordem.calib_*`/`ordem.data_calibracao` (`montar_contexto`). As mudanças são pequenas.

## Decisões (do usuário)
- **Data de calibração editável** no formulário de gerar/regerar (não resetar pra "hoje" automaticamente ao corrigir um certificado antigo).
- Regerar **só corrige o certificado** (valores + PDF da OS); **não** espelha no aparelho (já é o comportamento atual — espelhamento só ocorre no concluir-laboratório 5→6).
- Permissão inalterada: Laboratório/Admin.

## Escopo
**Dentro:**
- Backend: `GerarCertificadoIn` ganha `data_calibracao: date | None`; o endpoint passa a gravar a data vinda do form (UTC) em vez de forçar `agora()`.
- Frontend: campo "Data de calibração" no `GerarCertificadoModal`; botão Gerar/Regerar disponível para Lab/Admin quando for fase Laboratório **ou** já houver certificado (permite regerar OS finalizada).

**Fora:**
- Mudança de permissões; espelhamento no aparelho ao regerar; histórico/versionamento de certificados; bloquear regeração por fase.

## Backend

### Schema (`app/schemas/ordens.py`)
- `GerarCertificadoIn`: adicionar `data_calibracao: date | None = None` (o `date` já é importado no módulo).

### Endpoint `POST /ordens/{ordem_id}/gerar-certificado` (`app/api/certificados_os.py`)
- Continua gated Laboratório/Admin, sem checar fase.
- Ao receber corpo (`dados is not None`):
  - grava os campos `_CAMPOS_CALIB` (como hoje);
  - **data de calibração:** se `dados.data_calibracao` veio → `ordem.data_calibracao = datetime(ano, mês, dia, tzinfo=timezone.utc)`; senão, se `ordem.data_calibracao` é None → `agora()` (fallback 1ª geração); senão **mantém** a data atual (não reseta).
  - `db.flush()`.
- Depois, `gerar_certificados(...)` + commit (inalterado). **Não** chama `espelhar_calibracao`.
- Imports: adicionar `from datetime import datetime, timezone` no arquivo.

## Frontend

### `app/ordens/api.ts`
- `GerarCertificadoPayload`: adicionar `data_calibracao?: string | null` (string `YYYY-MM-DD`).

### `GerarCertificadoModal.tsx`
- Novo campo **"Data de calibração"** (`<Input type="date">`). Estado inicial: `os.data_calibracao` formatado como `YYYY-MM-DD` se houver; senão a data de hoje. Helper local `hojeISO()` para o default.
- Incluir no payload: `data_calibracao: dataCalib || null`.
- Layout: encaixar junto aos campos existentes (ex.: na mesma linha do Nº do certificado/Situação, ou em linha própria) — sem quebrar o grid responsivo.

### `OrdemDetailPage.tsx`
- Trocar a condição de exibição do botão na seção Certificados de `podeGerarCert && naFaseLab` para `podeGerarCert && (naFaseLab || certs.length > 0)`. Assim:
  - fase Laboratório: aparece "Gerar certificado de calibração" (1ª geração) e "Regerar certificado" (se já houver);
  - OS finalizada (ou qualquer fase) com certificado existente: aparece "Regerar certificado".
- O texto auxiliar quando não há certificado (`Nenhum certificado gerado. Clique em...`) deve continuar coerente: mostrar a dica de clique apenas quando o botão existir (`podeGerarCert && naFaseLab`), pois numa OS finalizada sem certificado o botão não aparece.

## Testes / verificação
- **Backend (pytest):** regerar com `data_calibracao` no corpo grava essa data (não "hoje"); regerar sem `data_calibracao` num OS que já tem data **mantém** a data; 1ª geração sem data usa hoje (fallback); regeração não altera o equipamento_cliente (sem espelho). Atualizar `test_certificado_os_api.py` (o teste `test_gerar_com_dados_salva_e_preenche` hoje espera `data_calibracao is not None` — continua válido; adicionar caso específico de data informada e de preservação).
- **Frontend (vitest/tsc/lint/build):** payload inclui `data_calibracao`; build verde.
- **E2E manual:** abrir uma OS finalizada com certificado → "Regerar certificado" → corrigir um valor e a data → gerar → baixar PDF e conferir valor/data corrigidos; a data não virou "hoje".

## Critérios de aceite
- Em OS finalizada (e em qualquer fase com certificado existente), Lab/Admin conseguem corrigir valores + data e regerar o certificado.
- A data de calibração reflete o que foi informado no formulário; regerar sem informar data não a reseta.
- Espelho do aparelho não é tocado ao regerar.
- pytest/vitest/tsc/lint/build verdes. Changelog v1.4.3.

## Fora do v1 desta etapa
Histórico/versionamento de certificados; espelhar correção no aparelho; auditoria de quem regerou.
