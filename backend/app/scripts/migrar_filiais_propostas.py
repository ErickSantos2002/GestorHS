"""Leva as propostas antigas para o modelo de Empresas (set/2026).

Duas coisas, na mesma rodada:

1. CONGELA a copia do destinatario (`propostas.destinatario`) de toda proposta
   que ainda nao tem, com o que o PDF sempre mostrou: cadastro do cliente com o
   `cliente_override` por cima (`destinatario_legado`).
2. CRIA as filiais escondidas nos overrides: proposta cujo override traz um
   documento diferente do cliente vira destinatario Empresa, com matriz = o
   cliente da proposta. O mesmo documento em varias propostas gera UMA Empresa.

    python -m app.scripts.migrar_filiais_propostas            # so simula
    python -m app.scripts.migrar_filiais_propostas --aplicar  # grava

A Empresa nasce SO com o que o override trazia — nada vem do cadastro da
matriz, para nao botar endereco da matriz na filial.

RECUSA (lista no resumo e deixa a proposta so congelada) quando o documento ja
e' de um Cliente — decidir a mao —, quando o documento e' invalido e quando o
override nao tem nome (`empresas.nome` e' NOT NULL).

Idempotente: proposta congelada nao e' congelada de novo, proposta ligada nao
e' ligada de novo, e o documento que ja virou Empresa e' reaproveitado.
"""
import argparse
from dataclasses import dataclass, field

from app.core.empresa import DocumentoInvalido, destinatario_legado, normalizar_documento, so_digitos
from app.models import Cliente, Empresa, Proposta
from app.models.database import SessionLocal


@dataclass
class Plano:
    congelar: list[int] = field(default_factory=list)
    criar: dict[str, int] = field(default_factory=dict)
    reaproveitar: dict[str, int] = field(default_factory=dict)
    recusados: dict[str, tuple[int, str]] = field(default_factory=dict)
    invalidos: dict[int, str] = field(default_factory=dict)
    ligar: dict[int, str] = field(default_factory=dict)


def _documento_do_override(p: Proposta) -> str:
    return so_digitos((p.cliente_override or {}).get("documento"))


def _eh_filial(p: Proposta) -> bool:
    doc = _documento_do_override(p)
    if not doc or p.empresa is not None:
        return False
    cli = p.cliente_rel
    return cli is None or doc != (cli.cgc or cli.cpf or "")


def planejar(db) -> Plano:
    plano = Plano()
    propostas = db.query(Proposta).order_by(Proposta.id).all()
    plano.congelar = [p.id for p in propostas if p.destinatario is None]

    for p in propostas:
        if not _eh_filial(p):
            continue
        doc = _documento_do_override(p)
        try:
            normalizar_documento(doc)
        except DocumentoInvalido as e:
            plano.invalidos[p.id] = f"documento {doc}: {e}"
            continue
        if not str((p.cliente_override or {}).get("nome") or "").strip():
            plano.invalidos[p.id] = f"documento {doc}: override sem nome"
            continue
        if doc in plano.recusados:
            continue
        dono = db.query(Cliente).filter((Cliente.cgc == doc) | (Cliente.cpf == doc)).first()
        if dono is not None:
            plano.recusados[doc] = (dono.id, dono.nome)
            continue
        existente = db.query(Empresa).filter((Empresa.cgc == doc) | (Empresa.cpf == doc)).first()
        if existente is not None:
            plano.reaproveitar[doc] = existente.id
        elif doc not in plano.criar:
            plano.criar[doc] = p.id
        plano.ligar[p.id] = doc
    return plano


def _texto(v, limite=None):
    s = str(v or "").strip()
    return (s[:limite] if limite else s) or None


def _empresa_do_override(p: Proposta, doc: str) -> Empresa:
    ov = p.cliente_override or {}
    cgc, cpf = normalizar_documento(doc)
    cep = so_digitos(ov.get("cep"))
    return Empresa(
        cliente=p.cliente, nome=_texto(ov.get("nome"), 100), cgc=cgc, cpf=cpf,
        endereco=_texto(ov.get("endereco"), 100), municipio=_texto(ov.get("municipio"), 100),
        estado=(_texto(ov.get("estado"), 2) or "").upper() or None,
        cep=cep if len(cep) == 8 else None,
        email=_texto(ov.get("email"), 100), telefone=_texto(ov.get("telefone"), 50),
    )


def aplicar(db, plano: Plano) -> dict[str, int]:
    ids_empresa = dict(plano.reaproveitar)
    for doc, proposta_id in plano.criar.items():
        empresa = _empresa_do_override(db.get(Proposta, proposta_id), doc)
        db.add(empresa)
        db.flush()
        ids_empresa[doc] = empresa.id

    for proposta_id in plano.congelar:
        p = db.get(Proposta, proposta_id)
        p.destinatario = destinatario_legado(p.cliente_rel, p.cliente_override)

    for proposta_id, doc in plano.ligar.items():
        p = db.get(Proposta, proposta_id)
        copia = destinatario_legado(p.cliente_rel, p.cliente_override)
        matriz = p.cliente_rel
        copia.update({"tipo": "empresa", "id": ids_empresa[doc],
                      "matriz_id": matriz.id if matriz else None,
                      "matriz_nome": matriz.nome if matriz else None})
        # o legado cai no cadastro da matriz para campo vazio; na filial, vazio fica vazio
        ov = p.cliente_override or {}
        for campo in ("endereco", "municipio", "estado", "email", "telefone", "cep"):
            if not str(ov.get(campo) or "").strip():
                copia[campo] = None
        p.empresa = ids_empresa[doc]
        p.destinatario = copia

    db.commit()
    return {
        "empresas_criadas": len(plano.criar),
        "empresas_reaproveitadas": len(plano.reaproveitar),
        "propostas_congeladas": len(plano.congelar),
        "propostas_ligadas": len(plano.ligar),
    }


def _imprimir(plano: Plano) -> None:
    print(f"Propostas a congelar: {len(plano.congelar)}")
    print(f"Empresas a criar: {len(plano.criar)}")
    for doc, pid in plano.criar.items():
        print(f"  + {doc} (a partir da proposta id {pid})")
    print(f"Empresas reaproveitadas: {len(plano.reaproveitar)}")
    for doc, eid in plano.reaproveitar.items():
        print(f"  = {doc} -> empresa {eid}")
    print(f"Propostas a ligar: {len(plano.ligar)}")
    if plano.recusados:
        print("RECUSADOS (documento ja e' de um Cliente — decidir a mao):")
        for doc, (cid, nome) in plano.recusados.items():
            print(f"  ! {doc} -> cliente {cid} {nome}")
    if plano.invalidos:
        print("INVALIDOS (ficam so congelados):")
        for pid, motivo in plano.invalidos.items():
            print(f"  ? proposta id {pid}: {motivo}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aplicar", action="store_true", help="grava (padrao: so simula)")
    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        plano = planejar(db)
        _imprimir(plano)
        if not args.aplicar:
            print("\nSIMULACAO — nada gravado. Rode com --aplicar para gravar.")
            return
        print("\nGravado:", aplicar(db, plano))
    finally:
        db.close()


if __name__ == "__main__":
    main()
