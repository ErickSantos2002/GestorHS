# Card do TaskHS enriquecido por fase + download público do certificado

**Data:** 2026-06-25
**Status:** aprovado (brainstorming)
**Depende de:** integração GestorHS → TaskHS (v1.9.0, já entregue) —
[2026-06-25-integracao-taskhs-design.md](2026-06-25-integracao-taskhs-design.md)

## Objetivo

Hoje o card do TaskHS carrega só `title`, move de coluna por fase, e tem
`due_date`/`priority`. Esta entrega enriquece a **`description`** do card com um
resumo que **cresce conforme a OS avança**, e adiciona um **link de download
público do certificado** (sem login no GestorHS) na seção de Laboratório.

Dois componentes:
- **A — Descrição cumulativa por seções** (remontada a cada upsert).
- **B — Endpoint público de download do certificado** (token assinado, sem login).

## Componente A — Descrição cumulativa

A descrição é **remontada do zero a cada upsert** a partir do estado atual da OS
(coerente com "envie sempre o estado completo" do contrato). Cada **seção** só
aparece quando a OS **atinge a fase dona dela**; dentro de uma seção, **linhas sem
valor são omitidas**. Resultado: em Finalizada o card mostra o resumo completo.

### Estrutura e fontes de dados

Fases: `Recebido=4, Laboratório=5, Pós-Vendas=6, Preparando Retorno=7, Finalizada=8`.

**Cabeçalho (sempre):**
- `Cliente: {ordem.cliente_nome}`
- `Aparelho: {ordem.equipamento_descricao} · Série {serie} / Patr. {patrimonio}`
  (série/patrimônio de `ordem.equipamento_rel`; partes vazias omitidas)
- `Serviço: {Calibração|Manutenção|Ambas}` — de `ordem.tipo_servico` (`C|M|A`)

**📋 Recebido — quando `fase >= 4`:**
- `Chegada: {data_chegada:DD/MM/AAAA} · Condição: {condicao_chegada}`
- `Acessórios: {ordem.acessorios_presentes join ', '}` (omite se vazio)
- `Pilhas: {pilhas} · Bocais: {bocais}` (omite cada um se 0/None)
- `Obs: {ordem.obs}` (omite se vazio)

**🔬 Laboratório — quando o certificado existir** (há `OSCertificado` para a OS;
equivale a "laboratório concluído"):
- `Resultado: {calib_situacao}` (omite se vazio)
- `Calibrado em: {data_calibracao:DD/MM/AAAA} · Próxima: {prox_calibragem:DD/MM/AAAA}`
- `Certificado: {calib_cert}` (nº; omite se vazio)
- **Link(s) de download** (Componente B), um por tipo de certificado existente:
  - `Certificado de Calibração: {url}` (tipo `C`)
  - `Certificado de Manutenção: {url}` (tipo `M`)

**🤝 Pós-Vendas — quando `fase >= 6`** (aparece na **entrada** da fase, é o que o
setor precisa durante o atendimento):
- `Contato: {cliente.contato} · {telefone}` — telefone = primeiro não-vazio de
  `celular`, `whatsapp`, `telefones` do cliente
- `Aceite: {data_aceite:DD/MM/AAAA}` (só quando `ordem.aceite` é true)

**🚚 Preparando Retorno — quando `fase >= 7`:**
- `Enviar para: {endereco}, {numero} {complemento} · {bairro} · {municipio}/{estado} · CEP {cep}`
  (campos de `ordem.cliente_rel`; partes vazias omitidas)

**📮 Finalizada — quando houver rastreio** (`ordem.cod_retorno`):
- `Rastreio: {cod_retorno} · Postado em: {data_retorno:DD/MM/AAAA}`

### Regras de montagem

- Datas formatadas `DD/MM/AAAA` (timezone-safe: usar `.date()` do DateTime).
- Uma seção só entra no texto se tiver **pelo menos uma linha** com valor.
- Seções separadas por linha em branco; título da seção em sua própria linha.
- `due_date` (próxima calibração) e `priority` (`medium`) **inalterados**.

## Componente B — Download público do certificado

### Endpoint

`GET /publico/certificado/{ordem_id}/{tipo}?t={token}` — **sem autenticação**.

- `tipo` ∈ `{"calibracao", "manutencao"}` (whitelist → mapeia para `OSCertificado.tipo`
  `C`/`M`; valor fora da whitelist → 404, sem path traversal).
- Valida `token`; se inválido → **403**.
- Busca `OSCertificado(os=ordem_id, tipo=...)`; se não existe ou sem `html` → **404**.
- Renderiza `html_para_pdf(osc.html)` (mesmo motor do endpoint logado
  [certificados_os.py](../../../backend/app/api/certificados_os.py)); falha → **500**.
- Responde `application/pdf`, `Content-Disposition: inline` (abre no navegador;
  o usuário baixa se quiser).

