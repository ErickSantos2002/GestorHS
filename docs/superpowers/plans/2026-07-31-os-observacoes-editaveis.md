# Observações da OS editáveis na própria página — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar seção própria às Observações da OS, entre Recebimento e Fotos, editável por qualquer usuário interno em qualquer fase.

**Architecture:** O campo já existe (`ordens.obs`) e já é exibido — só leitura, dentro do Recebimento, e sumindo quando vazio. A entrega adiciona um endpoint estreito (`PATCH /ordens/{id}/observacoes`, só autenticação, sem função exigida) e move o campo para uma seção própria com `textarea` + botão Salvar.

**Tech Stack:** Backend Python 3.12 / FastAPI / pytest. Frontend React 19 / TypeScript / Vitest + Testing Library.

**Spec:** [docs/superpowers/specs/2026-07-31-os-observacoes-editaveis-design.md](../specs/2026-07-31-os-observacoes-editaveis-design.md)

## Global Constraints

- **Reusar `ordens.obs`.** Nenhum campo novo, nenhuma migração. É a mesma coluna que o `AbrirOSModal` preenche e que aparece no card do TaskHS.
- **Endpoint novo e estreito.** **Não** alargar o `PUT /ordens/{id}/editar` — ele também altera `tipo_servico`, `checklist`, `data_chegada`, `garantia`, `pilhas` e `bocais`, e exige Administrador. Abri-lo entregaria muito mais do que observações.
- **Sem `require_funcao`** no endpoint novo: `Depends(get_current_usuario)` e nada mais. Qualquer usuário interno escreve.
- **Sem checagem de fase.** Editável em todas: 4, 5, 6, 7, 8, 10 e 9 (cancelada).
- **Uma única exibição.** O bloco de leitura de observações que hoje está no rodapé da seção Recebimento **sai de lá** — não podem sobrar dois lugares mostrando o mesmo texto.
- **O botão de salvar é explícito.** `textarea` + botão "Salvar observações"; nada de gravação automática ao digitar. (Hoje, 31/07, um interruptor que parecia salvar sozinho gerou confusão real — não repetir a promessa falsa.)
- **O card do TaskHS não é re-espelhado** ao editar a observação — mesmo comportamento do `editar` admin de hoje.
- Idioma PT-BR: textos de interface com acentos; identificadores sem acentos.
- **Commits:** Conventional Commits em português **sem acentos**, assunto de **uma linha só**, sem corpo e **sem trailer de co-autor**.
- **Branch:** `feat/os-observacoes-editaveis`. **Nunca `git add -A`** — listar os caminhos (há outro agente neste repo, com arquivos não rastreados em `backend/relatorios/` e PDFs em `docs/`). Conferir `git branch --show-current` antes de cada commit. **Não fazer push nem merge** sem o Erick pedir.
- **Baseline:** backend `4 failed` (2 em `tests/test_certificados_gerais.py`, 2 em `tests/test_publico_certificado_geral.py`, todas `PermissionError`); frontend **`0 failed`** — a suíte fecha limpa desde a v1.35.0, então qualquer vermelho no frontend é regressão.
- **Ambiente:** backend `cd backend && source .venv/bin/activate`; frontend `cd frontend`.

---

### Task 0: Preparar branch e baseline

**Files:** nenhum.

- [ ] **Step 1: Criar a branch**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current          # confirme que está em main
git checkout -b feat/os-observacoes-editaveis
```

- [ ] **Step 2: Registrar o baseline**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -3
cd ../frontend && npm test 2>&1 | tail -5
```

Esperado: backend `4 failed`, frontend **`0 failed`**.

---

### Task 1: Endpoint `PATCH /ordens/{id}/observacoes`

**Files:**
- Modify: `backend/app/schemas/ordens.py` (schema novo)
- Modify: `backend/app/api/ordens.py` (endpoint novo, logo depois da função `editar`)
- Test: `backend/tests/test_ordens_observacoes.py` (**novo**)

