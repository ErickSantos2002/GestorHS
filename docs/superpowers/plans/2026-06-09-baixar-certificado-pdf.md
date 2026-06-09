# Baixar certificado em PDF — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Botão "Baixar PDF" que gera o PDF A4 do certificado no servidor (Chromium headless), a partir do HTML já salvo, removendo o upload manual de PDF.

**Architecture:** Backend isola a conversão HTML→PDF num módulo (`certificado_pdf.py`) usando Playwright/Chromium; um endpoint `GET /ordens/{id}/certificado/{tipo}/pdf` devolve `application/pdf`. O frontend baixa via blob autenticado. O HTML dos modelos e o motor de preenchimento ficam intactos (aparência idêntica → ISO preservada).

**Tech Stack:** FastAPI + SQLAlchemy (backend), Playwright (Chromium headless), React 19 + TS + Vite (frontend), pytest/vitest.

**Branch:** `feat/geracao-certificado` (continuação; já contém o rework do fluxo do lab e os ajustes Situação/Tipo).

**Spec:** `docs/superpowers/specs/2026-06-09-baixar-certificado-pdf-design.md`

---

## Task 1: Módulo `certificado_pdf.py` (wrapper + motor)

**Files:**
- Create: `backend/app/core/certificado_pdf.py`
- Test: `backend/tests/test_certificado_pdf.py`

Contexto: `montar_documento` embrulha o HTML do certificado num documento HTML completo com CSS de impressão A4. É HTML confiável (modelo de admin/lab + valores já escapados em `preencher`), então o corpo entra **sem escapar**. `html_para_pdf` usa Playwright (Chromium) e só é exercitado em E2E — o pytest testa apenas `montar_documento`.

- [ ] **Step 1: Escrever o teste de `montar_documento`**

```python
# backend/tests/test_certificado_pdf.py
def test_montar_documento_embute_corpo_e_a4():
    from app.core.certificado_pdf import montar_documento
    doc = montar_documento("<table><tr><td>Cliente: ACME</td></tr></table>")
    assert "Cliente: ACME" in doc          # corpo embutido sem escapar
    assert "<table>" in doc
    assert "@page" in doc                  # CSS de impressão presente
    assert "A4" in doc
    assert doc.strip().lower().startswith("<!doctype html")


def test_montar_documento_corpo_vazio():
    from app.core.certificado_pdf import montar_documento
    doc = montar_documento("")
    assert "@page" in doc and "A4" in doc
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_certificado_pdf.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.certificado_pdf'`

- [ ] **Step 3: Implementar o módulo**

```python
# backend/app/core/certificado_pdf.py
"""Converte o HTML de um certificado (os_certificados.html) em PDF A4 usando
Chromium headless via Playwright. O HTML do certificado é confiável (modelo de
admin/lab + valores já escapados na geração), então entra no documento sem escapar."""

_DOCUMENTO = """<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 10mm; }}
  html, body {{ margin: 0; padding: 0; background: #fff; color: #000; }}
  * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
</style>
</head>
<body>
{corpo}
</body>
</html>"""


def montar_documento(html_cert: str) -> str:
    """Embrulha o HTML do certificado num documento A4 imprimível."""
    return _DOCUMENTO.format(corpo=html_cert or "")


def html_para_pdf(html_cert: str) -> bytes:
    """Renderiza o certificado em PDF A4 com Chromium headless.
    Levanta exceção se o navegador falhar (o endpoint converte em 500)."""
    from playwright.sync_api import sync_playwright

    documento = montar_documento(html_cert)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            page = browser.new_page()
            page.set_content(documento, wait_until="networkidle")
            pdf = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
            )
        finally:
            browser.close()
    return pdf
```

