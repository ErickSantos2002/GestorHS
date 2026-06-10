# Layout responsivo fluido — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Páginas internas preenchem a tela de forma fluida e consistente, com colunas que refluem conforme o espaço — eliminando o vazio à direita das páginas de detalhe.

**Architecture:** Primitivos compartilhados (`PageContainer` + `DetailGrid`/`DetailMain`/`DetailAside`) padronizam largura e a grade principal+lateral; páginas de detalhe passam a usá-los e seus grids de campos viram responsivos; páginas de lista trocam o wrapper por `PageContainer`. Só frontend, sem mudar lógica/identidade.

**Tech Stack:** React 19 + TypeScript + Vite + Tailwind v4.

**Branch:** `main` (mudança incremental de UX; será lançada na v1.4.1 junto com a navegação clicável já commitada).

**Spec:** `docs/superpowers/specs/2026-06-10-layout-responsivo-design.md`

**Verificação padrão (toda task de página):** `cd frontend && npx tsc -b --noEmit && npx eslint <arquivos> && npm run build`.

---

## Task 1: Primitivos de layout (`Page.tsx`)

**Files:**
- Create: `frontend/src/components/ui/Page.tsx`

Contexto: componentes estruturais puros que mesclam `className` com `cn` (de `frontend/src/lib/utils.ts`). Sem lógica, sem teste unitário (padrão do projeto p/ layout puro); a verificação é tsc/lint/build + uso nas próximas tasks.

- [ ] **Step 1: Criar o arquivo**

```tsx
import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

/** Wrapper padrão de página: largura fluida com teto alto p/ ultrawide. */
export function PageContainer({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('mx-auto w-full max-w-[1700px] px-4 sm:px-6 lg:px-8 py-6 space-y-6', className)}>
      {children}
    </div>
  )
}

/** Grade de página de detalhe: principal (2/3) + lateral (1/3), reflui no xl. */
export function DetailGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('grid grid-cols-1 xl:grid-cols-3 gap-6 items-start', className)}>
      {children}
    </div>
  )
}

/** Coluna principal do DetailGrid. */
export function DetailMain({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('xl:col-span-2 space-y-6 min-w-0', className)}>{children}</div>
}

/** Coluna lateral do DetailGrid. */
export function DetailAside({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('space-y-6 min-w-0', className)}>{children}</div>
}
```

- [ ] **Step 2: Verificar**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/components/ui/Page.tsx`
Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/Page.tsx
git commit -m "feat(ui): primitivos de layout PageContainer + DetailGrid"
```

---

## Task 2: Aparelho (Frota) — DetailGrid

**Files:**
- Modify: `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`

Contexto: hoje o conteúdo está em coluna única `max-w-3xl`. Header full width; formulário na principal; resultado da calibração + histórico na lateral. No modo **novo** (não-editando) usa coluna única estreita.

- [ ] **Step 1: Importar os primitivos**

Adicionar após a linha de import de `equipamentosApi`:

```tsx
import { PageContainer, DetailGrid, DetailMain, DetailAside } from '../../components/ui/Page'
```

- [ ] **Step 2: Trocar o wrapper externo**

Trocar `<div className="px-4 md:px-6 py-6 space-y-6 max-w-3xl">` (abertura do return principal) por `<PageContainer>`, e a `</div>` que fecha esse wrapper (a última, antes do fechamento da função) por `</PageContainer>`.

- [ ] **Step 3: Envolver form + laterais no DetailGrid**

Trocar a abertura `<form className="space-y-6" onSubmit={salvar}>` por:

```tsx
      <div className={editando ? '' : 'max-w-3xl'}>
      {editando ? (
        <DetailGrid>
          <DetailMain>
            <form className="space-y-6" onSubmit={salvar}>
```

E o bloco que hoje vem depois de `</form>` (as seções "Última calibração (resultado da OS)" e "Histórico de movimentação", cada uma com seu `{editando && ...}`) passa a ficar dentro de `DetailAside`. Estrutura final do trecho (do `</form>` até antes de `{abrindoOS && ...}`):

