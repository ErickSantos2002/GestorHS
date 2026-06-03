# GestorHS — Fase 3E (Calibração & Certificado)

**Data:** 2026-06-03
**Status:** Aprovado para implementação
**Parte de:** Fase 3 (Ordens de Serviço), sub-projeto 5 de 5 — **fecha a Fase 3** (3A schema ✅ → 3B backend ✅ → 3C kanban/lista/detalhe ✅ → 3D formulários-portão ✅ → **3E calibração/certificado**).
**Depende de:** 3B (modelos `Ordem`/`Fase`/`LogOS`, `EquipamentoCliente`; endpoint `avancar` com `AvancarIn`), 3D (`AvancarModal`, `TRANSICOES`, `ordensApi.avancar`). Migração 0002 já tem os campos `calib_*`/`prox_calibragem` em `ordens` e os campos-espelho em `equipamentos_cliente`.

---

## 1. Objetivo

Enriquecer o portão **Laboratório→Pós-Vendas** com os resultados da calibração (temperatura, pressão, três testes, média, situação), o certificado (número e referência do PDF), o tipo de calibragem e a próxima calibração — gravando tudo na OS e **espelhando no cadastro do aparelho** (`equipamentos_cliente`), de modo que o status de calibração da Frota atualize na hora. É o último sub-projeto da Fase 3.

## 2. Escopo

**Dentro:**
- Backend: modelo `TipoCalibragem` + `GET /tipos-calibragem`; extensão de `AvancarIn` com campos de calibração opcionais; enriquecimento do branch `origem == 5` do `avancar` (gravar na OS + espelhar no aparelho).
- Frontend: `tiposCalibragemApi`; `AvancarModal` em modo calibração (só fase Laboratório) com o formulário rico; link do PDF no detalhe.

**Fora (com a fase/destino):**
- Upload real de arquivo PDF (storage indefinido) — `pdf_certificado` é só referência (nome/URL).
- Tabela `certificados` (biblioteca de documentos do legado) — não usada no v1.
- Geração automática de PDF de certificado.
- Worklist de cobrança → Fase 4; `solicitacoes`/portal → Fase 5.

**Decisão registrada (follow-up da 3B):** `equipamentos_cliente.os_atual` é setado no abrir e **não** é limpo ao finalizar/cancelar — o aparelho reflete a última OS. O espelhamento dos resultados ocorre no portão Lab→Pós (não no abrir nem no cancelar).

## 3. Contexto do código atual

- `backend/app/api/ordens.py` → `avancar`: branch `origem == 5` hoje só faz `ordem.data_calibracao = agora()` e loga "Calibração/manutenção concluída". `exige_funcao_da_fase` autoriza (Laboratório responde pela fase 5). `agora()`/`registrar_log` em `ordens_acoes.py`.
- `backend/app/schemas/ordens.py` → `AvancarIn = { obs?, cod_retorno? }`. `OrdemOut` já expõe `calib_cert/temp/pressao/teste_media/situacao/pdf_certificado` (read).
- `backend/app/models/ordem.py` → tem todos os `calib_*`, `pdf_certificado`, `tipo_calibragem`, `data_calibracao`, `prox_calibragem` (DateTime tz). `backend/app/models/equipamento_cliente.py` → `calib_*` (String), `ult_calibragem`/`prox_calibragem` (Date), `os_atual` (Integer sem FK), `@property status_calibracao` (usa `prox_calibragem`).
- Schema `tipos_calibragem(id, descricao varchar(200), texto text, valor numeric(10,2))`.
- Padrões: modelo um-por-arquivo + `__init__`; router registrado em `main.py`; `GET` de catálogo liberado a `get_current_usuario`. Testes pytest com SQLite (fixtures `fases_seed`, `usuario_lab`, `os_base`, etc.).
- Frontend: `ordens/api.ts` (`ordensApi.avancar`, `AvancarPayload`, `TRANSICOES`); `AvancarModal` (3D) já recebe `transicao` e renderiza `obs` + `cod_retorno` condicional; `cadastros/api.ts` tem `crudClient`/`apiJson`. `Select`/`Input` padrão.

## 4. Backend

### 4.1 Tipos de calibragem
- Modelo `TipoCalibragem` (`tipos_calibragem`): `id`, `descricao`, `texto` (Text, nullable), `valor` (Numeric, default 0). Registrar em `models/__init__.py`.
- `app/api/tipos_calibragem.py`: `GET /tipos-calibragem` (prefix `/tipos-calibragem`, `get_current_usuario`) → `list[TipoCalibragemOut]` ordenado por descrição. Schema `TipoCalibragemOut = {id, descricao}` (`from_attributes`). Registrar router em `main.py`.

### 4.2 `AvancarIn` (estender — todos opcionais)
Acrescentar a `app/schemas/ordens.py`:
```
tipo_calibragem: int | None = None
calib_cert: str | None = None
calib_temp: str | None = None
calib_pressao: str | None = None
calib_teste1: str | None = None
calib_teste2: str | None = None
calib_teste3: str | None = None
calib_teste_media: str | None = None
calib_situacao: str | None = None
pdf_certificado: str | None = None
prox_calibragem: datetime | None = None
```
(`obs`/`cod_retorno` permanecem.)

