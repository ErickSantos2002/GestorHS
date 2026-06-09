# GestorHS — Baixar certificado em PDF (Chromium headless)

**Data:** 2026-06-09
**Status:** Aprovado para implementação
**Motivação:** Hoje o laboratório gera o certificado em HTML (salvo em `os_certificados.html`) e, para ter um PDF, precisa abrir "Imprimir" → salvar como PDF → reenviar manualmente o arquivo. Queremos um download direto: um botão **"Baixar PDF"** que gera o PDF no servidor a partir do HTML já gerado, eliminando o upload manual.

**Contexto:** continuação da feature de geração de certificado (branch `feat/geracao-certificado`, ainda não mesclada). O motor de preenchimento (`certificado_gerar.py`), os modelos e `os_certificados` já existem e ficam intactos.

## Decisões de design
- **Motor:** Chromium headless via **Playwright (Python)** no backend. É um navegador de verdade, então renderiza exatamente o mesmo HTML que o usuário vê hoje na pré-visualização/impressão. Isso preserva a aparência do certificado — requisito **ISO** (mudar o estilo exigiria nova revisão).
- **HTML dos modelos intocado.** Não reescrevemos os modelos. Só adicionamos um "envelope" de CSS de impressão em volta do HTML do certificado para controlar **paginação** (A4, margens, quebra de página), nunca o conteúdo visível.
- **Quebra de página / dois cabeçalhos:** os modelos legados têm um cabeçalho por página (proposital). Hoje a quebra `[pulapagina]` (já convertida em `<div style="page-break-after: always">`) não é respeitada na renderização atual; com Chromium ela funciona e o 2º cabeçalho cai sozinho na página 2.
- **Geração sob demanda:** o PDF é gerado a cada clique a partir do `os_certificados.html` atual. Não persistimos o PDF. A coluna `os_certificados.pdf` (existente, não usada neste fluxo) fica como está.
- **Custo aceito:** a imagem Docker do backend cresce (~300–400 MB: Chromium + libs de sistema) e o build fica mais lento. Trade-off aceito em troca da fidelidade.

## Escopo
**Dentro:**
- Módulo `app/core/certificado_pdf.py` que converte o HTML de um certificado em bytes de PDF (A4) usando Playwright/Chromium.
- Endpoint `GET /ordens/{id}/certificado/{tipo}/pdf` retornando `application/pdf` (download).
- Frontend: botão **"Baixar PDF"** por certificado na seção *Certificados*; remoção do "Imprimir", do upload "Enviar certificado (PDF)" e do "Baixar certificado" antigo; remoção da rota/componente `CertificadoImprimir` e do `certificadoApi`.
- Dockerfile do backend: instalar Playwright + Chromium + dependências de sistema.

**Fora:**
- Certificado de Manutenção (continua só Calibração no fluxo do lab; mas o endpoint aceita `tipo` genérico C/M).
- Persistir/cachear o PDF.
- Mudanças no HTML dos modelos ou no motor de preenchimento.

## Backend

### Novo módulo `app/core/certificado_pdf.py`
- Constante `_DOCUMENTO`: um HTML wrapper completo (`<!doctype html><html><head><meta charset><style>…</style></head><body>{corpo}</body></html>`) cujo `<style>` define o CSS de impressão:
  - `@page { size: A4; margin: 10mm; }`
  - `body { margin: 0; background: #fff; color: #000; }`
  - regra para a quebra de página já presente no corpo continuar funcionando (`div[style*="page-break-after"]`/o próprio inline style basta).
  - O `{corpo}` é o `os_certificados.html` inserido **sem escapar** (HTML confiável: modelo de admin/lab + valores já escapados no momento da geração por `preencher`).
- Função `montar_documento(html_cert: str) -> str`: retorna `_DOCUMENTO` com o corpo embutido. (Unitariamente testável, sem Chromium.)
- Função `html_para_pdf(html_cert: str) -> bytes`: usa `sync_playwright`; `browser = chromium.launch()`, `page.set_content(montar_documento(html_cert), wait_until="networkidle")` (espera o logo de URL pública carregar), `pdf = page.pdf(format="A4", print_background=True, margin=...)`, fecha o browser, retorna `pdf`. Levanta exceção se o Chromium falhar (o endpoint converte em 500).
  - Roda em endpoint **sync** do FastAPI (executado no threadpool), então a API síncrona do Playwright é adequada.

