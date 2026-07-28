# Editar OS (Administrador) — Design

**Data:** 2026-07-28
**Área:** backend (`app/api/ordens.py`, `app/schemas/ordens.py`) + frontend (`src/app/ordens/`)
**Tipo:** hotfix pequeno (novo endpoint Admin-only + modal de edição).

## Problema

Uma OS pode ser aberta com dados de recebimento errados (ex.: marcada como **Manutenção** quando era **Calibração** — caso real, OS 10870), e hoje **não há como corrigir** pela interface. Corrigir no banco resolve pontual, mas o time precisa de autonomia para ajustes de digitação.

## Objetivo

Permitir que o **Administrador** edite os **campos de recebimento/cabeçalho** de uma OS pela interface. Aparelho e cliente ficam **fora** (efeito em cascata — frota, certificado, cliente principal da caixa, integrações — tratados noutra hora).

## Campos editáveis (recebimento/cabeçalho)
- `tipo_servico` (`C` Calibração / `M` Manutenção / `A` Ambas)
- `condicao_chegada` (validada contra `rec.CONDICOES_CHEGADA`)
- `checklist` (acessórios — lista de ids, convertida via `rec.checklist_ids_para_csv`)
- `pilhas` (int)
- `bocais` (int → coluna `sopradores`)
- `garantia` (bool)
- `obs` (observações)
- `data_chegada` (date → gravada como datetime UTC, como no `abrir`)

**Fora de escopo:** aparelho (`equipamento_cliente`), `cliente`, `caixa`, resultados de calibração (`calib_*`), fase/desfecho, financeiro (`nota_fiscal`/`pago`).

## Design

### Backend — `PUT /ordens/{id}/editar` (Admin-only)
- `require_funcao("Administrador")`.
- Corpo `OrdemEditarIn` (todos os campos opcionais; só aplica os enviados via `model_dump(exclude_unset=True)`).
- Valida `condicao_chegada` (se enviada) contra `rec.CONDICOES_CHEGADA`; `checklist` via `rec.checklist_ids_para_csv` (mesma validação do `abrir`); `data_chegada` (date) → datetime UTC.
- `tipo_servico` restrito a `C`/`M`/`A`.
- Aplica os campos na OS, `registrar_log(db, ordem, usuario, "OS editada (admin): <resumo dos campos alterados>")`, commit.
- Recomputa `_anotar_modelos_faltantes(db, ordem)` na resposta (`certificado_modelos_faltantes` é transiente) — assim mudar o tipo já reflete o aviso de certificado. Retorna `OrdemOut`.

### Frontend — modal "Editar OS" (Admin-only)
- Botão **"Editar OS"** no cabeçalho da `OrdemDetailPage`, visível só para `isAdmin(user)` (de `auth/roles`).
- `EditarOSModal.tsx` — espelha os campos do `AbrirOSModal` (Select de tipo, Select de condição, checklist, pilhas/bocais, checkbox de garantia, textarea de obs, input de data), pré-preenchido com os valores atuais da OS.
- Ao salvar → `ordensApi.editar(id, payload)` (PUT) → recarrega a OS.

## Rollout
Produção. **Sem migração** (só edita colunas existentes). Deploy = push + rebuild. Mini versão **v1.26.1**.

## Testes
- **Backend:** editar exige Admin (403 pra outra função); mudar `tipo_servico` M→C recomputa `certificado_modelos_faltantes` (fica `[]` quando o aparelho tem modelo de C); `condicao_chegada` inválida → 400; campos não enviados não são sobrescritos; log registrado.
- **Frontend:** botão "Editar OS" só aparece para Admin; o modal pré-preenche e o submit chama `ordensApi.editar` com os campos.

## Arquivos afetados
- Backend: `schemas/ordens.py` (`OrdemEditarIn`), `api/ordens.py` (endpoint `editar`).
- Frontend: `ordens/EditarOSModal.tsx` (novo), `ordens/OrdemDetailPage.tsx` (botão), `ordens/api.ts` (`ordensApi.editar` + tipo).
- Changelog: v1.26.1.
