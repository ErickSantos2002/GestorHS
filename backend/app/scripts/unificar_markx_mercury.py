"""Unifica os cadastros duplicados de Mark-X e Mercury num so por aparelho.

O catalogo tinha DOIS registros para o mesmo aparelho, separados apenas pela
impressora — uma distincao comercial que o laboratorio nao faz e que o
certificado nao enxerga: os modelos de certificado dos dois pares sao
byte-a-byte identicos e trazem o modelo FIXO no HTML ("Modelo: Mark-X",
"Modelo: Mercury"), sem o token `[modelo]`.

    id 3  Bafometro Mark X - Plus                       <- sobrevive como "Mark-X"
    id 1  Bafometro Mark X - Plus - COM IMPRESSORA      <- absorvido
    id 4  Bafometro Mercury                             <- sobrevive como "Mercury"
    id 29 Mercury com impressora sem fio - Bluetooth    <- absorvido

Sobrevive o cadastro com a frota maior, para mover o minimo de linhas. O nome
final e o que o certificado ja imprime — era a divergencia a corrigir.

EFEITO NO RELATORIO DE MANUTENCAO: o modelo unico de manutencao usa `[modelo]`,
que vem de `equipamentos.descricao`. Depois disto ele imprime "Mark-X" em vez de
"Bafometro Mark X - Plus", batendo com o certificado. Documento ja gerado nao
muda (fica congelado em `os_certificados`) e resumo de manutencao ja salvo
tambem nao — o modal congela texto que difere da composicao automatica.

SEGURANCA: se o modelo de certificado do absorvido DIVERGIR do que sobrevive, o
par e' recusado inteiro em vez de apagar um template diferente no escuro.

QUATRO FKs referenciam `equipamentos.id` — `equipamentos_cliente`, `certificados`
e as legadas `documentos` e `links` (ver LEGADAS). Esquecer qualquer uma faz o
DELETE do cadastro morrer na FK, e a transacao inteira volta atras.

Idempotente: os ids absorvidos deixam de existir, entao rodar de novo nao acha
mais nada.

    python -m app.scripts.unificar_markx_mercury              # so simula
    python -m app.scripts.unificar_markx_mercury --aplicar    # grava
"""
import argparse

from sqlalchemy import inspect, text

from app.models import CertificadoModelo, Equipamento, EquipamentoCliente
from app.models.database import SessionLocal

# (id que sobrevive, nome final, ids absorvidos)
UNIFICACOES = (
    (3, "Mark-X", (1,)),
    (4, "Mercury", (29,)),
)

# Tabelas LEGADAS do sistema antigo que referenciam `equipamentos.id` por FK de
# verdade e nao tem model no GestorHS — nada aqui as le. Precisam ser tratadas
# ainda assim: sem isso o DELETE do cadastro morre em
# `documentos_equipamento_fkey`. Levantadas em `pg_constraint`, nao no
# `information_schema` (uma consulta mal montada la devolve vazio e da a falsa
# impressao de que nao existe FK).
#
# As linhas sao MOVIDAS para o sobrevivente, nunca apagadas: os PDFs vivem no
# volume do EasyPanel e nao ha como conferir daqui se sao o mesmo arquivo.
# (nome_da_tabela, coluna_que_aponta_para_equipamentos, coluna_de_titulo)
LEGADAS = (
    ("documentos", "equipamento", "titulo"),
    ("links", "item", "titulo"),
)


def _tabelas_legadas_presentes(db):
    """Só as que existem de fato — o banco de teste (SQLite pelos models) não as tem."""
    insp = inspect(db.bind)
    return [t for t in LEGADAS if insp.has_table(t[0])]


def _modelos_por_tipo(db, equipamento_id):
    return {
        m.tipo: m
        for m in db.query(CertificadoModelo)
        .filter(CertificadoModelo.equipamento == equipamento_id)
        .order_by(CertificadoModelo.id)
        .all()
    }