### Token

- `token = hmac_sha256(JWT_SECRET_KEY, f"cert:{ordem_id}:{tipo_codigo}").hexdigest()`
  onde `tipo_codigo` é `C`/`M`. Reusa `JWT_SECRET_KEY` com prefixo de domínio
  (`cert:`) — **sem segredo novo**.
- Estável (mesma OS+tipo → mesmo token), **sem expiração**.
- Validação em **tempo constante** (`hmac.compare_digest`).
- Impossível de adivinhar; adequado a um board interno (mesmas pessoas que já têm
  acesso aos dados no GestorHS).

### Link no card

- `CERT_PUBLIC_BASE_URL` (setting nova, default `""`): base pública do backend
  (ex.: `https://api.gestorhs...`; local `http://localhost:8001`). **Sem barra final.**
- `link_certificado(ordem_id, tipo_codigo) -> str | None`: retorna
  `{CERT_PUBLIC_BASE_URL}/publico/certificado/{ordem_id}/{nome}?t={token}` ou `None`
  se a base estiver vazia (degradação graciosa — card sai sem link).

## Arquitetura

Respeita as convenções: puro em `core/`, I/O isolado, wiring fino.

### Puro — `app/core/taskhs.py` (estende o módulo existente)
- `TIPO_SERVICO_LABEL = {"C": "Calibração", "M": "Manutenção", "A": "Ambas"}`
- `montar_descricao(ordem, *, certificados: list[dict]) -> str` — monta o texto
  multi-linha pelas regras acima. `certificados` é a lista (já resolvida pelo
  wiring) de dicts `{"tipo": "C"|"M", "url": str | None}` para a seção de
  Laboratório (uma linha de link por item com `url` não-nula).
- `montar_payload(...)` ganha o parâmetro `descricao: str | None` e o usa no campo
  `description` (hoje manda `ordem.obs`; passa a mandar a descrição montada).

### Puro — `app/core/certificado_link.py` (novo)
- `assinar(ordem_id: int, tipo_codigo: str) -> str` — HMAC hex.
- `verificar(ordem_id: int, tipo_codigo: str, token: str) -> bool` — compare_digest.
- `link_certificado(ordem_id: int, tipo_codigo: str) -> str | None` — usa
  `settings.CERT_PUBLIC_BASE_URL`. (Lê config, mas é determinística e sem rede;
  fica em core junto da lógica de assinatura.)

### Config — `app/core/config.py`
- `CERT_PUBLIC_BASE_URL: str = ""`

### Endpoint público — `app/api/publico.py` (novo router, registrado em main.py)
- `GET /publico/certificado/{ordem_id}/{tipo}` sem dependência de auth.
- Mapa `{"calibracao": "C", "manutencao": "M"}`; valida token via
  `certificado_link.verificar`; renderiza PDF.

### Wiring — `app/api/ordens.py`
Nos três pontos (`abrir`/`avancar`/`cancelar`), antes de montar o payload:
1. Consulta os `OSCertificado` da OS (tipos existentes).
2. Monta `certificados = [{"tipo": c.tipo, "url": link_certificado(ordem.id, c.tipo)} ...]`.
3. `descricao = taskhs.montar_descricao(ordem, certificados=certificados)`.
4. `payload = taskhs.montar_payload(ordem, lista=..., arquivado=..., descricao=descricao)`.

A consulta de certificados é barata e roda no request (objeto/Session vivos). O
payload (dict) continua sendo o único que vai pro BackgroundTask.

## Estratégia de testes

- **`montar_descricao`** (puro, stub de ordem): cabeçalho sempre; cada seção
  aparece/some conforme `fase` e presença de dados; linhas vazias omitidas; tipo de
  serviço traduzido; telefone pega o primeiro não-vazio; links de certificado
  entram quando passados; descrição sem certificado não tem a linha de link.
- **`certificado_link`** (puro): `assinar` determinístico; `verificar` aceita o
  token correto e rejeita adulterado; `link_certificado` retorna `None` com base
  vazia e a URL completa com base setada.
- **Endpoint público** (`test_publico_certificado.py`): 200 + `application/pdf` com
  token válido e certificado existente; 403 com token errado; 404 com tipo inválido
  ou certificado inexistente; **sem header de auth** (não exige login). Mockar
  `html_para_pdf` para não depender do motor real.
- **Wiring** (`test_ordens_taskhs.py`, estender): o payload agendado leva
  `description` com o cabeçalho e a seção da fase; quando a OS tem certificado, a
  descrição contém o link público.

## Fora de escopo (v1)

- Anexar o PDF como arquivo no card (a API de integração não suporta anexos).
- Cache do PDF renderizado.
- Expiração/revogação de token de certificado.
- Link para o `pdf_certificado` enviado manualmente (usamos só o gerado).
- Mudança em `due_date`/`priority`.
