"""Job DIARIO: cria um card no board Cobranca do GrowthHS para cada aparelho cuja
calibracao vence nos proximos N dias (padrao 50).

Uso: python -m app.scripts.enviar_vencendo_growthhs [--dias 50] [--dry-run]
     [--limite N] [--pendencias CAMINHO.csv]

Agendado por cron (ver docs/operacao-growthhs-cron.md).

PADRAO E' ENVIAR — ao contrario de `enviar_atrasados_growthhs`, que exige
`--enviar`. Nao e' inconsistencia: a chave daquele script leva a data da carga, entao
repetir cria duplicata irrecuperavel; a chave DESTE e' `{ec_id}:{prox_calibragem}`,
que nao muda com o dia da execucao — rodar de novo devolve `created: false` e nao
cria nada. Alem disso e' um job de cron: um default que nao envia viraria um
agendamento no-op silencioso, o pior modo de falha possivel aqui.

O job e' BURRO e SEM ESTADO: roda todo dia sobre a janela inteira e nao precisa
lembrar o que ja mandou, porque a criacao e' idempotente.
"""
import argparse
import csv
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.api.growthhs_cards import buscar_elo
from app.core.config import settings
from app.core.growthhs_vencendo import montar_card_vencendo
from app.integrations.hsgrowth_client import enviar_card_sync, integracao_ativa
from app.models import EquipamentoCliente
from app.models.database import SessionLocal

# backend/app/scripts/<arquivo>.py -> raiz do repo. O script roda a partir de
# `backend/`; resolver contra o CWD colocaria o CSV em `backend/docs/` (nao existe).
_RAIZ_REPO = Path(__file__).resolve().parents[3]

DIAS_PADRAO = 50


def buscar_vencendo(db: Session, dias: int) -> list[dict]:
    """Uma linha por aparelho com calibracao a vencer na janela `[hoje, hoje+dias]`.

    Cada linha: `{cliente_id, cliente, ec, equipamento_desc, elo}` — mesmo formato da
    Etapa 1, de proposito, para compartilhar `buscar_elo`.

    NAO inclui vencidos (`prox_calibragem < hoje`): esse backlog e' da Etapa 1.
    Exclui hospedeiros (Phoebus/EBS), o cliente de estoque interno da HS e aparelhos
    com OS em andamento (`os_atual` preenchido) — se o cliente ja mandou o aparelho,
    "entre em contato" e' ruido.
    """
    hoje = date.today()
    ecs = (
        db.query(EquipamentoCliente)
        .filter(
            EquipamentoCliente.ativo.is_(True),
            EquipamentoCliente.prox_calibragem.isnot(None),
            EquipamentoCliente.prox_calibragem >= hoje,
            EquipamentoCliente.prox_calibragem <= hoje + timedelta(days=dias),
            EquipamentoCliente.os_atual.is_(None),
            EquipamentoCliente.equipamento.notin_(
                [settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_EBS_ID]
            ),
            EquipamentoCliente.cliente != settings.CLIENTE_ESTOQUE_HS_ID,
        )
        .order_by(EquipamentoCliente.prox_calibragem, EquipamentoCliente.id)
        .all()
    )

    return [
        {
            "cliente_id": ec.cliente,
            "cliente": ec.cliente_rel,
            "ec": ec,
            "equipamento_desc": ec.equipamento_descricao,
            "elo": buscar_elo(db, ec),
        }
        for ec in ecs
    ]


