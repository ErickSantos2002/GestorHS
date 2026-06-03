# GestorHS — Fase 3D (Formulários-portão — ações de escrita da OS)

**Data:** 2026-06-03
**Status:** Aprovado para implementação
**Parte de:** Fase 3 (Ordens de Serviço), sub-projeto 4 de 5 (3A schema ✅ → 3B backend ✅ → 3C kanban/lista/detalhe ✅ → **3D formulários-portão** → 3E calibração/certificado).
**Depende de:** 3B (endpoints `POST /ordens`, `POST /ordens/{id}/avancar`, `POST /ordens/{id}/cancelar`, `GET /fases`) e 3C (módulo `app/ordens/`, `OrdemDetailPage`, `OrdensPage`; `fasesApi` em `cadastros/api.ts`; Frota `EquipamentoClienteDetailPage`).

---

## 1. Objetivo

Dar vida ao fluxo da OS no frontend: permitir **abrir** uma OS (a partir do aparelho na Frota), **avançar** pelas fases por formulário-portão e **cancelar**, consumindo os endpoints de escrita já prontos na 3B. As telas só-leitura da 3C ganham os botões de ação, gateados por função para boa UX (o backend continua sendo a autoridade).

## 2. Escopo

**Dentro:**
- Métodos de escrita em `ordens/api.ts`: `abrir`, `avancar`, `cancelar` + constante `TRANSICOES`.
- Helper de permissão em `auth/roles.ts` (`podeAbrirOS`).
- Botão "Abrir OS" + `AbrirOSModal` na `EquipamentoClienteDetailPage` (Frota).
- Botões "avançar" (rótulo dinâmico) e "Cancelar OS" + `AvancarModal`/`CancelarModal` na `OrdemDetailPage`, gateados pelo responsável da fase.

**Fora (com a fase/destino):**
- Resultados ricos de calibração/certificado no portão Laboratório→Pós-Vendas → **Fase 3E**. Na 3D, "Concluir laboratório" só envia `obs` (o backend grava `data_calibracao`).
- Espelhamento no `equipamentos_cliente` e limpeza de `os_atual` ao encerrar → **3E**.
- Ações rápidas de avanço no kanban (avanço só pelo detalhe).
- Upload de fotos do recebimento (storage indefinido).
- Portal do cliente → Fase 5.

## 3. Contexto do código atual

- `ordens/api.ts` (3C): `apiJson` de `lib/api`; `ordensApi` com `listar/quadro/obter/logs`; tipos `OrdemDetalhe`, `LogOS`; `TIPO_SERVICO`, `FASES_FILTRO`, `formatData`. Falta `apiVoid`? Não — os métodos de escrita retornam a OS (usar `apiJson` com `method: 'POST'`).
- `OrdemDetailPage` (3C): carrega `obter`+`logs`, exibe cabeçalho (badge da fase via `fase_cor`/`fase_descricao`), blocos e timeline; sem botões de ação. Estado `os`/`logs`.
- `EquipamentoClienteDetailPage` (Frota): no modo edição mostra botões "Excluir" (admin) e "Voltar" no cabeçalho; usa `useAuth`/`isAdmin`; já importa de `../cadastros/api`. Tem `obj` (o aparelho) com `id`, `os_atual`, `cliente_nome`, `equipamento_descricao`.
- `auth/roles.ts`: `FUNCAO_ADMIN`, `isAdmin(user)`. `User.funcao` = descrição da função (string|null).
- `cadastros/api.ts`: `fasesApi.listar()` → `Fase[]` (`{id, descricao, cor, funcao_responsavel, funcao_nome}`), liberado a qualquer interno (backend `GET /fases` usa `get_current_usuario`).
- Componentes: `Modal` (props `open`, `onClose`, `title`, `footer`, children — ver `CadastroSimples`), `Button` (variants primary/secondary/danger), `Input`, `Select`, `Spinner`, `Badge`. Padrão de modal com `<form id="...">` + botões no `footer` (`form="..."`).

## 4. API client (`ordens/api.ts` — estender)

```
abrir(payload: AbrirPayload): Promise<OrdemDetalhe>        // POST /ordens
avancar(id: number, payload: AvancarPayload): Promise<OrdemDetalhe>   // POST /ordens/{id}/avancar
cancelar(id: number, payload: { motivo: string }): Promise<OrdemDetalhe>  // POST /ordens/{id}/cancelar
```
- `AbrirPayload = { equipamento_cliente: number; tipo_servico: 'C'|'M'|'A'; condicao_chegada?: string|null; acessorios?: string|null }`.
- `AvancarPayload = { obs?: string|null; cod_retorno?: string|null }`.
- Todos usam `apiJson` com `method`/`body` (retornam a OS; erros viram `ApiError` com `status`).
- **`TRANSICOES: Record<number, { rotulo: string; pedeCodRetorno?: boolean }>`**:
  - `4 → { rotulo: 'Encaminhar ao laboratório' }`
  - `5 → { rotulo: 'Concluir laboratório' }`
  - `6 → { rotulo: 'Registrar aceite' }`
  - `7 → { rotulo: 'Postar retorno', pedeCodRetorno: true }`
  - (8/9 ausentes → sem avanço.)

## 5. Permissão (UX)

`auth/roles.ts`:
- `FUNCAO_EXPEDICAO = 'Expedição'`.
- `podeAbrirOS(user) = isAdmin(user) || user?.funcao === FUNCAO_EXPEDICAO`.

