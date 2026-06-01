# GestorHS — Documento de Design

**Data:** 2026-06-01
**Status:** Aprovado para implementação
**Substitui:** sistema legado *hstracktest*

---

## 1. Objetivo

O GestorHS gere os bafômetros que a Health Safety vende: cadastra os aparelhos, guarda seus certificados, controla as datas de calibração e conduz as Ordens de Serviço quando um aparelho chega para calibrar ou consertar.

O sistema resolve dois problemas de negócio:

1. **Vencimento de calibração.** Um bafômetro fora da validade não tem valor legal. O GestorHS sabe quando cada aparelho vence e entrega ao Comercial uma lista de quem cobrar — hoje a base tem **5.037 aparelhos vencidos**.
2. **Controle da Ordem de Serviço.** Quando um aparelho chega, ele passa por três times (Expedição, Laboratório, Comercial Pós-Vendas) até voltar calibrado ao cliente. O GestorHS rastreia cada etapa.

## 2. Contexto

O banco legado tinha 90 tabelas, sem chaves estrangeiras, misturando três sistemas (`hs`, `pgs`, `inf`). Já migramos a família `hs` para um schema novo e limpo: **33 tabelas, 140.460 registros**, em PostgreSQL 17 (porta 9998, banco `gestorhs-banco`). O GestorHS substitui o sistema antigo por completo — não integra com ele.

Dados-âncora da migração:

| Entidade | Registros |
|---|---|
| Clientes | 1.833 |
| Equipamentos do cliente (aparelhos físicos) | 8.548 |
| Ordens de Serviço | 10.168 |
| Catálogo de equipamentos | 44 |
| Logs de OS | 80.377 |

## 3. Princípios de design

- **Reaproveitar o design system do TaskHS.** O sistema irmão já define a linguagem visual (`DESIGN_SYSTEM.md`). O GestorHS nasce com a mesma cara.
- **Substituição total, não integração.** Preservamos os dados; descartamos o código e as convenções antigas.
- **Módulos pequenos e bem delimitados.** Cada domínio expõe uma interface clara e se entende sozinho.
- **A API manda na permissão.** Esconder uma rota no frontend não é segurança; o servidor autoriza cada requisição.

## 4. Arquitetura

### 4.1 Visão geral

```
┌─────────────────────────────┐         ┌──────────────────────────┐
│  Frontend SPA (React + TS)  │  HTTPS  │   Backend FastAPI         │
│  Vite + Tailwind v4         │ ──REST→ │   SQLAlchemy 2 · Pydantic │
│  /app  (equipe)             │ ←JSON── │   módulos por domínio     │
│  /portal (cliente)          │         │   JWT · OpenAPI           │
└─────────────────────────────┘         └────────────┬─────────────┘
                                                      │
                                              ┌───────▼────────┐
                                              │  PostgreSQL 17 │
                                              │  porta 9998    │
                                              └────────────────┘
```

### 4.2 Frontend

- **Stack:** React 19 + TypeScript + Vite + **Tailwind CSS v4** (config CSS-first via `@theme`), fonte **DM Sans**, marca **emerald `#10b981`**, **dark-first**.
- **Design system:** portado do TaskHS (`DESIGN_SYSTEM.md`). Sem biblioteca de UI; ícones SVG inline; `cn()` (clsx + tailwind-merge) como único utilitário de classes.
- **Roteamento:** `react-router-dom` v7. Um app, duas árvores de rota carregadas sob demanda (lazy):
  - `/app/*` — aplicativo interno da equipe.
  - `/portal/*` — portal do cliente.
  - O cliente baixa apenas o código do portal.
- **Shell:** sidebar colapsável + topbar (padrão `MainLayout` do TaskHS), `AuthProvider` + `ProtectedRoute`.
- **Kanban:** `@dnd-kit` para o quadro de OS (visualização), mas o avanço de fase ocorre por formulário, não por arrastar.

### 4.3 Backend

- **Stack:** FastAPI (Python), **SQLAlchemy 2** (ORM), **Pydantic v2** (validação), **Alembic** (migrações).
- **Estrutura:** monólito modular, um pacote por domínio:
  - `cadastros` — clientes, catálogo, marcas, categorias, grupos, funcionários.
  - `equipamentos` — frota do cliente e status de calibração.
  - `ordens` — Ordens de Serviço e workflow.
  - `calibracao` — resultados e certificados.
  - `alertas` — worklist de cobrança.
  - `acesso` — usuários, funções, autenticação, portal.
- **API:** REST/JSON, documentada automaticamente (OpenAPI/Swagger).

### 4.4 Autenticação e autorização

