-- GestorHS — Novo schema (família hs)
-- Banco: gestorhs-banco porta 9998
-- Convenções: snake_case, boolean real, FKs declaradas, sem prefixo hs

BEGIN;

-- =========================================================
-- TABELAS DE REFERÊNCIA (sem dependências)
-- =========================================================

CREATE TABLE setores (
    id      serial PRIMARY KEY,
    descricao varchar(200) NOT NULL
);

CREATE TABLE marcas (
    id        serial PRIMARY KEY,
    descricao varchar(100) NOT NULL,
    imagem    varchar(50)
);

CREATE TABLE grupos (
    id        serial PRIMARY KEY,
    descricao varchar(200) NOT NULL,
    texto     text
);

CREATE TABLE fases (
    id        serial PRIMARY KEY,
    descricao varchar(100) NOT NULL,
    cor       char(6)      NOT NULL DEFAULT '000000'
);

CREATE TABLE fases_lote (
    id        serial PRIMARY KEY,
    descricao varchar(100) NOT NULL,
    cor       varchar(50)
);

CREATE TABLE tipos_calibragem (
    id        serial PRIMARY KEY,
    descricao varchar(200) NOT NULL,
    texto     text,
    valor     numeric(10,2) NOT NULL DEFAULT 0.00
);

CREATE TABLE tipos_teste (
    id        serial PRIMARY KEY,
    descricao varchar(200) NOT NULL
);

CREATE TABLE programas (
    id        serial PRIMARY KEY,
    descricao varchar(200) NOT NULL
);

CREATE TABLE acesso (
    id     serial PRIMARY KEY,
    cnpj   varchar(14) NOT NULL,
    chave  varchar(12),
    limite timestamptz
);

CREATE TABLE checklist_templates (
    id        serial PRIMARY KEY,
    posicao   integer     NOT NULL DEFAULT 1,
    descricao varchar(500),
    opcoes    varchar(500)
);

-- =========================================================
-- CATEGORIAS
-- =========================================================

CREATE TABLE categorias (
    id        serial PRIMARY KEY,
    setor     integer REFERENCES setores(id),
    posicao   integer NOT NULL DEFAULT 0,
    descricao varchar(200)
);

-- =========================================================
-- CATÁLOGO DE EQUIPAMENTOS (tipos/modelos)
-- =========================================================

CREATE TABLE equipamentos (
    id               serial PRIMARY KEY,
    categoria        integer REFERENCES categorias(id),
    marca            integer REFERENCES marcas(id),
    descricao        varchar(100),
    detalhes         text,
    especificacao    text,
    preco_cod        numeric(10,2) NOT NULL DEFAULT 0.00,
    preco_por        numeric(10,2) NOT NULL DEFAULT 0.00,
    custo            numeric(10,2) NOT NULL DEFAULT 0.00,
    peso_calibragem  numeric(10,3) NOT NULL DEFAULT 0.000,
    peso             numeric(10,3) NOT NULL DEFAULT 0.000,
    imagem           varchar(50),
    estoque          integer NOT NULL DEFAULT 0,
    estoque_min      integer NOT NULL DEFAULT 0,
    ativo            boolean NOT NULL DEFAULT false,
    destaque         boolean NOT NULL DEFAULT false,
    datacad          date
);

-- =========================================================
-- CLIENTES
-- =========================================================

CREATE TABLE clientes (
    id          bigserial PRIMARY KEY,
    grupo       integer REFERENCES grupos(id),
    nome        varchar(100),
    cgc         varchar(14),
    cpf         varchar(11),
    endereco    varchar(100),
    numero      bigint,
    complemento varchar(60),
    bairro      varchar(100),
    municipio   varchar(100),
    estado      char(2),
    cep         char(8),
    contato     varchar(30),
    email       varchar(100),
    telefones   varchar(250),
    celular     varchar(250),
    whatsapp    varchar(50),
    whatsapp1   varchar(50),
    whatsapp2   varchar(50),
    insc_mun    varchar(20),
    insc_est    varchar(20),
    datcad      date,
    obs         text,
    imagem      varchar(50) DEFAULT 'imagem.jpg',
    ativo       boolean     NOT NULL DEFAULT true
);

CREATE TABLE usuarios (
    id          serial PRIMARY KEY,
    nome        varchar(100),
    login       varchar(20) UNIQUE NOT NULL,
    senha       varchar(12) NOT NULL,
    email       varchar(200),
    sexo        char(1),
    imagem      varchar(50)  DEFAULT 'imagem.jpg',
    permissoes  text,
    alertas     text,
    hora_ini    varchar(5)   DEFAULT '08:00',
    hora_fim    varchar(5)   DEFAULT '19:00',
    dias        varchar(50)  DEFAULT '2,3,4,5,6,7'
);