Nota: o `margin` do `@page` no CSS e o `margin` do `page.pdf` devem bater; mantemos 10mm nos dois.

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_certificado_pdf.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/certificado_pdf.py backend/tests/test_certificado_pdf.py
git commit -m "feat(cert): modulo certificado_pdf (HTML->PDF A4 via Chromium)"
```

---

## Task 2: Endpoint `GET /ordens/{id}/certificado/{tipo}/pdf`

**Files:**
- Modify: `backend/app/api/certificados_os.py`
- Test: `backend/tests/test_certificado_os_api.py`

Contexto: endpoint de leitura (usuário logado). Busca o `OSCertificado` por OS+tipo; sem certificado → 404. Gera o PDF via `html_para_pdf` e devolve como download. No teste, o motor é **mockado** (monkeypatch) para não subir Chromium.

- [ ] **Step 1: Escrever os testes (sucesso mockado + 404)**

Adicionar ao fim de `backend/tests/test_certificado_os_api.py` (o helper `_os_com_modelo`, `_headers` e fixtures já existem no arquivo):

```python
def test_baixar_pdf_sucesso(client, usuario_admin, db_session, monkeypatch):
    import app.api.certificados_os as mod
    monkeypatch.setattr(mod, "html_para_pdf", lambda html: b"%PDF-1.4 fake")
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    assert client.post(f"/ordens/{oid}/gerar-certificado", headers=h).status_code == 200
    r = client.get(f"/ordens/{oid}/certificado/C/pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content == b"%PDF-1.4 fake"


def test_baixar_pdf_sem_certificado_404(client, usuario_admin, db_session, monkeypatch):
    import app.api.certificados_os as mod
    monkeypatch.setattr(mod, "html_para_pdf", lambda html: b"%PDF")
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    # sem gerar certificado
    assert client.get(f"/ordens/{oid}/certificado/C/pdf", headers=h).status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_certificado_os_api.py -q -k pdf`
Expected: FAIL — 404/405 (rota inexistente) ou AttributeError no monkeypatch (`html_para_pdf` ainda não importado no módulo)

- [ ] **Step 3: Implementar o endpoint**

Em `backend/app/api/certificados_os.py`, adicionar o import no topo (junto aos outros):

```python
from fastapi import APIRouter, Depends, HTTPException, Response
```

e, junto aos imports do core:

```python
from app.core.certificado_pdf import html_para_pdf
```

Adicionar a rota ao fim do arquivo:

```python
_NOME_TIPO = {"C": "calibracao", "M": "manutencao"}


@router.get("/ordens/{ordem_id}/certificado/{tipo}/pdf")
def baixar_pdf(ordem_id: int, tipo: str, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if tipo not in _NOME_TIPO:
        raise HTTPException(status_code=404, detail="tipo inválido")
    _os_ou_404(db, ordem_id)
    osc = db.query(OSCertificado).filter(
        OSCertificado.os == ordem_id, OSCertificado.tipo == tipo
    ).first()
    if osc is None or not osc.html:
        raise HTTPException(status_code=404, detail="certificado não gerado")
    try:
        pdf = html_para_pdf(osc.html)
    except Exception:
        raise HTTPException(status_code=500, detail="falha ao gerar PDF")
    nome = _NOME_TIPO[tipo]
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificado-{ordem_id}-{nome}.pdf"'},
    )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_certificado_os_api.py -q`
Expected: PASS (todos do arquivo, incluindo os 2 novos)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/certificados_os.py backend/tests/test_certificado_os_api.py
git commit -m "feat(cert): endpoint GET certificado/{tipo}/pdf (download)"
```

---

## Task 3: Dockerfile + Playwright/Chromium

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`

Contexto: instalar o pacote Python `playwright` e o navegador Chromium com as libs de sistema. `playwright install --with-deps chromium` precisa rodar como root no build (a imagem já builda como root). O Chromium é instalado em `/root/.cache/ms-playwright` por padrão; como o container roda como root, o runtime acha o navegador.

- [ ] **Step 1: Adicionar `playwright` ao requirements**

Editar `backend/requirements.txt`, acrescentando a linha:

```
playwright
```

- [ ] **Step 2: Instalar Chromium no Dockerfile**

Em `backend/Dockerfile`, logo após o `RUN pip install --no-cache-dir -r requirements.txt` (linha 12), inserir:

```dockerfile
# Chromium headless para gerar PDF dos certificados (Playwright)
RUN playwright install --with-deps chromium
```

- [ ] **Step 3: Rebuild da imagem do backend**

Run: `docker compose up -d --build backend`
Expected: build conclui (baixa Chromium + libs); container `backend` sobe saudável.

- [ ] **Step 4: Smoke test do motor real dentro do container**

Run:
```bash
docker compose exec -T backend python -c "from app.core.certificado_pdf import html_para_pdf; b=html_para_pdf('<h1>ok</h1>'); print(len(b), b[:5])"
```
Expected: imprime um tamanho > 0 e `b'%PDF-'` (PDF válido gerado pelo Chromium).

- [ ] **Step 5: Rodar a suíte backend completa**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: PASS (todos verdes).

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/Dockerfile
git commit -m "build(backend): instala Chromium (Playwright) para PDF de certificados"
```

---

## Task 4: Frontend api — `baixarCertificadoPdf` + remover `certificadoApi`

**Files:**
- Modify: `frontend/src/app/ordens/api.ts`

Contexto: `apiFetch` e `ApiError` já são importados no topo de `api.ts`. Removemos `certificadoApi` (enviar/baixar — sem uso após esta feature) e adicionamos `baixarCertificadoPdf` ao `ordensApi`.

- [ ] **Step 1: Remover o objeto `certificadoApi`**

Em `frontend/src/app/ordens/api.ts`, apagar o bloco inteiro:

```ts
export const certificadoApi = {
  enviar: async (ordemId: number, file: File): Promise<{ pdf_certificado: string }> => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await apiFetch(`/ordens/${ordemId}/certificado`, { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try { const b = await res.json(); if (b.detail) detail = b.detail } catch { /* sem corpo */ }
      throw new ApiError(res.status, detail)
    }
    return (await res.json()) as { pdf_certificado: string }
  },
  baixar: async (ordemId: number): Promise<void> => {
    const url = await buscarBlobUrl(`/ordens/${ordemId}/certificado`)
    window.open(url, '_blank', 'noopener')
  },
}
```

- [ ] **Step 2: Adicionar `baixarCertificadoPdf` ao `ordensApi`**

Dentro do objeto `ordensApi`, logo após a propriedade `gerarCertificado: ...`, adicionar:

```ts
  baixarCertificadoPdf: async (id: number, tipo: 'C' | 'M'): Promise<void> => {
    const res = await apiFetch(`/ordens/${id}/certificado/${tipo}/pdf`)
    if (!res.ok) throw new ApiError(res.status, 'Falha ao baixar PDF')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const nome = tipo === 'C' ? 'calibracao' : 'manutencao'
    const a = document.createElement('a')
    a.href = url
    a.download = `certificado-${id}-${nome}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
```

- [ ] **Step 3: Conferir `buscarBlobUrl`**

`buscarBlobUrl` era usado só por `certificadoApi.baixar`. Procurar outros usos: `grep -rn "buscarBlobUrl" frontend/src`. Se não houver mais nenhum uso fora da própria definição, **manter** a função exportada (é util genérica e já é `export`) — não remover para não quebrar nada que importe depois. (Decisão: manter; é export público e barato.)

- [ ] **Step 4: Verificar tsc/lint**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: erros apenas em `OrdemDetailPage.tsx` (ainda referencia `certificadoApi`) — serão corrigidos na Task 5.
Run: `cd frontend && npx eslint src/app/ordens/api.ts`
Expected: sem erros.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/ordens/api.ts
git commit -m "feat(cert): ordensApi.baixarCertificadoPdf + remove certificadoApi"
```

---

## Task 5: Frontend — botão "Baixar PDF", remover upload/impressão

**Files:**
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx`
- Modify: `frontend/src/app/routes.tsx`
- Delete: `frontend/src/app/ordens/CertificadoImprimir.tsx`

Contexto: na seção *Certificados*, o link "Imprimir" vira botão "Baixar PDF". Na seção *Resultados da calibração*, somem o upload "Enviar certificado (PDF)" e o campo "PDF / Baixar certificado". Removemos handlers e a rota de impressão órfã.

- [ ] **Step 1: Ajustar o import de `./api`**

Em `OrdemDetailPage.tsx`, trocar:

```tsx
import { ordensApi, fotosApi, certificadoApi, TIPO_SERVICO, TRANSICOES, formatData, type OrdemDetalhe, type LogOS, type Foto, type OSCertificado } from './api'
```

por (remove `certificadoApi`):

```tsx
import { ordensApi, fotosApi, TIPO_SERVICO, TRANSICOES, formatData, type OrdemDetalhe, type LogOS, type Foto, type OSCertificado } from './api'
```

- [ ] **Step 2: Adicionar handler de download e remover os de PDF antigos**

Remover as funções `onEnviarCertificado` e `onBaixarCertificado` inteiras. No lugar (mesma região, perto de `aoGerarCert`), adicionar:

```tsx
  async function onBaixarPdf(tipo: 'C' | 'M') {
    setErroCert('')
    try {
      await ordensApi.baixarCertificadoPdf(osId, tipo)
    } catch (e) {
      setErroCert(e instanceof ApiError ? e.message : 'Falha ao baixar PDF')
    }
  }
```

- [ ] **Step 3: Remover `podeCertificado` e ajustar `temCalib`**

Remover a linha `const podeCertificado = isAdmin(user) || user?.funcao === 'Laboratório'` (ficará sem uso).
Trocar:

```tsx
  const temCalib = os.calib_cert || os.calib_temp || os.calib_pressao || os.calib_teste_media || os.calib_situacao || os.pdf_certificado
```

por (sem `pdf_certificado`):

```tsx
  const temCalib = os.calib_cert || os.calib_temp || os.calib_pressao || os.calib_teste_media || os.calib_situacao
```

- [ ] **Step 4: Limpar a seção "Resultados da calibração"**

Trocar a abertura da `Secao` (remove o `acao` de upload):

```tsx
      <Secao
        icon={<IconChart className="w-4 h-4" />}
        titulo="Resultados da calibração"
        acao={podeCertificado && (
          <label className="cursor-pointer">
            <span className="inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold bg-primary text-white hover:bg-primary-600 transition-colors">
              Enviar certificado (PDF)
            </span>
            <input type="file" accept="application/pdf" className="hidden" onChange={onEnviarCertificado} />
          </label>
        )}
      >
```

por:

```tsx
      <Secao
        icon={<IconChart className="w-4 h-4" />}
        titulo="Resultados da calibração"
      >
```

E remover o `Campo` do PDF dentro do grid:

```tsx
            <Campo label="PDF" valor={os.pdf_certificado
              ? <button type="button" onClick={() => void onBaixarCertificado()} className="text-primary hover:underline text-sm">Baixar certificado</button>
              : '—'} />
```

(apagar esse bloco; manter os Campos Certificado/Temperatura/Pressão/Média/Situação).

- [ ] **Step 5: Trocar "Imprimir" por "Baixar PDF" na seção Certificados**

Trocar:

```tsx
                <a href={`/app/ordens/${osId}/certificado/${c.tipo}/imprimir`} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold text-primary hover:underline">Imprimir</a>
```

por:

```tsx
                <button type="button" onClick={() => void onBaixarPdf(c.tipo)} className="text-xs font-semibold text-primary hover:underline">Baixar PDF</button>
```

- [ ] **Step 6: Remover a rota de impressão**

Em `frontend/src/app/routes.tsx`, remover a linha de import do `CertificadoImprimir` e a linha da rota:

```tsx
      <Route path="ordens/:id/certificado/:tipo/imprimir" element={<CertificadoImprimir />} />
```

(e o `import { CertificadoImprimir } from './ordens/CertificadoImprimir'` correspondente).

- [ ] **Step 7: Apagar o componente órfão**

```bash
git rm frontend/src/app/ordens/CertificadoImprimir.tsx
```

- [ ] **Step 8: Verificar tsc/lint/build**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: sem erros.
Run: `cd frontend && npx eslint src/app/ordens/OrdemDetailPage.tsx src/app/routes.tsx`
Expected: sem erros.
Run: `cd frontend && npm run build`
Expected: build verde.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/app/ordens/OrdemDetailPage.tsx frontend/src/app/routes.tsx
git commit -m "feat(cert): botao Baixar PDF + remove upload/impressao de certificado"
```

---

## Task 6: Changelog + E2E + memória

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

Contexto: a v1.4.0 ainda não foi publicada (branch não mesclada), então editamos a entrada existente em vez de criar nova versão. O texto atual da novidade já menciona "impresso/salvo em PDF direto na OS"; vamos refletir o download direto.

- [ ] **Step 1: Atualizar o texto da v1.4.0**

Em `frontend/src/app/changelog/data.ts`, na entrada `versao: '1.4.0'`, trocar o trecho do primeiro item:

`…que pode ser revisado e impresso/salvo em PDF direto na OS.`

por:

`…que pode ser revisado e baixado em PDF (gerado automaticamente) direto na OS.`

E adicionar um item de melhoria à lista da v1.4.0:

```ts
      { tipo: 'melhoria', texto: 'Download do certificado em PDF com um clique — o sistema gera o PDF no servidor a partir do certificado, sem precisar imprimir e reenviar o arquivo manualmente. Removido o envio manual de PDF.' },
```

- [ ] **Step 2: Verificar build do frontend**

Run: `cd frontend && npm run build`
Expected: build verde.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.4.0 reflete download direto de PDF do certificado"
```

- [ ] **Step 4: E2E manual (com o usuário)**

1. Logar (`admin`/`admin12345`), abrir uma OS na fase Laboratório com modelo de certificado cadastrado.
2. "Gerar certificado de calibração" → preencher dados → Gerar.
3. Na seção Certificados, clicar "Baixar PDF".
4. Abrir o PDF: conferir A4, **2 páginas com um cabeçalho cada**, quebra `[pulapagina]` correta, e aparência **idêntica** ao certificado em tela.

- [ ] **Step 5: Atualizar memória do projeto**

Atualizar `C:\Users\TI\.claude\projects\d--GitHub-GestorHS\memory\project_gestorhs.md` registrando: geração de PDF do certificado via Chromium headless (Playwright) no backend; endpoint `GET /ordens/{id}/certificado/{tipo}/pdf`; Dockerfile do backend agora instala Chromium.

---

## Self-Review (preenchido)

**Spec coverage:** módulo PDF (T1), endpoint (T2), Docker/Chromium (T3), api front (T4), UI botão+remoções+rota (T5), changelog/memória/E2E (T6). Todos os itens "Dentro" da spec cobertos.

**Type consistency:** `montar_documento(html_cert)`/`html_para_pdf(html_cert)`, `baixarCertificadoPdf(id, tipo)`, `_NOME_TIPO` (C→calibracao, M→manutencao) usados de forma consistente entre tasks. `Response` importado do FastAPI na T2.

**Placeholders:** nenhum — todos os passos têm código/comandos concretos.
