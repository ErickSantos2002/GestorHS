# GestorHS — Fase 3A (Schema & migração da OS)

**Data:** 2026-06-03
**Status:** Aprovado para implementação
**Parte de:** Fase 3 (Ordens de Serviço), sub-projeto 1 de 5 (3A schema/migração → 3B backend OS+avanço+config função→fase → 3C kanban → 3D formulários-portão → 3E calibração/certificado).
**Depende de:** Migração `0001_auth_hardening` aplicada (funcoes com os 4 papéis); banco real 9998 com os dados migrados.

---

## 1. Objetivo

Preparar o schema do banco real (9998) para o módulo de Ordens de Serviço: acrescentar as colunas que o fluxo novo exige e **redefinir as 9 fases legadas para as 5 fases novas + Cancelada** (com cores e responsável por função), remapeando as 10.168 OS existentes. É a fundação puramente de banco sobre a qual o 3B (backend da OS) será construído. Operação sensível (altera dados reais) — conduzida com migração reversível, dry-run e aprovação.

## 2. Escopo

**Dentro:** uma migração Alembic `0002_os_schema` com `upgrade`/`downgrade`, aplicada ao 9998 após dry-run e aprovação.

**Fora (com a fase de destino):**
- Modelos SQLAlchemy `Ordem`/`Fase`/`LogOS` e endpoints → **Fase 3B**.
- Tabela `solicitacoes` (recalibração via portal) → **Fase 5**.
- UI de configuração do mapa função→fase → **Fase 3B**.
- Campos financeiros de `ordens` (valor/fretes/pago) → fora do v1 (ignorados).

## 3. Contexto do banco atual (consultado no 9998)

Fases legadas e distribuição das OS:

| id | descrição legada | OS |
|---|---|---|
| 1 | Início | 0 |
| 2 | Com etiqueta | 0 |
| 3 | Enviado | 0 |
| 4 | Recebido | 35 |
| 5 | Realizando | 40 |
| 6 | Pronto | 290 |
| 7 | Retornando | 14 |
| 8 | Entregue/Finalizada | 9.583 |
| 9 | Cancelada | 206 |

Total: 10.168 OS. `funcoes` tem os 4 papéis (Administrador, Expedição, Laboratório, Comercial Pós-Vendas). Alembic já configurado (`alembic.ini`, `alembic/env.py`, `alembic/versions/0001_auth_hardening.py`). A `env.py`/conexão usa o `DATABASE_URL` do `backend/.env` (9998).

## 4. Conteúdo da migração `0002_os_schema`

### 4.1 Novas colunas (`upgrade`)

- **`ordens`**:
  - `tipo_servico varchar(1)` nullable, com CHECK `tipo_servico IN ('C','M','A')` (Calibração/Manutenção/Ambas).
  - `condicao_chegada text` nullable (como o aparelho chegou).
  - `acessorios text` nullable (o que veio junto).
  - `aceite boolean NOT NULL DEFAULT false` (aceite do cliente no Pós-Vendas).
  - `data_aceite timestamptz` nullable.
- **`fotos`**: `os integer` nullable, FK → `ordens(id)` (anexar fotos do recebimento à OS).
- **`fases`**: `funcao_responsavel integer` nullable, FK → `funcoes(id)` (qual função responde pela fase).

### 4.2 Redefinição das fases (renomear no lugar)

Mantém os ids 4–9 (as 10.168 OS já apontam para eles — **não se atualiza nenhuma linha de `ordens`**); apenas `UPDATE` em `fases` (descrição, cor, funcao_responsavel) e `DELETE` das 3 vazias.

| id | nova descrição | cor (char6) | funcao_responsavel (por descrição) |
|---|---|---|---|
| 4 | Recebido | `3b82f6` | Expedição |
| 5 | Laboratório | `6366f1` | Laboratório |
| 6 | Pós-Vendas | `f59e0b` | Comercial Pós-Vendas |
| 7 | Preparando Retorno | `14b8a6` | Expedição |
| 8 | Finalizada | `10b981` | *(nula)* |
| 9 | Cancelada | `ef4444` | *(nula)* |