def processar(db: Session, *, dias: int, enviar: bool, limite: Optional[int] = None) -> dict:
    """Busca a janela e manda um card por aparelho.

    Best-effort POR APARELHO: uma excecao num card e' contada em `falhas`, registrada
    em `pendencias` e o laco SEGUE para o proximo — nunca aborta a rodada inteira.
    """
    linhas = buscar_vencendo(db, dias)
    if limite is not None:
        linhas = linhas[:limite]

    hoje = date.today()
    criados = existentes = falhas = 0
    pendencias: list[dict] = []

    for linha in linhas:
        ec = linha["ec"]
        # Monta SEMPRE, inclusive em dry-run: e' assim que a simulacao cumpre o que
        # promete — validar que o payload de todo aparelho consegue ser construido.
        try:
            card = montar_card_vencendo(linha, hoje, settings.HSGROWTH_BOARD_COBRANCA)
        except Exception as exc:  # noqa: BLE001 — melhor esforco por aparelho
            falhas += 1
            pendencias.append({
                "equipamento_cliente_id": ec.id,
                "cliente_id": linha["cliente_id"],
                "serie": getattr(ec, "serie", "") or "",
                "prox_calibragem": ec.prox_calibragem.isoformat(),
                "motivo": f"falha ao montar o card: {exc}",
            })
            continue

        if not enviar:
            continue      # dry-run: montou (validou) e para aqui, sem request

        try:
            resposta = enviar_card_sync(card)
        except Exception as exc:  # noqa: BLE001 — segue para o proximo aparelho
            falhas += 1
            pendencias.append({
                "equipamento_cliente_id": ec.id,
                "cliente_id": linha["cliente_id"],
                "serie": getattr(ec, "serie", "") or "",
                "prox_calibragem": ec.prox_calibragem.isoformat(),
                "motivo": str(exc),
            })
            continue

        if resposta.get("created"):
            criados += 1
        else:
            existentes += 1

    return {
        "candidatos": len(linhas),
        "criados": criados,
        "existentes": existentes,
        "falhas": falhas,
        "pendencias": pendencias,
    }


def _escrever_csv_pendencias(caminho: str, pendencias: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "equipamento_cliente_id", "cliente_id", "serie", "prox_calibragem", "motivo",
        ])
        writer.writeheader()
        for p in pendencias:
            writer.writerow(p)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Job diario: cards de calibracao vencendo no board Cobranca do GrowthHS."
    )
    parser.add_argument("--dias", type=int, default=DIAS_PADRAO,
                        help=f"Tamanho da janela em dias (padrao {DIAS_PADRAO})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula: monta tudo e imprime o resumo, sem NENHUM request.")
    parser.add_argument("--limite", type=int, default=None,
                        help="Processa so os N primeiros aparelhos — para um teste controlado")
    parser.add_argument("--pendencias", default=None, help="Caminho do CSV de falhas")
    args = parser.parse_args()

    enviar = not args.dry_run

    if enviar and not integracao_ativa():
        print("ERRO: integracao com o GrowthHS esta DESLIGADA "
              "(configure HSGROWTH_BASE_URL e HSGROWTH_API_KEY) — abortando. "
              "Nada foi lido nem enviado.")
        raise SystemExit(1)

    caminho_pendencias = args.pendencias or str(
        _RAIZ_REPO / "docs" / f"pendencias-vencendo-growthhs-{date.today().isoformat()}.csv"
    )
    # Cria o diretorio ANTES de qualquer envio: um caminho invalido precisa falhar
    # rapido, nao depois de ja ter criado cards em producao.
    os.makedirs(os.path.dirname(caminho_pendencias) or ".", exist_ok=True)

    db = SessionLocal()
    try:
        r = processar(db, dias=args.dias, enviar=enviar)
    finally:
        db.close()

    _escrever_csv_pendencias(caminho_pendencias, r["pendencias"])

    print(f"Janela: {date.today()} -> {date.today() + timedelta(days=args.dias)} "
          f"({args.dias} dias)")
    print(f"Aparelhos na janela: {r['candidatos']}")
    if enviar:
        print(f"Criados: {r['criados']} / Ja existentes: {r['existentes']} / "
              f"Falhas: {r['falhas']}")
    else:
        print("MODO DRY-RUN — NADA FOI ENVIADO. Rode sem --dry-run para valer.")
    print(f"Pendencias/falhas gravadas em: {caminho_pendencias}")

    # Saida !=0 quando houve falha, para o cron conseguir alertar.
    if r["falhas"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
