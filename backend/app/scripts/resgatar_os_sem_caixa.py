"""Resgata as OS que ficaram sem caixa e nao tinham como andar.

Quem avanca de fase e' a CAIXA, nao a OS. Uma OS desvinculada fica parada na
fase em que estava, sem aparecer em caixa nenhuma e sem botao que a resgate. Em
24/08/2026 havia quatro assim, a mais antiga travada desde 24/07. O caminho que
as criava (o botao "Remover") foi fechado no mesmo dia; este script conserta o
que ja tinha acontecido.

Duas operacoes, decididas pelo Erick:

1. A OS 11080, aberta hoje, vai para a caixa 955.
   A caixa 955 esta SEM FASE (foi criada vazia, e a fase so nasce quando a
   primeira OS e' aberta dentro dela). `avancar_caixa` recusa caixa sem fase com
   409, entao vincular sem dar a fase deixaria tudo travado do mesmo jeito — o
   script assume a fase da propria OS.

2. As OS 10885, 10906 e 11014 sao encerradas administrativamente: os aparelhos
   ja sairam da Health Safety, so o registro ficou para tras. Seguem a mesma
   convencao do encerramento de 30/07/2026, que marcou 354 OS com
   `ENC-ADM-<data>` em `cod_retorno` — o marcador e' o que permite distinguir
   depois um retorno real de um acerto administrativo.

Diferente daquele de julho, este REGISTRA NO HISTORICO de cada OS, para quem
abrir a tela entender por que a OS pulou para Finalizada sem passar pelas fases.

    python -m app.scripts.resgatar_os_sem_caixa              # so simula
    python -m app.scripts.resgatar_os_sem_caixa --aplicar    # grava
"""
import argparse
from datetime import datetime, timezone

from app.api.ordens_acoes import registrar_log
from app.models import Caixa, Ordem
from app.models.database import SessionLocal

OS_PARA_CAIXA = (11080, 955)
OS_PARA_FINALIZAR = (10885, 10906, 11014)
MARCADOR = "ENC-ADM-20260824"

FASE_FINALIZADA = 8


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true", help="grava de fato (sem isso, so simula)")
    args = p.parse_args()

    db = SessionLocal()
    try:
        agora = datetime.now(timezone.utc)
        os_id, caixa_id = OS_PARA_CAIXA
        ordem = db.query(Ordem).filter(Ordem.id == os_id).one_or_none()
        caixa = db.query(Caixa).filter(Caixa.id == caixa_id).one_or_none()

        print("1) VINCULO")
        if ordem is None or caixa is None:
            print(f"   OS {os_id} ou caixa {caixa_id} nao encontrada — nada a fazer")
        else:
            print(f"   OS {os_id}: caixa {ordem.caixa} -> {caixa_id}  (fase da OS: {ordem.fase})")
            if caixa.fase is None:
                print(f"   caixa {caixa_id}: fase None -> {ordem.fase}  (senao nao avanca)")
            else:
                print(f"   caixa {caixa_id}: ja tem fase {caixa.fase}, mantida")

        print()
        print("2) ENCERRAMENTO ADMINISTRATIVO")
        finalizar = db.query(Ordem).filter(Ordem.id.in_(OS_PARA_FINALIZAR)).order_by(Ordem.id).all()
        for o in finalizar:
            print(f"   OS {o.id}: fase {o.fase} -> {FASE_FINALIZADA} · situacao {o.situacao!r} -> 'F' "
                  f"· cod_retorno {o.cod_retorno!r} -> {MARCADOR!r}")
        faltando = set(OS_PARA_FINALIZAR) - {o.id for o in finalizar}
        if faltando:
            print(f"   AVISO - nao encontradas: {sorted(faltando)}")

        if not args.aplicar:
            print("\n(simulacao — rode com --aplicar para gravar)")
            return

        if ordem is not None and caixa is not None:
            if caixa.fase is None:
                caixa.fase = ordem.fase
            ordem.caixa = caixa.id
            registrar_log(db, ordem, None,
                          f"OS vinculada à caixa #{caixa.id} (correção: estava sem caixa)")

        for o in finalizar:
            o.fase = FASE_FINALIZADA
            o.situacao = "F"
            o.cod_retorno = MARCADOR
            o.data_retorno = agora
            registrar_log(db, o, None,
                          f"OS finalizada administrativamente ({MARCADOR}): estava sem caixa, "
                          f"aparelho já devolvido ao cliente")

        db.commit()
        print(f"\ngravado: 1 vinculo e {len(finalizar)} encerramentos")
    finally:
        db.close()


if __name__ == "__main__":
    main()
