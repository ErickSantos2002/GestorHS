# GestorHS

Sistema de gestão de calibração de equipamentos e ordens de serviço da **Health Safety**, substituindo por completo o sistema legado (SST/calibração de bafômetros). Reúne, num só lugar, o cadastro de clientes e da frota de aparelhos, o ciclo de vida da ordem de serviço (recebimento → laboratório → pós-vendas → retorno), a cobrança de recalibrações vencidas e um portal de autoatendimento para o cliente.

> Repositório: <https://github.com/ErickSantos2002/GestorHS>

---

## Visão geral

O produto é composto por **duas aplicações web sobre uma única API**:

| App | Público | Rota | Login |
|-----|---------|------|-------|
| **Interno** (`/app`) | Equipe da Health Safety | `/login` | usuário + senha |
| **Portal** (`/portal`) | Clientes | `/portal/login` | documento (CNPJ/CPF) + login + senha |

A equipe interna opera tudo (cadastros, frota, OS, cobrança); o cliente vê apenas os dados do **seu próprio CNPJ/CPF** (isolamento de tenant garantido pelo token, nunca por parâmetro de URL) e pode solicitar recalibrações.

### O ciclo de negócio

```
Aparelho vence  →  Cobrança alerta a equipe  →  Cliente solicita no portal
      →  Comercial atende  →  Expedição abre a OS quando o aparelho chega
      →  Laboratório calibra e emite certificado  →  Retorno ao cliente
```

### Fluxo da Ordem de Serviço (fases)

A OS avança linearmente por fases, cada uma de responsabilidade de uma função:

`Recebido (Expedição)` → `Laboratório (Laboratório)` → `Pós-Vendas (Comercial)` → `Preparando Retorno (Expedição)` → `Finalizada`
(com `Cancelada` como saída a qualquer momento)

Ao concluir a fase de laboratório, os dados de calibração (certificado, próxima calibração, etc.) são **espelhados** no registro da frota do cliente.

---

## Stack

**Backend** — Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic v2 · Alembic · PostgreSQL · JWT (python-jose) · Argon2 (passlib) · pytest

**Frontend** — React 19 · TypeScript 6 · Vite 8 · Tailwind CSS v4 (dark-first) · React Router 7 · Vitest + Testing Library

**Infra** — Docker / Docker Compose (a API em container; o PostgreSQL é remoto)

---

## Estrutura do repositório

```
GestorHS/
├── backend/                 # API FastAPI
│   ├── app/
│   │   ├── api/             # routers (auth, clientes, ordens, portal, dashboard, ...)
│   │   ├── core/            # config, security (JWT/hash), calibracao, os_workflow
│   │   ├── models/          # modelos SQLAlchemy (um por arquivo)
│   │   ├── schemas/         # schemas Pydantic
│   │   ├── scripts/         # criar_usuario.py (bootstrap de admin)
│   │   └── main.py          # app + registro dos routers
│   ├── alembic/             # migrações (0001 auth, 0002 OS, 0003 solicitações)
│   ├── tests/               # ~178 testes (pytest, SQLite in-memory)
│   ├── requirements.txt · pyproject.toml · Dockerfile · alembic.ini
│   └── .env.example
├── frontend/                # SPA React (apps /app e /portal)
│   ├── src/
│   │   ├── app/             # módulos internos (acesso, cadastros, clientes,
│   │   │                    #   frota, ordens, alertas, solicitacoes, dashboard)
│   │   ├── portal/          # portal do cliente (auth próprio + páginas)
│   │   ├── auth/            # AuthContext, ProtectedRoute, roles
│   │   ├── components/ui/   # design system
│   │   ├── layout/          # MainLayout, Sidebar, Topbar
│   │   └── lib/             # cliente de API (refresh single-flight), storage, utils
│   └── .env.example
├── docs/
│   ├── ROADMAP.md           # roadmap em fases
│   ├── DATABASE.md          # mapeamento do banco legado
│   ├── schema.sql           # schema novo
│   └── superpowers/         # specs e plans de cada fase
└── docker-compose.yml
```

---

## Como rodar

