"""Garante no Tiny o Cliente que ja recebeu proposta (carga de 23/09/2026).

Para cada Cliente — ATIVO OU NAO — que e' destinatario de pelo menos uma
proposta (`propostas.empresa IS NULL`) e ainda nao tem `tiny_id`: pesquisa o
documento no Tiny e ADOTA o contato que existir; so cria o que faltar. Contato
que ja existe NUNCA e' alterado.

    python -m app.scripts.enviar_clientes_tiny                  # simula (pesquisa, nao cria nem grava)
    python -m app.scripts.enviar_clientes_tiny --aplicar        # grava
    python -m app.scripts.enviar_clientes_tiny --aplicar --limite 20

Limite da conta: 20 chamadas por minuto; cada cliente gasta ate duas, dai ~7s
entre eles. Levando bloqueio (codigo 6/11) ou caindo a rede, o script PARA e diz
quantos faltaram — e' so rodar de novo. Idempotente: quem tem `tiny_id` sai da fila.

Os que pedem atencao (sem documento, pesquisa inconclusiva, recusa do Tiny) saem
no stdout e num CSV (`--pendencias`, padrao `relatorios/` na pasta atual).
"""
import argparse
import csv
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from app.core import tiny
from app.integrations import tiny_client
from app.models import Cliente, Proposta
from app.models.database import SessionLocal

PAUSA_PADRAO = 7.0


def planejar(db, limite: Optional[int] = None) -> list:
    """Clientes com proposta propria e sem contato no Tiny, em ordem de id."""
    com_proposta = (db.query(Proposta.cliente)
                    .filter(Proposta.empresa.is_(None), Proposta.cliente.isnot(None),
                            Proposta.is_deleted.is_(False)))
    query = (db.query(Cliente)
             .filter(Cliente.tiny_id.is_(None), Cliente.id.in_(com_proposta))
             .order_by(Cliente.id))
    if limite:
        query = query.limit(limite)
    return query.all()


def _marcar(db, cliente, *, status: str, tiny_id=None, erro=None) -> None:
    if tiny_id is not None:
        cliente.tiny_id = tiny_id
    cliente.tiny_status = status
    cliente.tiny_erro = (erro or "")[:255] or None
    cliente.tiny_em = datetime.now(timezone.utc)
    db.commit()


