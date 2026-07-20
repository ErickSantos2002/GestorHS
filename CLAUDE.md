# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é

GestorHS é o sistema de gestão de calibração de equipamentos (bafômetros) e ordens de serviço da **Health Safety**, substituindo o sistema legado. São **duas aplicações web sobre uma única API**:

- **Interno** (`/app`) — equipe da Health Safety; login por usuário + senha.
- **Portal** (`/portal`) — clientes; login por documento (CNPJ/CPF) + login + senha; vê só os dados do próprio tenant.

O idioma do domínio é **português** — nomes de modelos, rotas, variáveis e mensagens são em PT-BR. Mantenha esse padrão ao escrever código novo.

## Comandos

### Backend (`backend/`, Python 3.12 · FastAPI · SQLAlchemy 2)
```bash
source .venv/bin/activate                       # venv local
pytest -q                                        # todos os testes (SQLite in-memory, não toca no Postgres)
pytest tests/test_ordens_avancar.py             # um arquivo
pytest tests/test_ordens_avancar.py::test_nome  # um teste
alembic upgrade head                             # aplica migrações no Postgres (DATABASE_URL no .env)
alembic revision -m "descricao"                  # nova migração
uvicorn app.main:app --reload                    # API em :8000 (Swagger em /docs)
python -m app.scripts.criar_usuario admin <senha> Administrador   # bootstrap de admin (idempotente)
python -m app.scripts.enviar_atrasados_growthhs                   # SIMULA a carga de vencidos (padrao: nao envia)
python -m app.scripts.enviar_atrasados_growthhs --enviar          # carga real no GrowthHS (ver aviso abaixo)
python -m app.scripts.enviar_vencendo_growthhs --dry-run          # SIMULA o job diario dos 50 dias
python -m app.scripts.enviar_vencendo_growthhs                    # job diario real (agendado por cron)
```

> ⚠️ **`enviar_atrasados_growthhs` nao envia nada sem `--enviar`.** A chave do card e
> `{cliente_id}:{data_da_carga}`, entao rodar a carga em **duas datas diferentes cria um card
> duplicado por cliente** — e o GrowthHS nao expoe leitura para o script detectar isso. Rode
> sem a flag primeiro, confira o resumo e o CSV de pendencias, e so entao use `--enviar`.

> ℹ️ **`enviar_vencendo_growthhs` ENVIA por padrao** (use `--dry-run` para simular) — o inverso
> do script de atrasados, de proposito. A chave e `{equipamento_cliente_id}:{prox_calibragem}`,
> que **nao muda com a data da execucao**, entao repetir devolve `created: false` e nao duplica;
> alem disso e um job de cron, e um default que nao envia viraria um agendamento inutil em
> silencio. Operacao e agendamento em [docs/operacao-growthhs-cron.md](docs/operacao-growthhs-cron.md).

### Frontend (`frontend/`, React 19 · TS · Vite 8 · Tailwind v4)
```bash
npm run dev                              # :5173
npm test                                 # vitest run (todos)
npx vitest run src/lib/api.test.ts       # um arquivo
npm run lint                             # eslint
npm run build                            # tsc -b && vite build (checagem de tipos + build)
```

Verificação completa antes de commitar frontend: `npm run lint && npx tsc -b --noEmit && npm run build`.

### Docker
`docker compose up -d` na raiz sobe **só a API** com hot-reload (o PostgreSQL é remoto, configurado em `backend/.env`).

## Arquitetura

### O ciclo de negócio e o workflow da OS
A Ordem de Serviço avança **linearmente** por fases, cada uma de responsabilidade de uma função. O grafo de transições está centralizado e puro (sem I/O) em [backend/app/core/os_workflow.py](backend/app/core/os_workflow.py):

```
Recebido(4) → Laboratório(5) → Pós-Vendas(6) → Preparando Retorno(7) → Finalizada(8)
```
Com `Cancelada(9)` como saída a qualquer momento. As fases são IDs fixos (`FASE_RECEBIDO=4`, `FASE_FINALIZADA=8`, etc.); use as constantes e `proxima_fase()`/`eh_ativa()` em vez de hard-codar números.

Ao concluir o laboratório, os dados de calibração são **espelhados** no registro da frota do cliente (`equipamento_cliente`/`historico_equipamento`).

