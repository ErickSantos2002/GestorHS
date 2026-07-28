# Proposta: campo Introdução no formulário — Design

**Data:** 2026-07-28
**Área:** frontend (`app/propostas/PropostaModal.tsx`).
**Tipo:** completar port do GrowthHS (campo faltante na UI).

## Problema

A proposta tem o campo **Introdução** (texto livre) para o pós-vendas escrever notas (ex.: "Endereço Confirmado."), mas ele não aparece no formulário — ficou de fora na portabilidade do GrowthHS. O backend já suporta tudo:
- Coluna `propostas.intro` (Text) já existe; schema `intro: Optional[str]` já aceito.
- O PDF já renderiza a seção "Introdução" (`proposta_pdf.py:549-555`).
- O form já **guarda e carrega** `intro` (`PropostaModal` defaults `intro: ''`, load `p.intro ?? ''`) e o submit já envia (payload usa `...form`).

Falta só o **`<textarea>` na tela**.

## Design

Adicionar um textarea rotulado **"Introdução"** na `PropostaModal`, **logo abaixo da seção de dados do cliente/endereço de entrega** (antes da seção "Aparelhos"), sempre visível, vazio por padrão. Ligar a `form.intro` via `setField('intro', ...)`, espelhando o markup do textarea de `endereco_entrega` (mesmo componente/estilo). Nada mais muda — form/payload/backend/PDF já prontos.

## Fora de escopo
- Backend, migração, PDF (já existem).

## Rollout
Frontend puro, sem migração. Mini versão **v1.27.8**.

## Testes
- **PropostaModal:** o textarea "Introdução" é renderizado; digitar nele atualiza o estado e o submit envia `intro` no payload (`propostasApi.criar`/`atualizar` chamado com `intro: '<texto>'`). Ao editar uma proposta existente com `intro`, o textarea vem pré-preenchido.

## Arquivos
`app/propostas/PropostaModal.tsx` (+ teste). Changelog v1.27.8.
