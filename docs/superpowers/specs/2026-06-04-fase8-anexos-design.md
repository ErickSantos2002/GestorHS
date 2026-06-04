# GestorHS — Fase 8 (Anexos: fotos da OS + PDF de certificado)

**Data:** 2026-06-04
**Status:** Aprovado para implementação
**Motivação:** Fechar duas divergências roadmap↔código herdadas: (1) fotos do recebimento da OS — a coluna `fotos.os` existe (migração 0002) mas não há modelo/endpoint/UI; (2) PDF do certificado — hoje `ordens.pdf_certificado` é só um texto/URL, sem upload real. Habilita a primeira versão de produção a guardar e servir arquivos de verdade.
**Depende de:** Fase 3 (`Ordem`/`Fase`, fluxo da OS, `AvancarModal`, `OrdemDetailPage`), Fase 5B (portal de certificados), auth (`get_current_usuario`/`require_funcao`/`get_current_cliente`).
**Decisão de armazenamento (do usuário):** disco local + volume persistente. Em produção (EasyPanel) o volume é montado em `/data/uploads` e a env `UPLOAD_DIR=/data/uploads`. Em dev/testes o default é `uploads/` (relativo).

---

## 1. Objetivo

Permitir anexar arquivos à OS e servi-los com autenticação: **fotos** no recebimento (várias por OS) e **PDF de certificado** na calibração. Tudo gravado em disco sob `UPLOAD_DIR`, servido por endpoints autenticados (nunca arquivos públicos), preservando o isolamento de tenant do portal.

## 2. Escopo

**Dentro:**
- Camada de storage compartilhada (`app/core/storage.py` + setting `UPLOAD_DIR`), validando tipo e tamanho.
- 8A — Fotos da OS: modelo `Foto`, endpoints de upload/listar/servir/excluir, seção de fotos no detalhe da OS.
- 8B — PDF de certificado: upload/servir o PDF da OS (interno) + download no portal (tenant-scoped); UI no detalhe da OS e na página de certificados do portal.
- `python-multipart` no `requirements.txt`; `UPLOAD_DIR` no `.env.example`; volume local no `docker-compose.yml`.

**Fora:**
- Migrar os ~19.696 arquivos legados de `fotos` (não temos os binários no repo; exige os arquivos originais + migração de binários — esforço à parte).
- Geração automática de PDF; thumbnails/resize/compressão; antivírus; CDN.
- Anexos genéricos fora da OS (documentos do equipamento etc.).

**Sem migração de banco:** a coluna `fotos.os` e a tabela `fotos` já existem; o PDF guarda só o nome curto do arquivo (cabe em `pdf_certificado VARCHAR(50)`).

## 3. Contexto do código atual

- **Backend:** routers em `app/api/` registrados em `main.py`; `Ordem` (`cliente`, `fase`, `pdf_certificado` String(50), props `cliente_nome`/`fase_descricao`); tabela `fotos` = `id, cliente, codigo, cor, tipo, posicao, arquivo varchar(50), legenda varchar(250)` + `os` (FK ordens, da 0002). `pdf_certificado` é setado no branch lab do `POST /ordens/{id}/avancar` (`ordens.py`/`ordens_acoes.py`) e lido em `portal.py` (certificados via outerjoin `equipamentos_cliente.os_atual→ordens.pdf_certificado`). Settings em `app/core/config.py` (pydantic-settings, campos sem default exigidos). `require_funcao(*)`, `get_current_usuario`, `get_current_cliente` em `deps.py`. `excluir_protegido` em `cadastros_common.py`. Testes pytest/SQLite (conftest com `client`, `db_session`, `usuario_admin`, `usuario_comum`(Expedição), `usuario_lab`(Laboratório), `fases_seed`, `os_base`, `cliente_portal`).
- **Frontend:** `app/ordens/OrdemDetailPage.tsx` (detalhe só-leitura + botões de ação + timeline; busca `/fases`), `AvancarModal.tsx` (modo calibração no passo lab, com campo texto de PDF), `ordens/api.ts` (`ordensApi`); `portal/PortalCertificadosPage.tsx` + `portal/api.ts` (`portalApi.certificados`; hoje abre o PDF como link se a string começa com `http`). `apiJson`/`apiFetch` em `lib/api.ts` (anexa Bearer; refresh single-flight). Componentes `Button/Modal/Spinner/Badge/Input`.

## 4. Camada de armazenamento (`app/core/storage.py`)