```tsx
            </form>
          </DetailMain>
          <DetailAside>
            {obj && (obj.calib_cert || obj.calib_situacao || obj.calib_teste_media) && (
              <Secao titulo="Última calibração (resultado da OS)">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-slate-300">
                  <p>Certificado: <span className="text-slate-100">{obj.calib_cert ?? '—'}</span></p>
                  <p>Situação: <span className="text-slate-100">{obj.calib_situacao ?? '—'}</span></p>
                  <p>Temperatura: <span className="text-slate-100">{obj.calib_temp ?? '—'}</span></p>
                  <p>Pressão: <span className="text-slate-100">{obj.calib_pressao ?? '—'}</span></p>
                  <p>Média dos testes: <span className="text-slate-100">{obj.calib_teste_media ?? '—'}</span></p>
                </div>
              </Secao>
            )}
            <Secao titulo="Histórico de movimentação">
              {historico.length === 0 ? (
                <p className="text-sm text-slate-500">Sem movimentações.</p>
              ) : (
                <Table head={<><TH>Data</TH><TH>Saída</TH><TH>Entrada</TH></>}>
                  {historico.map((m) => (
                    <tr key={m.id} className="hover:bg-background-elevated transition-colors">
                      <TD>{m.datamov ?? '—'}</TD>
                      <TD>{m.saida ?? '—'}</TD>
                      <TD>{m.entrada ?? '—'}</TD>
                    </tr>
                  ))}
                </Table>
              )}
            </Secao>
          </DetailAside>
        </DetailGrid>
      ) : (
        <form className="space-y-6" onSubmit={salvar}>
```

Ou seja: quando **editando**, o form vai em `DetailMain` e as seções read-only em `DetailAside` dentro de `DetailGrid`; quando **novo**, só o form (em coluna única, dentro do `max-w-3xl`). Para isso, o form precisa ser fechado e reaberto nas duas ramificações. **Atenção:** o conteúdo do `<form>` (seções Aparelho/Calibração + botão submit) é idêntico nas duas ramificações — reproduza-o nas duas, ou extraia uma variável `const formConteudo = (<>...</>)` antes do return e use `<form ...>{formConteudo}</form>` nos dois lugares (preferível p/ DRY). Fechar o `<div>` aberto no Step 3 com `</div>` antes de `{abrindoOS && ...}`.

- [ ] **Step 4: Grids de campos responsivos**

Dentro do form, trocar:
- `<div className="grid grid-cols-2 gap-3">` → `<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">` (ambas as ocorrências na seção Aparelho)
- `<div className="grid grid-cols-3 gap-3">` (seção Calibração) → `<div className="grid grid-cols-1 sm:grid-cols-3 gap-3">`

- [ ] **Step 5: Verificar**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/frota/EquipamentoClienteDetailPage.tsx && npm run build`
Expected: sem erros, build verde.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/frota/EquipamentoClienteDetailPage.tsx
git commit -m "feat(ux): pagina do aparelho em layout fluido (DetailGrid)"
```

---

## Task 3: OS — DetailGrid

**Files:**
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx`

Contexto: o hero (cabeçalho + FaseStepper) continua full width no topo. As seções abaixo passam a um `DetailGrid`: principal = Recebimento + Fotos + Datas + Resultados da calibração; lateral = Certificados + Histórico.

- [ ] **Step 1: Importar primitivos**

Adicionar após o import de `./FotoLightbox`:

```tsx
import { PageContainer, DetailGrid, DetailMain, DetailAside } from '../../components/ui/Page'
```

- [ ] **Step 2: Trocar o wrapper externo**

Trocar `<div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl">` por `<PageContainer>` e a `</div>` correspondente (última antes do fechamento da função, depois dos modais) por `</PageContainer>`.

- [ ] **Step 3: Inserir o DetailGrid após o hero**

Logo após o fechamento do bloco do hero (a `</div>` que fecha `{/* Hero */}` … o card que contém título+stepper), inserir `<DetailGrid><DetailMain>` antes do comentário `{/* Recebimento */}`. As seções **Recebimento**, **Fotos**, **Datas** e **Resultados da calibração** ficam dentro de `DetailMain`. Depois da seção "Resultados da calibração", fechar `</DetailMain>` e abrir `<DetailAside>`; as seções **Certificados** e **Histórico** ficam dentro de `DetailAside`; fechar `</DetailAside></DetailGrid>` antes dos modais (`{acao === 'avancar' && ...}`).

- [ ] **Step 4: Verificar**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/ordens/OrdemDetailPage.tsx && npm run build`
Expected: sem erros, build verde.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/ordens/OrdemDetailPage.tsx
git commit -m "feat(ux): detalhe da OS em layout fluido (DetailGrid)"
```

---

## Task 4: Cliente — DetailGrid

**Files:**
- Modify: `frontend/src/app/clientes/ClienteDetailPage.tsx`

Contexto: header full width; principal = form (Identificação + Endereço + Contatos + Observações + botão salvar); lateral = Funcionários + Usuários do portal (só editando). No modo **novo** usa coluna única estreita.

- [ ] **Step 1: Importar primitivos**

Adicionar após o import de `UsuariosPortalSection`:

```tsx
import { PageContainer, DetailGrid, DetailMain, DetailAside } from '../../components/ui/Page'
```

- [ ] **Step 2: Trocar o wrapper externo**

Trocar `<div className="px-4 md:px-6 py-6 space-y-6 max-w-3xl">` por `<PageContainer>` e a `</div>` final por `</PageContainer>`.