### 4.3 `avancar` — branch `origem == 5`
Passa a (mantendo `data_calibracao = agora()` e o log):
1. Aplicar à OS os campos enviados (somente os não-`None`): `tipo_calibragem`, `calib_cert/temp/pressao/teste1/teste2/teste3/teste_media/situacao`, `pdf_certificado`, `prox_calibragem`.
2. **Espelhar no aparelho** quando `ordem.equipamento_cliente` existe: carregar o `EquipamentoCliente`; copiar os `calib_*` (os que vieram); `ult_calibragem = ordem.data_calibracao.date()`; se `prox_calibragem` foi enviada, `equip.prox_calibragem = prox_calibragem.date()`. `os_atual` não muda (já é a OS).
3. Log "Calibração/manutenção concluída" (+`obs`).

Demais transições ignoram os campos de calibração. `cancelar` e as outras fases inalterados. Helper de espelhamento isolado em `ordens_acoes.py` (`espelhar_calibracao(db, ordem)`), testável.

### 4.4 Testes (pytest)
- `avancar` 5→6 com payload de calibração: a OS recebe `calib_*`/`tipo_calibragem`/`prox_calibragem`; o `EquipamentoCliente` é espelhado (`calib_cert` etc., `ult_calibragem` = data da calibração, `prox_calibragem` = a enviada) e seu `status_calibracao` reflete a nova data.
- Manutenção pura (5→6 sem nenhum campo de calibração): avança, loga, **não** altera os `calib_*` do aparelho.
- OS sem `equipamento_cliente`: 5→6 com calibração não quebra (sem espelho).
- Campos de calibração enviados em outra transição (ex.: 4→5) são ignorados (não gravam).
- `GET /tipos-calibragem` lista (qualquer interno), 401 sem token.

## 5. Frontend

### 5.1 API
- `cadastros/api.ts`: `interface TipoCalibragem { id: number; descricao: string }` + `tiposCalibragemApi = { listar: () => apiJson<TipoCalibragem[]>('/tipos-calibragem') }`.
- `ordens/api.ts`: estender `AvancarPayload` com os campos de calibração (mesmos nomes do backend; `prox_calibragem: string|null`). Em `TRANSICOES`, `5` ganha `pedeCalibracao: true` (`{ rotulo: 'Concluir laboratório', pedeCalibracao: true }`).

### 5.2 `AvancarModal` — modo calibração
- Nova prop `pedeCalibracao?: boolean` (passada pelo detalhe a partir de `TRANSICOES[os.fase]`).
- Quando `pedeCalibracao`, antes da `obs`, renderiza o bloco de calibração:
  - `Select` **Tipo de calibragem** (carrega `tiposCalibragemApi.listar()` no `useEffect` do modal; opção vazia "— selecione —").
  - `Input` **Nº do certificado**, **Temperatura**, **Pressão**, **Teste 1**, **Teste 2**, **Teste 3**, **Média dos testes**, **Situação** (todos texto, opcionais).
  - `Input` **PDF do certificado** (texto: nome/URL).
  - `Input type=date` **Próxima calibração**, pré-preenchida com hoje + 12 meses (editável).
  - **Média automática:** quando Teste 1/2/3 são numéricos (aceitando vírgula decimal), `calib_teste_media` é recalculada (média aritmética, formatada com vírgula) e mantém-se editável; se o usuário digitar a média manualmente, respeitar.
- Ao confirmar, envia em `ordensApi.avancar(os.id, {...})` os campos preenchidos (vazios viram `null`) + `prox_calibragem` (string ISO `YYYY-MM-DD`) + `obs`.
- Fases sem `pedeCalibracao`: comportamento da 3D (só `obs`/`cod_retorno`).

### 5.3 Detalhe da OS
- O bloco "Resultados da calibração" já existe (3C). Ajuste pequeno: se `pdf_certificado` começa com `http`, renderizar como link (`<a target="_blank">`); senão, texto.

### 5.4 Testes (Vitest)
- `ordens/api.test.ts`: `avancar` inclui os campos de calibração no corpo quando fornecidos; `tiposCalibragemApi.listar` bate em `/tipos-calibragem`.
- Modal/telas: `tsc -b` + `lint` + `build`.

## 6. Verificação / E2E

- pytest e `npm run test` verdes; `tsc`/`lint`/`build` limpos.
- **E2E não-destrutivo**: abrir o `AvancarModal` numa OS na fase Laboratório (admin), conferir o formulário rico, o pré-preenchimento da próxima calibração (+12 meses) e o cálculo automático da média ao digitar os 3 testes — **sem submeter**. Escrita real (que espelha no aparelho) só mediante pedido explícito do usuário (cria OS de teste).

## 7. Critérios de aceite

- No portão Laboratório→Pós-Vendas, Laboratório/Admin preenche tipo de calibragem, resultados, certificado e próxima calibração; a OS guarda tudo e o aparelho é espelhado (status de calibração da Frota muda na hora).
- Manutenção pura (sem dados de calibração) avança normalmente, sem alterar o aparelho.
- `GET /tipos-calibragem` popula o Select; detalhe da OS mostra os resultados e o link do PDF quando for URL.
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos; E2E não-destrutivo ok.
- **Fase 3 completa** após este merge.

## 8. Fora de escopo (reafirmando)
Upload real de PDF; tabela `certificados`; geração de PDF; worklist (Fase 4); portal/`solicitacoes` (Fase 5).
