# Aba "Certificados Gerais" com link público + QR — Design

**Data:** 2026-07-15
**Área:** backend (novo modelo/router/endpoint público + migração) e frontend (nova aba na página Certificados)

## Problema

Todo ano a Health Safety recebe um novo **certificado de gás** (documento único, geral) que é
impresso e distribuído — gastando muito papel. A equipe quer anexar esse certificado no
sistema, dar um nome, e gerar um **link público** (sem login) para o cliente baixar. Esse
link vira um **QR code**, que substitui a impressão em papel.

## Objetivo

Adicionar uma aba **"Gerais"** na página Certificados para anexar documentos PDF avulsos
(sem vínculo com cliente ou OS), cada um com nome e um link público assinado. A tela mostra
o link e o **QR code pronto para baixar**. Reaproveita o mecanismo de link público HMAC que
já existe para certificados de OS e nota fiscal.

## Não-objetivos

- Não vincular os certificados a cliente/OS (são gerais/compartilhados).
- Não versionar/substituir arquivo no mesmo item — renovação anual é um **item novo** (o
  histórico fica na lista; excluir remove de vez).
- Não aceitar outros formatos além de **PDF**.
- Não gerar o QR no backend — é gerado no frontend a partir do link.

## Arquitetura

Segue os padrões já existentes: `storage` para upload, `assinatura`/link-module para o HMAC,
`publico.py` para o download sem login, e uma aba na página Certificados como as outras.

### Backend

**Modelo `CertificadoGeral`** (`models/certificado_geral.py`, tabela `certificados_gerais`):
- `id` (PK)
- `nome` (String, not null) — ex.: "Certificado de Gás 2027"
- `arquivo` (String, not null) — basename do PDF salvo pelo `storage`
- `usuario` (FK `usuarios.id`, nullable) — quem anexou; property `usuario_nome`
- `data_upload` (DateTime)

Migração `0015_certificado_geral.py` cria a tabela.

**Storage:** subdir fixo `"certificados-gerais"`; `storage.salvar_upload(file, subdir=..., tipos_permitidos=storage.TIPOS_PDF)`. Limite 10 MB (padrão). Excluir remove o arquivo com `storage.remover_arquivo`.

**Link público** (`core/certificado_geral_link.py`):
- mensagem HMAC: `certgeral:{id}` (novo namespace, não colide com `cert:`/`nf:`).
- `assinar(id)` / `verificar(id, token)` delegando a `core/assinatura`.
- `link_certificado_geral(id) -> str | None`: `{CERT_PUBLIC_BASE_URL}/publico/certificado-geral/{id}?t={assinar(id)}`; retorna `None` se `CERT_PUBLIC_BASE_URL` vazio.

**Endpoint público** (novo em `api/publico.py`):
- `GET /publico/certificado-geral/{id}?t=…` — valida `certificado_geral_link.verificar`; carrega o registro; serve o PDF do disco via `FileResponse`, `Content-Disposition: inline`, `X-Content-Type-Options: nosniff`. 403 link inválido / 404 não encontrado.

**Router autenticado** (`api/certificados_gerais.py`, prefixo `/certificados-gerais`), registrado no `main.py`:
- `GESTOR_CERT_GERAL = ("Administrador", "Laboratório", "Qualidade")`.
- `POST ""` (multipart: `nome: Form(str)`, `arquivo: UploadFile`) — `require_funcao(*GESTOR_CERT_GERAL)`; valida nome não-vazio (422); salva via `storage`; cria o registro; **201** com o item serializado (inclui `link`).
- `GET ""` — qualquer `get_current_usuario`; lista `order_by(id.desc())`; cada item inclui `link` (via `link_certificado_geral`, pode ser `None`).
- `DELETE /{id}` — `require_funcao(*GESTOR_CERT_GERAL)`; remove arquivo + registro; 204/200.

**Schemas** (`schemas/certificado_geral.py`): `CertificadoGeralOut` (`id`, `nome`, `data_upload`, `usuario_nome`, `link: str | None`).

### Frontend

**Nova aba "Gerais"** em `CertificadosPage` (adicionar ao array `ABAS` e renderizar `CertificadosGeraisTab`).

**`CertificadosGeraisTab.tsx`:**
- **Anexar** (só quem tem permissão): campo **nome** + input de arquivo **PDF** (`accept="application/pdf"`); botão "Anexar certificado". Envia multipart.
- **Lista** (todos os usuários logados veem): nome, data, quem anexou; por item:
  - **Copiar link** (padrão do `ImagensTab.copiar` com `navigator.clipboard`).
  - **QR code**: gerado no front a partir do link (lib `qrcode` → data URL), exibido e com botão **Baixar QR** (baixa a imagem PNG).
  - **Excluir** (só permissão) com `window.confirm`.
- Se o `link` do item vier `null` (base pública não configurada), mostrar aviso "link público indisponível" no lugar do QR/copiar.

**`certificados/api.ts`:** `listarGerais()`, `enviarGeral(nome, file)` (FormData), `excluirGeral(id)`; tipo `CertificadoGeralItem` (`id`, `nome`, `data_upload`, `usuario_nome`, `link`).

**`auth/roles.ts`:** `podeGerenciarCertificadosGerais(user)` = admin || funcao ∈ {Laboratório, Qualidade}.

**QR:** dependência nova `qrcode` (gera no cliente, sem serviço externo). Confirmar compatibilidade com React 19/Vite 8 no plano (via context7 se preciso).

## Segurança

- Download só pelo link **HMAC** (`certgeral:{id}`) — sem token válido, 403. Mesmo esquema já em produção.
- PDF servido **inline** com `nosniff`. PDF-only elimina o risco de XSS por XML/HTML (diferente da nota fiscal, que aceita XML e por isso força `attachment`).
- Escrita (anexar/excluir) atrás de `require_funcao`; leitura da lista exige login interno. O **público** só alcança o download por link assinado, nunca a lista.
- `storage.salvar_upload` valida content-type (só PDF) e tamanho (10 MB); `caminho_arquivo` confina ao subdir (anti path traversal).

## Testes

- **Backend** (SQLite, espelhando `test_certificado_avulso`): POST cria e exige permissão (403 para função sem acesso); GET lista com `link`; DELETE remove arquivo+registro; link público **válido** baixa o PDF (200, `application/pdf`, inline) e **inválido/adulterado** dá 403; id inexistente 404.
- **Frontend** (Vitest): `api.ts` monta os paths certos; `roles` libera/bloqueia por função; a aba renderiza a lista e esconde "Anexar"/"Excluir" para quem não tem permissão. O QR pode ser testado de forma leve (mock da lib) ou deixado para verificação manual.

## Riscos

- **Nova dependência de QR**: escolher lib estável para React 19/Vite 8; gerar no cliente evita chamada externa (bom para o padrão de segurança do projeto).
- **`CERT_PUBLIC_BASE_URL` não setado** em algum ambiente → `link = None`; a UI trata (não quebra). Em produção já está configurado (usado pelos links de certificado no TaskHS).
