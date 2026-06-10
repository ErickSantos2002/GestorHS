# GestorHS — Ficha do aparelho: atalho pro cliente, OS e certificados

**Data:** 2026-06-10
**Status:** Aprovado para implementação
**Motivação:** Na ficha do aparelho (Frota) falta navegação e histórico de serviço. O laboratório precisa: ir rápido para o cliente do aparelho; ver as OS daquele aparelho; e — importante — acessar os **certificados de calibração antigos** do aparelho.

**Contexto:** continuação das melhorias de UX (v1.4.x). Reusa o motor/endpoint de PDF já existente (`GET /ordens/{os}/certificado/{tipo}/pdf`).

## Escopo
**Dentro:**
- Backend: `GET /equipamentos-cliente/{id}/ordens` (lista de OS do aparelho) e `GET /equipamentos-cliente/{id}/certificados` (certificados gerados das OS do aparelho).
- Frontend (ficha do aparelho): "Cliente: Nome" vira link; seção full-width "Ordens de serviço" (tabela) e seção full-width "Certificados" (lista com Baixar PDF), abaixo do `DetailGrid`.

**Fora:**
- Filtrar OS por aparelho na página de Ordens (lista global) — não faz parte; usamos sub-recurso dedicado.
- Geração de PDF nova (reusa a existente).
- Portal do cliente.
- Backend/migração de banco (nenhuma migração; só leitura).

## Backend

### `GET /equipamentos-cliente/{id}/ordens`
- Em `app/api/equipamentos_cliente.py`, seguindo o padrão de `historico`.
- Leitura para usuário logado (`get_current_usuario`).
- 404 se o aparelho não existir.
- Retorna `list[OrdemListOut]` (schema já existente em `app/schemas/ordens.py`): `db.query(Ordem).filter(Ordem.equipamento_cliente == id).order_by(Ordem.id.desc()).all()`, validado com `OrdemListOut.model_validate`.

### `GET /equipamentos-cliente/{id}/certificados`
- Mesmo arquivo, mesmo padrão/auth, 404 se aparelho não existir.
- Novo schema em `app/schemas/frota.py`: `EquipCertItem(BaseModel)` com `os: int`, `tipo: str`, `data_geracao: datetime | None`.
- Query: `db.query(OSCertificado).join(Ordem, OSCertificado.os == Ordem.id).filter(Ordem.equipamento_cliente == id).order_by(OSCertificado.os.desc(), OSCertificado.tipo).all()`.
- Retorna `list[EquipCertItem]` montado a partir de cada `OSCertificado` (`os=c.os, tipo=c.tipo, data_geracao=c.data_geracao`). (Não inclui o `html` — só metadados; o PDF é baixado pelo endpoint existente.)
- Imports necessários no arquivo: `Ordem`, `OSCertificado` (de `app.models`).

## Frontend

### `app/frota/api.ts`
- Tipos: importar/expor `OrdemListItem` (já existe em `ordens/api.ts` — reusar via import de tipo) para a lista de OS; novo tipo `EquipCertItem { os: number; tipo: 'C' | 'M'; data_geracao: string | null }`.
- `equipamentosClienteApi.ordens(id)`: `GET /equipamentos-cliente/{id}/ordens` → `OrdemListItem[]`.
- `equipamentosClienteApi.certificados(id)`: `GET /equipamentos-cliente/{id}/certificados` → `EquipCertItem[]`.

### `app/frota/EquipamentoClienteDetailPage.tsx`
- **Cliente link:** trocar `<p>Cliente: {nomeCliente}</p>` por um link para `/app/clientes/{obj.cliente}` quando houver `obj?.cliente` (no modo novo, sem `obj`, manter texto simples).
- Carregar OS e certificados quando `editando` (no mesmo `useEffect` que já busca histórico, ou um novo — buscar por `id`).
- **Seções full-width abaixo do `DetailGrid`** (fora dele, antes dos modais), só quando `editando`:
  - "Ordens de serviço": se vazio → texto "Nenhuma OS."; senão `Table` com colunas: OS (link `/app/ordens/{id}`, `#id`), Data de chegada (`formatData`), Tipo (`TIPO_SERVICO[tipo]?.label ?? '—'`), Fase (bolinha de cor `#fase_cor` + `fase_descricao`), Situação.
  - "Certificados": se vazio → "Nenhum certificado gerado."; senão lista/`Table` com: OS (link), Tipo (`tipo === 'C' ? 'Calibração' : 'Manutenção'`), Data de geração (`formatData`), e botão **Baixar PDF** que chama `ordensApi.baixarCertificadoPdf(os, tipo)`.
- Reaproveitar `formatData`, `TIPO_SERVICO` e `ordensApi` de `../ordens/api` (já importável). Tratar erro de download com um estado simples (`erroCert`) exibido perto da seção.

## Testes / verificação
- **Backend (pytest):** `/ordens` retorna as OS do aparelho (e só dele), ordenadas desc; `/certificados` retorna os os_certificados das OS do aparelho com `os/tipo/data_geracao`; 404 para aparelho inexistente em ambos.
- **Frontend (vitest/tsc/lint/build):** `equipamentosClienteApi.ordens/certificados` montam as URLs certas; build verde.
- **E2E manual:** abrir um aparelho com OS e certificados → ver a lista de OS (clicável) e os certificados → baixar um PDF antigo.

## Critérios de aceite
- Ficha do aparelho tem link pro cliente, lista de OS (clicável) e lista de certificados com download de PDF (incluindo certificados antigos).
- Endpoints 404 corretamente e retornam só dados do aparelho pedido.
- pytest/vitest/tsc/lint/build verdes. Changelog v1.4.2.

## Fora do v1 desta etapa
Paginação das listas (aparelhos têm poucas OS); filtro de OS por aparelho na lista global; visualizar o HTML do certificado inline.