- [ ] **Step 3: DetailGrid quando editando**

Quando `editando`, envolver o `<form>` em `DetailMain` e as duas seções abaixo (`FuncionariosSection` e `UsuariosPortalSection`) em `DetailAside`, tudo dentro de `DetailGrid`. Quando **novo**, manter só o `<form>` em coluna única `max-w-3xl` (sem grid). Estrutura:

```tsx
      {editando ? (
        <DetailGrid>
          <DetailMain>
            <form className="space-y-6" onSubmit={salvar}>{/* …conteúdo do form… */}</form>
          </DetailMain>
          <DetailAside>
            <FuncionariosSection clienteId={Number(id)} podeEditar={podeEditar} />
            {podeEditar && <UsuariosPortalSection clienteId={Number(id)} />}
          </DetailAside>
        </DetailGrid>
      ) : (
        <div className="max-w-3xl">
          <form className="space-y-6" onSubmit={salvar}>{/* …mesmo conteúdo… */}</form>
        </div>
      )}
```

Para evitar duplicar o conteúdo do form, extrair `const formConteudo = (<>…</>)` antes do return (incluindo as 4 `<Secao>` e o botão submit) e usar `<form className="space-y-6" onSubmit={salvar}>{formConteudo}</form>` nas duas ramificações.

- [ ] **Step 4: Grids de campos responsivos**

Trocar todas as ocorrências de `<div className="grid grid-cols-2 gap-3">` por `<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">` e `<div className="grid grid-cols-3 gap-3">` por `<div className="grid grid-cols-1 sm:grid-cols-3 gap-3">` dentro do form (Identificação, Endereço, Contatos).

- [ ] **Step 5: Verificar**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/clientes/ClienteDetailPage.tsx && npm run build`
Expected: sem erros, build verde.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/clientes/ClienteDetailPage.tsx
git commit -m "feat(ux): detalhe do cliente em layout fluido (DetailGrid)"
```

---

## Task 5: Caixa — DetailGrid

**Files:**
- Modify: `frontend/src/app/caixas/CaixaDetailPage.tsx`

Contexto: cabeçalho full width; principal = ações do lote + tabela de OS; lateral = descrição/obs (form ou texto) + um card de resumo (totais/clientes). O bloco de erro do caminho de carregamento (`if (erro || !caixa)`) também ganha `PageContainer` para padronizar (opcional, ver Step 2).

- [ ] **Step 1: Importar primitivos**

Adicionar após o import de `AbrirOSModal`:

```tsx
import { PageContainer, DetailGrid, DetailMain, DetailAside } from '../../components/ui/Page'
```

- [ ] **Step 2: Trocar o wrapper do return principal**

Trocar `<div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl">` por `<PageContainer>` e a `</div>` final (antes do fechamento da função, depois dos modais) por `</PageContainer>`. (O bloco de erro com `<div className="px-4 md:px-6 py-6">` pode permanecer como está.)

- [ ] **Step 3: Reorganizar em DetailGrid**

Manter o cabeçalho (link "← Caixas" + título + erroAcao) full width logo após `<PageContainer>`. Depois, envolver o restante em `DetailGrid`:

- `DetailMain`: as **Ações do lote** (`{podeEscrever && (<div className="flex gap-2 flex-wrap">…)}`) + a **section "Ordens de serviço"** (tabela).
- `DetailAside`: a **descrição/obs** (o `<section>` do form `podeEscrever` e o `<section>` read-only `!podeEscrever && caixa.obs`) + um novo card de resumo:

```tsx
            <section className="rounded-2xl bg-background-surface border border-border p-5">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Resumo</p>
              <dl className="space-y-1 text-sm text-slate-300">
                <div className="flex justify-between"><dt>Data</dt><dd className="text-slate-100">{formatData(caixa.data)}</dd></div>
                <div className="flex justify-between"><dt>OS</dt><dd className="text-slate-100">{caixa.total_os}</dd></div>
                <div className="flex justify-between"><dt>Clientes</dt><dd className="text-slate-100">{clientesUnicos}</dd></div>
              </dl>
            </section>
```

Os modais (Vincular/Mover/Picker/AbrirOSModal) ficam fora do `DetailGrid`, antes de `</PageContainer>` (como já estão hoje no fim do return).

- [ ] **Step 4: Verificar**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/caixas/CaixaDetailPage.tsx && npm run build`
Expected: sem erros, build verde.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/caixas/CaixaDetailPage.tsx
git commit -m "feat(ux): detalhe da caixa em layout fluido (DetailGrid)"
```

---

## Task 6: Páginas de lista e demais telas — PageContainer