**Interfaces:**
- Produces: `PATCH /ordens/{ordem_id}/observacoes`, corpo `{"observacoes": str | null}`, resposta `OrdemOut`. Consumido pela Task 2.

**Contexto do arquivo:** `app/api/ordens.py` já importa o que você precisa — `get_current_usuario` (linha 9) e `registrar_log` (linha 10, de `app.api.ordens_acoes`). A função `editar` termina por volta da linha 234; o endpoint novo entra logo depois dela. `_anotar_modelos_faltantes(db, ordem)` é chamado antes do `return` em `abrir` e em `editar` — faça igual, para a resposta ter a mesma forma.

- [ ] **Step 1: Escrever os testes que falham**

Crie `backend/tests/test_ordens_observacoes.py`:

```python
"""Observacoes da OS: anotacao livre, sem dono de fase, editavel por qualquer
usuario interno em qualquer fase."""


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os_na_fase(db, os_base, fase):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico="C", situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o.id


def test_funcao_nao_admin_edita_observacoes(client, usuario_lab, fases_seed, os_base, db_session):
    """Laboratorio (nao-admin) escreve: o campo e' anotacao livre, nao tem dono."""
    from app.models import Ordem
    oid = _os_na_fase(db_session, os_base, 5)
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "aparelho veio sem tampa"}, headers=h)
    assert r.status_code == 200
    assert r.json()["obs"] == "aparelho veio sem tampa"
    db_session.expire_all()
    assert db_session.get(Ordem, oid).obs == "aparelho veio sem tampa"


def test_edita_observacoes_em_os_finalizada(client, usuario_lab, fases_seed, os_base, db_session):
    """'Qualquer fase' inclui a terminal — a anotacao nao acompanha o fluxo."""
    oid = _os_na_fase(db_session, os_base, 8)
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "nota tardia"},
                        headers=h).status_code == 200


def test_edita_observacoes_em_os_cancelada(client, usuario_lab, fases_seed, os_base, db_session):
    oid = _os_na_fase(db_session, os_base, 9)
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "motivo do cancelamento"},
                        headers=h).status_code == 200


def test_observacoes_vazia_limpa_o_campo(client, usuario_lab, fases_seed, os_base, db_session):
    """Texto em branco vira None, nao string vazia — o card do TaskHS testa `if ordem.obs`."""
    from app.models import Ordem
    oid = _os_na_fase(db_session, os_base, 5)
    h = _headers(client, "lab@hs.com", "senha123")
    client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "algo"}, headers=h)
    r = client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "   "}, headers=h)
    assert r.status_code == 200
    assert r.json()["obs"] is None
    db_session.expire_all()
    assert db_session.get(Ordem, oid).obs is None


def test_edicao_de_observacoes_entra_no_historico(client, usuario_lab, fases_seed, os_base, db_session):
    from app.models import LogOS
    oid = _os_na_fase(db_session, os_base, 5)
    h = _headers(client, "lab@hs.com", "senha123")
    client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "anotado"}, headers=h)
    logs = db_session.query(LogOS).filter(LogOS.os == oid).all()
    assert any("bserva" in (l.texto or "") for l in logs)


def test_observacoes_sem_token_401(client, fases_seed, os_base, db_session):
    oid = _os_na_fase(db_session, os_base, 5)
    assert client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "x"}).status_code == 401


def test_observacoes_os_inexistente_404(client, usuario_lab, fases_seed):
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.patch("/ordens/999999/observacoes", json={"observacoes": "x"},
                        headers=h).status_code == 404
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_ordens_observacoes.py -q`
Expected: FAIL — a rota não existe (405 ou 404 no lugar de 200).

- [ ] **Step 3: Criar o schema**

Em `backend/app/schemas/ordens.py`, acrescente ao fim do arquivo:

```python
class ObservacoesIn(BaseModel):
    observacoes: str | None = None
```

- [ ] **Step 4: Criar o endpoint**