- **Mecanismo:** JWT (token de acesso + refresh).
- **Senhas:** hash com bcrypt ou argon2. O legado guardava senha em texto puro (`varchar(12)`); na migração de credenciais, forçamos redefinição ou re-hash no primeiro login.
- **Dois públicos:**
  - **Funcionários** (`usuarios`) — acessam `/app`, têm uma **função** (papel).
  - **Clientes** (`usuarios_cliente`) — acessam `/portal`, escopados ao próprio cliente.
- A API valida o público e a função em cada rota.

## 5. Modelo de domínio

O fluxo central — a espinha do sistema:

```
Cliente ──< Equipamento do cliente ──< Ordem de Serviço ──> Calibração ──> Certificado
```

- **Cliente** possui muitos **equipamentos do cliente** (aparelhos físicos, com série e patrimônio).
- Cada **equipamento do cliente** referencia um tipo do **catálogo de equipamentos**.
- Uma **Ordem de Serviço** processa um equipamento do cliente e produz uma **calibração** (com resultados) e um **certificado**.
- O resultado da última OS **espelha** no cadastro do equipamento (última/próxima calibração).

## 6. Módulos do v1

### 6.1 Cadastros base
CRUD de clientes, catálogo de equipamentos, marcas, categorias, grupos e funcionários do cliente. É a fundação dos demais módulos.

### 6.2 Equipamentos do cliente
Gere a frota física de cada cliente: série, patrimônio, datas de compra e calibração, status (Ativo/Inativo/Manutenção) e histórico de movimentação. Calcula o status de calibração de cada aparelho: **em dia**, **vencendo** (próximos 90 dias) ou **vencido**.

### 6.3 Ordens de Serviço
O coração operacional. Quadro kanban como visão geral; avanço por formulário-portão. Detalhado na seção 7.

### 6.4 Calibração e Certificados
Captura os resultados da calibração dentro da OS (temperatura, pressão, três testes, média, situação), registra o número e o PDF do certificado e calcula a próxima calibração. Ao concluir, espelha o resultado no cadastro do equipamento.

### 6.5 Alertas e Cobrança
Entrega ao Comercial Pós-Vendas uma **worklist priorizada** de aparelhos vencendo ou vencidos, agrupada por cliente. O Comercial trabalha a lista e contata os clientes por fora (telefone, WhatsApp, e-mail). O v1 **não** dispara mensagens automáticas.

### 6.6 Acesso e Portal
Usuários internos com funções e permissões; portal do cliente. Detalhado nas seções 8 e 9.

## 7. Fluxo da Ordem de Serviço

A OS nasce quando o aparelho **chega** à Health Safety. O sistema não controla o envio do cliente (as três fases iniciais do sistema antigo — Início, Com etiqueta, Enviado — deixam de existir). Três times conduzem a OS:

```
        Expedição          Laboratório        Comercial          Expedição
        ┌─────────┐        ┌───────────┐      ┌───────────┐      ┌──────────────────┐      ┌────────────┐
INÍCIO →│ Recebido│───────→│Laboratório│─────→│ Pós-Vendas│─────→│ Preparando Retorno│────→│ Finalizada │
        └─────────┘        └───────────┘      └───────────┘      └──────────────────┘      └────────────┘
             │                   │                  │                     │
             └───────────────────┴──────── Cancelada (saída lateral) ─────┘
```

| Fase | Time responsável | Significado |
|---|---|---|
| **Recebido** | Expedição | A Expedição abre a OS quando o aparelho chega. |
| **Laboratório** | Laboratório | Calibração e/ou manutenção. |
| **Pós-Vendas** | Comercial Pós-Vendas | O Comercial avisa o cliente e aguarda o aceite da proposta. |
| **Preparando Retorno** | Expedição | A Expedição prepara o aparelho para voltar. |
| **Finalizada** | — | Encerrada na postagem (não na entrega). |
| **Cancelada** | — | Saída lateral, a partir de qualquer fase. |

### 7.1 Avanço por formulário-portão

A OS **não** avança por arrastar. Cada passagem de fase exige um formulário que captura os dados daquela etapa:

| Passagem | Quem | O formulário captura |
|---|---|---|
| **Abrir → Recebido** | Expedição | Equipamento; como chegou (condição); o que veio junto (acessórios); fotos do recebimento. |
| **Recebido → Laboratório** | Expedição | Encaminhamento ao laboratório (um clique; opcionalmente atribui o técnico). |
| **Laboratório → Pós-Vendas** | Laboratório | Tipo de serviço (Calibração / Manutenção / Ambas); resultados; certificado (nº, PDF, próxima calibração); notas de manutenção. |
| **Pós-Vendas → Preparando Retorno** | Comercial | Aceite do cliente (proposta e valores ficam fora do sistema). |
| **Preparando Retorno → Finalizada** | Expedição | Código de rastreio de retorno + data de saída. |
| **Cancelar** | qualquer | Motivo do cancelamento. |

