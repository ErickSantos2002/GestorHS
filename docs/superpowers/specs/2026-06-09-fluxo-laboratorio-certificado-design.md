# GestorHS — Fluxo correto do laboratório: gerar certificado antes de concluir

**Data:** 2026-06-09
**Status:** Aprovado para implementação
**Motivação:** Corrigir o fluxo do laboratório. Hoje os dados de calibração (Nº do certificado, temperatura, pressão, testes, etc.) são informados no momento de "Concluir laboratório", e o certificado é gerado nesse instante. O correto: o operador **gera o certificado informando esses dados** (num passo próprio), **revisa**, e só então **conclui o laboratório** informando apenas a **próxima calibração** e a **observação**.

**Contexto:** continuação da feature de geração de certificado (branch `feat/geracao-certificado`, ainda não mesclada). Reaproveita modelos/motor/`os_certificados`/impressão já implementados; muda o GATILHO e ONDE os dados são digitados.

## Escopo
**Dentro:** mover os dados de calibração do "Concluir laboratório" para o passo "Gerar certificado"; tornar a geração um passo deliberado (com formulário); reduzir o concluir-lab (5→6) a próxima calibração + observação; bloquear a conclusão se não houver certificado gerado. Apenas **Calibração** (Manutenção fica para depois).
**Fora:** PDF no servidor; certificado de Manutenção; mudanças no template/motor (já prontos).

## Fluxo novo
1. OS na fase **Laboratório (5)**. Na seção "Certificados" do detalhe da OS, botão **"Gerar certificado de calibração"** (Laboratório/Admin).
2. O botão abre um **formulário** com os dados de calibração: Tipo de calibragem, Nº do certificado, Temperatura, Pressão, Testes 1/2/3, Média (auto-calculada, editável), Situação.
3. Ao **Gerar**: o backend salva esses dados em `ordens.calib_*`, seta `ordens.data_calibracao = agora()`, e gera/atualiza o HTML em `os_certificados` (tipo C). O certificado fica disponível na seção para **revisar/imprimir**. **Regerar** reabre o formulário pré-preenchido com os dados atuais.
4. **Concluir laboratório (5→6)**: o modal pede apenas **Próxima calibração** (data, padrão +1 ano) + **Observação**. Bloqueia (409) se a OS ainda não tem certificado gerado. Ao concluir: grava `prox_calibragem`, faz `espelhar_calibracao` (com a próxima calibração) e avança.

## Backend
### Schema (`app/schemas/ordens.py`)
- Novo `GerarCertificadoIn`: `tipo_calibragem: int | None`, `calib_cert/calib_temp/calib_pressao/calib_teste1/calib_teste2/calib_teste3/calib_teste_media/calib_situacao: str | None`.
- `AvancarIn`: mantém `obs`, `cod_retorno`, `prox_calibragem`; os campos `calib_*`/`tipo_calibragem` continuam existindo no schema mas **não são mais lidos** no branch 5→6 (podem ser removidos do uso; manter no schema é inócuo — decisão de implementação: removê-los do `AvancarIn` é o ideal, já que ninguém mais os envia).

### Endpoint `POST /ordens/{id}/gerar-certificado` (em `app/api/certificados_os.py`)
- Passa a aceitar um corpo opcional `GerarCertificadoIn`. Quando enviado, grava os campos em `ordens` (`tipo_calibragem`, `calib_*`) e seta `data_calibracao = agora()` se ainda não setada (ou sempre — ver abaixo). Sem corpo → regerar com os dados já salvos (não altera dados).
- Depois, chama `gerar_certificados(db, ordem, tipos_para(ordem))` (hoje gera Calibração; Manutenção quando houver modelo e serviço M/A — mantém). Commit. Retorna a lista.
- **data_calibracao:** setar (ou atualizar) para `agora()` sempre que vier corpo com dados (a geração representa o ato da calibração). Sem corpo, não altera.
- Gated Laboratório/Admin (já é).

