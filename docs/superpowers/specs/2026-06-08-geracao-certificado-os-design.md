# GestorHS — Geração de certificado no laboratório (OS)

**Data:** 2026-06-08
**Status:** Aprovado para implementação
**Motivação:** Fechar a etapa de laboratório da OS gerando o **certificado de calibração** (sempre) e o **de manutenção** (quando houver manutenção), a partir dos modelos cadastrados (página Certificados), preenchidos com os dados reais da OS/cliente/aparelho/calibração. Saída: HTML preenchido guardado na OS, impresso pelo navegador (PDF no servidor fica para etapa futura).

## Escopo
**Dentro:** suporte a 2 tipos de modelo por aparelho (Calibração/Manutenção); motor que preenche os campos `[...]` com dados reais; geração automática ao concluir o laboratório + botão regerar; armazenamento do HTML preenchido por OS+tipo; tela na OS para ver/imprimir; ajuste da página Certificados para editar os dois tipos.
**Fora:** geração de PDF no servidor (anexo automático) — o campo `pdf` em `os_certificados` já fica preparado; agora o PDF sai pela impressão do navegador.

## Contexto atual
- Avanço **5→6 ("Concluir laboratório")** (`app/api/ordens.py` `avancar`, branch `origem==5`) já grava os dados de calibração da `AvancarIn` (`tipo_calibragem`, `calib_cert/temp/pressao/teste1-3/teste_media/situacao`, `prox_calibragem`, `pdf_certificado`) e chama `espelhar_calibracao`.
- Modelos de certificado: tabela `certificados` (`equipamento` FK catálogo, `descricao`, `texto` HTML), 1 por aparelho (recurso recém-criado). Sem lib de PDF no backend.
- `tipo_servico` da OS: `C`=Calibração, `M`=Manutenção, `A`=Ambas.

## Decisões
- **2 modelos por aparelho:** `certificados.tipo` ∈ {`C` Calibração, `M` Manutenção}; unicidade **(equipamento, tipo)**; os 12 existentes viram `C`.
- **Geração:** preencher `[campo]` → HTML, guardar em `os_certificados`. **Impressão pelo navegador** (página de impressão); **PDF no servidor adiado** (campo `pdf` reservado).
- **Gatilho:** automático no 5→6 (best-effort: gera Calibração se houver modelo; Manutenção se `tipo_servico` ∈ {M,A} e houver modelo; ausência de modelo não trava o avanço) + **botão "Gerar/Regerar"** no detalhe da OS.
- **Permissões:** gerar/regerar = Laboratório + Administrador; ver/imprimir = qualquer interno.

## Banco — migração `0007_os_certificados`
1. `certificados`: `ADD COLUMN tipo varchar(1) NOT NULL DEFAULT 'C'` (com CHECK `tipo IN ('C','M')`); trocar `UNIQUE(equipamento)` por `UNIQUE(equipamento, tipo)`.
2. Nova `os_certificados`: `id serial PK`, `os integer NOT NULL REFERENCES ordens(id)`, `tipo varchar(1) NOT NULL` (CHECK C/M), `html text`, `pdf varchar(50)` (nullable, futuro), `data_geracao timestamptz`; `UNIQUE(os, tipo)`.
- down_revision: `0006_certificados_modelo`. Reversível.

## Backend
### Modelos
- `CertificadoModelo` (`app/models/certificado_modelo.py`): adicionar `tipo` (String(1), default "C"); a unicidade real é (equipamento, tipo) (constraint no banco; no SQLite de teste cria via metadata — usar `UniqueConstraint("equipamento","tipo")` em `__table_args__`).
- `OSCertificado` (`app/models/os_certificado.py`, tabela `os_certificados`): `os`, `tipo`, `html`, `pdf`, `data_geracao`.

### Motor `app/core/certificado_gerar.py` (puro)
- `CAMPOS` documentado; `montar_contexto(db, ordem) -> dict[str, str]` resolve os valores a partir de `ordem`, `ordem.cliente_rel`, `ordem.equipamento_rel` (EquipamentoCliente), o catálogo `Equipamento` (modelo) + `Marca`, e `TipoCalibragem`. Datas formatadas pt-BR; valores ausentes viram "".
- `preencher(html: str, contexto: dict) -> str`: substitui cada `[campo]` (case-sensitive) pelo valor.
- **Mapa de campos:**
  - Cliente: `[nomecli]`=nome, `[cnpj]`=cgc ou cpf (formatado), `[endcli]`=endereço completo (endereco, numero, bairro, municipio/estado).
  - Aparelho: `[modelo]`=Equipamento.descricao (catálogo), `[marca]`=Marca.descricao, `[serie]`=equip_cliente.serie, `[patrimonio]`=patrimonio, `[datacompra]`=datacompra.
  - OS/calibração: `[os]`=ordem.id, `[calibcert]`=calib_cert, `[datacalibracao]`=data_calibracao, `[proxcalibragem]`=prox_calibragem, `[tipocalibragem]`=TipoCalibragem.descricao, `[temperatura]`=calib_temp, `[pressao]`=calib_pressao, `[teste1/2/3]`=calib_teste1/2/3, `[media]`=calib_teste_media, `[situacao]`=calib_situacao, `[dataemissao]`=`[datacli]`=data de geração (hoje).