### Autorização (dois mundos de token)
[backend/app/api/deps.py](backend/app/api/deps.py) define a autorização. O JWT carrega `tipo` (`usuario` interno vs `cliente` portal) e `token_use` (`access`/`refresh`):
- `get_current_usuario` / `get_current_cliente` — separam os dois públicos; o token do cliente também valida o campo `cliente` (isolamento de tenant **pelo token, nunca por parâmetro de URL**).
- `require_funcao("Administrador", "Expedição", ...)` — gateia escrita por função interna. Os nomes das funções são strings em PT-BR (ex.: `"Comercial Pós-Vendas"`).

No frontend, o espelho dessas regras está em [frontend/src/auth/roles.ts](frontend/src/auth/roles.ts) (`podeAbrirOS`, `podeAtenderSolicitacao`, etc.) — ao adicionar uma regra de função, atualize **os dois lados**.

### Certificados (área mais ativa do código)
A geração de certificado é o subsistema mais elaborado:
- [backend/app/core/certificado_gerar.py](backend/app/core/certificado_gerar.py) — motor que monta o contexto a partir da OS e substitui tokens `[campo]` no HTML do modelo. A lista `CAMPOS` define os tokens suportados (nomes batem com o legado, com aliases amigáveis).
- **Overrides por OS**: a coluna `ordens.cert_overrides` (JSON, migração `0008`) guarda ajustes de campos válidos só para aquela OS. `montar_contexto` sobrepõe esses overrides sem alterar o cadastro do cliente/aparelho. O endpoint `certificado-campos` ([certificados_os.py](backend/app/api/certificados_os.py)) entrega os campos pré-preenchidos e editáveis; o modal do frontend grava os overrides ao gerar/regerar.
- Certificado pode ser gerado em **qualquer OS pós-laboratório (fases 5–8)**, inclusive sob demanda em OS antigas.
- [certificado_pdf.py](backend/app/core/certificado_pdf.py) gera o PDF; [storage.py](backend/app/core/storage.py) lida com upload de imagens/PDF (limite 10 MB; `UPLOAD_DIR` em config).

`status_calibracao()` em [calibracao.py](backend/app/core/calibracao.py) classifica a próxima calibração (`sem_data`/`vencido`/`vencendo`/`em_dia`, janela padrão 90 dias) — reutilize-o em vez de recalcular.

### Integracao com o TaskHS
A cada abrir/avancar/cancelar de OS, o GestorHS espelha a OS como um card no board `Servico` do TaskHS ([app/core/taskhs.py](backend/app/core/taskhs.py) puro + [app/integrations/taskhs_client.py](backend/app/integrations/taskhs_client.py) I/O, disparado via `BackgroundTasks` best-effort). Nasce desligada: sem `TASKHS_BASE_URL`/`TASKHS_API_KEY` eh no-op. Backfill: `python -m app.scripts.sincronizar_taskhs`.

O card leva uma descricao que cresce por fase (cabecalho + secoes Recebido/Laboratorio/Pos-Vendas/Preparando Retorno/Finalizada) e, na secao de Laboratorio, um link publico de download do certificado (`/publico/certificado/...`, token HMAC sem login, via `app/core/certificado_link.py` e `app/api/publico.py`; base em `CERT_PUBLIC_BASE_URL`).

### Cliente de API do frontend
[frontend/src/lib/api.ts](frontend/src/lib/api.ts) centraliza todo o acesso HTTP:
- **Refresh single-flight**: renova o token automaticamente no 401, com uma única promise compartilhada (`refreshOnce`) para evitar múltiplos refreshes concorrentes.
- **URL da API em camadas**: `window.__API_URL__` (injetado em runtime via `/config.js` em produção, sem rebuild) → `VITE_API_URL` (build) → `http://localhost:8000`.

### Convenções de estrutura
- **Backend**: um arquivo por modelo em `models/`, schemas Pydantic em `schemas/`, routers em `api/` (registrados manualmente em [main.py](backend/app/main.py) — ao criar um router novo, adicione o `include_router`). Lógica de negócio pura vai em `core/` (sem I/O, testável isolada).
- **Frontend**: módulos por domínio em `src/app/<modulo>/` (acesso, cadastros, clientes, frota, ordens, alertas, solicitacoes, dashboard, certificados, caixas); portal separado em `src/portal/`; design system em `src/components/ui/`. Rotas em [src/app/routes.tsx](frontend/src/app/routes.tsx) e [src/App.tsx](frontend/src/App.tsx) (árvores `/app` e `/portal` lazy-loaded).
- **Testes**: backend usa SQLite in-memory (`conftest.py`), espelhando o nome do alvo (`test_<modulo>.py`). Frontend usa Vitest + Testing Library, com `*.test.ts(x)` ao lado do arquivo.