### `avancar` branch 5→6 (`app/api/ordens.py`)
- **Remove** a gravação dos campos `calib_*`/`tipo_calibragem` e a auto-geração (SAVEPOINT) — geração agora é passo anterior.
- Passa a: exigir certificado — se `db.query(OSCertificado).filter(os==ordem.id).first()` é None → `HTTPException(409, "gere o certificado antes de concluir o laboratório")`; gravar `prox_calibragem` (de `dados.prox_calibragem`); `espelhar_calibracao(db, ordem)`; `texto = "Laboratório concluído"`.
- `data_calibracao` não é mais setada aqui (já foi na geração).

## Frontend
### `app/ordens/api.ts`
- `AvancarPayload`: manter `obs`, `cod_retorno`, `prox_calibragem`; remover os campos `calib_*`/`tipo_calibragem` (não enviados mais no avançar).
- Novo tipo/método: `GerarCertificadoPayload` (os campos calib) e `ordensApi.gerarCertificado(id, payload?)` (POST com corpo opcional). `TRANSICOES[5]`: trocar `pedeCalibracao` por `pedeProxCalibragem` (rótulo "Concluir laboratório").

### `AvancarModal.tsx`
- Remover o bloco `pedeCalibracao` inteiro (tipo/cert/temp/pressão/testes/média/pdf). Para a fase 5 (`pedeProxCalibragem`), mostrar só **Próxima calibração** (date, default +1 ano) + **Observação**. Tratar o 409 de "sem certificado" com mensagem amigável.

### Novo `GerarCertificadoModal.tsx` (`app/ordens/`)
- Formulário com: Tipo de calibragem (Select de `tiposCalibragemApi`), Nº do certificado, Temperatura, Pressão, Testes 1/2/3, Média (auto via `calcMedia`, editável), Situação. (Reaproveita a lógica de média do AvancarModal atual.) Pré-preenche com os dados atuais da OS (`os.calib_*`) ao regerar. Submete via `ordensApi.gerarCertificado(os.id, payload)`; ao concluir, atualiza a lista de certificados (callback).

### `OrdemDetailPage.tsx` — seção "Certificados"
- Quando a OS está na fase Laboratório (5) e `podeGerarCert`: botão **"Gerar certificado de calibração"** abre o `GerarCertificadoModal`. Após gerar, recarrega `certs` (e a OS, pois `calib_*`/`data_calibracao` mudaram).
- A lista de certificados mantém Imprimir; o botão de regerar abre o mesmo modal pré-preenchido.
- O botão "Gerar/Regerar" sem formulário (atual) é substituído por este fluxo com formulário.

## Testes / verificação
- **Backend (pytest):** `gerar-certificado` com corpo grava `calib_*` + `data_calibracao` e gera o cert; sem corpo regenera sem alterar dados; avanço 5→6 **bloqueia (409)** sem certificado; com certificado, grava `prox_calibragem`, espelha e vai p/ fase 6 sem tocar `calib_*`; `data_calibracao` setada na geração, não no avanço. Ajustar `test_ordens_avancar` (5→6 agora exige cert + só prox/obs) e `test_certificado_os_api` (POST com corpo).
- **Frontend (vitest):** `gerarCertificado` com payload; `AvancarPayload` sem calib. Telas tsc/lint/build. **E2E manual:** OS no lab → Gerar certificado (preenche dados) → revisar/imprimir → tentar concluir sem? (bloqueia) → concluir com próxima calibração + obs → fase 6.

## Critérios de aceite
- Na fase Laboratório, "Gerar certificado de calibração" abre o formulário dos dados; gerar salva e produz o certificado preenchido (revisável/imprimível); regerar reabre pré-preenchido. Concluir laboratório pede só próxima calibração + observação e é **bloqueado** sem certificado. `data_calibracao` na geração; `prox_calibragem`+espelhamento no concluir; sem auto-geração no avanço. pytest/vitest/tsc/lint/build verdes. Changelog (ajuste da v1.4.0 ou v1.4.1). Só Calibração.

## Fora do v1 desta etapa
Certificado de Manutenção (form próprio), PDF no servidor, exigir revisão explícita (flag "revisado") antes de concluir.