Em `backend/app/api/ordens.py`, acrescente `ObservacoesIn` ao import de schemas que já traz `OrdemEditarIn` (procure a linha do `from app.schemas.ordens import ...`), e insira a função logo **depois** de `editar` e **antes** de `avancar`:

```python
@router.patch("/{ordem_id}/observacoes", response_model=OrdemOut)
def editar_observacoes(ordem_id: int, dados: ObservacoesIn, db: Session = Depends(get_db),
                       usuario: Usuario = Depends(get_current_usuario)):
    """Anotacao livre da OS: sem dono de fase e sem funcao exigida.

    Endpoint proprio de proposito — o `/editar` mexe em tipo de servico, checklist,
    datas e garantia, e exige Administrador; abri-lo daria muito mais que isto.
    """
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    texto = (dados.observacoes or "").strip() or None
    ordem.obs = texto
    registrar_log(db, ordem, usuario,
                  "Observações editadas" if texto else "Observações apagadas")
    db.commit()
    db.refresh(ordem)
    _anotar_modelos_faltantes(db, ordem)
    return ordem
```

- [ ] **Step 5: Rodar e confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_ordens_observacoes.py tests/test_ordens_editar.py -q`
Expected: PASS. O segundo arquivo cobre o `PUT /editar` admin e prova que ele não foi afetado.

- [ ] **Step 6: Conferir que o `editar` admin não mudou**

Run: `cd backend && grep -n "require_funcao" app/api/ordens.py`
Expected: o `PUT /{ordem_id}/editar` continua com `require_funcao("Administrador")`. O endpoint novo **não** aparece nessa lista.

- [ ] **Step 7: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add backend/app/schemas/ordens.py backend/app/api/ordens.py backend/tests/test_ordens_observacoes.py
git commit -m "feat(ordens): endpoint de observacoes editavel por qualquer funcao"
```

---

### Task 2: Seção "Observações" na página da OS

**Files:**
- Modify: `frontend/src/app/ordens/api.ts` (por volta da linha 347, ao lado de `editar`)
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx`
- Test: `frontend/src/app/ordens/OrdemDetailPage.observacoes.test.tsx` (**novo**)

**Interfaces:**
- Consumes: `PATCH /ordens/{id}/observacoes` da Task 1, resposta `OrdemDetalhe`.
- Produces: `ordensApi.editarObservacoes(id: number, observacoes: string | null): Promise<OrdemDetalhe>`.

**Contexto do arquivo:** a página usa **estado de erro por seção** (`erroFoto`, `erroCert`, `erroNF`, linhas 110-112) — siga o padrão com `erroObs`. O componente `Secao` aceita `{ icon, titulo, acao, children }`; o botão vai na prop `acao`, como em Fotos. A seção Recebimento termina na linha 333 e a de Fotos começa na 336.

- [ ] **Step 1: Escrever o teste que falha**

Crie `frontend/src/app/ordens/OrdemDetailPage.observacoes.test.tsx`. Antes de escrever, **leia `frontend/src/app/ordens/OrdemDetailPage.editar.test.tsx`** e copie dele o bloco de mocks (`vi.mock` de `./api`, de `../../auth/AuthContext`, e o objeto de OS de exemplo) — a página faz várias chamadas no carregamento e o mock precisa cobrir todas. Adapte:

```tsx
  it('mostra a secao Observacoes mesmo quando a OS nao tem observacao', async () => {
    // obter() devolve uma OS com obs: null
    expect(await screen.findByRole('heading', { name: 'Observações' })).toBeInTheDocument()
  })

  it('a secao Observacoes fica entre Recebimento e Fotos', async () => {
    await screen.findByRole('heading', { name: 'Observações' })
    const recebimento = screen.getByRole('heading', { name: 'Recebimento' })
    const observacoes = screen.getByRole('heading', { name: 'Observações' })
    const fotos = screen.getByRole('heading', { name: 'Fotos' })
    // DOCUMENT_POSITION_FOLLOWING = 4: o segundo elemento vem DEPOIS do primeiro
    expect(recebimento.compareDocumentPosition(observacoes) & 4).toBeTruthy()
    expect(observacoes.compareDocumentPosition(fotos) & 4).toBeTruthy()
  })

  it('o botao Salvar nasce desabilitado e habilita quando o texto muda', async () => {
    const campo = await screen.findByLabelText('Observações')
    const botao = screen.getByRole('button', { name: /salvar observações/i })
    expect(botao).toBeDisabled()
    await userEvent.type(campo, 'veio sem tampa')
    expect(botao).not.toBeDisabled()
  })

  it('salvar manda o texto digitado para a API', async () => {
    const campo = await screen.findByLabelText('Observações')
    await userEvent.type(campo, 'veio sem tampa')
    await userEvent.click(screen.getByRole('button', { name: /salvar observações/i }))
    expect(editarObservacoes).toHaveBeenCalledWith(expect.any(Number), 'veio sem tampa')
  })

  it('a observacao aparece uma unica vez na pagina', async () => {
    // obter() devolve uma OS com obs: 'anotacao existente'
    await screen.findByRole('heading', { name: 'Observações' })
    expect(screen.getAllByText('anotacao existente')).toHaveLength(1)
  })
