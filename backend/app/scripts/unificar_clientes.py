"""Unifica cadastros duplicados de cliente — o mesmo CNPJ cadastrado duas vezes.

Duplicado NAO e' matriz e filial: essas tem CNPJs diferentes (raiz igual, ordem
diferente) e sao clientes separados de verdade. Duplicado e' o mesmo `cgc`
repetido, com a frota do cliente dividida entre os dois cadastros — na tela do
cliente aparecem cinco aparelhos quando ele tem dez, e o alerta de vencimento
sai partido em dois.

    python -m app.scripts.unificar_clientes --cgc 05571228001127            # so simula
    python -m app.scripts.unificar_clientes --cgc 05571228001127 --aplicar  # grava
    python -m app.scripts.unificar_clientes --manter 1059 --absorver 1064   # par explicito

Sem `--manter`, quem sobrevive e' decidido por `escolher_sobrevivente`: caixa
viva primeiro, depois numero de OS, depois o id menor.

O cadastro absorvido e' APAGADO, nao desativado: desativar deixaria um cliente
inativo com CNPJ igual ao ativo, que e' exatamente a ambiguidade que estamos
tirando do caminho. Nada se perde — toda linha que apontava para ele passa a
apontar para o que fica, antes do DELETE.

RECUSA em vez de adivinhar quando: os cadastros divergem em algum campo
(`--aceitar-divergencia` manda ficar com o do sobrevivente); os dois tem usuario
de portal com o mesmo login (a unica de `usuarios_cliente` so estouraria no meio
do UPDATE); ou o banco tem FK para `clientes` fora de REFERENCIAS.

Idempotente: o id absorvido deixa de existir, entao rodar de novo nao acha mais nada.
"""
import argparse
import re

from sqlalchemy import inspect, text

from app.core.unificacao_cliente import divergencias, escolher_sobrevivente
from app.scripts.renumerar_patrimonios import aplicar as aplicar_patrimonio
from app.scripts.renumerar_patrimonios import planejar as planejar_patrimonio
from app.models import Cliente
from app.models.database import SessionLocal

# TODA coluna que aponta para `clientes.id`. Esquecer uma deixa linha orfa
# apontando para cadastro apagado (ou mata o DELETE na FK, no melhor caso).
#
# Levantada em `pg_constraint` — uma consulta ao `information_schema` juntando
# `constraint_column_usage` devolve vazio aqui e da a falsa impressao de que nao
# existe FK nenhuma. `_conferir_cobertura` refaz esse levantamento no banco real
# a cada rodada, para que uma tabela nova nao passe despercebida.
#
# `mensagens`, `testes` e `testes_detalhes` sao LEGADAS do sistema antigo: tem FK
# de verdade no Postgres mas nao tem model aqui, entao nao existem no SQLite dos
# testes — dai o `has_table` antes de tocar nelas.
REFERENCIAS = (
    ("caixas", "cliente_principal"),
    ("equipamentos_cliente", "cliente"),
    ("fotos", "cliente"),
    ("funcionarios", "cliente"),
    ("mensagens", "cliente"),
    ("ordens", "cliente"),
    ("propostas", "cliente"),
    ("solicitacoes", "cliente"),
    ("testes", "cliente"),
    ("testes_detalhes", "cliente"),
    ("transferencias_equipamento", "de_cliente"),
    ("transferencias_equipamento", "para_cliente"),
    ("usuarios_cliente", "cliente"),
)

_SO_DIGITOS = re.compile(r"[^0-9]")


def _referencias_presentes(db):
    insp = inspect(db.bind)
    return [(t, c) for t, c in REFERENCIAS if insp.has_table(t)]


def _contar(db, tabela, coluna, cliente_id) -> int:
    return db.execute(
        text(f"select count(*) from {tabela} where {coluna} = :cli"),
        {"cli": cliente_id},
    ).scalar_one()


def _conferir_cobertura(db) -> list[str]:
    """FK para `clientes` que o script nao conhece — so da para perguntar no Postgres."""
    if db.bind.dialect.name != "postgresql":
        return []
    achadas = db.execute(text("""
        select src.relname,
               (select a.attname from unnest(con.conkey) as k(attnum)
                  join pg_attribute a on a.attrelid = con.conrelid and a.attnum = k.attnum
                limit 1)
          from pg_constraint con
          join pg_class src on src.oid = con.conrelid
          join pg_class tgt on tgt.oid = con.confrelid
         where con.contype = 'f' and tgt.relname = 'clientes'
    """)).all()
    faltando = {(t, c) for t, c in achadas} - set(REFERENCIAS)
    return [f"o banco tem FK para clientes em {t}.{c}, fora de REFERENCIAS — "
            f"adicione a coluna antes de rodar" for t, c in sorted(faltando)]