### Endpoint `GET /ordens/{id}/certificado/{tipo}/pdf` (em `app/api/certificados_os.py`)
- Acesso de **leitura** para usuário logado (`Depends(get_current_usuario)`), consistente com `GET /ordens/{id}/certificados`.
- `tipo` é `C` ou `M` (valida; outro → 422/404).
- Busca `OSCertificado` por `os == id` e `tipo`. Se não existe ou `html` vazio → `HTTPException(404, "certificado não gerado")`.
- Chama `html_para_pdf(osc.html)`.
- Retorna `Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="certificado-{id}-{nome}.pdf"'})`, onde `nome` = `calibracao` para C e `manutencao` para M.
- Em falha do motor → `HTTPException(500, "falha ao gerar PDF")`.

### Dockerfile (`backend/Dockerfile`)
- Adicionar `playwright` ao `requirements.txt`.
- No build: `playwright install --with-deps chromium` (instala o Chromium e as libs de sistema). Garantir que rode como root no build e que o cache do navegador esteja acessível em runtime (usar `PLAYWRIGHT_BROWSERS_PATH` padrão ou caminho fixo).

## Frontend

### `app/ordens/api.ts`
- Remover `certificadoApi` (enviar/baixar) — sem uso após esta mudança.
- Adicionar em `ordensApi` (ou helper) `baixarCertificadoPdf(id, tipo)`: busca `GET /ordens/{id}/certificado/{tipo}/pdf` com `apiFetch` (Bearer), pega o `blob`, cria object URL e dispara download via âncora com `download="certificado-{id}-{tipo}.pdf"`, depois `revokeObjectURL`.

### `app/ordens/OrdemDetailPage.tsx`
- Seção **Certificados**: trocar o link `Imprimir` por um botão **"Baixar PDF"** que chama `baixarCertificadoPdf(osId, c.tipo)`; estado de erro reaproveita `erroCert`.
- Seção **Resultados da calibração**: remover o botão de upload "Enviar certificado (PDF)" (a `acao` da seção) e a linha/Campo "PDF" com "Baixar certificado". Manter os demais campos (Certificado, Temperatura, Pressão, Média, Situação) exibidos. Remover handlers `onEnviarCertificado`/`onBaixarCertificado` e `podeCertificado` se ficarem sem uso. `temCalib` deixa de considerar `pdf_certificado`.

### Rotas / componente
- Remover a rota `ordens/:id/certificado/:tipo/imprimir` de `routes.tsx` e o arquivo `CertificadoImprimir.tsx` (sem referências após a troca).

## Erros
- Sem certificado gerado → 404 → front mostra "certificado não gerado" (não deve acontecer pelo fluxo, pois o botão só aparece quando há certificado na lista).
- Falha do Chromium → 500 → front mostra "Falha ao baixar PDF".

## Testes / verificação
- **Backend (pytest):** unitário de `montar_documento` — confirma que o corpo do certificado está embutido e que o wrapper contém `@page` e `size: A4`. **Não** subir Chromium no pytest. Endpoint: pode-se testar o 404 (sem certificado) com o motor mockado; o caminho de sucesso real fica para o E2E.
- **Frontend (vitest/tsc/lint/build):** `baixarCertificadoPdf` monta a request certa; `certificadoApi` removido sem quebrar imports; build verde.
- **E2E manual:** OS no lab com certificado gerado → "Baixar PDF" → abrir o PDF → conferir A4, 2 páginas com um cabeçalho cada e a quebra correta. Comparar visualmente com o certificado em tela (deve ser idêntico).

## Critérios de aceite
- Botão "Baixar PDF" em cada certificado gerado baixa um PDF A4 com aparência idêntica ao certificado em tela (mesmo estilo → ISO preservada), paginado corretamente (cabeçalho por página, quebra `[pulapagina]` respeitada).
- Upload manual de PDF e a rota de impressão removidos; sem código órfão.
- HTML dos modelos e o motor de preenchimento inalterados.
- Backend builda com Chromium; pytest/vitest/tsc/lint/build verdes. Changelog (v1.4.0) atualizado.

## Fora do v1 desta etapa
Cache/persistência do PDF, certificado de Manutenção no fluxo do lab, edição WYSIWYG do modelo.