### Geração (`app/api/certificados_os.py` ou em `ordens_acoes.py`)
- `gerar_certificados(db, ordem, *, tipos: list[str]) -> list[OSCertificado]`: para cada `tipo` pedido, busca `CertificadoModelo(equipamento=<catálogo do aparelho>, tipo)`; se existe, preenche e upserta em `os_certificados` (os, tipo). Retorna os gerados. Sem modelo → ignora aquele tipo.
- Quais tipos: Calibração sempre; Manutenção se `ordem.tipo_servico in ("M","A")`.
- O catálogo do aparelho = `ordem.equipamento_rel.equipamento` (EquipamentoCliente.equipamento → id do catálogo).

### Endpoints (router novo `app/api/certificados_os.py`, registrado em main)
| Método | Rota | Descrição |
|---|---|---|
| GET | `/ordens/{id}/certificados` | Lista os certificados gerados da OS (`tipo`, `html`, `data_geracao`, `pdf`). Leitura interna. |
| POST | `/ordens/{id}/gerar-certificado` | (Re)gera os certificados da OS (calibração + manutenção conforme tipo_servico). Laboratório/Admin. Retorna a lista. 404 OS. |

### Auto-geração no avanço 5→6
- No branch `origem==5` de `avancar`, **após** gravar os dados de calibração e antes do commit, chamar `gerar_certificados(db, ordem, tipos=...)` em modo best-effort (try/except logado; falha de geração não derruba o avanço).

## Frontend
### Página Certificados (Modelos) — `app/certificados/ModelosTab.tsx`
- No editor de um modelo, **alternar tipo**: abas/segmented "Calibração | Manutenção"; cada tipo carrega/salva seu próprio HTML (`GET/PUT /certificados-modelo/{equip}?tipo=C|M`). A lista pode indicar quais tipos têm certificado (ex.: dois selos). `certificadosApi` ganha `tipo` em obter/salvar; a lista passa a refletir por tipo (decisão de UI: manter simples — selo "Calibração"/"Manutenção").
- Lista de **campos disponíveis** atualizada com os novos placeholders.

### Detalhe da OS — `app/ordens/OrdemDetailPage.tsx`
- Nova seção **"Certificados"**: lista os gerados (Calibração/Manutenção) com **Imprimir** (abre `/app/ordens/:id/certificado/:tipo/imprimir` — página limpa que renderiza o HTML e chama `window.print()`) e **Gerar/Regerar** (Laboratório/Admin → `POST /ordens/{id}/gerar-certificado`, recarrega). Se não houver modelo para o tipo, mostra aviso ("sem modelo cadastrado para este aparelho").
- Página de impressão: rota dedicada que injeta o HTML do certificado (via `dangerouslySetInnerHTML` num container isolado ou `<iframe srcDoc>`), com CSS de impressão e auto-print. As imagens usam as URLs públicas (já resolvem).

### Backend schemas/front api
- Schemas `OSCertificadoOut {tipo, html, data_geracao, pdf}`. `app/ordens/api.ts`: `ordensApi.certificados(id)`, `ordensApi.gerarCertificado(id)`.

## Testes / verificação
- **Backend (pytest):** `preencher` substitui campos; `montar_contexto` mapeia (cliente/aparelho/calibração) com valores e vazios; `gerar_certificados` cria Calibração; gera Manutenção quando tipo_servico M/A e há modelo; ignora tipo sem modelo; upsert (regerar atualiza, não duplica); endpoints (GET lista, POST regenera, 404, permissão 403 não-Lab); avanço 5→6 gera best-effort (com modelo → cria os_certificados; sem modelo → avança sem erro). `certificados` com `tipo` (unicidade equipamento+tipo).
- **Frontend (vitest):** `certificadosApi`/`ordensApi` query/payloads (tipo, gerar). Telas por tsc/lint/build. **E2E manual:** numa OS no laboratório, concluir lab com dados de calibração → ver certificado de Calibração gerado no detalhe → Imprimir (abre página e print). Editar o modelo de Manutenção de um aparelho e abrir uma OS de Manutenção/Ambas → conferir os dois certificados.

## Critérios de aceite
- A página Certificados edita **dois tipos** por aparelho (Calibração/Manutenção). Concluir o laboratório **gera automaticamente** o certificado de calibração (e o de manutenção quando o serviço inclui manutenção), preenchidos com os dados reais; há botão **Regerar**; o detalhe da OS lista e **imprime** (navegador). Sem modelo cadastrado → não trava, avisa. Permissões: gerar = Lab/Admin; ver = interno. pytest/vitest/tsc/lint/build verdes. Changelog **v1.4.0**. Sem PDF no servidor (campo `pdf` reservado).

## Fora do v1 desta etapa
PDF no servidor (WeasyPrint/Chromium) com anexo automático em `os_certificados.pdf` e exibição no portal; numeração automática do `[calibcert]`; histórico de versões do certificado.
