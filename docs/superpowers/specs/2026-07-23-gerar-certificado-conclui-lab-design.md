# Gerar certificado conclui o laboratório — design

**Data:** 2026-07-23
**Área:** OS / Laboratório / Caixa (workflow)

## Problema

No fluxo novo de caixa (caixa como unidade de movimento, v1.24.0), a caixa só
avança saindo do Laboratório quando **toda OS ativa** tem `desfecho_lab` terminal
(`concluido` ou `sem_conserto`). O contador "N/M prontos" e `pode_avancar_caixa`
leem exclusivamente `Ordem.desfecho_lab`.

Gerar o certificado de calibração **não** marca `desfecho_lab`. Ele é apenas
pré-requisito para o endpoint separado `POST /ordens/{id}/desfecho-lab`
(`desfecho=concluido`). Mas esse passo de "concluir" **não tem botão no
frontend** — o único desfecho clicável na tela da caixa é "Sem conserto". Logo,
uma OS com certificado gerado fica presa em `desfecho_lab="pendente"`, a caixa
mostra "0/1 prontos" e o botão "Avançar caixa — Concluir laboratório" não libera.

Caso real: caixa 755, OS 10866 — certificado gerado, mas caixa travada.

## Objetivo

Gerar (ou regerar) um certificado de **calibração ou manutenção** passa a marcar
a OS como **concluída** no laboratório automaticamente, sem botão dedicado.
`desfecho_lab` continua sendo a única fonte de verdade do contador e do gate da
caixa — só passa a ser preenchido no momento da geração do certificado.

## Comportamento

Ao chamar `POST /ordens/{id}/gerar-certificado` com sucesso:

- **Se** `ordem.fase == FASE_LABORATORIO (5)` **e** `ordem.desfecho_lab == "pendente"`
  → a OS é concluída (marca `desfecho_lab="concluido"`, espelha, registra log).
- **Caso contrário** (OS já passou do laboratório, ou já está `concluido`/
  `sem_conserto`) → gerar/regerar o certificado **não altera** o desfecho; segue
  só gerando/regerando o PDF como hoje.

A guarda `desfecho_lab == "pendente"` garante que regerar certificado numa OS
`sem_conserto` **não** a vira `concluido`, e que OS antigas já finalizadas
(desfecho terminal) não são reabertas nem re-tocadas.

## Implementação

### Backend (único ponto de mudança)

**Helper reutilizável** — extrair as três ações que "concluir laboratório"
implica (hoje inline em `marcar_desfecho_lab`, [ordens.py:222-225](../../../backend/app/api/ordens.py)) para uma função
reaproveitável em `app/api/ordens_acoes.py` (junto de `espelhar_calibracao`):

```python
def concluir_laboratorio(db, ordem, usuario) -> None:
    """Conclui o laboratório de uma OS: espelha na frota, marca desfecho e loga.
    Idempotente na prática (espelhar_calibracao sobrescreve; não insere histórico)."""
    espelhar_calibracao(db, ordem)
    ordem.desfecho_lab = wf.DESFECHO_CONCLUIDO
    ordem.desfecho_lab_obs = None
    registrar_log(db, ordem, usuario, "Laboratório concluído — certificado gerado")
```

`marcar_desfecho_lab` passa a chamar esse helper no ramo `concluido` (mantendo
antes a checagem de certificado existente, que continua válida para o caminho
manual via API), com o texto de log próprio dele. Como o texto de log difere
entre os dois chamadores, o helper recebe o texto ou cada chamador registra o
log — decidir no plano; o essencial é não duplicar as linhas de espelhar+setar.

**Endpoint `gerar`** — em [certificados_os.py:86-90](../../../backend/app/api/certificados_os.py),
após `gerar_certificados(...)` e antes do `db.commit()`:

```python
gerados = gerar_certificados(db, ordem, tipos_para(ordem))
if ordem.fase == wf.FASE_LABORATORIO and ordem.desfecho_lab == wf.DESFECHO_PENDENTE:
    concluir_laboratorio(db, ordem, _usuario)
db.commit()
```

Isso exige o usuário autenticado no endpoint `gerar` (hoje ele usa
`_: Usuario = Depends(_gerar)` sem nomear a variável) — passar a nomear o
usuário para poder registrar o log. A função `_gerar` já exige "Laboratório" ou
"Administrador", coerente com quem conclui o laboratório.

### O que NÃO muda

- `pode_avancar_caixa` e o contador "prontos" ([caixas.py](../../../backend/app/api/caixas.py),
  [os_workflow.py](../../../backend/app/core/os_workflow.py)) — intactos.
- `POST /ordens/{id}/desfecho-lab` continua existindo: o "Sem conserto" do modal
  usa ele; o `concluido` manual segue válido (agora redundante).
- Frontend: nada obrigatório. Após gerar, o botão "Sem conserto" some (só aparece
  com desfecho pendente) e, ao recarregar a caixa, o contador vira 1/1 e o
  "Avançar caixa" libera. Reflexo sem F5 na tela da caixa é polimento fora do
  escopo deste bug.

## Testes (backend, SQLite in-memory)

1. Gerar certificado numa OS em Laboratório com desfecho pendente →
   `desfecho_lab == "concluido"` e valores espelhados no `equipamento_cliente`.
2. Regerar certificado numa OS já `sem_conserto` → permanece `sem_conserto`.
3. Gerar/regerar numa OS fora do Laboratório (ex.: Finalizada) → desfecho inalterado.
4. Ponta a ponta: caixa com 1 OS em Laboratório → gera certificado → contador vira
   1/1 e `pode_avancar_caixa` retorna liberado; avançar a caixa funciona.

## Fora de escopo

- Botão "Concluir laboratório" no frontend (deixa de ser necessário).
- Correção pontual da caixa 755 (é um `UPDATE` manual; a mudança vale daqui pra frente).
- Reflexo em tempo real do contador na tela da caixa sem recarregar (polimento de UX).