### 7.2 Por que finalizar na postagem

A OS encerra no momento da **postagem nos Correios** — o último ato sob controle da empresa. A entrega ao cliente é acompanhada por outra plataforma. Assim, nenhuma OS fica presa esperando um evento externo, e o controle permanece 100% interno.

No banco: `data_retorno` passa a registrar a **postagem**; `cod_retorno`, o rastreio; `data_entrega` torna-se opcional/externa.

## 8. Funções e permissões

Funcionários internos têm uma **função**: Administrador, Expedição, Laboratório ou Comercial Pós-Vendas (extensível). O **Administrador** define qual função responde por cada fase da OS. Disso decorre:

- Cada função vê a **fila** das OS nas fases sob sua responsabilidade.
- Apenas a função responsável avança a OS para fora dessas fases.
- O Administrador vê tudo e configura o mapa função → fase.

## 9. Portal do cliente

**Papel:** informativo + solicitar. O cliente, ao entrar, vê apenas os próprios dados:

- **Frota** com o status de calibração de cada aparelho (em dia / vencendo / vencido).
- **Certificados** para download (PDF).
- **Ordens de Serviço** em andamento, com a fase atual.
- **Solicitar recalibração** — o botão cria uma **solicitação** que entra na worklist do Comercial Pós-Vendas.

Isso fecha o ciclo do negócio: alerta de vencimento → cliente solicita → Comercial atende → vira OS quando o aparelho chega.

## 10. Mudanças no schema

Sobre o schema migrado, o v1 acrescenta:

1. **`ordens`:**
   - `tipo_servico` — `C` (Calibração), `M` (Manutenção) ou `A` (Ambas).
   - `condicao_chegada` e `acessorios` — recebimento estruturado.
   - `aceite` (boolean) + `data_aceite` — registro do aceite no Pós-Vendas.
2. **`fotos`:** adicionar FK `os` → `ordens(id)`, para anexar fotos do recebimento à OS (hoje a foto liga apenas ao cliente).
3. **Funções:** nova tabela `funcoes`; FK `funcao` em `usuarios`; coluna `funcao_responsavel` em `fases`.
4. **`solicitacoes`:** nova tabela — solicitações de recalibração vindas do portal (cliente, equipamento, status, datas, quem atendeu).
5. **`fases`:** redefinir as nove fases legadas para as cinco novas + Cancelada, com cores atribuídas. As OS antigas (9.583 "Entregue") mapeiam para "Finalizada".

## 11. Superfície de API (alto nível)

| Recurso | Rotas principais |
|---|---|
| Autenticação | `POST /auth/login` (equipe e portal), `POST /auth/refresh`, `GET /auth/me` |
| Cadastros | `/clientes`, `/equipamentos`, `/marcas`, `/categorias`, `/grupos`, `/funcionarios` |
| Frota | `/equipamentos-cliente` (com status de calibração) |
| Ordens | `/ordens` (lista e quadro), `/ordens/{id}`, `POST /ordens/{id}/avancar`, `/ordens/{id}/logs`, `/ordens/{id}/fotos` |
| Calibração | `/certificados`, `/tipos-calibragem` |
| Alertas | `GET /alertas` (worklist), `/solicitacoes` |
| Acesso | `/usuarios`, `/funcoes`, `/fases` (+ responsabilidade) |
| Portal | `/portal/minha-frota`, `/portal/certificados`, `/portal/minhas-os`, `POST /portal/solicitar-recalibracao` |

## 12. Fora de escopo do v1

Estes ficam para evoluções futuras:

- **Testes de campo** (aplicação de bafômetro em funcionários).
- **Financeiro** (valores de OS, fretes, caixa).
- **Galeria geral de mídia/documentos** (o PDF do certificado permanece no v1).
- **Disparo automático de mensagens** (e-mail/WhatsApp).
- **SSO com o TaskHS.**

## 13. Premissas e questões em aberto

- **TaskHS:** sistemas separados que compartilham a linguagem visual. Sem base de usuários comum no v1.
- **Implantação:** mesmo servidor do banco (62.72.11.28), provavelmente via Docker. A definir.
- **PDF do certificado:** o v1 anexa um PDF existente. A geração automática fica para depois — **confirmar**.
- **Migração de senhas:** redefinição forçada vs. re-hash no primeiro login — **confirmar**.
- **Armazenamento de imagens:** o legado guarda apenas o nome do arquivo. Precisamos definir onde os arquivos vivem (sistema de arquivos ou storage de objetos) — **confirmar**.