- Setting novo em `config.py`: `UPLOAD_DIR: str = "uploads"` (com default — não quebra testes/CI).
- Constantes: `MAX_UPLOAD_BYTES = 10 * 1024 * 1024`; `TIPOS_IMAGEM = {"image/jpeg","image/png","image/webp"}`; `TIPOS_PDF = {"application/pdf"}`; mapa de extensão por content-type.
- `salvar_upload(file: UploadFile, *, subdir: str, tipos_permitidos: set[str]) -> str`:
  - valida `file.content_type ∈ tipos_permitidos` (senão 415/400), lê o conteúdo respeitando `MAX_UPLOAD_BYTES` (senão 413), gera `nome = uuid4().hex[:16] + ext`, garante `UPLOAD_DIR/subdir/` (mkdir parents), grava, retorna **só o basename** `nome` (cabe em VARCHAR(50)).
- `caminho_arquivo(subdir: str, basename: str) -> Path` → `UPLOAD_DIR/subdir/basename` (resolve e valida que está sob `UPLOAD_DIR` — anti path traversal).
- `remover_arquivo(subdir: str, basename: str) -> None` (ignora se não existir).
- Validação levanta exceções próprias (`ArquivoInvalido`) que os routers convertem em `HTTPException` (400/413/415).

## 5. 8A — Fotos da OS

### 5.1 Modelo (`app/models/foto.py`) + export no `__init__`
`Foto` → tabela `fotos`: `id`, `os` (FK ordens), `cliente`, `arquivo` (basename), `legenda`, `posicao`, `tipo`, `codigo`, `cor` (mapear as colunas existentes; só usamos `os`/`cliente`/`arquivo`/`legenda` na feature). Sem novas colunas.

### 5.2 Schemas (`app/schemas/fotos.py`)
- `FotoOut { id: int, os: int, arquivo: str, legenda: str | None, url: str }` (`url` = `/ordens/{os}/fotos/{id}/arquivo`).

### 5.3 Endpoints (`app/api/fotos.py`, router sem prefixo, registrado em `main.py`)
- `POST /ordens/{ordem_id}/fotos` — `require_funcao("Expedição","Administrador")`; `UploadFile` + `legenda: str | None = Form(None)`; 404 se OS não existe; `salvar_upload(subdir=f"os/{ordem_id}", tipos=TIPOS_IMAGEM)`; cria `Foto(os=ordem_id, cliente=ordem.cliente, arquivo=basename, legenda=...)`; 201 `FotoOut`.
- `GET /ordens/{ordem_id}/fotos` — `get_current_usuario`; lista as fotos da OS (`order_by id`), retorna `list[FotoOut]`.
- `GET /ordens/{ordem_id}/fotos/{foto_id}/arquivo` — `get_current_usuario`; 404 se a foto não é da OS; `FileResponse(caminho_arquivo(f"os/{ordem_id}", foto.arquivo))` com media_type pela extensão; 404 se o arquivo sumiu do disco.
- `DELETE /fotos/{foto_id}` — `require_funcao("Expedição","Administrador")`; remove o registro e o arquivo (`remover_arquivo`); 204.

### 5.4 Frontend
- `ordens/api.ts`: tipo `Foto { id, os, arquivo, legenda, url }`; `fotosApi.listar(ordemId)` (`GET /ordens/{id}/fotos`), `enviar(ordemId, file, legenda?)` (POST multipart — usar `apiFetch` com `FormData`, **sem** `Content-Type` manual), `excluir(fotoId)` (`DELETE /fotos/{id}`). A `url` é relativa à API; o `<img>` precisa do host + Bearer → como imagens não mandam header, servir via `apiFetch`→`blob()`→`URL.createObjectURL` num componente de imagem autenticada (`FotoImg`), ou expor a imagem por blob. (Decisão: componente `FotoImg` que busca via `apiFetch` e renderiza `objectURL`.)
- `OrdemDetailPage`: seção **"Fotos"** — grid de miniaturas (`FotoImg`), botão "Enviar foto" (input file, gated `podeAbrirOS`/Expedição-Admin) com legenda opcional, excluir por foto (confirm). Spinner/erro.

### 5.5 Testes 8A (pytest)
- Upload 201 grava `Foto` + arquivo no disco (usar `tmp_path` via override de `settings.UPLOAD_DIR`/monkeypatch); `GET` lista; `GET .../arquivo` devolve 200 com bytes; `DELETE` 204 e some da lista + arquivo apagado.
- 415/400 em content-type não-imagem; 413 acima do limite; 404 OS/ foto inexistente.
- 403: `usuario_comum`? (Expedição é o `usuario_comum` do conftest — usar `usuario_lab` como não-autorizado) em POST/DELETE; GET liberado a qualquer interno.

