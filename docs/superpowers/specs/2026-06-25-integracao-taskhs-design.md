# Integração GestorHS → TaskHS (espelhar OS como cards)

**Data:** 2026-06-25
**Status:** aprovado (brainstorming)

## Objetivo

Espelhar cada Ordem de Serviço do GestorHS como um **card** no board `Serviço` do
TaskHS, refletindo a **fase da OS** como **coluna (lista)** do board. A cada
abertura, avanço de fase e cancelamento de OS, o GestorHS empurra o estado atual
completo para o TaskHS via a API de integração (`POST /integration/cards`).

Princípios (do contrato em [docs/integration.md](../../integration.md)):

- **GestorHS é o dono da verdade**; o TaskHS é só espelho (sem sync reverso).
- **Idempotente** por `(source, external_id)` = `("gestorhs", str(os.id))`.
- **Best-effort**: falha de espelhamento **loga e segue**, nunca trava nem atrasa
  a ação do usuário. O próximo upsert reconcilia.
- **Nasce desligada**: sem API key configurada, a integração é no-op total.

## Mapa fase → lista (board `Serviço`)

| Fase GestorHS | id | Lista no TaskHS |
|---|---|---|
| Recebido | 4 | `🚚 Expedição (Abrindo caixa)` |
| Laboratório | 5 | `🔬Laboratório Calibração` |
| Pós-Vendas | 6 | `Serviços 🪛` |
| Preparando Retorno | 7 | `🚚 Expedição (Preparando para Envio)` |
| Finalizada | 8 | `📮Correios` |
| Cancelada | 9 | — (arquiva: `archived=true`) |

Os nomes são **exatos** (emoji incluso) e resolvidos pelo TaskHS por nome. Devem
ser constantes fixas no código — qualquer divergência de string criaria lista nova.

## Decisões de design (aprovadas)

- **Disparo:** `BackgroundTasks` do FastAPI, **após o commit** da OS. A resposta ao
  usuário sai na hora; o POST ao TaskHS roda em background.
- **Prioridade do card:** sempre `"medium"` (o time organiza pela coluna, não pela
  prioridade). Refinável depois.
- **Backfill:** script avulso `python -m app.scripts.sincronizar_taskhs` para popular
  o board com as OS já existentes. Daqui pra frente é automático.
- **Cancelada:** upsert com `archived=true` e `list` = **lista da fase de origem**
  (mantém o card na coluna onde estava e arquiva, sem criar coluna "Cancelada").
- **Sem `DELETE`** no v1: o GestorHS nunca exclui OS de verdade (só cancela→arquiva).

## Arquitetura

Segue as convenções do projeto: lógica pura em `core/` (sem I/O, testável), I/O
isolado, wiring fino nos endpoints.

### 1. Configuração — `app/core/config.py`

Duas settings novas (default `""`):

```python
TASKHS_BASE_URL: str = ""   # ex.: "https://taskhs.exemplo/api" (sem barra final)
TASKHS_API_KEY: str = ""    # X-API-Key; vazio = integração desligada
```

Constantes de domínio ficam no módulo da integração (não em env): `SOURCE="gestorhs"`,
`BOARD="Serviço"`.

### 2. Lógica pura — `app/core/taskhs.py` (sem I/O)

```python
SOURCE = "gestorhs"
BOARD = "Serviço"

FASE_PARA_LISTA: dict[int, str] = {
    4: "🚚 Expedição (Abrindo caixa)",
    5: "🔬Laboratório Calibração",
    6: "Serviços 🪛",
    7: "🚚 Expedição (Preparando para Envio)",
    8: "📮Correios",
}

def lista_da_fase(fase: int) -> str | None:
    return FASE_PARA_LISTA.get(fase)

def montar_titulo(ordem) -> str: ...
    # "OS #{id} · {cliente_nome} · {equipamento_descricao or serie}"
    # junta as partes não-vazias com " · "

def montar_payload(ordem, *, lista: str, arquivado: bool) -> dict:
    # {source, external_id, board, list, title, description, due_date, priority, archived}
```

Detalhes do payload:

- `external_id`: `str(ordem.id)`.
- `title`: `montar_titulo(ordem)` (descarta partes vazias; nunca vazio — id sempre existe).
- `description`: `ordem.obs` (ou `None`).
- `due_date`: `ordem.prox_calibragem.date().isoformat()` se houver, senão `None`.
  (Só existe pós-laboratório; nas fases iniciais vai `null`.)
- `priority`: `"medium"`.
- `archived`: o booleano recebido.

`montar_payload` **não** decide a lista nem o flag de arquivo — recebe ambos prontos.
Isso mantém a função pura e deixa a orquestração (qual lista, arquivar ou não) na
camada de I/O, que conhece o contexto (abrir/avançar vs cancelar).

### 3. Cliente I/O — `app/integrations/taskhs.py`

