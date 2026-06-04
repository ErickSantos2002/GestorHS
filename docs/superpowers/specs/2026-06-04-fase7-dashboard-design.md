# GestorHS — Fase 7 (Dashboard interno)

**Data:** 2026-06-04
**Status:** Aprovado para implementação
**Motivação:** O `/app` ainda mostra o placeholder da Fase 0 ("A fundação está no ar…"). O roadmap nunca teve um módulo de dashboard; agora que todos os módulos existem, esta fase entrega uma home operacional. Também remove o `portal/pages/PlaceholderPage.tsx` (órfão desde a 5A).
**Depende de:** Fase 2 (`EquipamentoCliente`/`status_calibracao`), Fase 3 (`Ordem`/`Fase`), Fase 4 (lógica de cobrança), Fase 5C (`Solicitacao`).

---

## 1. Objetivo

Substituir o placeholder do `/app` por um dashboard que reúne os números-chave do negócio numa tela: aparelhos vencidos/vencendo, solicitações pendentes, clientes a cobrar e OS ativas por fase — com atalhos para os módulos. Visão operacional imediata para a equipe interna.

## 2. Escopo

**Dentro:**
- Backend: `GET /dashboard` (agregado, qualquer interno).
- Frontend: reescrita da `DashboardPage` (cards + OS por fase + atalhos); `dashboardApi`.
- Limpeza: remover `frontend/src/portal/pages/PlaceholderPage.tsx` (não referenciado).

**Fora:**
- Gráficos / séries temporais / tendências.
- Métricas por função (dashboard global no v1).
- Personalização / widgets configuráveis.

## 3. Contexto do código atual

- **Backend:** routers em `app/api/` registrados em `main.py`; `get_current_usuario` (qualquer interno). `EquipamentoCliente` (`cliente`, `ativo`, `prox_calibragem` Date); fronteiras de status iguais à frota (vencido `<hoje`; vencendo `hoje..hoje+90`). `Ordem` (`fase`, FK→`fases`); fases ativas `(4,5,6,7)`; `Fase` (`id, descricao, cor`). `Solicitacao` (`status`). `func`/`distinct` do SQLAlchemy. Testes pytest/SQLite; fixtures `fases_seed`, `usuario_admin`/`usuario_comum`, `db_session`.
- **Frontend:** `app/pages/DashboardPage.tsx` é o placeholder atual (usa `useAuth`). Componentes `Badge`, `Spinner`; `apiJson`; `useNavigate`; `cn`. `app/routes.tsx` já roteia `index → DashboardPage`. Padrão de página com `useEffect`+guarda. `portal/pages/PlaceholderPage.tsx` não é mais importado (a 5A reescreveu `portal/routes.tsx`).

## 4. Backend

### 4.1 `GET /dashboard` (`app/api/dashboard.py`, `get_current_usuario`)
`hoje = date.today()`, `limite = hoje + timedelta(days=90)`. Registrar router em `main.py`. Retorna `DashboardOut`:
- `aparelhos_vencidos` = `count(EquipamentoCliente)` com `ativo == True`, `prox_calibragem != None`, `prox_calibragem < hoje`.
- `aparelhos_vencendo` = idem + `prox_calibragem >= hoje`, `prox_calibragem <= limite`.
- `solicitacoes_pendentes` = `count(Solicitacao)` com `status == 'pendente'`.
- `clientes_a_cobrar` = `count(distinct EquipamentoCliente.cliente)` com `ativo == True`, `prox_calibragem != None`, `prox_calibragem <= limite` (vencido ou vencendo).
- `os_por_fase` = para cada `Fase` com `id in (4,5,6,7)` (ordenado por id): `{ fase: id, descricao, cor, total }`, onde `total = count(Ordem)` com `Ordem.fase == id`. Inclui fases com `total = 0`. (Implementação: um `group_by` de `Ordem.fase in (4,5,6,7)` → dict `{fase: total}`; depois iterar as `Fase` 4–7 montando a lista com `total = dict.get(id, 0)`.)

### 4.2 Schemas (`app/schemas/dashboard.py`)
- `OsPorFaseItem { fase: int, descricao: str, cor: str, total: int }`.
- `DashboardOut { aparelhos_vencidos: int, aparelhos_vencendo: int, solicitacoes_pendentes: int, clientes_a_cobrar: int, os_por_fase: list[OsPorFaseItem] }`.

### 4.3 Testes (pytest)
Fixtures (`fases_seed` p/ a FK de `Ordem.fase`): aparelhos de um cliente A (1 vencido, 1 vencendo, 1 em_dia, 1 inativo-vencido) e de um cliente B (1 vencido); OS em fases 4, 5, 8 (a 8 não conta); 1 solicitação pendente + 1 atendida.
- `aparelhos_vencidos == 2` (A + B; ignora inativo), `aparelhos_vencendo == 1`, `solicitacoes_pendentes == 1`, `clientes_a_cobrar == 2` (A e B têm vencido/vencendo).
- `os_por_fase`: lista das 4 fases ativas na ordem 4,5,6,7; fase 4 e 5 com seus totais, 6 e 7 com 0; a OS finalizada (8) não aparece.
- 401 sem token.

## 5. Frontend

### 5.1 API (`app/dashboard/api.ts`)
- Tipos `OsPorFaseItem { fase, descricao, cor, total }`, `DashboardResumo { aparelhos_vencidos, aparelhos_vencendo, solicitacoes_pendentes, clientes_a_cobrar, os_por_fase }`.
- `dashboardApi.resumo()` → `GET /dashboard`.

### 5.2 `DashboardPage` (reescrita, `app/pages/DashboardPage.tsx`)
- Carrega `dashboardApi.resumo()` (`useEffect` + guarda `ativo`; `Spinner`; erro inline). Saudação "Olá, {user.nome ?? user.login}".
- **4 cards** (grid responsivo): "Aparelhos vencidos" (número destacado em danger se > 0), "Vencendo (90 dias)" (warning), "Solicitações pendentes", "Clientes a cobrar". Cada card é clicável (`navigate`): vencidos/vencendo → `/app/frota`; solicitações → `/app/solicitacoes`; clientes a cobrar → `/app/cobranca`.
- **"OS ativas por fase"**: para cada item de `os_por_fase`, um bloco com bolinha da cor (`style={{ background: '#'+cor }}`), descrição e total; clica → `/app/ordens`.
- Sem dados de tendência; só os números atuais.

### 5.3 Limpeza
- Remover `frontend/src/portal/pages/PlaceholderPage.tsx` (confirmar que nenhum import o referencia antes de apagar).

### 5.4 Testes (Vitest)
- `app/dashboard/api.test.ts`: `dashboardApi.resumo` bate em `/dashboard`; propaga `ApiError`.
- Tela: `tsc -b` + `lint` + `build`.

## 6. Verificação / E2E
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos.
- **E2E manual:** logar no `/app` e ver o dashboard com os indicadores reais (vencidos ≈ alguns milhares, OS por fase, etc.) e os atalhos funcionando; não-destrutivo (só leitura).

## 7. Critérios de aceite
- `/app` mostra o dashboard (4 indicadores + OS ativas por fase + atalhos), substituindo o placeholder; os números conferem com os módulos (ex.: vencidos = filtro "Vencido" da Frota; clientes a cobrar = total da Cobrança).
- `GET /dashboard` exige autenticação (401 sem token).
- `PlaceholderPage.tsx` órfão removido.
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos; E2E ok.

## 8. Fora de escopo (reafirmando)
Gráficos/tendências; métricas por função; personalização.
