# GestorHS — Página de Certificados (modelos + imagens)

**Data:** 2026-06-08
**Status:** Aprovado para implementação
**Motivação:** Base do gerador de certificados do laboratório. Cada **modelo de aparelho** (catálogo) tem um **modelo de certificado** em HTML, com campos entre colchetes (`[nomecli]`, `[serie]`, …) que serão substituídos por dados reais na geração. Espelha o "Cadastro de Certificados" do sistema legado, permitindo **copiar/colar o HTML antigo** (código-fonte) para não recriar do zero.

## Escopo
**Dentro (esta etapa):** página "Certificados" com duas abas — (1) **Modelos**: lista os modelos do catálogo e edita o HTML do certificado de cada um (código-fonte + pré-visualização); (2) **Imagens**: gerencia imagens usáveis nos certificados, servidas por URL pública. Migração que conserta a tabela `certificados` e reaproveita os 12 templates legados.
**Fora (próxima etapa):** geração automática do certificado na OS/laboratório (substituir os campos por dados reais, produzir o PDF e guardá-lo). Esta spec NÃO implementa geração.

## Descoberta de contexto
- A tabela `certificados` no banco novo já tem **12 templates** legados (HTML ~9.300 chars em `texto`), mas a FK ficou errada: `equipamento_cliente integer REFERENCES equipamentos_cliente(id)` quando deveria referenciar o **catálogo** `equipamentos(id)`. Os valores guardados são, na verdade, ids do catálogo legado e **todos os 12 casam com `equipamentos`** (ex.: 3→"Bafômetro Mark X - Plus", 48→"Iblow10 PRO") — 0 órfãos.
- Catálogo de modelos = `equipamentos` (44 itens). Storage de uploads = `app/core/storage.py` (volume `/data/uploads`); hoje servido só por endpoint autenticado.
- Já existe `app/api/certificados.py` (PDF do certificado **da OS** — não confundir). O novo recurso usa prefixos distintos (`/certificados-modelo`, `/certificado-imagens`).

## Decisões
- **1 certificado por modelo do catálogo** (`UNIQUE(equipamento)`).
- **Editor:** código-fonte HTML (textarea) + **pré-visualização** ao lado, renderizada em **`<iframe sandbox>`** (isola o HTML colado).
- **Imagens com URL pública:** upload protegido (Admin/Lab), mas leitura por endpoint **sem auth** para funcionar no `<img src>` da preview e do PDF.
- **Permissões:** escrita (salvar template, subir/excluir imagem) = **Administrador + Laboratório**; leitura = qualquer usuário interno.

## Banco — migração `0006_certificados_modelo`
1. **Conserta `certificados`:**
   - Adiciona `equipamento integer REFERENCES equipamentos(id)`.
   - Backfill: `UPDATE certificados SET equipamento = equipamento_cliente WHERE equipamento_cliente IN (SELECT id FROM equipamentos)` (os 12 casam todos).
   - Remove linhas que não casarem (não há, mas defensivo) e a coluna antiga `equipamento_cliente` (+ sua FK).
   - Dedup defensivo antes de `UNIQUE(equipamento)`: se houver mais de um por modelo, manter o de maior `id`.
   - Cria `UNIQUE(equipamento)`.
2. **Cria `certificado_imagens`:** `id serial PK`, `arquivo varchar(120) NOT NULL` (basename salvo no storage), `nome varchar(150)` (rótulo amigável), `datacad timestamptz`.
- Reversível (downgrade recria `equipamento_cliente` e dropa a tabela nova/constraint). Aplicar no banco real após dry-run + aprovação (protocolo do projeto).

## Backend
### Modelos
- `app/models/certificado_modelo.py` → `CertificadoModelo` (tabela `certificados`): `id`, `equipamento` (FK equipamentos), `descricao` (String 100), `texto` (Text). Property `equipamento_descricao` (via relationship lazy joined ao `Equipamento`).
- `app/models/certificado_imagem.py` → `CertificadoImagem` (tabela `certificado_imagens`): `id`, `arquivo`, `nome`, `datacad`. Property `url` (= `/certificado-imagens/arquivo/{arquivo}`).
- Registrar ambos em `app/models/__init__.py`.

### Schemas (`app/schemas/certificados_modelo.py`)
- `ModeloItem` (linha da lista): `equipamento` (id), `equipamento_descricao`, `tem_certificado: bool`.
- `ModeloListOut`: `{ items: list[ModeloItem] }` (ou lista simples).
- `CertificadoModeloOut`: `equipamento`, `equipamento_descricao`, `descricao`, `texto`.
- `CertificadoModeloIn`: `descricao: str | None`, `texto: str`.
- `ImagemOut`: `id`, `nome`, `arquivo`, `url`.