### Pré-requisitos
- Python 3.12+
- Node.js 20+
- Acesso a um PostgreSQL (local ou remoto)
- (Opcional) Docker Desktop

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate    |  Linux/Mac:  source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # e edite os valores (ver abaixo)
alembic upgrade head          # aplica as migrações no banco
uvicorn app.main:app --reload # API em http://localhost:8000  (docs em /docs)
```

Variáveis em `backend/.env`:

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | string de conexão (`postgresql+psycopg2://user:senha@host:porta/banco`) |
| `JWT_SECRET_KEY` | chave aleatória (≥32 bytes) para assinar os tokens |
| `JWT_ALGORITHM` | algoritmo JWT (padrão `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | validade do access token (padrão `30`) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | validade do refresh token (padrão `7`) |
| `BACKEND_CORS_ORIGINS` | origens liberadas no CORS (padrão inclui `http://localhost:5173`) |

> O arquivo `.env` **não é versionado** (está no `.gitignore`); use o `.env.example` como base.

**Criar o usuário admin inicial** (idempotente — re-rodar redefine a senha):

```bash
python -m app.scripts.criar_usuario admin <senha> Administrador
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env          # VITE_API_URL=http://localhost:8000
npm run dev                   # http://localhost:5173
```

### 3. Alternativa: Docker (só a API)

O `docker-compose.yml` na raiz sobe apenas a API com hot-reload (o PostgreSQL é remoto, configurado em `backend/.env`):

```bash
docker compose up -d          # sobe a API em http://localhost:8000
docker compose logs -f backend
docker compose down
```

---

## Testes

```bash
# Backend (pytest, banco SQLite em memória — não toca no Postgres)
cd backend && pytest -q

# Frontend (Vitest)
cd frontend && npm test          # ou: npm run test:watch

# Verificação completa do frontend
cd frontend && npm run lint && npx tsc -b --noEmit && npm run build
```

Cobertura atual: **~178 testes** de backend e **~140** de frontend.

---

## Autenticação & papéis

- **JWT** com par *access* (curto) + *refresh* (longo). O cliente de API do frontend renova o token automaticamente no 401 (refresh *single-flight*).
- **Senhas** com hash Argon2; senhas legadas foram invalidadas na migração.
- **Reset forçado no 1º acesso**: quando o admin cria/redefine uma senha, ela é temporária — o usuário define a sua na primeira entrada (internos e portal).
- **Papéis internos**: `Administrador`, `Expedição`, `Laboratório`, `Comercial Pós-Vendas`. As ações de escrita são gateadas por função (ex.: só Expedição/Admin abre OS; só Comercial/Admin registra cobrança e atende solicitações). Cada **fase** da OS aponta a função responsável por avançá-la.

---

## Módulos

**Interno (`/app`)**
- **Dashboard** — indicadores (vencidos, vencendo, solicitações pendentes, clientes a cobrar) + OS ativas por fase.
- **Acesso** — usuários internos, funções e troca de senha.
- **Cadastros** — setores, marcas, grupos, categorias, catálogo de equipamentos, funções e fases.
- **Clientes** — clientes, funcionários e usuários do portal.
- **Frota** — aparelhos por cliente, com status de calibração e histórico.
- **Ordens** — quadro kanban + lista, abertura/avanço/cancelamento e calibração/certificado.
- **Cobrança** — worklist de clientes com aparelhos vencidos/vencendo + registro de contato.
- **Solicitações** — atendimento das solicitações vindas do portal.

**Portal (`/portal`)**
- Início (resumo), minha frota, certificados, minhas OS e solicitar recalibração.

---

## Documentação

- `docs/ROADMAP.md` — roadmap por fases.
- `docs/DATABASE.md` — mapeamento do banco legado.
- `docs/schema.sql` — schema novo.
- `docs/superpowers/specs` e `docs/superpowers/plans` — especificação e plano de implementação de cada fase.
- API interativa: `http://localhost:8000/docs` (Swagger) com a API no ar.

---

## Status & próximos passos

O escopo **v1 está completo** (Fases 0 a 7) e em uso. Itens conscientemente adiados para versões futuras:

- Upload/armazenamento real de **fotos** do recebimento e de **PDF** de certificado (hoje o certificado é referenciado por URL/texto).
- **Financeiro** (valores, fretes, caixa) — colunas já existem no modelo, sem lógica/UI.
- **Notificações automáticas** (e-mail/WhatsApp) e **recuperação de senha por e-mail**.
- **CI** (lint + testes no GitHub Actions) e cancelamento de solicitação pelo cliente.