```

O último teste é o que prova que o bloco antigo saiu do Recebimento — se ele sobrar, o texto aparece duas vezes e `getAllByText` devolve 2.

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd frontend && npx vitest run src/app/ordens/OrdemDetailPage.observacoes.test.tsx`
Expected: FAIL — não existe seção "Observações" nem botão de salvar.

- [ ] **Step 3: Adicionar o método no cliente HTTP**

Em `frontend/src/app/ordens/api.ts`, logo depois de `editar` (linha 347-348):

```ts
  editarObservacoes: (id: number, observacoes: string | null): Promise<OrdemDetalhe> =>
    apiJson<OrdemDetalhe>(`/ordens/${id}/observacoes`, { method: 'PATCH', body: JSON.stringify({ observacoes }) }),
```

- [ ] **Step 4: Adicionar estado e handler na página**

Em `frontend/src/app/ordens/OrdemDetailPage.tsx`, junto dos outros estados de erro (linhas 110-112):

```tsx
  const [erroObs, setErroObs] = useState('')
  const [obsTexto, setObsTexto] = useState('')
  const [salvandoObs, setSalvandoObs] = useState(false)
```

Sincronize o campo quando a OS carrega (acrescente perto dos outros `useEffect`):

```tsx
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setObsTexto(os?.obs ?? '')
  }, [os?.obs])
```

E o handler, junto das outras funções de ação (perto de `onEnviarFoto`):

```tsx
  async function onSalvarObs() {
    setErroObs('')
    setSalvandoObs(true)
    try {
      const atualizado = await ordensApi.editarObservacoes(osId, obsTexto.trim() || null)
      setOs(atualizado)
    } catch (err) {
      setErroObs(err instanceof ApiError ? err.message : 'Falha ao salvar observações')
    } finally {
      setSalvandoObs(false)
    }
  }
```

- [ ] **Step 5: Remover o bloco antigo do Recebimento**

Ainda em `OrdemDetailPage.tsx`, apague o bloco condicional de observações que fica no rodapé da seção Recebimento (linhas 327-332), aquele que começa com `{os.obs && (`. A seção Recebimento passa a terminar logo depois do bloco de Acessórios.

- [ ] **Step 6: Criar a seção nova entre Recebimento e Fotos**

Insira, **entre** o `</Secao>` que fecha o Recebimento e o comentário `{/* Fotos */}`:

```tsx
      <Secao
        icon={<IconPencil className="w-4 h-4" />}
        titulo="Observações"
        acao={
          <button
            type="button"
            onClick={onSalvarObs}
            disabled={salvandoObs || obsTexto === (os.obs ?? '')}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold bg-primary text-white hover:bg-primary-600 disabled:opacity-50 transition-colors"
          >
            Salvar observações
          </button>
        }
      >
        <label htmlFor="os-obs" className="sr-only">Observações</label>
        <textarea
          id="os-obs"
          value={obsTexto}
          onChange={(e) => setObsTexto(e.target.value)}
          rows={4}
          placeholder="Anotações sobre esta OS — visíveis para toda a equipe, em qualquer fase."
          className="w-full rounded-lg bg-background border border-border px-3 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/40"
        />
        {erroObs && <p className="text-sm text-danger">{erroObs}</p>}
      </Secao>
```

O `<label>` com `sr-only` existe para o `getByLabelText('Observações')` do teste funcionar sem poluir a tela — o título da seção já diz o nome visualmente.

- [ ] **Step 7: Rodar e confirmar que passa**

Run: `cd frontend && npx vitest run src/app/ordens/`
Expected: PASS — o arquivo novo e os que já existiam na pasta.

- [ ] **Step 8: Verificação de tipos e build**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro.

**Atenção ao ícone:** a página importa hoje `IconNote, IconCalendar, IconChart, IconCamera, IconClock, IconCheck, IconSearch, IconBattery, IconWrench, IconCaixas, IconX, IconCertificado` (linhas 6-9) — **`IconPencil` não está na lista**, acrescente-o. Escolhi o lápis de propósito: `IconNote` já é o ícone da seção Recebimento logo acima, e repetir o mesmo símbolo em seções vizinhas confunde; o lápis ainda sinaliza que aquela seção é a editável.

- [ ] **Step 9: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add frontend/src/app/ordens/api.ts frontend/src/app/ordens/OrdemDetailPage.tsx frontend/src/app/ordens/OrdemDetailPage.observacoes.test.tsx
git commit -m "feat(ordens): secao de observacoes editavel na pagina da os"
```

---

### Task 3: Changelog e verificação final

**Files:**
- Modify: `frontend/src/app/changelog/data.ts` (nova entrada no topo)

- [ ] **Step 1: Rodar a suíte inteira do backend**

Run: `cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5`
Expected: `4 failed` (as pré-existentes) e nenhuma falha nova.

- [ ] **Step 2: Rodar a suíte inteira do frontend**

Run: `cd frontend && npm test 2>&1 | tail -8`
Expected: **`0 failed`.** Qualquer falha é regressão — pare e reporte.

- [ ] **Step 3: Adicionar a entrada no changelog**

Em `frontend/src/app/changelog/data.ts`, como **primeira** entrada de `CHANGELOG`:

```ts
  {
    versao: '1.36.0',
    data: '31/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'A página da OS ganhou uma seção "Observações", entre Recebimento e Fotos, com um campo de texto que qualquer pessoa da equipe pode preencher — em qualquer fase da OS. A anotação fica na OS, não na fase, e o histórico registra quem alterou.' },
      { tipo: 'melhoria', texto: 'As observações antes só apareciam quando já havia texto e só o Administrador conseguia alterá-las, pelo modal de editar OS. Agora o campo está sempre visível na própria página.' },
    ],
  },
```

- [ ] **Step 4: Verificar o frontend de novo**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro.

- [ ] **Step 5: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.36.0 — observacoes editaveis na pagina da os"
```

- [ ] **Step 6: Resumo para o Erick**

Não faça push nem merge. Reporte: falhas antes/depois nas duas suítes, arquivos tocados, e confirmação de que o `PUT /ordens/{id}/editar` continua exigindo Administrador.

---

## Notas de execução

- **Task 1 antes da Task 2** — o frontend consome o endpoint.
- **O risco desta entrega é sobrar exibição duplicada.** O Step 5 da Task 2 (apagar o bloco antigo) e o último teste (`getAllByText(...)` com `toHaveLength(1)`) existem justamente para isso. Se o teste acusar 2, o bloco antigo não foi removido.
- **Não confundir `obs` com `desfecho_lab_obs`.** O segundo é a justificativa do laboratório e não tem relação com este campo; `app/api/ordens.py` usa os dois em funções vizinhas.