CREATE TABLE usuarios_cliente (
    id          serial PRIMARY KEY,
    cliente     bigint NOT NULL REFERENCES clientes(id),
    nome        varchar(100),
    login       varchar(20) NOT NULL,
    senha       varchar(12) NOT NULL,
    email       varchar(200),
    sexo        char(1),
    imagem      varchar(50) DEFAULT 'imagem.jpg',
    permissoes  text,
    alertas     text,
    hora_ini    varchar(5)  DEFAULT '08:00',
    hora_fim    varchar(5)  DEFAULT '19:00',
    dias        varchar(50) DEFAULT '2,3,4,5,6,7'
);

CREATE TABLE funcionarios (
    id        serial PRIMARY KEY,
    cliente   bigint  NOT NULL REFERENCES clientes(id),
    setor     integer REFERENCES setores(id),
    matricula varchar(50) NOT NULL DEFAULT '0',
    centro    varchar(50),
    nome      varchar(100),
    email     varchar(200),
    cargo     varchar(50),
    admissao  date,
    idade     integer,
    sexo      char(1),
    estado    varchar(2) DEFAULT 'SP',
    cidade    varchar(100),
    ativo     boolean NOT NULL DEFAULT true
);

-- =========================================================
-- EQUIPAMENTOS DO CLIENTE (instâncias físicas)
-- =========================================================

CREATE TABLE equipamentos_cliente (
    id               serial PRIMARY KEY,
    cliente          bigint  NOT NULL REFERENCES clientes(id),
    equipamento      integer NOT NULL REFERENCES equipamentos(id),
    modulo           integer NOT NULL DEFAULT 0,
    serie            varchar(50),
    patrimonio       varchar(50),
    datacompra       date,
    ult_calibragem   date,
    prox_calibragem  date,
    ult_aviso        timestamptz,
    ativo            boolean    NOT NULL DEFAULT true,
    status           varchar(1) NOT NULL DEFAULT 'A' CHECK (status IN ('A','I','M')),
    os_atual         integer,
    -- espelho dos resultados da última OS concluída
    calib_cert       varchar(50),
    calib_temp       varchar(50),
    calib_pressao    varchar(50),
    calib_teste1     varchar(50),
    calib_teste2     varchar(50),
    calib_teste3     varchar(50),
    calib_teste_media varchar(50),
    calib_situacao   varchar(50)
);

CREATE TABLE historico_equipamentos (
    id                   serial PRIMARY KEY,
    equipamento_cliente  integer NOT NULL REFERENCES equipamentos_cliente(id),
    datamov              date,
    saida                integer,
    entrada              integer
);

-- =========================================================
-- ORDENS DE SERVIÇO
-- =========================================================

CREATE TABLE ordens (
    id                  serial PRIMARY KEY,
    cliente             bigint  NOT NULL REFERENCES clientes(id),
    equipamento_cliente integer REFERENCES equipamentos_cliente(id),
    fase                integer REFERENCES fases(id),
    tipo_calibragem     integer REFERENCES tipos_calibragem(id),
    caixa               integer,
    checklist           varchar(50),
    -- datas do ciclo
    data_solicitacao    timestamptz,
    data_envio          timestamptz,
    data_chegada        timestamptz,
    data_calibracao     timestamptz,
    data_retorno        timestamptz,
    data_entrega        timestamptz,
    prox_calibragem     timestamptz,
    -- rastreio logístico
    cod_envio           varchar(50),
    cod_retorno         varchar(50),
    etiqueta            varchar(50),
    -- resultados de calibração
    calib_cert          varchar(50),
    calib_temp          varchar(50),
    calib_pressao       varchar(50),
    calib_teste1        varchar(50),
    calib_teste2        varchar(50),
    calib_teste3        varchar(50),
    calib_teste_media   varchar(50),
    calib_situacao      varchar(50),
    pdf_certificado     varchar(50),
    certificado         text,
    -- financeiro
    valor               numeric(10,2) NOT NULL DEFAULT 0.00,
    frete_envio         numeric(10,2) NOT NULL DEFAULT 0.00,
    frete_retorno       numeric(10,2) NOT NULL DEFAULT 0.00,
    pago                boolean NOT NULL DEFAULT false,
    recebido            boolean NOT NULL DEFAULT false,
    -- controle
    garantia            boolean    NOT NULL DEFAULT true,
    situacao            varchar(1) NOT NULL DEFAULT 'E' CHECK (situacao IN ('E','C','F')),
    chave               varchar(12),
    pilhas              integer DEFAULT 0,
    sopradores          integer DEFAULT 0,
    arquivo             varchar(50),
    obs                 text
);

-- FK circular resolvida após criação das duas tabelas
ALTER TABLE equipamentos_cliente
    ADD CONSTRAINT fk_equip_cli_os FOREIGN KEY (os_atual) REFERENCES ordens(id);

