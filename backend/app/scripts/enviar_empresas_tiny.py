"""Acerta no Tiny as Empresas que ja existem no GestorHS.

Para cada Empresa ativa sem `tiny_id`: pesquisa o documento no Tiny e ADOTA o
contato que existir; so cria o que faltar. Na base de 16/09/2026, 9 das 10
filiais ja estavam la — sem a pesquisa, o primeiro uso criaria 9 duplicados.

    python -m app.scripts.enviar_empresas_tiny                 # so simula
    python -m app.scripts.enviar_empresas_tiny --aplicar       # grava
    python -m app.scripts.enviar_empresas_tiny --aplicar --limite 5

O limite desta conta e' de 20 chamadas por minuto (cabecalho `x-limit-api`):
cada empresa gasta duas chamadas e a conta permite 20 por minuto, dai ~7s entre
elas. Levando bloqueio (codigo 6/11), o script PARA e diz quantas faltaram — e'
so rodar de novo depois.

Idempotente: empresa com `tiny_id` nao e' tocada.
"""
import argparse
import time
from datetime import datetime, timezone
from typing import Optional

from app.core import tiny
from app.integrations import tiny_client
from app.models import Empresa
from app.models.database import SessionLocal

PAUSA_PADRAO = 7.0


def planejar(db, limite: Optional[int] = None) -> list:
    """Empresas ativas ainda sem contato no Tiny, em ordem de id."""
    query = (db.query(Empresa)
             .filter(Empresa.ativo.is_(True), Empresa.tiny_id.is_(None))
             .order_by(Empresa.id))
    if limite:
        query = query.limit(limite)
    return query.all()


def _marcar(db, empresa, *, status: str, tiny_id=None, erro=None) -> None:
    if tiny_id is not None:
        empresa.tiny_id = tiny_id
    empresa.tiny_status = status
    empresa.tiny_erro = (erro or "")[:255] or None
    empresa.tiny_em = datetime.now(timezone.utc)
    db.commit()


def processar(db, empresas, *, aplicar: bool, pausa: float = PAUSA_PADRAO) -> dict:
    resumo = {"candidatas": len(empresas), "adotadas": 0, "criadas": 0,
              "erros": 0, "interrompido": False}
    if not aplicar:
        for e in empresas:
            print(f"  ? {e.id:5} {e.nome[:40]:40} {e.cgc or e.cpf}")
        return resumo

    for i, empresa in enumerate(empresas):
        if i:
            time.sleep(pausa)
        documento = empresa.cgc or empresa.cpf or ""
        achado = tiny_client.pesquisar_contato(documento) if documento else tiny.Resultado(ok=False)
        if achado.ok and achado.id:
            _marcar(db, empresa, status="enviada", tiny_id=achado.id)
            resumo["adotadas"] += 1
            print(f"  = {empresa.id:5} {empresa.nome[:40]:40} adotou contato {achado.id}")
            continue
        if achado.deve_tentar_de_novo:
            resumo["interrompido"] = True
            break

        resultado = tiny_client.incluir_contato(tiny.contato_para_criar(empresa))
        if resultado.ok:
            _marcar(db, empresa, status="enviada", tiny_id=resultado.id)
            resumo["criadas"] += 1
            print(f"  + {empresa.id:5} {empresa.nome[:40]:40} criou contato {resultado.id}")
        elif resultado.deve_tentar_de_novo:
            resumo["interrompido"] = True
            break
        else:
            _marcar(db, empresa, status="erro", erro=resultado.mensagem)
            resumo["erros"] += 1
            print(f"  ! {empresa.id:5} {empresa.nome[:40]:40} {resultado.mensagem}")

    if resumo["interrompido"]:
        feitas = resumo["adotadas"] + resumo["criadas"] + resumo["erros"]
        print(f"\nPAROU: o Tiny bloqueou por excesso de chamadas. "
              f"{resumo['candidatas'] - feitas} empresa(s) ficaram para a proxima rodada.")
    return resumo


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aplicar", action="store_true", help="grava (padrao: so simula)")
    parser.add_argument("--limite", type=int, default=None, help="processa no maximo N empresas")
    args = parser.parse_args(argv)

    if not tiny_client.integracao_ativa():
        raise SystemExit("TINY_TOKEN vazio: integracao desligada, nada a fazer.")

    db = SessionLocal()
    try:
        empresas = planejar(db, args.limite)
        print(f"Empresas ativas sem contato no Tiny: {len(empresas)}")
        resumo = processar(db, empresas, aplicar=args.aplicar)
        if not args.aplicar:
            print("\nSIMULACAO — nada enviado. Rode com --aplicar para valer.")
            return
        print(f"\nResultado: {resumo}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
