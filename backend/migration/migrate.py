"""
Migração: gestorhs-banco (porta 9999) → gestorhs-banco (porta 9998)
Família hs → novo schema limpo

Ordem respeitando FKs:
  Nível 0: setores, marcas, grupos, fases, fases_lote, tipos_calibragem,
            tipos_teste, programas, acesso, checklist_templates, caixas
  Nível 1: categorias, clientes, usuarios, menus_sistema
  Nível 2: equipamentos, usuarios_cliente, funcionarios
  Nível 3: equipamentos_cliente (sem os_atual)
  Nível 4: ordens
  Nível 5: logs_os, certificados, checklist_respostas, lotes,
            historico_equipamentos, testes, testes_detalhes,
            documentos, documentos_equipamento_cliente,
            fotos, links, mensagens, envios
  Pós:     UPDATE equipamentos_cliente.os_atual
"""

import os

import psycopg2
from psycopg2.extras import execute_values
from dataclasses import dataclass, field
from typing import Any

# ─── Conexões ────────────────────────────────────────────────────────────────
# Credenciais via ambiente (não versionar segredos). Defina antes de rodar, ex.:
#   set MIGRACAO_HOST=...  MIGRACAO_USER=...  MIGRACAO_PASSWORD=...
# (Windows: `set`; Linux/macOS: `export`.) Os defaults abaixo NÃO são secretos.

_HOST = os.getenv("MIGRACAO_HOST", "localhost")
_USER = os.getenv("MIGRACAO_USER", "administrador")
_PASSWORD = os.getenv("MIGRACAO_PASSWORD", "")
_DBNAME = os.getenv("MIGRACAO_DBNAME", "gestorhs-banco")

ORIGEM = dict(host=_HOST, port=int(os.getenv("MIGRACAO_ORIGEM_PORT", "9999")),
              dbname=_DBNAME, user=_USER, password=_PASSWORD)

DESTINO = dict(host=_HOST, port=int(os.getenv("MIGRACAO_DESTINO_PORT", "9998")),
               dbname=_DBNAME, user=_USER, password=_PASSWORD)

# ─── Relatório ───────────────────────────────────────────────────────────────

@dataclass
class Relatorio:
    migradas: dict[str, int] = field(default_factory=dict)
    ignoradas: dict[str, list[str]] = field(default_factory=dict)
    erros: list[str] = field(default_factory=list)

    def ok(self, tabela: str, n: int):
        self.migradas[tabela] = n
        print(f"  [OK] {tabela}: {n} registros")

    def warn(self, tabela: str, msg: str):
        self.ignoradas.setdefault(tabela, []).append(msg)
        print(f"  [AVISO] {tabela}: {msg}")

    def erro(self, tabela: str, msg: str):
        self.erros.append(f"{tabela}: {msg}")
        print(f"  [ERRO] {tabela}: {msg}")

    def resumo(self):
        print("\n" + "=" * 50)
        print("RESUMO DA MIGRACAO")
        print("=" * 50)
        total = sum(self.migradas.values())
        print(f"Tabelas migradas : {len(self.migradas)}")
        print(f"Total de linhas  : {total}")
        if self.ignoradas:
            print(f"\nAvisos ({len(self.ignoradas)} tabelas):")
            for t, msgs in self.ignoradas.items():
                for m in msgs:
                    print(f"  [AVISO] {t}: {m}")
        if self.erros:
            print(f"\nErros ({len(self.erros)}):")
            for e in self.erros:
                print(f"  [ERRO] {e}")
        else:
            print("\n[OK] Migracao concluida sem erros criticos.")

# ─── Helpers ─────────────────────────────────────────────────────────────────

def sn_bool(v) -> bool | None:
    if v is None:
        return None
    return str(v).strip().upper() == 'S'