CREATE TABLE logs_os (
    id       serial PRIMARY KEY,
    os       integer NOT NULL REFERENCES ordens(id),
    usuario  integer REFERENCES usuarios(id),
    datalog  timestamptz,
    autor    varchar(1) NOT NULL DEFAULT '0',
    texto    text
);

CREATE TABLE certificados (
    id                  serial PRIMARY KEY,
    equipamento_cliente integer NOT NULL REFERENCES equipamentos_cliente(id),
    descricao           varchar(100),
    texto               text
);

-- =========================================================
-- CHECKLIST RESPOSTAS
-- =========================================================

CREATE TABLE checklist_respostas (
    id        serial PRIMARY KEY,
    os        integer REFERENCES ordens(id),
    lote      integer,
    item      integer REFERENCES checklist_templates(id),
    opcao     integer,
    dataresp  timestamptz,
    obs       varchar(1000)
);

-- =========================================================
-- LOTES
-- =========================================================

CREATE TABLE lotes (
    id          serial PRIMARY KEY,
    datalote    timestamptz,
    equipamentos text,
    status      integer DEFAULT 1,
    obs         varchar(1000)
);

-- =========================================================
-- TESTES (bafômetro / equipamentos de segurança)
-- =========================================================

CREATE TABLE testes (
    id           serial PRIMARY KEY,
    numero       integer,
    tipo_teste   integer REFERENCES tipos_teste(id),
    datateste    timestamptz,
    cliente      bigint  REFERENCES clientes(id),
    equipamentos bigint  NOT NULL DEFAULT 0,
    funcionarios integer NOT NULL DEFAULT 1,
    testados     integer NOT NULL DEFAULT 0,
    obs          text
);

CREATE TABLE testes_detalhes (
    id                  serial PRIMARY KEY,
    teste               integer NOT NULL REFERENCES testes(id),
    cliente             bigint  REFERENCES clientes(id),
    funcionario         integer REFERENCES funcionarios(id),
    equipamento_cliente integer REFERENCES equipamentos_cliente(id),
    datateste           timestamptz,
    situacao            char(1) DEFAULT 'N',
    obs                 varchar(250)
);

-- =========================================================
-- CAIXA
-- =========================================================

CREATE TABLE caixas (
    id     serial PRIMARY KEY,
    data   date,
    status varchar(1) NOT NULL DEFAULT 'P' CHECK (status IN ('P','A','F')),
    obs    varchar(1000)
);

-- =========================================================
-- DOCUMENTOS E FOTOS
-- =========================================================

CREATE TABLE documentos (
    id        serial PRIMARY KEY,
    equipamento integer REFERENCES equipamentos(id),
    posicao   integer DEFAULT 0,
    titulo    varchar(250),
    arquivo   varchar(50)
);

CREATE TABLE documentos_equipamento_cliente (
    id                  serial PRIMARY KEY,
    equipamento_cliente integer REFERENCES equipamentos_cliente(id),
    posicao             integer DEFAULT 0,
    titulo              varchar(250),
    arquivo             varchar(50)
);

CREATE TABLE fotos (
    id       serial PRIMARY KEY,
    cliente  bigint  REFERENCES clientes(id),
    codigo   integer,
    cor      integer DEFAULT 0,
    tipo     char(1) DEFAULT 'I',
    posicao  integer DEFAULT 1,
    arquivo  varchar(50),
    legenda  varchar(250)
);

CREATE TABLE links (
    id        serial PRIMARY KEY,
    item      integer REFERENCES equipamentos(id),
    posicao   integer DEFAULT 0,
    titulo    varchar(250),
    arquivo   varchar(250)
);

-- =========================================================
-- COMUNICAÇÃO
-- =========================================================

CREATE TABLE mensagens (
    id       serial PRIMARY KEY,
    cliente  bigint NOT NULL REFERENCES clientes(id),
    data     date,
    titulo   varchar(100),
    texto    text
);

CREATE TABLE envios (
    id         serial PRIMARY KEY,
    tipo       varchar(3) NOT NULL DEFAULT 'I',
    modo       varchar(1) NOT NULL DEFAULT 'E',
    datain     timestamptz,
    objetivo   varchar(250),
    assunto    varchar(250),
    texto      text,
    programado text,
    realizar   text,
    status     varchar(1) NOT NULL DEFAULT 'P' CHECK (status IN ('P','E','F'))
);

-- =========================================================
-- MENUS DO SISTEMA (3 níveis unificados)
-- =========================================================

CREATE TABLE menus_sistema (
    id        serial PRIMARY KEY,
    nivel     integer    NOT NULL DEFAULT 1 CHECK (nivel IN (1,2,3)),
    posicao   integer,
    chave     varchar(50),
    descricao varchar(50),
    programa  varchar(50),
    codigo    integer,
    icone     varchar(50)
);

COMMIT;
