# Database — gestorhs-banco

**Host:** 62.72.11.28:9999  
**Banco:** gestorhs-banco  
**Usuário:** administrador  
**Engine:** PostgreSQL 17

---

## Prefixos de tabelas

O banco tem **90 tabelas** divididas em três famílias:

| Prefixo | Qtd | Domínio |
|---------|-----|---------|
| `hs`  | 44  | Core do GestorHS — calibração, OS, clientes, equipamentos |
| `pgs` | 44  | CMS / e-commerce / site |
| `inf` | 2   | CRM via telefonia (integração 4com) |

> Não existem FOREIGN KEYs declaradas. Os relacionamentos são por convenção de nomes (ex: `hsordens.cliente` → `hsclientes.id`).

---

## Família `hs` — Core GestorHS

### Fluxo principal: Equipamento → OS → Calibração

```
hsclientes (empresa cliente)
  ├── hsfuncionarios      (funcionários do cliente)
  ├── hsequipempresa      (equipamentos cadastrados no cliente)
  │     └── hsequiphist   (histórico de movimentação do equipamento)
  └── hsordens (OS)
        ├── hschecklistdet (respostas de checklist da OS)
        ├── hslogos        (log de alterações da OS)
        └── hsdocequip     (documentos ligados ao equipamento da OS)

hslotes                   (lote de equipamentos para envio/calibração em grupo)
  └── hsfaseslote         (fases do lote)

hscabteste                (cabeçalho de teste — agrupamento)
  └── hsdetteste          (detalhe: resultado por equipamento/funcionário)
```

### Tabelas cadastrais / auxiliares `hs`

| Tabela | Descrição |
|--------|-----------|
| `hsacesso` | Controle de licença por CNPJ (chave + data limite) |
| `hsapi4com` | Fila de mensagens para integração com API 4com (tipo O/I, processado S/N) |
| `hscaixas` | Caixa diário (data, status P/A/F) |
| `hscategorias` | Categorias de itens/equipamentos (com campos SEO) |
| `hscertificados` | Certificados gerados para equipamentos |
| `hschecklist` | Template de checklist (perguntas com opções) |
| `hscheckos` | Itens de checklist específicos para OS |
| `hsclimar` | Climatizadores — tipos vinculados a setores |
| `hsdestaques` | Banners/destaques do sistema (tipo G/E, por setor/categoria) |
| `hsdocumentos` | Documentos genéricos ligados a itens |
| `hsenvios` | Campanhas de envio de email/SMS (status P/E/F) |
| `hsfases` | Fases do workflow de OS (cor hex) |
| `hsfotos` | Fotos de itens ou clientes (tipo I=imagem) |
| `hsgrupos` | Grupos de clientes |
| `hsitens` | Catálogo de equipamentos/produtos (preço, estoque, peso para calibragem) |
| `hslinks` | Links anexados a itens |
| `hsmarcas` | Marcas/fabricantes |
| `hsmensagens` | Mensagens enviadas a clientes |
| `hspaginas` | Páginas de conteúdo |
| `hsprogramas` | Módulos/programas do sistema |
| `hssetores` | Setores internos da empresa |
| `hssetorescli` | Setores de clientes (com campos SEO) |
| `hssistemas` / `hssistemas1` / `hssistemas2` | Menus do sistema (3 níveis, chave + programa + código) |
| `hstiposcalibragem` | Tipos de calibragem com valor padrão |
| `hstiposteste` | Tipos de teste |
| `hsusuarios` | Usuários internos (permissões, alertas, horário/dias de acesso) |
| `hsusuarios2` | Usuários do portal do cliente (vinculados a `hsclientes`) |

### Tabela `hsordens` — campos-chave

| Campo | Tipo | Significado |
|-------|------|-------------|
| `os` | integer PK (seq) | Número da OS |
| `cliente` | integer | → hsclientes.id |
| `equipamento` | integer | → hsequipempresa.id |
| `fase` | integer | → hsfases.id |
| `tipocali` | integer | → hstiposcalibragem.id |
| `datasoli/dataenvi/datacheg/datacali/datareto/dataentr` | timestamptz | Datas do ciclo (solicitação, envio, chegada, calibração, retorno, entrega) |
| `proxcalibragem` | timestamptz | Próxima calibração |
| `situserv` | varchar(1) | Situação do serviço: E=Em andamento |
| `pago/recebido` | varchar(1) | S/N |
| `garantia` | varchar(1) | S=Com garantia |
| `calibcert/calibtemp/calibpressao/calibteste1..3/calibtestemedia/calibsitu` | varchar(50) | Resultados de calibração |
| `pdfcertificado` | varchar(50) | Arquivo PDF do certificado |
| `checklist` | varchar(50) | IDs de checklist associados |
| `codenvio/codretorno` | varchar(50) | Códigos de rastreio (envio e retorno) |