**Files:**
- Modify: `frontend/src/app/ordens/OrdensPage.tsx`, `frontend/src/app/clientes/ClientesPage.tsx`, `frontend/src/app/frota/FrotaPage.tsx`, `frontend/src/app/alertas/CobrancaPage.tsx`, `frontend/src/app/solicitacoes/SolicitacoesPage.tsx`, `frontend/src/app/cadastros/CadastrosPage.tsx`, `frontend/src/app/certificados/CertificadosPage.tsx`, `frontend/src/app/caixas/CaixasPage.tsx`, `frontend/src/app/pages/DashboardPage.tsx`, `frontend/src/app/pages/MinhaContaPage.tsx`, `frontend/src/app/acesso/UsuariosPage.tsx`

Contexto: padronizar o wrapper de página. Em cada arquivo, trocar a `<div>` externa da página (a que tem `className="px-4 md:px-6 py-6 space-y-6 …"`) por `<PageContainer>`…`</PageContainer>`, importando o componente. Classes de largura antigas (`max-w-*`) são descartadas — o teto vem do `PageContainer`. Se a `<div>` externa tiver classes extras NÃO relacionadas a largura/padding (raro), passá-las via `className` do `PageContainer`.

- [ ] **Step 1: Para CADA arquivo da lista acima**

  1. Adicionar o import: `import { PageContainer } from '../../components/ui/Page'` (ajustar a profundidade `../` conforme a pasta — todas estão em `src/app/<modulo>/`, então `../../components/ui/Page`).
  2. Localizar a `<div className="px-4 md:px-6 py-6 space-y-6 …">` que abre o conteúdo da página e trocar por `<PageContainer>`; trocar a `</div>` que a fecha por `</PageContainer>`.
  3. Se o componente tiver mais de um `return` (ex.: estado de carregando/erro com wrapper próprio), padronizar **apenas** o return principal da página; estados de loading podem ficar como estão.

- [ ] **Step 2: Verificar tudo junto**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app && npm run build`
Expected: sem erros, build verde.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app
git commit -m "feat(ux): paginas de lista usam PageContainer (largura padrao)"
```

---

## Task 7: Changelog v1.4.1 + verificação final + memória

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

Contexto: as melhorias de UX (navegação clicável já commitada + layout fluido) entram numa nova versão v1.4.1 (a v1.4.0 já foi publicada). Inserir a entrada no topo do array `CHANGELOG`.

- [ ] **Step 1: Adicionar a versão v1.4.1 no topo do array**

No início de `export const CHANGELOG: VersaoChangelog[] = [`, inserir:

```ts
  {
    versao: '1.4.1',
    data: '10/06/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Layout das páginas agora preenche a tela e se adapta ao tamanho do monitor — o conteúdo se distribui em colunas em telas grandes e reflui em telas menores, acabando com o espaço vazio à direita nas páginas de detalhe.' },
      { tipo: 'melhoria', texto: 'No detalhe da OS, o nome do cliente e o aparelho viraram links — clicar leva direto à ficha do cliente ou do equipamento.' },
    ],
  },
```

- [ ] **Step 2: Verificar build + suíte**

Run: `cd frontend && npm run build && npx vitest run`
Expected: build verde; 113 testes passando.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.4.1 — layout fluido + navegacao clicavel"
```

- [ ] **Step 4: E2E visual (com o usuário)**

Abrir Aparelho, OS, Cliente e Caixa em tela cheia: confirmar que preenchem a largura, refluem ao reduzir janela/zoom, e nada quebra (overflow de tabela/inputs). Conferir uma página de lista (ex.: Ordens) e o modo "novo" (Novo cliente / cadastrar aparelho) em coluna única.

- [ ] **Step 5: Atualizar memória**

Atualizar `C:\Users\TI\.claude\projects\d--GitHub-GestorHS\memory\project_gestorhs.md`: registrar os primitivos de layout (`PageContainer`/`DetailGrid`/`DetailMain`/`DetailAside` em `components/ui/Page.tsx`), o padrão de largura fluida (teto ~1700px) e que as páginas de detalhe usam grade principal+lateral.

---

## Self-Review (preenchido)

**Spec coverage:** primitivos (T1); páginas de detalhe Aparelho/OS/Cliente/Caixa (T2–T5); listas/demais (T6); grids de campos responsivos (T2/T4); changelog/memória/E2E (T7). Tudo coberto.

**Type consistency:** `PageContainer`, `DetailGrid`, `DetailMain`, `DetailAside` com a mesma assinatura `{ children, className? }` em todas as tasks; import sempre de `../../components/ui/Page`.

**Placeholders:** as transformações de página usam âncoras exatas (classes/strings presentes nos arquivos atuais) e mostram a estrutura-alvo; o conteúdo extenso de form é reutilizado via `formConteudo` (DRY) em vez de reproduzido. Sem TODOs.