## 6. 8B — PDF de certificado

### 6.1 Endpoints internos (`app/api/ordens.py` ou novo `certificados.py`)
- `POST /ordens/{ordem_id}/certificado` — `require_funcao("Laboratório","Administrador")`; `UploadFile` PDF; 404 OS; `salvar_upload(subdir=f"certificados/{ordem_id}", tipos=TIPOS_PDF)`; se já havia PDF enviado (basename, não-URL), remove o antigo; grava o **basename** em `ordem.pdf_certificado`; commit; retorna `OrdemDetalhe` (ou `{pdf_certificado}`).
- `GET /ordens/{ordem_id}/certificado` — `get_current_usuario`; 404 se sem `pdf_certificado`; se o valor começa com `http` → `RedirectResponse` (URL legada/manual); senão `FileResponse(caminho_arquivo(f"certificados/{ordem_id}", pdf), media_type="application/pdf")` (404 se sumiu).

### 6.2 Endpoint do portal (tenant-scoped) (`app/api/portal.py`)
- `GET /portal/certificados/{ordem_id}` — `get_current_cliente`; 404 se a OS não existe **ou não é do cliente** (`Ordem.cliente == cli.cliente`); mesma lógica de servir (URL→redirect; arquivo→FileResponse). Isolamento de tenant aqui é obrigatório.

### 6.3 Frontend
- `ordens/api.ts`: `certificadoApi.enviar(ordemId, file)` (POST multipart) e helper de URL de download interno (`/ordens/{id}/certificado`). No `OrdemDetailPage` (e/ou `AvancarModal` passo lab): botão "Enviar certificado (PDF)" (gated Laboratório/Admin) e, se houver `pdf_certificado`, botão "Baixar certificado" (abre via `apiFetch`→blob, pois precisa de Bearer). Mantém compatibilidade: se `pdf_certificado` for URL http, "Baixar" só abre o link.
- `portal/api.ts`: `portalApi.baixarCertificado(ordemId)` (via `apiFetch`→blob). `PortalCertificadosPage`: botão "Baixar certificado" quando houver PDF, apontando para `/portal/certificados/{ordem_id}` (em vez de só linkar `http`). O item de certificado precisa expor o `ordem_id` (a `os_atual`) — ajustar `PortalCertItem` se necessário para trazer o id da OS.

### 6.4 Testes 8B (pytest)
- Upload PDF 201 grava arquivo + seta `pdf_certificado` (basename); reenvio substitui (remove o antigo); 415 em não-PDF; 413 acima do limite; 404 OS.
- `GET /ordens/{id}/certificado`: 200 com bytes para arquivo; redirect (3xx) quando `pdf_certificado` é URL http; 404 sem PDF.
- Portal `GET /portal/certificados/{id}`: 200 para OS do próprio cliente; **404 para OS de outro cliente** (tenant); 401 sem token de portal.
- 403: não-Laboratório/Admin no upload.

## 7. Verificação / E2E
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos.
- **E2E:** numa OS de teste, enviar 1–2 fotos (recebimento) e vê-las no detalhe; excluir uma. Enviar um PDF de certificado, baixar pelo interno; logar no portal do cliente dono e baixar o mesmo certificado; confirmar que outro cliente não acessa (tenant). Limpar os dados/arquivos de teste ao fim. (Os uploads de teste vão para `UPLOAD_DIR` local.)

## 8. Critérios de aceite
- É possível anexar fotos a uma OS (Expedição/Admin), listá-las e excluí-las; as imagens são servidas só com autenticação.
- É possível enviar um PDF de certificado (Laboratório/Admin); interno baixa; o cliente dono baixa pelo portal; cliente diferente recebe 404; URLs legadas continuam abrindo.
- Tipos inválidos (não-imagem / não-PDF) e arquivos acima de 10 MB são rejeitados (400/413/415).
- Sem migração de banco. `python-multipart` adicionado. `UPLOAD_DIR` documentado (`.env.example`) e com volume local no compose.
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos; E2E ok.

## 9. Notas de deploy (EasyPanel)
- Volume persistente já criado: montagem `/data/uploads`; env `UPLOAD_DIR=/data/uploads`. Backup pelo "Criar Backup de Volume". O default do código (`uploads/`) só vale fora de produção.