### Endpoints (`app/api/certificados_modelo.py`)
Escrita = `require_funcao("Administrador", "Laboratório")`; leitura = `get_current_usuario`. Público = sem dependência de auth.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/certificados-modelo?q=` | Lista os modelos do catálogo (`equipamentos`), com `tem_certificado`; busca por descrição. Ordena por descrição. |
| GET | `/certificados-modelo/{equipamento_id}` | Retorna o template do modelo (`texto`/`descricao`); 404 se o equipamento não existe; se ainda não há certificado, retorna `texto=""`. |
| PUT | `/certificados-modelo/{equipamento_id}` | Upsert do template (cria ou atualiza `texto`/`descricao`). 404 se o equipamento não existe. |
| GET | `/certificado-imagens` | Lista imagens (id, nome, arquivo, url). |
| POST | `/certificado-imagens` | Upload (multipart: file + nome?), valida via `storage.salvar_upload` (tipo imagem, ≤10MB), cria registro. |
| DELETE | `/certificado-imagens/{id}` | Remove registro + arquivo do storage. |
| GET | `/certificado-imagens/arquivo/{nome}` | **Público.** `FileResponse` do arquivo no storage. Anti path-traversal (usa só o basename). 404 se não existe. |

Registrar o router em `app/main.py`.

## Frontend — `frontend/src/app/certificados/`
- **`api.ts`** (`certificadosApi`): `listarModelos({q})`, `obterModelo(equipId)`, `salvarModelo(equipId, {descricao, texto})`, `listarImagens()`, `enviarImagem(file, nome?)`, `excluirImagem(id)`. Tipos `ModeloItem`, `CertificadoModelo`, `ImagemCert`. Constante `CAMPOS_CERTIFICADO` (lista de placeholders disponíveis com descrição).
- **`CertificadosPage.tsx`**: cabeçalho + **abas "Modelos" | "Imagens"** (estado local).
  - **Aba Modelos:** lista (busca) dos modelos do catálogo, cada linha com nome + selo "Com certificado/Sem certificado". Clicar abre o **editor** (mesma página ou sub-rota): à esquerda `textarea` de **código-fonte HTML** (monospace), à direita **pré-visualização** em `<iframe sandbox srcDoc={texto}>`; botão **Salvar**; um bloco com os **campos disponíveis** (chips copiáveis). Voltar à lista.
  - **Aba Imagens:** grade das imagens (miniatura via a URL pública), com **nome**, **URL + botão copiar** e **excluir**; botão **enviar imagem** (nome opcional).
- **Nav "Certificados"** na Sidebar, visível a Admin/Laboratório (gate `isAdmin || funcao === 'Laboratório'`). Ações de escrita gateadas igualmente.
- Rotas em `app/routes.tsx`: `certificados` (lista/abas) e, se usar sub-rota, `certificados/modelo/:equipamentoId` (ou editor inline na própria página — decisão de implementação, manter simples).

### Segurança da preview
- A pré-visualização usa `<iframe sandbox>` (sem `allow-scripts`) para renderizar o HTML colado isolado do app. Os `<img src>` apontam para a URL pública das imagens.

## Changelog
Entra como **v1.3.0** (novidade): "Cadastro de Certificados — modelos de certificado por aparelho (edição em HTML com pré-visualização) e biblioteca de imagens para usar nos certificados." (regra: toda mudança bumpa versão + entra no ChangelogModal.)

## Testes / verificação
- **Backend (pytest):** migração à parte (SQLite usa metadata); listar modelos com/sem certificado (flag correta), obter (vazio quando não há), upsert PUT (cria e depois atualiza), 404 equipamento inexistente, permissões (403 para função fora de Admin/Lab nas rotas de escrita; 200 leitura interno); imagens: upload cria registro+arquivo, listar, excluir remove arquivo, **GET público do arquivo responde sem token** e bloqueia path-traversal.
- **Frontend (vitest):** query/payloads do `certificadosApi`. Telas por `tsc`/lint/build. **E2E manual:** abrir Certificados → ver os 12 modelos com certificado → abrir um, ver o HTML legado + preview → salvar uma edição → aba Imagens: enviar uma imagem, copiar URL, abrir a URL pública.

## Critérios de aceite
- Existe nav "Certificados" (Admin/Lab). A aba Modelos lista os modelos do catálogo com selo de "tem certificado"; os 12 legados aparecem preenchidos. Editar mostra código-fonte + preview e salva (upsert). A aba Imagens permite enviar/listar/excluir e fornece URL pública que abre a imagem sem login.
- FK de `certificados` aponta para `equipamentos`; 12 templates remapeados; `UNIQUE(equipamento)`.
- Escrita restrita a Admin/Laboratório; leitura interna. pytest/vitest/tsc/lint/build verdes. Changelog v1.3.0. Sem geração de PDF (próxima etapa).