- `funcao_responsavel` resolvido em tempo de migração: `SELECT id FROM funcoes WHERE descricao = '<papel>'` (se o papel não existir, deixa nulo — não falha).
- `DELETE FROM fases WHERE id IN (1,2,3)` (Início/Com etiqueta/Enviado — 0 OS; seguro). A migração deve **verificar** que essas fases têm 0 OS antes de deletar; se houver alguma, aborta com erro (proteção).

### 4.3 `downgrade`

- Dropa as colunas adicionadas (`ordens.tipo_servico/condicao_chegada/acessorios/aceite/data_aceite`, `fotos.os`, `fases.funcao_responsavel`) e o CHECK/constraints associados.
- Restaura nomes/cores legados das fases 4–9 (Recebido/Realizando/Pronto/Retornando/Entregue-Finalizada/Cancelada, cor `000000`) e recria as fases 1–3 (Início/Com etiqueta/Enviado) com os ids originais.
- **Limitação documentada:** como o remapeamento é semântico (rename), as OS não "voltam" para distribuições antigas no downgrade — o downgrade restaura a estrutura, não reverte interpretação de dados. Isso é aceitável (a migração é forward-only na prática; o downgrade existe para reverter a estrutura em dev).

## 5. Procedimento de aplicação (dry-run → aprovação → aplicar)

1. Escrever `backend/alembic/versions/0002_os_schema.py` (segue o padrão da `0001`).
2. **Dry-run / contagem** (script de leitura, sem alterar nada): reportar quantas OS cairão em cada fase nova após o rename e confirmar que as fases 1–3 têm 0 OS. Esperado: Recebido 35, Laboratório 40, Pós-Vendas 290, Preparando Retorno 14, Finalizada 9.583, Cancelada 206; fases 1–3 → 0.
3. **Apresentar o resultado do dry-run + o SQL/diff da migração ao usuário para aprovação.**
4. Com o OK: `alembic upgrade head` no 9998 (via container) e **re-verificar** as contagens e a estrutura.

## 6. Verificação

Migração de dados não tem teste unitário pytest (a suíte atual usa SQLite via `create_all` dos modelos, não Alembic; e os modelos da OS só chegam no 3B). A verificação do 3A é:
- O **dry-run** bate com os números esperados (seção 5.2).
- Após `upgrade`: `SELECT id, descricao, cor, funcao_responsavel FROM fases` mostra as 6 fases corretas; `SELECT fase, count(*) FROM ordens GROUP BY fase` bate com a distribuição esperada; as colunas novas existem (`\d ordens`, `\d fotos`, `\d fases`).
- `alembic downgrade -1` roda sem erro e `alembic upgrade head` reaplica (confirma reversibilidade estrutural).
- A suíte pytest atual (74 testes) continua verde (não afetada — não usa Alembic).

## 7. Critérios de aceite

- `0002_os_schema` escrita (upgrade+downgrade), revisada e **aprovada por você no dry-run**, e aplicada ao 9998.
- Pós-apply: `fases` tem exatamente 6 linhas (Recebido/Laboratório/Pós-Vendas/Preparando Retorno/Finalizada/Cancelada) com cores e `funcao_responsavel` setados (4 das 6 com responsável); as 10.168 OS distribuídas conforme a tabela 4.2; colunas novas presentes em `ordens`/`fotos`/`fases`.
- A proteção "abortar se fases 1–3 tiverem OS" está na migração.
- `downgrade` definido e executável.
- pytest atual segue verde.

## 8. Fora de escopo (reafirmando)
Modelos/endpoints da OS (3B); `solicitacoes` (Fase 5); UI de configuração função→fase (3B); campos financeiros; geração de PDF de certificado (3E).
