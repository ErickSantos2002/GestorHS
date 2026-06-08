# GestorHS — Abrir OS: formulário de recebimento completo

**Data:** 2026-06-08
**Status:** Aprovado para implementação
**Motivação:** Aproximar (e melhorar) o formulário de recebimento de OS do sistema legado. Hoje o "Abrir OS" tem só Tipo de serviço + Condição de chegada (texto livre) + Acessórios (texto livre). O legado registra no recebimento: data de chegada, caixa, tipo de serviço, checklist de acessórios que vieram com o aparelho, quantidade de pilhas, quantidade de bocais e observações. Esta é a **primeira etapa** de uma revisão maior dos processos de abertura e fechamento de OS (hoje: só abertura).

## Escopo
**Dentro:** redesenho do formulário de **abrir OS** (campos, backend e exibição no detalhe da OS).
**Fora:** fluxo de fechamento/laboratório, checklist técnico de diagnóstico (`checklist_templates`/`checklist_respostas` — usado no laboratório, não no recebimento), portal do cliente.

## Decisão de armazenamento
Reaproveitar colunas **já existentes** em `ordens` — **sem migração de banco**:

| Campo do formulário | Coluna em `ordens` | Tipo |
|---|---|---|
| Data de chegada | `data_chegada` | timestamptz (recebe uma data; default hoje) |
| Caixa | `caixa` | integer FK → caixas (já existe) |
| Tipo de serviço | `tipo_servico` | varchar(1) C/M/A (já existe) |
| Condição de chegada | `condicao_chegada` | text (passa a guardar um valor de lista fixa) |
| Checklist de acessórios | `checklist` | varchar(50) — CSV de ids (ex.: `"1,3,5"`) |
| Pilhas (qtd) | `pilhas` | integer (default 0) |
| Bocais (qtd) | `sopradores` | integer (default 0) — rotulado "Bocais" na UI |
| Observações | `obs` | text |

O campo de texto livre **`acessorios` sai do formulário** (a coluna permanece no banco, sem uso novo). `data_chegada` já existia mas era sempre `agora()`; passa a vir do formulário (default hoje).

## Listas fixas (no código)

**Checklist de acessórios** — lista fixa com ids estáveis (a fonte canônica fica no backend; o front replica para renderizar os checkboxes — manter em sincronia):
1. Bobinas
2. Bocal
3. Cabos USB
4. Capa
5. Carregador veicular
6. Carregadores AC/DC
7. Impressora
8. Maleta
9. Nf de Remessa

**Condição de chegada** — select com opções fixas: `Bom estado`, `Com avarias`, `Oxidado`, `Lacrado`, `Sem acessórios`.

## Backend

### `OrdemAbrirIn` (em `app/schemas/ordens.py`)
Passa a ser:
```python
class OrdemAbrirIn(BaseModel):
    equipamento_cliente: int
    tipo_servico: Literal["C", "M", "A"]
    data_chegada: date | None = None        # default hoje se ausente
    caixa: int | None = None                # já existia
    condicao_chegada: str | None = None     # deve ser uma das CONDICOES_CHEGADA
    checklist: list[int] | None = None      # ids do checklist fixo → CSV
    pilhas: int | None = 0
    bocais: int | None = 0                  # gravado em ordens.sopradores
    observacoes: str | None = None          # gravado em ordens.obs
```
O campo `acessorios` é **removido** de `OrdemAbrirIn`.

### Constantes (em `app/core/recebimento.py`, novo)
- `CHECKLIST_ACESSORIOS: dict[int, str]` — mapa id→label (a lista acima).
- `CONDICOES_CHEGADA: tuple[str, ...]` — as 5 opções.
- Helpers: `checklist_ids_para_csv(ids) -> str` (valida ids ∈ chaves, ordena, junta com vírgula) e `checklist_csv_para_ids(csv) -> list[int]` (parse defensivo, ignora ids inválidos/legados).

### Endpoint `abrir` (`app/api/ordens.py`)
- Validações novas (após as existentes de equipamento/OS-ativa/caixa):
  - se `condicao_chegada` informado e não estiver em `CONDICOES_CHEGADA` → 422/400.
  - `checklist`: ids inválidos (fora de `CHECKLIST_ACESSORIOS`) → 400; CSV gravado via helper.
- Ao criar a `Ordem`, gravar:
  - `data_chegada` = `dados.data_chegada` convertida para datetime com timezone (meia-noite UTC) ou `agora()` se ausente,
  - `condicao_chegada`, `checklist` (CSV), `pilhas` (default 0), `sopradores` = `dados.bocais` (default 0), `obs` = `dados.observacoes`, `caixa` (como hoje).
- Remover o set de `acessorios`.