def strip_or_none(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None

def inserir(cur_dst, tabela: str, colunas: list[str], linhas: list[tuple]) -> int:
    if not linhas:
        return 0
    sql = f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES %s ON CONFLICT DO NOTHING"
    execute_values(cur_dst, sql, linhas)
    return len(linhas)

def resetar_sequence(cur_dst, tabela: str, coluna: str = "id"):
    cur_dst.execute(f"""
        SELECT setval(
            pg_get_serial_sequence('{tabela}', '{coluna}'),
            COALESCE(MAX({coluna}), 1)
        ) FROM {tabela}
    """)

# ─── Migrações por tabela ─────────────────────────────────────────────────────

def migrar_setores(src, dst, rel):
    src.execute("SELECT id, descricao FROM hssetores")
    rows = [(r[0], r[1]) for r in src.fetchall()]
    n = inserir(dst, "setores", ["id", "descricao"], rows)
    resetar_sequence(dst, "setores")
    rel.ok("setores", n)


def migrar_marcas(src, dst, rel):
    src.execute("SELECT id, descricao, imagem FROM hsmarcas")
    rows = [(r[0], r[1], r[2]) for r in src.fetchall()]
    n = inserir(dst, "marcas", ["id", "descricao", "imagem"], rows)
    resetar_sequence(dst, "marcas")
    rel.ok("marcas", n)


def migrar_grupos(src, dst, rel):
    src.execute("SELECT id, descricao, texto FROM hsgrupos")
    rows = [(r[0], r[1], r[2]) for r in src.fetchall()]
    n = inserir(dst, "grupos", ["id", "descricao", "texto"], rows)
    resetar_sequence(dst, "grupos")
    rel.ok("grupos", n)


def migrar_fases(src, dst, rel):
    """NAO migra: as fases sao definidas pelas migracoes 0002 e 0010, nao pelo legado.

    A 0002 redefiniu as fases 4-9 (descricao, cor, funcao_responsavel) e apagou
    as extintas 1-3; a 0010 acrescentou a 10 (Financeiro). Reimportar hsfases
    cru sobrescreveria essa definicao e ressuscitaria as fases 1-3, que o
    workflow em app/core/os_workflow.py nao conhece.
    """
    dst.execute("SELECT count(*) FROM fases")
    n = dst.fetchone()[0]
    rel.warn("fases", f"pulada de proposito — {n} fases definidas pelas migracoes 0002/0010")


def migrar_fases_lote(src, dst, rel):
    src.execute("SELECT id, descricao, cor FROM hsfaseslote")
    rows = [(r[0], r[1], r[2]) for r in src.fetchall()]
    n = inserir(dst, "fases_lote", ["id", "descricao", "cor"], rows)
    resetar_sequence(dst, "fases_lote")
    rel.ok("fases_lote", n)


def migrar_tipos_calibragem(src, dst, rel):
    src.execute("SELECT id, descricao, texto, valor FROM hstiposcalibragem")
    rows = [(r[0], r[1], r[2], r[3]) for r in src.fetchall()]
    n = inserir(dst, "tipos_calibragem", ["id", "descricao", "texto", "valor"], rows)
    resetar_sequence(dst, "tipos_calibragem")
    rel.ok("tipos_calibragem", n)


def migrar_tipos_teste(src, dst, rel):
    src.execute("SELECT id, descricao FROM hstiposteste")
    rows = [(r[0], r[1]) for r in src.fetchall()]
    n = inserir(dst, "tipos_teste", ["id", "descricao"], rows)
    resetar_sequence(dst, "tipos_teste")
    rel.ok("tipos_teste", n)


def migrar_programas(src, dst, rel):
    src.execute("SELECT id, descricao FROM hsprogramas")
    rows = [(r[0], r[1]) for r in src.fetchall()]
    n = inserir(dst, "programas", ["id", "descricao"], rows)
    resetar_sequence(dst, "programas")
    rel.ok("programas", n)


def migrar_acesso(src, dst, rel):
    src.execute("SELECT id, cnpj, chave, limite FROM hsacesso")
    rows = [(r[0], r[1], r[2], r[3]) for r in src.fetchall()]
    n = inserir(dst, "acesso", ["id", "cnpj", "chave", "limite"], rows)
    resetar_sequence(dst, "acesso")
    rel.ok("acesso", n)


def migrar_checklist_templates(src, dst, rel):
    src.execute("SELECT id, posicao, descricao, opcoes FROM hschecklist")
    rows = [(r[0], r[1], r[2], r[3]) for r in src.fetchall()]
    n = inserir(dst, "checklist_templates", ["id", "posicao", "descricao", "opcoes"], rows)
    resetar_sequence(dst, "checklist_templates")
    rel.ok("checklist_templates", n)


def migrar_caixas(src, dst, rel):
    # 'status' foi removido pela migracao 0005 — caixa e so agrupamento fisico
    src.execute("SELECT id, data, obs FROM hscaixas")
    rows = [(r[0], r[1], r[2]) for r in src.fetchall()]
    n = inserir(dst, "caixas", ["id", "data", "obs"], rows)
    resetar_sequence(dst, "caixas")
    rel.ok("caixas", n)


def migrar_categorias(src, dst, rel):
    src.execute("SELECT id, posicao, setor, descricao FROM hscategorias")
    # setor pode não existir na nova tabela — filtra órfãos
    dst.execute("SELECT id FROM setores")
    setores_validos = {r[0] for r in dst.fetchall()}
    rows, ignorados = [], 0
    for r in src.fetchall():
        setor = r[2] if r[2] and r[2] in setores_validos else None
        rows.append((r[0], setor, r[1], r[3]))
        if r[2] and r[2] not in setores_validos:
            ignorados += 1
    n = inserir(dst, "categorias", ["id", "setor", "posicao", "descricao"], rows)
    resetar_sequence(dst, "categorias")
    if ignorados:
        rel.warn("categorias", f"{ignorados} registros com setor órfão (setor_id setado como NULL)")
    rel.ok("categorias", n)


def migrar_clientes(src, dst, rel):
    src.execute("""
        SELECT id, usuario, grupo, nome, cgc, cpf, endereco, numero, complemento,
               bairro, municipio, estado, cep, contato, email, telefones, celular,
               whatsapp, whatsapp1, whatsapp2, insc_mun, insc_est, datcad, obs, imagem
        FROM hsclientes
    """)
    dst.execute("SELECT id FROM grupos")
    grupos_validos = {r[0] for r in dst.fetchall()}
    rows = []
    for r in src.fetchall():
        grupo = r[2] if r[2] and r[2] in grupos_validos else None
        rows.append((
            r[0], grupo,
            strip_or_none(r[3]),   # nome
            strip_or_none(r[4]),   # cgc
            strip_or_none(r[5]),   # cpf
            strip_or_none(r[6]),   # endereco
            r[7],                  # numero
            strip_or_none(r[8]),   # complemento
            strip_or_none(r[9]),   # bairro
            strip_or_none(r[10]),  # municipio
            strip_or_none(r[11]),  # estado
            strip_or_none(r[12]),  # cep
            strip_or_none(r[13]),  # contato
            strip_or_none(r[14]),  # email
            r[15], r[16],          # telefones, celular
            r[17], r[18], r[19],   # whatsapp x3
            strip_or_none(r[20]),  # insc_mun
            strip_or_none(r[21]),  # insc_est
            r[22],                 # datcad
            r[23],                 # obs
            r[24],                 # imagem
            True,                  # ativo (hsclientes não tem campo ativo)
        ))
    cols = ["id", "grupo", "nome", "cgc", "cpf", "endereco", "numero", "complemento",
            "bairro", "municipio", "estado", "cep", "contato", "email", "telefones",
            "celular", "whatsapp", "whatsapp1", "whatsapp2", "insc_mun", "insc_est",
            "datcad", "obs", "imagem", "ativo"]
    n = inserir(dst, "clientes", cols, rows)
    resetar_sequence(dst, "clientes")
    rel.ok("clientes", n)


def migrar_usuarios(src, dst, rel):
    """NAO migra: os usuarios internos sao recadastrados no sistema novo.

    O legado tem 3 usuarios com senha em texto puro, e a credencial mudou de
    'login' para e-mail na migracao 0012. Em vez de arrastar isso, o acesso
    comeca do zero com um admin criado por:
        python -m app.scripts.criar_usuario <email> <senha> Administrador

    Efeito colateral esperado: migrar_logs_os grava usuario=NULL em todos os
    logs (o campo textual 'autor' preserva quem foi no legado).
    """
    src.execute("SELECT count(*) FROM hsusuarios")
    n = src.fetchone()[0]
    rel.warn("usuarios", f"pulada de proposito — {n} usuarios do legado descartados")


def migrar_menus_sistema(src, dst, rel):
    total = 0
    for nivel, tabela in [(1, "hssistemas"), (2, "hssistemas1"), (3, "hssistemas2")]:
        try:
            if nivel == 3:
                src.execute(f"SELECT id, posicao, chave, descricao, programa, codigo, icone FROM {tabela}")
                rows = [(r[0], nivel, r[1], r[2], r[3], r[4], r[5], r[6]) for r in src.fetchall()]
                cols = ["id", "nivel", "posicao", "chave", "descricao", "programa", "codigo", "icone"]
            else:
                src.execute(f"SELECT id, posicao, chave, descricao, programa, codigo FROM {tabela}")
                rows = [(r[0], nivel, r[1], r[2], r[3], r[4], r[5], None) for r in src.fetchall()]
                cols = ["id", "nivel", "posicao", "chave", "descricao", "programa", "codigo", "icone"]
            total += inserir(dst, "menus_sistema", cols, rows)
        except Exception as e:
            rel.warn("menus_sistema", f"nivel {nivel} ({tabela}): {e}")
    resetar_sequence(dst, "menus_sistema")
    rel.ok("menus_sistema", total)


def migrar_equipamentos(src, dst, rel):
    src.execute("""
        SELECT id, ativo, destaque, datacad, categoria, marca, descricao,
               detalhes, especificacao, precode, precopor, custo,
               pesocalibragem, peso, imagem, estoque, estmin
        FROM hsitens
    """)
    dst.execute("SELECT id FROM categorias")
    cats = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM marcas")
    marcas = {r[0] for r in dst.fetchall()}
    rows = []
    for r in src.fetchall():
        cat   = r[4] if r[4] and r[4] in cats   else None
        marca = r[5] if r[5] and r[5] in marcas else None
        rows.append((
            r[0],
            cat, marca,
            r[6],   # descricao
            r[7],   # detalhes
            r[8],   # especificacao
            r[9] or 0, r[10] or 0, r[11] or 0,
            r[12] or 0, r[13] or 0,
            r[14],  # imagem
            r[15] or 0, r[16] or 0,
            sn_bool(r[1]),   # ativo
            sn_bool(r[2]),   # destaque
            r[3],            # datacad
        ))
    cols = ["id", "categoria", "marca", "descricao", "detalhes", "especificacao",
            "preco_cod", "preco_por", "custo", "peso_calibragem", "peso",
            "imagem", "estoque", "estoque_min", "ativo", "destaque", "datacad"]
    n = inserir(dst, "equipamentos", cols, rows)
    resetar_sequence(dst, "equipamentos")
    rel.ok("equipamentos", n)


def migrar_usuarios_cliente(src, dst, rel):
    src.execute("""
        SELECT id, cliente, email, nome, login, senha, imagem, sexo,
               permissoes, alertas, horain, horafi, dias
        FROM hsusuarios2
    """)
    dst.execute("SELECT id FROM clientes")
    clientes = {r[0] for r in dst.fetchall()}
    rows, ignorados = [], 0
    for r in src.fetchall():
        if r[1] not in clientes:
            ignorados += 1
            continue
        login = (r[4] or r[2] or f"cli_{r[0]}")[:20]  # fallback: email ou id, max 20
        # senha do legado e texto puro; entra vazia e forca redefinicao (igual a 0001)
        rows.append((r[0], r[1], r[2], r[3], login, "", True, r[6],
                     strip_or_none(r[7]), r[8], r[9], r[10], r[11], r[12]))
    cols = ["id", "cliente", "email", "nome", "login", "senha", "precisa_redefinir_senha",
            "imagem", "sexo", "permissoes", "alertas", "hora_ini", "hora_fim", "dias"]
    n = inserir(dst, "usuarios_cliente", cols, rows)
    resetar_sequence(dst, "usuarios_cliente")
    if ignorados:
        rel.warn("usuarios_cliente", f"{ignorados} registros ignorados por cliente inexistente")
    rel.ok("usuarios_cliente", n)


def migrar_funcionarios(src, dst, rel):
    src.execute("""
        SELECT id, setor, cliente, matricula, centro, estado, cidade, nome,
               email, idade, sexo, cargo, admissao, ativo
        FROM hsfuncionarios
    """)
    dst.execute("SELECT id FROM clientes")
    clientes = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM setores")
    setores = {r[0] for r in dst.fetchall()}
    rows, ignorados = [], 0
    for r in src.fetchall():
        if r[2] not in clientes:
            ignorados += 1
            continue
        setor = r[1] if r[1] and r[1] in setores else None
        rows.append((
            r[0], r[2], setor, r[3], r[4],
            r[5], r[6], r[7], r[8], r[9],
            strip_or_none(r[10]), r[11], r[12],
            sn_bool(r[13]),
        ))
    cols = ["id", "cliente", "setor", "matricula", "centro", "estado", "cidade",
            "nome", "email", "idade", "sexo", "cargo", "admissao", "ativo"]
    n = inserir(dst, "funcionarios", cols, rows)
    resetar_sequence(dst, "funcionarios")
    if ignorados:
        rel.warn("funcionarios", f"{ignorados} registros ignorados por cliente inexistente")
    rel.ok("funcionarios", n)


def migrar_equipamentos_cliente(src, dst, rel):
    src.execute("""
        SELECT id, modulo, equipamento, cliente, serie, patrimonio, datacompra,
               ultcalibragem, ultaviso, proxcalibragem, ativo, os, status,
               calibcert, calibtemp, calibpressao, calibteste1, calibteste2,
               calibteste3, calibtestemedia, calibsitu
        FROM hsequipempresa
    """)
    dst.execute("SELECT id FROM clientes")
    clientes = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM equipamentos")
    equipamentos = {r[0] for r in dst.fetchall()}
    rows, ignorados = [], 0
    for r in src.fetchall():
        if r[3] not in clientes or r[2] not in equipamentos:
            ignorados += 1
            continue
        rows.append((
            r[0], r[3], r[2],    # id, cliente, equipamento
            r[1],                 # modulo
            r[4], r[5],           # serie, patrimonio
            r[6], r[7], r[8], r[9],  # datas
            sn_bool(r[10]),       # ativo
            None,                 # os_atual — preenchido depois
            r[12] if r[12] in ('A','I','M') else 'A',  # status
            r[13], r[14], r[15], r[16], r[17], r[18], r[19], r[20],
        ))
    cols = ["id", "cliente", "equipamento", "modulo", "serie", "patrimonio",
            "datacompra", "ult_calibragem", "ult_aviso", "prox_calibragem",
            "ativo", "os_atual", "status",
            "calib_cert", "calib_temp", "calib_pressao",
            "calib_teste1", "calib_teste2", "calib_teste3",
            "calib_teste_media", "calib_situacao"]
    n = inserir(dst, "equipamentos_cliente", cols, rows)
    resetar_sequence(dst, "equipamentos_cliente")
    if ignorados:
        rel.warn("equipamentos_cliente", f"{ignorados} ignorados por cliente/equipamento inexistente")
    rel.ok("equipamentos_cliente", n)


def migrar_ordens(src, dst, rel):
    src.execute("""
        SELECT os, caixa, chave, checklist, pilhas, sopradores, cliente, equipamento,
               fase, datasoli, dataenvi, datacheg, datacali, datareto, dataentr,
               proxcalibragem, obs, certificado, codenvio, codretorno, etiqueta,
               calibcert, calibtemp, calibpressao, calibteste1, calibteste2,
               calibteste3, calibtestemedia, calibsitu, pdfcertificado,
               tipocali, valor, freteenvio, freteretorno, pago, recebido,
               arquivo, situserv, garantia
        FROM hsordens
    """)
    dst.execute("SELECT id FROM clientes")
    clientes = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM equipamentos_cliente")
    equips = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM fases")
    fases = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM tipos_calibragem")
    tipos_cal = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM caixas")
    caixas = {r[0] for r in dst.fetchall()}

    # Fases 1-3 do legado (Inicio, Com etiqueta, Enviado) sao estados pre-chegada
    # extintos pela 0002 — as OS nesses estados entram como Recebido (FASE_RECEBIDO=4).
    FASES_EXTINTAS = {1, 2, 3}
    FASE_RECEBIDO = 4

    rows, ignorados, remapeadas = [], 0, 0
    for r in src.fetchall():
        if r[6] not in clientes:
            ignorados += 1
            continue
        equip  = r[7]  if r[7]  and r[7]  in equips    else None
        fase_origem = r[8]
        if fase_origem in FASES_EXTINTAS:
            fase_origem = FASE_RECEBIDO
            remapeadas += 1
        fase   = fase_origem if fase_origem and fase_origem in fases else None
        tipocal= r[30] if r[30] and r[30] in tipos_cal  else None
        caixa  = r[1]  if r[1]  and r[1]  in caixas     else None
        rows.append((
            r[0],          # id (os)
            r[6],          # cliente
            equip, fase, tipocal, caixa,
            r[3],          # checklist
            r[9], r[10], r[11], r[12], r[13], r[14], r[15],  # datas
            r[18], r[19], r[20],  # cod_envio, cod_retorno, etiqueta
            r[21], r[22], r[23], r[24], r[25], r[26], r[27], r[28], r[29],  # calib
            r[31] or 0, r[32] or 0, r[33] or 0,  # valor, frete_envio, frete_retorno
            sn_bool(r[34]),  # pago
            sn_bool(r[35]),  # recebido
            sn_bool(r[38]),  # garantia
            r[37] if r[37] in ('E','C','F') else 'E',  # situacao
            r[2],            # chave
            r[4] or 0, r[5] or 0,  # pilhas, sopradores
            r[36],           # arquivo
            r[16],           # obs
            r[17],           # certificado
        ))
    cols = [
        "id", "cliente", "equipamento_cliente", "fase", "tipo_calibragem", "caixa",
        "checklist",
        "data_solicitacao", "data_envio", "data_chegada", "data_calibracao",
        "data_retorno", "data_entrega", "prox_calibragem",
        "cod_envio", "cod_retorno", "etiqueta",
        "calib_cert", "calib_temp", "calib_pressao",
        "calib_teste1", "calib_teste2", "calib_teste3",
        "calib_teste_media", "calib_situacao", "pdf_certificado",
        "valor", "frete_envio", "frete_retorno",
        "pago", "recebido", "garantia", "situacao",
        "chave", "pilhas", "sopradores", "arquivo", "obs", "certificado",
    ]
    n = inserir(dst, "ordens", cols, rows)
    resetar_sequence(dst, "ordens")
    if ignorados:
        rel.warn("ordens", f"{ignorados} ignorados por cliente inexistente")
    if remapeadas:
        rel.warn("ordens", f"{remapeadas} OS em fase extinta (1-3) remapeadas para Recebido")
    rel.ok("ordens", n)


def migrar_os_atual(src, dst, rel):
    src.execute("SELECT id, os FROM hsequipempresa WHERE os IS NOT NULL AND os > 0")
    dst.execute("SELECT id FROM ordens")
    ordens_validas = {r[0] for r in dst.fetchall()}
    atualizados = 0
    for r in src.fetchall():
        if r[1] and r[1] in ordens_validas:
            dst.execute("UPDATE equipamentos_cliente SET os_atual = %s WHERE id = %s", (r[1], r[0]))
            atualizados += 1
    rel.ok("equipamentos_cliente.os_atual (update)", atualizados)


def migrar_logs_os(src, dst, rel):
    src.execute("SELECT id, datalog, os, autor, usuario, texto FROM hslogos")
    dst.execute("SELECT id FROM ordens")
    ordens = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM usuarios")
    usuarios = {r[0] for r in dst.fetchall()}
    rows, ignorados = [], 0
    for r in src.fetchall():
        if r[2] not in ordens:
            ignorados += 1
            continue
        usuario = r[4] if r[4] and r[4] in usuarios else None
        rows.append((r[0], r[2], usuario, r[1], r[3], r[5]))
    cols = ["id", "os", "usuario", "datalog", "autor", "texto"]
    n = inserir(dst, "logs_os", cols, rows)
    resetar_sequence(dst, "logs_os")
    if ignorados:
        rel.warn("logs_os", f"{ignorados} ignorados por OS inexistente")
    rel.ok("logs_os", n)


def migrar_certificados(src, dst, rel):
    """A 0006 trocou 'equipamento_cliente' por 'equipamento' — e o sentido mudou.

    Deixou de ser "certificado do aparelho do cliente" e virou MODELO de
    certificado por item do catalogo (FK -> equipamentos). O vinculo do legado
    aponta mesmo para hsitens (catalogo), nao para a frota.
    """
    src.execute("SELECT id, equipamento, descricao, texto FROM hscertificados")
    dst.execute("SELECT id FROM equipamentos")
    catalogo = {r[0] for r in dst.fetchall()}
    rows, orfaos = [], 0
    for r in src.fetchall():
        equip = r[1] if r[1] and r[1] in catalogo else None
        if r[1] and equip is None:
            orfaos += 1
        rows.append((r[0], equip, r[2], r[3]))
    # 'tipo' fica de fora: NOT NULL com server_default 'C' (migracao 0007)
    cols = ["id", "equipamento", "descricao", "texto"]
    n = inserir(dst, "certificados", cols, rows)
    resetar_sequence(dst, "certificados")
    if orfaos:
        rel.warn("certificados", f"{orfaos} sem equipamento valido no catalogo (equipamento=NULL)")
    rel.ok("certificados", n)


def migrar_checklist_respostas(src, dst, rel):
    src.execute("SELECT id, dataresp, os, lote, item, opcao, obs FROM hschecklistdet")
    dst.execute("SELECT id FROM ordens")
    ordens = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM checklist_templates")
    templates = {r[0] for r in dst.fetchall()}
    rows = []
    for r in src.fetchall():
        os_id   = r[2] if r[2] and r[2] in ordens    else None
        item_id = r[4] if r[4] and r[4] in templates else None
        rows.append((r[0], os_id, r[3], item_id, r[5], r[1], r[6]))
    cols = ["id", "os", "lote", "item", "opcao", "dataresp", "obs"]
    n = inserir(dst, "checklist_respostas", cols, rows)
    resetar_sequence(dst, "checklist_respostas")
    rel.ok("checklist_respostas", n)


def migrar_lotes(src, dst, rel):
    src.execute("SELECT id, datalote, equipamentos, status, obs FROM hslotes")
    rows = [(r[0], r[1], r[2], r[3], r[4]) for r in src.fetchall()]
    n = inserir(dst, "lotes", ["id", "datalote", "equipamentos", "status", "obs"], rows)
    resetar_sequence(dst, "lotes")
    rel.ok("lotes", n)


def migrar_historico_equipamentos(src, dst, rel):
    src.execute("SELECT id, idequip, datamov, saida, entrada FROM hsequiphist")
    dst.execute("SELECT id FROM equipamentos_cliente")
    equips = {r[0] for r in dst.fetchall()}
    rows, ignorados = [], 0
    for r in src.fetchall():
        if r[1] not in equips:
            ignorados += 1
            continue
        rows.append((r[0], r[1], r[2], r[3], r[4]))
    cols = ["id", "equipamento_cliente", "datamov", "saida", "entrada"]
    n = inserir(dst, "historico_equipamentos", cols, rows)
    resetar_sequence(dst, "historico_equipamentos")
    if ignorados:
        rel.warn("historico_equipamentos", f"{ignorados} ignorados por equipamento inexistente")
    rel.ok("historico_equipamentos", n)


def migrar_testes(src, dst, rel):
    src.execute("""
        SELECT id, numero, tipoteste, datateste, cliente, equipamentos, funcionarios, testados, obs
        FROM hscabteste
    """)
    dst.execute("SELECT id FROM tipos_teste")
    tipos = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM clientes")
    clientes = {r[0] for r in dst.fetchall()}
    rows = []
    for r in src.fetchall():
        tipo    = r[2] if r[2] and r[2] in tipos    else None
        cliente = r[4] if r[4] and r[4] in clientes else None
        rows.append((r[0], r[1], tipo, r[3], cliente, r[5], r[6], r[7], r[8]))
    cols = ["id", "numero", "tipo_teste", "datateste", "cliente",
            "equipamentos", "funcionarios", "testados", "obs"]
    n = inserir(dst, "testes", cols, rows)
    resetar_sequence(dst, "testes")
    rel.ok("testes", n)


def migrar_testes_detalhes(src, dst, rel):
    src.execute("""
        SELECT id, teste, datateste, cliente, funcionario, equipamento, situacao, obs
        FROM hsdetteste
    """)
    dst.execute("SELECT id FROM testes")
    testes = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM clientes")
    clientes = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM funcionarios")
    funcs = {r[0] for r in dst.fetchall()}
    dst.execute("SELECT id FROM equipamentos_cliente")
    equips = {r[0] for r in dst.fetchall()}
    rows, ignorados = [], 0
    for r in src.fetchall():
        if r[1] not in testes:
            ignorados += 1
            continue
        cliente = r[3] if r[3] and r[3] in clientes else None
        func    = r[4] if r[4] and r[4] in funcs    else None
        equip   = r[5] if r[5] and r[5] in equips   else None
        rows.append((r[0], r[1], cliente, func, equip, r[2], r[6], r[7]))
    cols = ["id", "teste", "cliente", "funcionario", "equipamento_cliente",
            "datateste", "situacao", "obs"]
    n = inserir(dst, "testes_detalhes", cols, rows)
    resetar_sequence(dst, "testes_detalhes")
    if ignorados:
        rel.warn("testes_detalhes", f"{ignorados} ignorados por teste inexistente")
    rel.ok("testes_detalhes", n)


def migrar_documentos(src, dst, rel):
    src.execute("SELECT id, item, posicao, titulo, arquivo FROM hsdocumentos")
    dst.execute("SELECT id FROM equipamentos")
    equips = {r[0] for r in dst.fetchall()}
    rows, ignorados = [], 0
    for r in src.fetchall():
        equip = r[1] if r[1] and r[1] in equips else None
        if equip is None:
            ignorados += 1
            continue
        rows.append((r[0], equip, r[2], r[3], r[4]))
    cols = ["id", "equipamento", "posicao", "titulo", "arquivo"]
    n = inserir(dst, "documentos", cols, rows)
    resetar_sequence(dst, "documentos")
    if ignorados:
        rel.warn("documentos", f"{ignorados} ignorados por equipamento inexistente")
    rel.ok("documentos", n)


def migrar_documentos_equipamento_cliente(src, dst, rel):
    src.execute("SELECT id, item, posicao, titulo, arquivo FROM hsdocequip")
    dst.execute("SELECT id FROM equipamentos_cliente")
    equips = {r[0] for r in dst.fetchall()}
    rows, ignorados = [], 0
    for r in src.fetchall():
        equip = r[1] if r[1] and r[1] in equips else None
        if equip is None:
            ignorados += 1
            continue
        rows.append((r[0], equip, r[2], r[3], r[4]))
    cols = ["id", "equipamento_cliente", "posicao", "titulo", "arquivo"]
    n = inserir(dst, "documentos_equipamento_cliente", cols, rows)
    resetar_sequence(dst, "documentos_equipamento_cliente")
    if ignorados:
        rel.warn("documentos_equipamento_cliente", f"{ignorados} ignorados")
    rel.ok("documentos_equipamento_cliente", n)


def migrar_fotos(src, dst, rel):
    src.execute("SELECT id, cliente, codigo, cor, tipo, posicao, arquivo, legenda FROM hsfotos")
    dst.execute("SELECT id FROM clientes")
    clientes = {r[0] for r in dst.fetchall()}
    rows = []
    for r in src.fetchall():
        cliente = r[1] if r[1] and r[1] in clientes else None
        rows.append((r[0], cliente, r[2], r[3], strip_or_none(r[4]), r[5], r[6], r[7]))
    cols = ["id", "cliente", "codigo", "cor", "tipo", "posicao", "arquivo", "legenda"]
    n = inserir(dst, "fotos", cols, rows)
    resetar_sequence(dst, "fotos")
    rel.ok("fotos", n)


def migrar_links(src, dst, rel):
    src.execute("SELECT id, item, posicao, titulo, arquivo FROM hslinks")
    dst.execute("SELECT id FROM equipamentos")
    equips = {r[0] for r in dst.fetchall()}
    rows, ignorados = [], 0
    for r in src.fetchall():
        equip = r[1] if r[1] and r[1] in equips else None
        if equip is None:
            ignorados += 1
            continue
        rows.append((r[0], equip, r[2], r[3], r[4]))
    cols = ["id", "item", "posicao", "titulo", "arquivo"]
    n = inserir(dst, "links", cols, rows)
    resetar_sequence(dst, "links")
    if ignorados:
        rel.warn("links", f"{ignorados} ignorados por equipamento inexistente")
    rel.ok("links", n)


def migrar_mensagens(src, dst, rel):
    src.execute("SELECT id, data, cliente, titulo, texto FROM hsmensagens")
    dst.execute("SELECT id FROM clientes")
    clientes = {r[0] for r in dst.fetchall()}
    rows, ignorados = [], 0
    for r in src.fetchall():
        if r[2] not in clientes:
            ignorados += 1
            continue
        rows.append((r[0], r[2], r[1], r[3], r[4]))
    cols = ["id", "cliente", "data", "titulo", "texto"]
    n = inserir(dst, "mensagens", cols, rows)
    resetar_sequence(dst, "mensagens")
    if ignorados:
        rel.warn("mensagens", f"{ignorados} ignorados por cliente inexistente")
    rel.ok("mensagens", n)


def migrar_envios(src, dst, rel):
    STATUS_MAP = {'P': 'P', 'E': 'E', 'F': 'F', 'R': 'F'}
    src.execute("""
        SELECT id, tipo, modo, datain, objetivo, assunto, texto, programado, realizar, status
        FROM hsenvios
    """)
    rows = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8],
             STATUS_MAP.get(str(r[9]).strip() if r[9] else 'P', 'P'))
            for r in src.fetchall()]
    cols = ["id", "tipo", "modo", "datain", "objetivo", "assunto",
            "texto", "programado", "realizar", "status"]
    n = inserir(dst, "envios", cols, rows)
    resetar_sequence(dst, "envios")
    rel.ok("envios", n)