### Tabela `hsequipempresa` — campos-chave

| Campo | Tipo | Significado |
|-------|------|-------------|
| `equipamento` | integer | → hsitens.id (tipo/modelo) |
| `cliente` | integer | → hsclientes.id |
| `serie` | varchar(50) | Número de série |
| `patrimonio` | varchar(50) | Número de patrimônio |
| `ultcalibragem/proxcalibragem` | date | Controle de vencimento |
| `ativo` | char(1) | S/N |
| `status` | varchar(1) | A=Ativo |
| `os` | integer | Última OS |
| `calibcert..calibsitu` | varchar(50) | Espelho dos resultados da última calibração (da OS) |

---

## Família `pgs` — CMS / E-commerce / Site

### Fluxo de venda/pedido

```
pgsclientes / pgscompradores (compradores pessoa física/jurídica)
  └── pgscabcarrinho (pedido/carrinho)
        ├── pgsdetcarrinho  (itens do pedido → hsitens)
        ├── pgsmovcarrinho  (movimentação de fase do pedido)
        ├── pgsmsgcarrinho  (mensagens do pedido)
        └── pgsdocscarrinho (documentos anexos)

pgscabmov / pgsdetmov       (notas fiscais / movimentos)
pgsfinance                  (financeiro: contas a pagar/receber)
```

### Tabelas de conteúdo `pgs`

| Tabela | Descrição |
|--------|-----------|
| `pgsartigos` | Blog/artigos (com SEO) |
| `pgscatalogo` | Catálogos PDF por setor |
| `pgsconteudos` | Conteúdos genéricos (tipo, produto, texto, link) |
| `pgsdestaques` / `pgsdestaques2` / `pgsdestaques3` | Banners/slides (3 zonas) |
| `pgspaginas` | Páginas institucionais |
| `pgssetores` | Setores/departamentos do site |
| `pgsslides` | Slides de produtos |
| `pgstags` | Tags de conteúdo |
| `pgstipoconteudo` | Tipos de conteúdo |
| `pgsvideos` | Vídeos com SEO |

### Tabelas de configuração `pgs`

| Tabela | Descrição |
|--------|-----------|
| `pgsbandeiras` | Bandeiras de cartão |
| `pgsconfigs` | Configurações globais (chave-valor) |
| `pgscontas` | Contas financeiras |
| `pgsdespesas` | Categorias de despesa |
| `pgsemails` | Lista de emails (newsletter, confirmado S/N) |
| `pgsfases` / `pgsfasesint` | Fases de pedido (externas e internas) |
| `pgsformapg` | Formas de pagamento |
| `pgsfretes` | Tabela de fretes (CEP range + valor) |
| `pgstipofrete` | Tipos de frete (com código transportadora) |
| `pgsmenus` / `pgsmenuitem` / `pgstipomenu` | Estrutura de menus do site |
| `pgsnotificacoes` | Notificações de pagamento/retorno de gateway |
| `pgstiposcrm` | Tipos de CRM do site |
| `pgsusuarios` | Usuários do backoffice do site |
| `pgscontatos` / `pgscontatos2` | Formulários de contato recebidos |
| `pgschat` | Chat interno (tipo CL=cliente, tipo AD=admin) |
| `pgscrm` | CRM do site (vinculado a cliente e OS) |
| `pgsperguntas` | FAQ / perguntas frequentes por produto |

---

## Família `inf` — CRM por Telefonia

| Tabela | Descrição |
|--------|-----------|
| `inftipocrm` | Tipos de ticket CRM |
| `infcrm` | Tickets vinculados a gravações de ligação (integração 4com). Campos: `idligacao`, `gravacao`, `catcrm` (I/E=entrada/saída), `situacao` (P=pendente), `transcrito` (S/N) |

---

## Convenções observadas

- **Flags booleanas** são `varchar(1)` com valores `'S'`/`'N'` ou `char(1)` `'S'`/`'N'`
- **Status** geralmente `varchar(1)`: `'P'`=Pendente, `'A'`=Ativo/Aberto, `'F'`=Fechado/Finalizado, `'E'`=Em andamento
- **Imagens** armazenadas como nome de arquivo `varchar(50)` (default `'imagem.jpg'`), não como BLOB
- **Permissões e alertas** em usuários são campos `text` (provavelmente JSON ou lista delimitada)
- **Relacionamentos** são numéricos sem FK declarada — integridade é garantida pela aplicação
- **Datas** de negócio usam `date`; timestamps de evento usam `timestamptz`
