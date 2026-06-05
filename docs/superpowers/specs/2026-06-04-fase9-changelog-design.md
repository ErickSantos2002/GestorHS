# GestorHS — Fase 9 (Changelog / "O que há de novo?")

**Data:** 2026-06-04
**Status:** Aprovado para implementação
**Motivação:** Espelhar o recurso do HSGrowth CRM: um rodapé de versão na sidebar que, ao clicar, abre um modal de changelog com todas as versões e suas mudanças (Corrigido/Melhoria/Novidade). Dá visibilidade das entregas à equipe.

## Escopo
**Dentro:** rodapé de versão na sidebar interna (`/app`) + modal de changelog; dados num arquivo TS no front (a equipe edita a cada release).
**Fora:** changelog no portal do cliente; backend/admin para gerenciar versões; i18n.

## Decisões
- **Dados hardcoded no front** (`src/app/changelog/data.ts`) — sem backend; a equipe controla. A versão atual = primeira entrada da lista (`VERSAO_ATUAL`).
- **Conteúdo inicial:** uma entrada **v1.0.0 (2026-06-04)** marcando o go-live, listando os módulos como Novidades.

## Dados (`src/app/changelog/data.ts`)
- `TipoMudanca = 'novidade' | 'melhoria' | 'correcao'`.
- `MudancaItem { tipo: TipoMudanca; texto: string }`.
- `VersaoChangelog { versao: string; data: string /* DD/MM/AAAA */; itens: MudancaItem[] }`.
- `CHANGELOG: VersaoChangelog[]` em ordem **decrescente** (mais nova primeiro).
- `VERSAO_ATUAL = CHANGELOG[0].versao`.
- Mapa de rótulo/tom por tipo: `correcao`→{label:'Corrigido', tone:'warning'}, `melhoria`→{label:'Melhoria', tone:'primary'}, `novidade`→{label:'Novidade', tone:'info'}.

## UI
**Rodapé da sidebar** (`layout/Sidebar.tsx`, após o `<nav>`): botão clicável.
- Expandida: "GestorHS v{VERSAO_ATUAL}" (negrito) + "© 2026 Health & Safety Tech" (menor, slate-600); hover destaca.
- Colapsada: só "v{VERSAO_ATUAL}" centralizado, menor.
- Ao clicar, abre o `ChangelogModal` (estado local `aberto` na Sidebar).

**`ChangelogModal`** (`app/changelog/ChangelogModal.tsx`) — modal próprio (mais largo que o `Modal` padrão, que é `max-w-md`):
- Overlay igual ao `Modal` (fixed inset, `bg-black/60 backdrop-blur-sm`, fecha ao clicar fora e no X; fecha no Esc).
- Cartão `max-w-lg`, altura limitada (`max-h-[85vh]`), corpo com scroll (`overflow-y-auto`).
- Cabeçalho: título "O que há de novo?" + subtítulo "Atualizações recentes do GestorHS" + botão X.
- Corpo: para cada versão — linha com `Badge primary` da versão (`v1.0.0`) + data + (na primeira) `Badge primary` "Versão atual"; abaixo, os itens, cada um com `Badge` do tipo (Corrigido/Melhoria/Novidade) + texto.
- Rodapé: "GestorHS — desenvolvido internamente pela equipe".

## Conteúdo v1.0.0 (Novidades)
Acesso (usuários/funções/portal); Clientes e frota (com status de calibração); Ordens de serviço (kanban, fases, calibração, certificado); Cobrança (alertas + contato); Portal do cliente (frota/certificados/OS/solicitações); Dashboard (indicadores + OS por fase); Anexos (fotos da OS + PDF de certificado).

## Testes / verificação
- Vitest: `data.test.ts` — `VERSAO_ATUAL === CHANGELOG[0].versao`; toda versão tem `itens` não-vazio; todo `tipo` é válido.
- Telas: `tsc -b` + `lint` + `build`; conferência visual no navegador (rodapé abre o modal; tags coloridas; scroll).

## Critérios de aceite
- Rodapé na sidebar mostra "GestorHS v1.0.0" + copyright; clicar abre o modal com a v1.0.0 e suas novidades; etiquetas coloridas por tipo; "Versão atual" na mais recente; fecha por X/fora/Esc. Colapsada mostra a versão compacta. tsc/lint/build verdes.