# ─── Orquestrador ────────────────────────────────────────────────────────────

ETAPAS = [
    ("Nível 0 — Referências",   [migrar_setores, migrar_marcas, migrar_grupos, migrar_fases,
                                  migrar_fases_lote, migrar_tipos_calibragem, migrar_tipos_teste,
                                  migrar_programas, migrar_acesso, migrar_checklist_templates,
                                  migrar_caixas]),
    ("Nível 1 — Clientes/Usuários", [migrar_categorias, migrar_clientes, migrar_usuarios,
                                      migrar_menus_sistema]),
    ("Nível 2 — Equipamentos/Funcs", [migrar_equipamentos, migrar_usuarios_cliente,
                                       migrar_funcionarios]),
    ("Nível 3 — Equip. Cliente",  [migrar_equipamentos_cliente]),
    ("Nível 4 — Ordens",          [migrar_ordens]),
    ("Nível 5 — Dependentes",     [migrar_os_atual, migrar_logs_os, migrar_certificados,
                                    migrar_checklist_respostas, migrar_lotes,
                                    migrar_historico_equipamentos, migrar_testes,
                                    migrar_testes_detalhes, migrar_documentos,
                                    migrar_documentos_equipamento_cliente,
                                    migrar_fotos, migrar_links, migrar_mensagens,
                                    migrar_envios]),
]


def main():
    print("Conectando...")
    con_src = psycopg2.connect(**ORIGEM)
    con_dst = psycopg2.connect(**DESTINO)
    con_src.autocommit = True
    con_dst.autocommit = False

    cur_src = con_src.cursor()
    cur_dst = con_dst.cursor()
    rel = Relatorio()

    try:
        for titulo, funcoes in ETAPAS:
            print(f"\n--- {titulo} ---")
            for fn in funcoes:
                try:
                    fn(cur_src, cur_dst, rel)
                    con_dst.commit()
                except Exception as e:
                    con_dst.rollback()
                    rel.erro(fn.__name__, str(e))
    finally:
        cur_src.close()
        cur_dst.close()
        con_src.close()
        con_dst.close()

    rel.resumo()


if __name__ == "__main__":
    main()