def _logins_repetidos(db, fica_id, vai_id) -> list[str]:
    """`usuarios_cliente` e' unica em (cliente, login): dois portais com o mesmo
    login viram o mesmo par no UPDATE e estouram no meio da transacao."""
    if not inspect(db.bind).has_table("usuarios_cliente"):
        return []
    return [l for (l,) in db.execute(text("""
        select u.login from usuarios_cliente u
         where u.cliente = :vai
           and exists (select 1 from usuarios_cliente v
                        where v.cliente = :fica and v.login = u.login)
    """), {"vai": vai_id, "fica": fica_id}).all()]


# `regexp_replace` nao existe no SQLite dos testes; `replace` aninhado cobre a
# mascara de CNPJ dos dois lados sem precisar de extensao.
_SQL_CGC_LIMPO = {
    "postgresql": "regexp_replace(coalesce(cgc,''), '[^0-9]', '', 'g')",
}
_SQL_CGC_LIMPO_PADRAO = (
    "replace(replace(replace(replace(coalesce(cgc,''), '.', ''), '/', ''), '-', ''), ' ', '')"
)


def localizar_por_cgc(db, cgc: str) -> list[Cliente]:
    """Cadastros com esse CNPJ, com ou sem mascara nos dois lados da comparacao."""
    limpo = _SO_DIGITOS.sub("", cgc or "")
    if not limpo:
        return []
    expr = _SQL_CGC_LIMPO.get(db.bind.dialect.name, _SQL_CGC_LIMPO_PADRAO)
    ids = db.execute(
        text(f"select id from clientes where {expr} = :cgc order by id"),
        {"cgc": limpo},
    ).scalars().all()
    return [db.get(Cliente, i) for i in ids]


def pesos(db, clientes) -> list[dict]:
    """Quanto cada cadastro 'pesa' para a escolha de quem sobrevive."""
    return [
        {"id": c.id,
         "caixas": _contar(db, "caixas", "cliente_principal", c.id),
         "ordens": _contar(db, "ordens", "cliente", c.id)}
        for c in clientes
    ]


def planejar(db, manter_id: int, absorver_ids, aceitar_divergencia: bool = False):
    """Monta o plano sem gravar nada. `recusas` nao vazio = nao aplicar."""
    plano = {
        "sobrevivente": db.get(Cliente, manter_id),
        "absorvidos": [],
        "mover": [],            # (tabela, coluna, absorvido_id, quantas linhas)
        "divergencias": [],     # (absorvido_id, campo, do_que_fica, do_que_vai)
        "patrimonios_repetidos": [],
        "frota_absorvida": [],  # ids de equipamentos_cliente que mudam de dono
    }
    recusas = _conferir_cobertura(db)
    if plano["sobrevivente"] is None:
        recusas.append(f"o cadastro que deveria sobreviver (#{manter_id}) nao existe")
        return plano, recusas

    referencias = _referencias_presentes(db)
    for aid in absorver_ids:
        if aid == manter_id:
            recusas.append(f"#{aid} nao pode absorver a si mesmo")
            continue
        absorvido = db.get(Cliente, aid)
        if absorvido is None:
            continue            # ja unificado numa rodada anterior
        plano["absorvidos"].append(absorvido)

        for campo, a, b in divergencias(plano["sobrevivente"], absorvido):
            plano["divergencias"].append((aid, campo, a, b))
            if not aceitar_divergencia:
                recusas.append(
                    f"#{aid} diverge de #{manter_id} em '{campo}': "
                    f"{a!r} vs {b!r} — confira se e' mesmo o mesmo cliente"
                )
        for login in _logins_repetidos(db, manter_id, aid):
            recusas.append(
                f"os dois cadastros tem usuario de portal com o login '{login}' — "
                f"apague ou renomeie um antes"
            )
        for tabela, coluna in referencias:
            quantos = _contar(db, tabela, coluna, aid)
            if quantos:
                plano["mover"].append((tabela, coluna, aid, quantos))
        plano["patrimonios_repetidos"].extend(_patrimonios_repetidos(db, manter_id, aid))
        plano["frota_absorvida"].extend(_frota_de(db, aid))

    return plano, recusas


def _frota_de(db, cliente_id) -> list[int]:
    """Aparelhos do absorvido — sao eles que cedem o patrimonio na renumeracao."""
    if not inspect(db.bind).has_table("equipamentos_cliente"):
        return []
    return list(db.execute(
        text("select id from equipamentos_cliente where cliente = :cli order by id"),
        {"cli": cliente_id},
    ).scalars().all())