```python
def integracao_ativa() -> bool:
    return bool(settings.TASKHS_BASE_URL and settings.TASKHS_API_KEY)

def _enviar(payload: dict) -> None:
    # POST {BASE}/integration/cards, header X-API-Key, timeout=5, raise_for_status
    # try/except -> logger.exception(...) e segue. NUNCA propaga.

def espelhar_os(ordem, *, lista: str, arquivado: bool = False) -> None:
    # no-op se not integracao_ativa()
    # monta payload puro e chama _enviar
```

`espelhar_os` é a função síncrona que o `BackgroundTask` executa. É segura para
rodar fora do request (recebe os dados já materializados do `ordem`, não a Session).

> ⚠️ Cuidado com lazy-load: o objeto `ordem` é usado depois do commit/refresh. As
> relações necessárias (`cliente_rel`, `equipamento_rel`) são `lazy="joined"`, então
> já vêm carregadas. O payload deve ser **montado dentro do request** (antes de
> agendar) OU o `ordem` acessado deve ter os atributos já resolvidos. Decisão:
> **montar o `dict` de payload no request e agendar só o `_enviar(payload)`** — assim
> o background task não toca em objeto SQLAlchemy nem na Session (evita
> `DetachedInstanceError`). Ver wiring abaixo.

### 4. Wiring nos endpoints — `app/api/ordens.py`

Cada endpoint ganha o parâmetro `background_tasks: BackgroundTasks` e, **após o
`db.commit()`/`db.refresh()`**, monta o payload e agenda o envio:

- **`abrir`** (fase Recebido=4):
  ```python
  if taskhs.integracao_ativa():
      payload = taskhs.montar_payload(ordem, lista=taskhs.lista_da_fase(ordem.fase), arquivado=False)
      background_tasks.add_task(taskhs.enviar_card, payload)
  ```
- **`avancar`** (nova fase 5/6/7/8): igual, usando `ordem.fase` já atualizada.
- **`cancelar`**: a fase já é 9 (sem lista). Captura-se `origem` (a fase **antes** do
  cancelamento, já lida no início do endpoint não existe — adicionar `origem = ordem.fase`
  antes de setar Cancelada) e agenda:
  ```python
  payload = taskhs.montar_payload(ordem, lista=taskhs.lista_da_fase(origem), arquivado=True)
  background_tasks.add_task(taskhs.enviar_card, payload)
  ```

Para isso, expor em `integrations/taskhs.py` uma função `enviar_card(payload: dict)`
que é o alvo do background task (no-op se desligada + try/except). `espelhar_os` fica
como helper de conveniência para o script de backfill.

O acesso a `taskhs.lista_da_fase(...)` para fases ativas/finalizada nunca é `None`
(4–8 mapeados); para a origem do cancelamento idem (origem ∈ ATIVAS = 4–7). Guardar
um fallback defensivo: se `lista is None`, não agenda (loga debug).

### 5. Backfill — `app/scripts/sincronizar_taskhs.py`

`python -m app.scripts.sincronizar_taskhs`:

- Abre uma Session, busca OS em fases 4–8 (ativas + finalizada), ordena por id.
- Para cada uma: `espelhar_os(ordem, lista=lista_da_fase(fase), arquivado=False)`
  **síncrono** (não best-effort silencioso aqui — imprime ok/erro por OS e um resumo).
- Idempotente: pode rodar quantas vezes quiser.
- Não toca em OS canceladas (não faz sentido popular arquivadas; opcional: flag futura).

## Estratégia de testes

- **`tests/test_taskhs.py`** (puro): `lista_da_fase` cobre 4–8 e devolve `None` p/ 9;
  `montar_titulo` com/sem equipamento; `montar_payload` monta todos os campos,
  `due_date=None` quando sem `prox_calibragem`, `archived` refletido.
- **Cliente**: `enviar_card` é no-op quando `TASKHS_API_KEY` vazio (monkeypatch
  settings; garante que httpx **não** é chamado); com key, monta a request certa
  (mock httpx — `monkeypatch` em `httpx.post` ou `respx`); exceção de rede é engolida
  (não propaga).
- **Endpoint** (`test_ordens_*`): ao `abrir`/`avancar`/`cancelar` com integração ativa,
  o background task é agendado com o payload esperado (monkeypatch `enviar_card` e
  capturar chamadas; ou inspecionar `BackgroundTasks`). Com integração desligada,
  nada é agendado. Os testes existentes de fluxo de OS continuam passando (default
  desligado no ambiente de teste).

## Fora de escopo (v1)

- `DELETE /integration/cards` (sem exclusão real de OS no GestorHS).
- Fila/retry sofisticado (best-effort + reconciliação no próximo upsert bastam).
- Sync reverso (TaskHS → GestorHS).
- Membros/etiquetas/comentários/checklists no card.
- Refino de prioridade por garantia/calibração (decidido: sempre `medium`).