### `OrdemOut` (`app/schemas/ordens.py`)
- `OrdemOut` (detalhe) ganha: `checklist: list[int]` (ids parseados), `acessorios_presentes: list[str]` (labels, derivado do CSV via `CHECKLIST_ACESSORIOS`), `pilhas: int`, `bocais: int` (= `sopradores`). `condicao_chegada`, `data_chegada`, `obs`, `caixa` já existem.
- `OrdemListOut` (listagem) **não** muda — esses campos são só do detalhe.
- No modelo `Ordem` (`app/models/ordem.py`), adicionar properties: `checklist_ids` (parse do CSV) e `acessorios_presentes` (labels) e `bocais` (= `self.sopradores`) para o `from_attributes` do Pydantic.

## Frontend

### `AbrirOSModal` (`app/ordens/AbrirOSModal.tsx`)
Redesenhado (modal mais largo) com os campos na ordem do design. Mantém as props atuais (`equipamentoClienteId`, `osAtual`, `onClose`, `caixa?`, `onAberta?`). Quando `caixa` vem por prop (aberto a partir de uma caixa), o seletor de caixa vem **pré-preenchido e travado**.
- **Data de chegada:** `<Input type="date">`, default hoje.
- **Caixa:** componente de busca — input que consulta `GET /caixas?q=` e lista resultados para escolher; botão "Nova caixa" que chama `caixasApi.criar({obs})` e seleciona a recém-criada. Opcional.
- **Tipo de serviço:** `<Select>` C/M/A (como hoje).
- **Condição de chegada:** `<Select>` com as 5 opções (constante no front).
- **Checklist de acessórios:** 9 checkboxes (constante no front, ids batendo com o backend).
- **Pilhas / Bocais:** `<Input type="number" min=0>`.
- **Observações:** `<textarea>`.
- No submit, monta o `AbrirPayload` novo (inclui `checklist: number[]`, `pilhas`, `bocais`, `condicao_chegada`, `data_chegada`, `observacoes`).

### `app/ordens/api.ts`
- `AbrirPayload` atualizado com os novos campos (remove `acessorios`).
- `OrdemDetalhe` ganha `pilhas`, `bocais`, `checklist: number[]`, `acessorios_presentes: string[]` (conforme o backend expõe no `OrdemOut`). `OrdemListItem` não muda.
- Constantes `CHECKLIST_ACESSORIOS` (id→label) e `CONDICOES_CHEGADA` exportadas para o modal.

### `OrdemDetailPage` (`app/ordens/OrdemDetailPage.tsx`)
Seção "Recebimento" passa a mostrar: Condição de chegada, **Acessórios** (lista de presentes, de `acessorios_presentes`), Pilhas, Bocais, Observações (de `obs`), além de Data de chegada e Caixa (já exibidos). Remove a exibição do antigo "Acessórios" (texto livre).

## Changelog
Entra como **v1.2.0** (novidade): "Recebimento de OS mais completo — data de chegada, vínculo a caixa, condição de chegada, checklist de acessórios, pilhas, bocais e observações ao abrir a OS." (regra: toda mudança bumpa versão + entra no ChangelogModal.)

## Testes / verificação
- **Backend (pytest):** abrir OS com todos os campos (grava data_chegada da data informada, condicao_chegada, checklist CSV, pilhas, sopradores=bocais, obs); default de data_chegada=hoje quando ausente; condição inválida → erro; checklist com id inválido → 400; `OrdemOut` retorna `checklist` ids + `acessorios_presentes` labels + pilhas + bocais; abrir sem os campos novos (mínimo: equipamento+tipo) continua funcionando; abrir com caixa (já coberto) segue ok.
- **Frontend (vitest):** `AbrirPayload` montado corretamente (checklist ids, bocais, etc.); o `caixasApi`/busca não regride. Telas: `tsc` + lint + build. E2E manual: abrir OS pela Frota com checklist/pilhas/bocais/condição/caixa nova → conferir no detalhe da OS.

## Critérios de aceite
- O formulário de abrir OS tem: data de chegada (default hoje), busca/cria caixa, tipo de serviço, condição de chegada (select), checklist de 9 acessórios, pilhas, bocais e observações.
- Ao abrir, todos os campos são persistidos nas colunas indicadas; o detalhe da OS exibe condição, acessórios presentes, pilhas, bocais e observações.
- Abrir a partir de uma caixa mantém a caixa pré-vinculada.
- Abertura "mínima" (só equipamento + tipo) continua funcionando.
- Sem migração de banco. pytest/vitest/tsc/lint/build verdes. Changelog em v1.2.0.

## Fora do v1 desta etapa (próximas etapas do processo de OS)
- Fechamento/laboratório, checklist técnico de diagnóstico (`checklist_templates`), leitura/edição dos campos de recebimento após aberta, exibição no portal.
