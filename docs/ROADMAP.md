# GestorHS — Roadmap de Implementação

Roadmap para acompanhar a construção do GestorHS v1. Estrutura pensada para o **ClickUp**:

- **Fase** → uma *List* (ou *Milestone*).
- **Épico** → uma *Task*.
- **Tarefa** (`- [ ]`) → uma *Subtask* ou item de checklist.

**Esforço:** P = pequeno · M = médio · G = grande. **Dependências** indicadas por fase.

> O v1 entrega seis módulos: Cadastros base, Equipamentos do cliente, Ordens de Serviço, Calibração & Certificados, Alertas & Cobrança, Acesso & Portal. Veja o design completo em [docs/superpowers/specs/2026-06-01-gestorhs-design.md](superpowers/specs/2026-06-01-gestorhs-design.md).

---

## Fase 0 — Fundação técnica
*Destrava todo o resto. Nada visível ao usuário ainda.*

### Épico 0.1 — Base do frontend (G)
- [ ] Configurar Tailwind v4 (bloco `@theme`, tokens emerald, DM Sans) a partir do `DESIGN_SYSTEM.md`
- [ ] Aplicar overrides de base no `index.css` (inversão de texto no light, scrollbar, glow)
- [ ] Criar o helper `cn()` (clsx + tailwind-merge)
- [ ] Implementar dark mode (toggle + script anti-FOUC + `localStorage`)
- [ ] Montar o App Shell (`MainLayout`: sidebar colapsável + topbar)
- [ ] Configurar `react-router-dom` com as árvores `/app` e `/portal` (lazy-loaded)
- [ ] Implementar `AuthProvider` + `ProtectedRoute`
- [ ] Construir os componentes base (Button, Modal, Drawer, Input, Select, Table, StatCard, Badge, Toggle, Spinner)

### Épico 0.2 — Base do backend (G)
- [ ] Inicializar o projeto FastAPI com estrutura modular por domínio
- [ ] Configurar variáveis de ambiente e conexão com o PostgreSQL (porta 9998)
- [ ] Mapear os modelos SQLAlchemy 2 do schema migrado
- [ ] Criar os schemas Pydantic v2 (entrada/saída)
- [ ] Configurar o Alembic para migrações
- [ ] Habilitar a documentação OpenAPI/Swagger

### Épico 0.3 — Alterações de schema (M) — *depende de 0.2*
- [ ] Migração: `ordens.tipo_servico`, `condicao_chegada`, `acessorios`, `aceite`, `data_aceite`
- [ ] Migração: FK `fotos.os` → `ordens(id)`
- [ ] Migração: tabela `funcoes`, FK `usuarios.funcao`, coluna `fases.funcao_responsavel`
- [ ] Migração: tabela `solicitacoes`
- [ ] Migração: redefinir as fases (5 novas + Cancelada) com cores; mapear OS antigas para "Finalizada"

### Épico 0.4 — Autenticação (M) — *depende de 0.2, 0.3*
- [ ] Implementar JWT (access + refresh)
- [ ] Implementar hash de senha (bcrypt/argon2)
- [ ] Criar os endpoints de login (equipe e portal) e `GET /auth/me`
- [ ] Criar as dependências de autorização (público + função) por rota

### Épico 0.5 — DevOps e qualidade (M)
- [ ] Definir a estrutura do repositório (frontend, backend, docs)
- [ ] Configurar lint/format (ruff + black; eslint + prettier)
- [ ] Configurar CI básico (lint + testes)
- [ ] Escrever o `Dockerfile` / `docker-compose` para subir o ambiente
- [ ] Atualizar o `README` com instruções de setup

---

## Fase 1 — Acesso & Cadastros base
*Primeiro app utilizável: login + dados-mestre. Depende da Fase 0.*

### Épico 1.1 — Login e sessão (M)
- [ ] Tela de login da equipe (referência: seção 11 do `DESIGN_SYSTEM.md`)
- [ ] Armazenar token e tratar refresh/expiração
- [ ] Logout e proteção de rotas

### Épico 1.2 — Funções e permissões (M)
- [ ] CRUD de funções (Administrador, Expedição, Laboratório, Comercial Pós-Vendas)
- [ ] Atribuir função a usuário
- [ ] Configurar o mapa função → fase (tela do Administrador)
- [ ] Aplicar as permissões na navegação e nas ações

### Épico 1.3 — Usuários internos (P)
- [ ] CRUD de usuários internos (com função e permissões)

### Épico 1.4 — Cadastros (G)
- [ ] Clientes — lista, busca, detalhe e formulário
- [ ] Catálogo de equipamentos — CRUD
- [ ] Marcas, categorias e grupos — CRUD
- [ ] Funcionários do cliente — CRUD

---