def _patrimonios_repetidos(db, fica_id, vai_id) -> list[str]:
    """Aviso, nao recusa: `patrimonio` e' etiqueta do cliente e sai no certificado.

    A carga do legado numerou 1..N por cadastro, entao o duplicado quase sempre
    repete os numeros do que fica. Renumerar a mao e' decisao do cliente — o
    script nao mexe.
    """
    if not inspect(db.bind).has_table("equipamentos_cliente"):
        return []
    return [p for (p,) in db.execute(text("""
        select ec.patrimonio from equipamentos_cliente ec
         where ec.cliente = :vai and coalesce(ec.patrimonio,'') <> ''
           and exists (select 1 from equipamentos_cliente o
                        where o.cliente = :fica and o.patrimonio = ec.patrimonio)
         order by ec.patrimonio
    """), {"vai": vai_id, "fica": fica_id}).all()]


def descrever(plano) -> None:
    s = plano["sobrevivente"]
    print(f'SOBREVIVE  #{s.id}  "{s.nome}"  CNPJ {s.cgc}')
    for absorvido in plano["absorvidos"]:
        print(f'  absorve  #{absorvido.id}  "{absorvido.nome}"')
        for tabela, coluna, aid, quantos in plano["mover"]:
            if aid == absorvido.id:
                print(f"     {tabela}.{coluna}: {quantos} linha(s) passam para #{s.id}")
        print(f"     cadastro #{absorvido.id} APAGADO")
    for aid, campo, a, b in plano["divergencias"]:
        print(f"     DIVERGENCIA #{aid} '{campo}': fica {a!r}, some {b!r}")
    for p in plano["patrimonios_repetidos"]:
        print(f'     ATENCAO patrimonio "{p}" vai ficar repetido na frota de #{s.id}'
              ' — resolva com --renumerar-patrimonios')


def aplicar(db, plano, renumerar_patrimonio: bool = False) -> int:
    """Reaponta tudo e apaga os absorvidos. Devolve quantas linhas mudaram de dono.

    Com `renumerar_patrimonio`, resolve na sequencia o patrimonio repetido que a
    juncao acabou de criar — as duas numeracoes comecavam em 1. Quem cede e'
    sempre o aparelho que veio do absorvido; a etiqueta que o cliente ja conhece
    no cadastro que fica nao anda.
    """
    s = plano["sobrevivente"]
    movidas = 0
    for tabela, coluna, aid, _ in plano["mover"]:
        movidas += db.execute(
            text(f"update {tabela} set {coluna} = :novo where {coluna} = :antigo"),
            {"novo": s.id, "antigo": aid},
        ).rowcount
    for absorvido in plano["absorvidos"]:
        db.delete(absorvido)
    if renumerar_patrimonio and plano["frota_absorvida"]:
        db.flush()          # a frota precisa ja estar sob o sobrevivente
        _, mudancas, _ = planejar_patrimonio(db, s.id, set(plano["frota_absorvida"]))
        for ec_id, (serie, de, para) in sorted(mudancas.items()):
            print(f"     aparelho #{ec_id} ({serie}): patrimonio {de} -> {para}")
        aplicar_patrimonio(db, mudancas)
    return movidas


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cgc", help="CNPJ duplicado, com ou sem mascara")
    p.add_argument("--manter", type=int, help="id do cadastro que sobrevive")
    p.add_argument("--absorver", help="ids a absorver, separados por virgula")
    p.add_argument("--aceitar-divergencia", action="store_true",
                   help="unifica mesmo com campos diferentes, ficando com os do sobrevivente")
    p.add_argument("--renumerar-patrimonios", action="store_true",
                   help="resolve o patrimonio repetido que a juncao cria (so os absorvidos andam)")
    p.add_argument("--aplicar", action="store_true", help="grava de fato (sem isso, so simula)")
    args = p.parse_args()

    db = SessionLocal()
    try:
        if args.cgc:
            achados = localizar_por_cgc(db, args.cgc)
            if len(achados) < 2:
                print(f"CNPJ {args.cgc}: {len(achados)} cadastro(s) — nada a unificar")
                return
            manter_id = args.manter or escolher_sobrevivente(pesos(db, achados))
            absorver = [c.id for c in achados if c.id != manter_id]
        elif args.manter and args.absorver:
            manter_id = args.manter
            absorver = [int(x) for x in args.absorver.split(",") if x.strip()]
        else:
            p.error("informe --cgc, ou --manter junto com --absorver")

        plano, recusas = planejar(db, manter_id, absorver, args.aceitar_divergencia)
        if recusas:
            print("RECUSADO — nada foi gravado:")
            for r in recusas:
                print(f"     {r}")
            return
        if not plano["absorvidos"]:
            print("NADA A FAZER: ja unificado")
            return

        descrever(plano)
        print()
        if not args.aplicar:
            print("(simulacao — rode com --aplicar para gravar)")
            return

        movidas = aplicar(db, plano, args.renumerar_patrimonios)
        db.commit()
        print(f"gravado: {len(plano['absorvidos'])} cadastro(s) absorvido(s), "
              f"{movidas} linha(s) reapontada(s) para #{manter_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