No `OrdemDetailPage`, após carregar `os` e `fases`, resolve `faseAtual = fases.find(f => f.id === os.fase)` e:
- `responsavelNome = faseAtual?.funcao_nome ?? null`.
- `podeAgir = isAdmin(user) || (!!responsavelNome && user?.funcao === responsavelNome)`.
- `ativa = os.fase != null && os.fase >= 4 && os.fase <= 7` (usar os ids; alternativamente `os.fase in TRANSICOES || os.fase === 7`). Botões aparecem só quando `ativa && podeAgir`.

O backend é a autoridade final — qualquer ação ainda valida no servidor (403/409/422 exibidos inline).

## 6. Abrir OS (Frota)

- `EquipamentoClienteDetailPage`: no modo edição (aparelho existe) e se `podeAbrirOS(user)`, adicionar botão **"Abrir OS"** (primary) no grupo de botões do cabeçalho.
- **`AbrirOSModal`** (novo componente, em `app/ordens/AbrirOSModal.tsx` para reuso/coesão): props `{ equipamentoClienteId, equipamentoNome, onClose, onAberta(os) }`.
  - Campos: `Select` **Tipo de serviço** (Calibração=C / Manutenção=M / Ambas=A; obrigatório), textarea **Condição de chegada** (opcional), textarea **Acessórios** (opcional).
  - Confirma → `ordensApi.abrir({ equipamento_cliente, tipo_servico, condicao_chegada, acessorios })`.
  - Sucesso → `onAberta(os)`; a página da Frota navega para `/app/ordens/{os.id}`.
  - **409** "aparelho já possui OS ativa" → erro inline no modal, com botão/link "Ver OS atual" quando `obj.os_atual` existir (`navigate('/app/ordens/{obj.os_atual}')`).

## 7. Avançar / Cancelar (detalhe)

- `OrdemDetailPage` passa a carregar `fases` (via `fasesApi.listar()`) junto de `obter`/`logs`. Calcula `responsavelNome`/`podeAgir`/`ativa` (§5).
- No cabeçalho, quando `ativa && podeAgir`:
  - Botão **avanço** (primary) com `TRANSICOES[os.fase].rotulo` → abre `AvancarModal`.
  - Botão **"Cancelar OS"** (danger) → abre `CancelarModal`.
- **`AvancarModal`** (`app/ordens/AvancarModal.tsx`): props `{ os, transicao, onClose, onConcluido(os) }`.
  - Sempre: textarea **Observação** (`obs`, opcional).
  - Se `transicao.pedeCodRetorno`: `Input` **Código de retorno** (obrigatório; bloquear submit/validação inline se vazio).
  - Confirma → `ordensApi.avancar(os.id, { obs, cod_retorno })`; sucesso → `onConcluido(os)`. Erros (403/409/422) inline.
- **`CancelarModal`** (`app/ordens/CancelarModal.tsx`): props `{ os, onClose, onConcluido(os) }`. Textarea **Motivo** (obrigatório). Confirma → `ordensApi.cancelar(os.id, { motivo })`.
- Ao `onConcluido(novaOS)`/`onAberta`: o detalhe substitui `os` por `novaOS`, fecha o modal e recarrega `ordensApi.logs(os.id)` (nova entrada na timeline). Recalcula badge/botões (ex.: ao finalizar/cancelar, os botões somem).

## 8. Testes

- **Vitest** (`ordens/api.test.ts`, estender): `abrir` faz `POST /ordens` com corpo `{equipamento_cliente, tipo_servico, ...}`; `avancar` faz `POST /ordens/{id}/avancar` com `obs`/`cod_retorno`; `cancelar` faz `POST /ordens/{id}/cancelar` com `motivo`; um caso de propagação de `ApiError` (ex.: 409 no abrir).
- **Vitest** (`auth/roles.test.ts`, criar ou estender): `podeAbrirOS` → true p/ admin e p/ Expedição; false p/ Laboratório/Comercial/null.
- **Telas/modais:** `tsc -b` + `npm run lint` + `npm run build` limpos.
- **E2E manual** (cuidado com produção): como não há DELETE de OS, criar 1 OS de teste num aparelho sem OS ativa, percorrer Recebido→…→Finalizada e/ou cancelar com motivo "teste E2E 3D"; confirmar badge + timeline + gating por função. O controlador avisa antes de tocar no banco real e deixa a OS de teste claramente marcada.

## 9. Critérios de aceite

- Expedição/Admin abre OS a partir do aparelho na Frota; 409 se já há OS ativa (com link para a atual); sucesso leva ao detalhe da OS em Recebido.
- No detalhe, o responsável da fase atual (ou admin) vê o botão de avanço (rótulo do portão) e "Cancelar OS"; avança preenchendo o formulário (cód. de retorno obrigatório na postagem) e cancela com motivo; quem não é responsável vê só-leitura.
- Cada ação atualiza na hora: badge da fase muda e a nova entrada aparece na timeline; 403/409/422 aparecem inline.
- `npm run test` verde; `tsc -b`, `lint`, `build` limpos; E2E manual ok.

## 10. Fora de escopo (reafirmando)
Resultados ricos de calibração/certificado e espelhamento/`os_atual` (3E); ações no kanban; fotos; portal (Fase 5).
