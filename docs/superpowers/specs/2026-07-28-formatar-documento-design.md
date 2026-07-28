# Formatar CNPJ/CPF na interface — Design

**Data:** 2026-07-28
**Área:** frontend (novo `src/lib/documento.ts` + ~aplicação nos pontos de documento) + 1 respingo backend (`proposta_pdf.py`).
**Tipo:** melhoria de UX (formatação de documento), sem mudança de dado.

## Problema

Na tela (página de Propostas e outras), CNPJ/CPF aparecem como número cru (`36312056000552`) porque o **frontend não tem formatador**. O pessoal copia de fora já formatado (`36.312.056/0005-52`) e hoje não há máscara nos campos. Queremos formatar automaticamente em **todo lugar** — exibição **e** digitação — para **CNPJ e CPF**.

## Contexto que simplifica

- **Backend já normaliza a entrada:** validator em `schemas/clientes.py` faz `re.sub(r"\D","",v)` em `cgc`/`cpf` — colar formatado já salva como dígitos. Storage é dígitos-only (não muda).
- **PDFs já formatam:** certificado (`certificado_gerar._fmt_doc`) e proposta (`proposta_pdf._fmt_documento`) já saem com máscara. **Única exceção:** o documento do endereço de entrega da proposta (`proposta_pdf.py:490`) sai cru.

Logo, a mudança é **quase toda frontend** (exibição + máscara de input) + 1 correção pontual no PDF da proposta.

## Design

### 1. Util `src/lib/documento.ts` (novo)
- `soDigitos(v: string | null | undefined): string` — remove tudo que não é dígito.
- `formatarDocumento(v): string` — **exibição**: 14 díg → `00.000.000/0000-00`; 11 díg → `000.000.000-00`; qualquer outro tamanho → devolve os dígitos como estão (espelha o backend). Robusto a valor já formatado (tira e recoloca).
- `mascararCNPJ(v)` / `mascararCPF(v)` — **máscara progressiva** para inputs de tipo conhecido (insere `.`/`/`/`-` conforme os dígitos entram; capa em 14/11 díg).
- `formatarDocumento` serve o campo combinado (portal) e todo display; as máscaras progressivas servem os campos de tipo fixo.

### 2. Exibição (aplicar `formatarDocumento`)
- `clientes/ClientesPage.tsx:83` (`{c.cgc || c.cpf}`)
- `propostas/PropostasPage.tsx:150` (`{p.cliente_documento}`)
- `propostas/PropostaModal.tsx:462` e `:486` (CNPJ/CPF do cliente selecionado e nos resultados de busca)
- **Varredura:** aplicar em qualquer outro render read-only de `cgc`/`cpf`/`documento` em `.tsx` (certificados/ordens/frota) encontrado no sweep.

### 3. Digitação (máscara automática)
- `clientes/ClienteFormFields.tsx:52` — campos **separados** CNPJ (`cgc`) e CPF (`cpf`): `mascararCNPJ`/`mascararCPF`. Estado guarda dígitos; envio manda dígitos (backend normaliza de qualquer forma).
- `portal/PortalLoginPage.tsx:66` — campo combinado "CNPJ ou CPF": `formatarDocumento` (formata quando completa 11/14; aceita colado). Normaliza pra dígitos no `login`/`definirSenha`.
- `propostas/PropostaModal.tsx:517` — override `documento`: máscara + o **default** (vindo de `cgc || cpf`, hoje cru) passa a ser formatado.
- **Campos `cnpj` dos certificados** (certificados/frota/ordens modais) — máscara no input (o PDF já formata no backend; é só consistência na tela).

### 4. Respingo backend
- `proposta_pdf.py:490` — o documento do endereço de entrega passa por `_fmt_documento` como os demais.

## Fora de escopo
- Mudar storage (continua dígitos), validação de dígito verificador de CPF/CNPJ (só máscara visual), e formatação em relatórios/exports fora da UI.

## Rollout
Frontend + 1 linha backend. **Sem migração**, sem mudar dado. Mini versão **v1.27.3**.

## Testes
- **Util:** `formatarDocumento` (14→CNPJ, 11→CPF, 8/vazio/estranho→dígitos; já-formatado→reformata); `mascararCNPJ`/`mascararCPF` (progressivo, capa no tamanho, ignora não-dígitos).
- **Exibição:** os pontos enumerados renderizam formatado (ex.: lista de clientes mostra `36.312.056/0005-52`).
- **Input:** digitar/colar no campo de CNPJ do cadastro mostra formatado e o payload sai só com dígitos; login do portal normaliza.
- **Backend:** o documento de entrega no HTML da proposta sai formatado.

## Arquivos
Frontend: `lib/documento.ts` (novo) + `clientes/ClientesPage.tsx`, `clientes/ClienteFormFields.tsx`, `propostas/PropostasPage.tsx`, `propostas/PropostaModal.tsx`, `portal/PortalLoginPage.tsx`, e os modais de certificado com campo `cnpj`. Backend: `core/proposta_pdf.py`. Changelog v1.27.3.