def processar(db, clientes, *, aplicar: bool, pausa: float = PAUSA_PADRAO) -> dict:
    """Pesquisa cada cliente, adota o que existir e so cria o que faltar.

    A SIMULACAO pesquisa de verdade (leitura) — e' o unico jeito de responder
    "vai criar quantos?" antes de valer — mas nao grava nada no banco nem trava
    linha nenhuma.

    Com `--aplicar`, a carga leva ~25 min para ~212 clientes (I2, revisao de
    23/09/2026): nesse tempo a rota da proposta e o worker de `pendentes` podem
    mexer no MESMO cliente por fora. Por isso cada cliente e' RETRAVADO
    (`stmt_travar_cliente`, a mesma trava de `sincronizar_cliente`) bem antes de
    pesquisar — se essa releitura ja mostrar `tiny_id`, alguem resolveu por
    outro caminho enquanto a carga rodava, e criar aqui duplicaria o contato.
    """
    resumo = {"candidatas": len(clientes), "adotadas": 0, "criadas": 0, "erros": 0,
              "puladas": 0, "sem_documento": 0, "ja_feitos": 0, "interrompido": False,
              "pendencias": []}

    def pendencia(cliente, documento, motivo):
        resumo["pendencias"].append({"cliente_id": cliente.id, "cliente": cliente.nome or "",
                                     "documento": documento, "motivo": motivo})

    pausar = False
    for cliente in clientes:
        rotulo = f"{cliente.id:5} {(cliente.nome or '')[:40]:40}"

        # A pausa entre chamadas vem ANTES da trava: dormir com a linha travada
        # faria uma proposta salva para este cliente esperar os 7s inteiros.
        if pausar and pausa:
            time.sleep(pausa)                      # a pesquisa tambem gasta chamada
        pausar = False

        if aplicar:
            # Trava a linha e reconfere: se sumiu ou ja ganhou tiny_id por
            # outro caminho, libera a trava e pula sem gastar chamada.
            # `populate_existing`: o `planejar` deixou os clientes no identity
            # map e nada commitou antes da primeira trava — sem isso a releitura
            # devolve o objeto em memoria, com o tiny_id VELHO.
            stmt = tiny_client.stmt_travar_cliente(cliente.id).execution_options(populate_existing=True)
            atual = db.execute(stmt).scalars().first()
            if atual is None or atual.tiny_id:
                db.commit()
                resumo["ja_feitos"] += 1
                print(f"  = {rotulo} ja resolvido por outro caminho enquanto a carga rodava, pulando")
                continue
            cliente = atual

        documento = cliente.cgc or cliente.cpf or ""
        if not documento:
            if aplicar:
                _marcar(db, cliente, status="erro", erro="cliente sem CNPJ/CPF")
            resumo["sem_documento"] += 1
            pendencia(cliente, "", "sem CNPJ/CPF")
            print(f"  ! {rotulo} sem CNPJ/CPF")
            continue

        pausar = True
        achado = tiny_client.pesquisar_contato(documento)

        if achado.ok and achado.id:
            if aplicar:
                _marcar(db, cliente, status="enviada", tiny_id=achado.id)
            resumo["adotadas"] += 1
            print(f"  = {rotulo} {'adotou' if aplicar else 'adotaria'} contato {achado.id}")
            continue
        if achado.deve_tentar_de_novo:
            if aplicar:
                db.commit()  # libera a trava desta linha antes de parar
            resumo["interrompido"] = True
            break
        if not achado.nao_encontrado:
            # So o erro 20 e' "nao existe la": o resto deixa em aberto se o
            # contato ja existe — criar aqui geraria DUPLICADO no ERP.
            if aplicar:
                db.commit()  # nada mudou no cliente, so libera a trava
            resumo["puladas"] += 1
            motivo = achado.mensagem or "pesquisa sem resposta clara"
            pendencia(cliente, documento, motivo)
            print(f"  ~ {rotulo} pulado: {motivo}")
            continue

        if not aplicar:
            resumo["criadas"] += 1
            print(f"  + {rotulo} criaria contato novo")
            continue

        resultado = tiny_client.incluir_contato(tiny.contato_cliente_para_criar(cliente))
        if resultado.duplicidade:
            # Rede de seguranca: alguem criou entre a pesquisa e a inclusao —
            # mesmo tratamento de sincronizar_cliente.
            seguranca = tiny_client.pesquisar_contato(documento)
            if seguranca.ok and seguranca.id:
                _marcar(db, cliente, status="enviada", tiny_id=seguranca.id)
                resumo["adotadas"] += 1
                print(f"  = {rotulo} duplicidade no Tiny: adotou contato {seguranca.id}")
                continue
            motivo = resultado.mensagem or "duplicidade sem achar o contato de novo"
            _marcar(db, cliente, status="erro", erro=motivo)
            resumo["erros"] += 1
            pendencia(cliente, documento, motivo)
            print(f"  ! {rotulo} {motivo}")
            continue

        if resultado.ok and resultado.id is not None:
            _marcar(db, cliente, status="enviada", tiny_id=resultado.id)
            resumo["criadas"] += 1
            print(f"  + {rotulo} criou contato {resultado.id}")
        elif resultado.ok:
            # OK sem id: nao e' recusa do Tiny (T6) — fica pendente para o
            # worker/reenvio conferir, sem virar erro sticky.
            _marcar(db, cliente, status="pendente")
            resumo["puladas"] += 1
            motivo = "incluido sem id; conferir no Tiny"
            pendencia(cliente, documento, motivo)
            print(f"  ~ {rotulo} {motivo}")
        elif resultado.deve_tentar_de_novo:
            db.commit()  # libera a trava desta linha antes de parar
            resumo["interrompido"] = True
            break
        else:
            _marcar(db, cliente, status="erro", erro=resultado.mensagem or "recusado sem id")
            resumo["erros"] += 1
            pendencia(cliente, documento, resultado.mensagem or "recusado sem id")
            print(f"  ! {rotulo} {resultado.mensagem}")

    if resumo["interrompido"]:
        feitos = (resumo["adotadas"] + resumo["criadas"] + resumo["erros"] + resumo["puladas"]
                  + resumo["sem_documento"] + resumo["ja_feitos"])
        print(f"\nPAROU: o Tiny bloqueou por excesso de chamadas (ou a rede caiu). "
              f"{resumo['candidatas'] - feitos} cliente(s) ficaram para a proxima rodada.")
    return resumo


def _escrever_csv(caminho: Path, pendencias: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["cliente_id", "cliente", "documento", "motivo"])
        writer.writeheader()
        writer.writerows(pendencias)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aplicar", action="store_true", help="grava (padrao: so simula)")
    parser.add_argument("--limite", type=int, default=None, help="processa no maximo N clientes")
    parser.add_argument("--pendencias", default=None,
                        help="CSV dos que pedem atencao (padrao: relatorios/pendencias-clientes-tiny-<data>.csv)")
    args = parser.parse_args(argv)

    if not tiny_client.integracao_ativa():
        raise SystemExit("TINY_TOKEN vazio: integracao desligada, nada a fazer.")

    db = SessionLocal()
    try:
        clientes = planejar(db, args.limite)
        print(f"Clientes com proposta e sem contato no Tiny: {len(clientes)}")
        resumo = processar(db, clientes, aplicar=args.aplicar)
        caminho = Path(args.pendencias or f"relatorios/pendencias-clientes-tiny-{date.today().isoformat()}.csv")
        _escrever_csv(caminho, resumo["pendencias"])
        print(f"\nResultado: { {k: v for k, v in resumo.items() if k != 'pendencias'} }")
        print(f"Pendencias ({len(resumo['pendencias'])}) em {caminho}")
        if not args.aplicar:
            print("SIMULACAO — a pesquisa rodou (leitura), mas nada foi criado nem "
                  "gravado. Rode com --aplicar para valer.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