### Changelog visível ao usuário
O changelog exibido na sidebar do app é **editado à mão** em [frontend/src/app/changelog/data.ts](frontend/src/app/changelog/data.ts) (ordem decrescente, versão mais nova primeiro; a primeira entrada vira a versão atual). Atualize-o ao concluir uma release com mudanças visíveis ao usuário.

## Commits & versionamento

**Convenção de commit** (Conventional Commits, em **português sem acentos** — mensagens em ASCII):
```
tipo(escopo): descricao curta no imperativo
```
- **Tipos** usados: `feat`, `fix`, `docs`, `refactor` (mudança interna sem alterar comportamento — ex.: remover duplicação, extrair util).
- **Escopos** comuns: `cert`, `frota`, `ux`, `ui`, `changelog`, `plan`, `spec` (use o módulo/área afetada).
- Assunto de **uma linha só** — sem corpo e **sem trailer de co-autor**. Para nota de versão pode usar travessão `—` (ex.: `docs(changelog): v1.5.0 — certificado com campos editaveis por OS`).

**Fluxo de uma entrega** (do menor ao maior commit):
1. `docs(spec): ...` — especificação (em `docs/superpowers/specs/`).
2. `docs(plan): ...` — plano de implementação (em `docs/superpowers/plans/`).
3. `feat(...)`/`fix(...)` — um ou mais commits, geralmente backend → frontend.
4. `docs(changelog): vX.Y.Z — ...` — fecha a release; **bump da versão em [data.ts](frontend/src/app/changelog/data.ts)** (a primeira entrada é a versão atual).

**Branches & push**: fases grandes vão em branch `feat/<nome>` e entram na `main` por commit de merge no formato `merge: <descricao> (vX.Y.Z) — <detalhe>`. Trabalho incremental menor é commitado direto na `main`. `push.autoSetupRemote=true` está ativo. **Só faça commit/push quando o Erick pedir.**

## Ferramentas do Claude Code (plugins instalados)

Esta máquina tem plugins do Claude Code que ampliam o que está disponível — use-os quando couber:

- **superpowers** — fluxo de desenvolvimento dirigido por skills. É a origem dos `docs/superpowers/specs/` e `plans/`. Use `brainstorming` antes de desenhar feature, `writing-plans` para planejar, `test-driven-development` ao implementar e `verification-before-completion` antes de afirmar que algo está pronto.
- **context7** (MCP) — puxa documentação **atualizada** de libs direto da fonte. Use ao mexer com as versões de ponta do projeto (React 19, Tailwind v4, Vite 8, SQLAlchemy 2, Pydantic v2) em vez de confiar na memória.
- **LSP** (Pyright + TypeScript) — inteligência de código real: `hover`, `goToDefinition`, `findReferences`, `documentSymbol`. Prefira o LSP a varrer arquivos no escuro ao navegar tipos/símbolos. Requer os binários `pyright-langserver` e `typescript-language-server` no PATH (via npm).
- **code-review** — revisão automatizada do diff (espelha a skill `/code-review`); use antes de fechar uma feature.
- **semgrep** + **Security Guidance** — varredura estática de vulnerabilidades e guia de libs seguras. Relevante aqui por causa de JWT, isolamento de tenant e upload de arquivos.
- **commit-commands** — `commit` / `commit-push-pr` seguindo a convenção (lembrar: PT-BR sem acentos, uma linha — ver seção acima).
- **playwright** (MCP) — automação de browser / E2E (login, abrir OS, gerar certificado) quando precisar validar fluxo ponta a ponta.
- **frontend-design** / **skill-creator** — design de UI nova e criação de skills próprias do projeto.
- **gh** (GitHub CLI) — autenticado; usado por `commit-push-pr` para abrir PRs (branches `feat/<nome>`).

## Migrações Alembic
Migrações já aplicadas (`0001`–`0008`) cobrem auth, schema de OS, solicitações, caixas, certificados (modelo, por-OS) e cert_overrides. Cada migração tem um propósito único e nomeado — siga o padrão `NNNN_descricao.py`.