## Fase 2 — Equipamentos do cliente
*A frota física e o status de calibração. Depende da Fase 1.*

### Épico 2.1 — Backend da frota (M)
- [ ] Endpoints de equipamentos do cliente (lista, detalhe, filtros)
- [ ] Calcular o status de calibração (em dia / vencendo 90 dias / vencido)
- [ ] Endpoint do histórico de movimentação

### Épico 2.2 — Frontend da frota (M)
- [ ] Lista da frota (filtro por cliente e por status)
- [ ] Detalhe do aparelho (série, patrimônio, datas, status, histórico)
- [ ] Atalhos para certificados e OS do aparelho

---

## Fase 3 — Ordens de Serviço
*O coração do sistema. Depende das Fases 1 e 2.*

### Épico 3.1 — Backend da OS (G)
- [ ] Modelo e endpoints de OS (lista, detalhe)
- [ ] Consulta do quadro (OS agrupadas por fase)
- [ ] Endpoint de avanço de fase (`POST /ordens/{id}/avancar`) validando a função responsável
- [ ] Registro de logs da OS (`logs_os`)
- [ ] Upload de fotos do recebimento, ligadas à OS

### Épico 3.2 — Quadro Kanban (M)
- [ ] Colunas por fase com cartões de OS (dados reais)
- [ ] Filtros e fila por função
- [ ] Abrir a OS a partir do cartão

### Épico 3.3 — Formulários-portão (G)
- [ ] Abrir OS → **Recebido** (equipamento, condição, acessórios, fotos)
- [ ] **Recebido → Laboratório** (encaminhamento)
- [ ] **Laboratório → Pós-Vendas** (tipo de serviço, resultados, certificado, manutenção)
- [ ] **Pós-Vendas → Preparando Retorno** (aceite do cliente)
- [ ] **Preparando Retorno → Finalizada** (rastreio + data de saída)
- [ ] **Cancelar** (motivo, a partir de qualquer fase)

### Épico 3.4 — Calibração e certificado (M) — *integra com 3.3*
- [ ] Capturar resultados (temperatura, pressão, testes, média, situação)
- [ ] Registrar nº do certificado e anexar o PDF
- [ ] Calcular a próxima calibração
- [ ] Espelhar o resultado no cadastro do equipamento e atualizar o vencimento

---

## Fase 4 — Alertas & Cobrança
*A worklist do Comercial. Depende das Fases 2 e 3.*

### Épico 4.1 — Backend de alertas (M)
- [ ] Consulta da worklist (vencendo/vencidos por cliente, priorizada)
- [ ] Endpoints de solicitações (`/solicitacoes`)
- [ ] Registrar "último contato" por aparelho/cliente

### Épico 4.2 — Frontend de cobrança (M)
- [ ] Painel da worklist (ranking, filtros)
- [ ] Tratar as solicitações vindas do portal
- [ ] Marcar contato realizado

---

## Fase 5 — Portal do Cliente
*A visão do cliente. Depende das Fases 2, 3 e 4.*

### Épico 5.1 — Backend do portal (M)
- [ ] Login e escopo por cliente
- [ ] Endpoints: minha frota, certificados, minhas OS
- [ ] Endpoint `POST /portal/solicitar-recalibracao` (gera solicitação)

### Épico 5.2 — Frontend do portal (M)
- [ ] Login do cliente e dashboard (indicadores + banner de vencidos)
- [ ] Minha frota (status + download de certificado)
- [ ] Minhas OS (acompanhamento das fases)
- [ ] Botão "Solicitar recalibração"

---

## Fase 6 — Migração final, QA & Go-live
*Virada do sistema antigo. Depende de todas as anteriores.*

### Épico 6.1 — Dados (M)
- [ ] Reexecutar e validar a migração (contagens e integridade)
- [ ] Migrar credenciais (redefinição forçada ou re-hash no primeiro login)

### Épico 6.2 — Qualidade (G)
- [ ] Testes ponta a ponta dos seis módulos
- [ ] Correção de bugs e ajustes de UX

### Épico 6.3 — Implantação (M)
- [ ] Provisionar o servidor (Docker, variáveis, HTTPS)
- [ ] Configurar backups do banco

### Épico 6.4 — Go-live (M)
- [ ] Rodar em paralelo com o hstracktest
- [ ] Treinar Expedição, Laboratório e Comercial Pós-Vendas
- [ ] Virar a chave e desativar o sistema antigo

---

## Itens fora do v1 (backlog futuro)
- [ ] Testes de campo (bafômetro em funcionários)
- [ ] Financeiro (valores, fretes, caixa)
- [ ] Galeria geral de mídia e documentos
- [ ] Disparo automático de mensagens (e-mail/WhatsApp)
- [ ] SSO com o TaskHS
- [ ] Geração automática do PDF do certificado