def planejar(db, sobrevivente_id, nome_final, absorvidos_ids):
    """Monta o plano de um par sem gravar nada.

    Devolve (plano, recusas). `recusas` nao vazio = nao aplicar este par.
    """
    plano = {
        "sobrevivente": db.get(Equipamento, sobrevivente_id),
        "nome_final": nome_final,
        "absorvidos": [],
        "mover_frota": [],       # (absorvido_id, quantos)
        "mover_modelos": [],     # CertificadoModelo a reapontar
        "apagar_modelos": [],    # CertificadoModelo redundante (texto identico)
        "mover_legadas": [],     # (tabela, coluna, absorvido_id, quantos)
        "titulos_repetidos": [], # (tabela, titulo) que o sobrevivente ja tem
    }
    recusas = []
    if plano["sobrevivente"] is None:
        recusas.append(f"o cadastro que deveria sobreviver (#{sobrevivente_id}) nao existe")
        return plano, recusas

    do_sobrevivente = _modelos_por_tipo(db, sobrevivente_id)

    for aid in absorvidos_ids:
        absorvido = db.get(Equipamento, aid)
        if absorvido is None:
            continue                      # ja unificado numa rodada anterior
        plano["absorvidos"].append(absorvido)
        plano["mover_frota"].append((
            aid,
            db.query(EquipamentoCliente)
            .filter(EquipamentoCliente.equipamento == aid).count(),
        ))
        for tipo, modelo in _modelos_por_tipo(db, aid).items():
            igual = do_sobrevivente.get(tipo)
            if igual is None:
                plano["mover_modelos"].append(modelo)
            elif (modelo.texto or "") == (igual.texto or ""):
                plano["apagar_modelos"].append(modelo)
            else:
                recusas.append(
                    f"modelo de certificado tipo '{tipo}' do #{aid} DIFERE do #{sobrevivente_id} "
                    f"(cert #{modelo.id} vs #{igual.id}) — decida a mao antes"
                )

        for tabela, coluna, col_titulo in _tabelas_legadas_presentes(db):
            titulos = [
                t for (t,) in db.execute(
                    text(f"select {col_titulo} from {tabela} where {coluna} = :eq"),
                    {"eq": aid},
                ).all()
            ]
            if not titulos:
                continue
            plano["mover_legadas"].append((tabela, coluna, aid, len(titulos)))
            jah = {
                t for (t,) in db.execute(
                    text(f"select {col_titulo} from {tabela} where {coluna} = :eq"),
                    {"eq": sobrevivente_id},
                ).all()
            }
            plano["titulos_repetidos"].extend(
                (tabela, t) for t in titulos if t in jah
            )
    return plano, recusas


def _descrever(plano) -> None:
    s = plano["sobrevivente"]
    print(f"SOBREVIVE  #{s.id}  \"{s.descricao}\"  ->  \"{plano['nome_final']}\"")
    for absorvido, (aid, quantos) in zip(plano["absorvidos"], plano["mover_frota"]):
        print(f"  absorve  #{aid}  \"{absorvido.descricao}\"")
        print(f"     frota: {quantos} aparelhos passam a apontar para #{s.id}")
    for m in plano["mover_modelos"]:
        print(f"     modelo de certificado #{m.id} (tipo {m.tipo}) reaponta para #{s.id}")
    for m in plano["apagar_modelos"]:
        print(f"     modelo de certificado #{m.id} (tipo {m.tipo}) APAGADO — identico ao que fica")
    for tabela, _coluna, aid, quantos in plano["mover_legadas"]:
        print(f"     {tabela}: {quantos} linha(s) do #{aid} reapontam para #{s.id} (tabela legada)")
    for tabela, titulo in plano["titulos_repetidos"]:
        print(f"     ATENCAO {tabela}: \"{titulo}\" ja existe no #{s.id} — vai ficar repetido")
    for absorvido in plano["absorvidos"]:
        print(f"     cadastro #{absorvido.id} APAGADO")


def aplicar(db, plano) -> int:
    s = plano["sobrevivente"]
    movidos = 0
    for aid, _ in plano["mover_frota"]:
        movidos += (
            db.query(EquipamentoCliente)
            .filter(EquipamentoCliente.equipamento == aid)
            .update({EquipamentoCliente.equipamento: s.id}, synchronize_session=False)
        )
    for m in plano["mover_modelos"]:
        m.equipamento = s.id
    for m in plano["apagar_modelos"]:
        db.delete(m)
    for tabela, coluna, aid, _ in plano["mover_legadas"]:
        db.execute(
            text(f"update {tabela} set {coluna} = :novo where {coluna} = :antigo"),
            {"novo": s.id, "antigo": aid},
        )
    s.descricao = plano["nome_final"]
    for absorvido in plano["absorvidos"]:
        db.delete(absorvido)
    return movidos


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true", help="grava de fato (sem isso, so simula)")
    args = p.parse_args()

    db = SessionLocal()
    try:
        planos, houve_recusa = [], False
        for sobrevivente_id, nome_final, absorvidos_ids in UNIFICACOES:
            plano, recusas = planejar(db, sobrevivente_id, nome_final, absorvidos_ids)
            if recusas:
                houve_recusa = True
                print(f"RECUSADO  #{sobrevivente_id} / {nome_final}:")
                for r in recusas:
                    print(f"     {r}")
                print()
                continue
            if not plano["absorvidos"]:
                print(f"NADA A FAZER  #{sobrevivente_id} / {nome_final}: ja unificado")
                print()
                continue
            _descrever(plano)
            print()
            planos.append(plano)

        if houve_recusa:
            print("Ha par recusado — nada foi gravado. Resolva a divergencia primeiro.")
            return
        if not planos:
            print("(nada a unificar)")
            return
        if not args.aplicar:
            print("(simulacao — rode com --aplicar para gravar)")
            return

        total = sum(aplicar(db, plano) for plano in planos)
        db.commit()
        print(f"gravado: {len(planos)} pares unificados, {total} aparelhos movidos")
    finally:
        db.close()


if __name__ == "__main__":
    main()
