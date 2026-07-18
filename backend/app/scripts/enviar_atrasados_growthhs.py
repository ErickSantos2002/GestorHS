"""Carga (backfill unico) dos clientes com calibracao ATRASADA para o board
Cobranca do GrowthHS — um card por cliente, com todos os aparelhos vencidos
dele em `devices[]`.

Uso: python -m app.scripts.enviar_atrasados_growthhs [--enviar] [--pendencias CAMINHO.csv]
     [--limite N]

SEGURANCA — o padrao e' NAO enviar. Sem `--enviar`, o script monta tudo,
imprime o resumo e escreve o CSV, mas faz ZERO requests. O envio real exige
`--enviar` explicito.

Por que': a chave do card e' `{cliente_id}:{data_da_carga}` (ver
`app.core.growthhs_atrasados.montar_card_atrasados`), entao rodar a carga em
duas datas diferentes cria um card DUPLICADO por cliente — e o GrowthHS nao
expoe leitura, logo o script nao tem como detectar que ja enviou. Invertendo
o default, um comando repetido por engano (esquecer a flag, apertar
seta-pra-cima no shell) e' inofensivo.
"""
import argparse
import csv
import os
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.growthhs_atrasados import agrupar_por_cliente, montar_card_atrasados
from app.integrations.hsgrowth_client import enviar_card_sync, integracao_ativa
from app.models import EquipamentoCliente, InstalacaoModulo
from app.models.database import SessionLocal

# backend/app/scripts/enviar_atrasados_growthhs.py -> raiz do repo GestorHS.
# O script roda a partir de `backend/`; resolver o CSV padrao contra o CWD
# colocaria em `backend/docs/` (nao existe) em vez do `docs/` real da raiz —
# mesma licao de `importar_elo_modulos.py`.
_RAIZ_REPO = Path(__file__).resolve().parents[3]


def buscar_atrasados(db: Session) -> list[dict]:
    """Uma linha por equipamento com calibracao vencida, elegivel para a carga.

    Cada linha: `{cliente_id, cliente, ec, equipamento_desc, elo}`.

    Regras (ver Task 4 brief):
    - `ativo` e `prox_calibragem < hoje`;
    - exclui hospedeiros (Phoebus/EBS) e o cliente de estoque interno da HS;
    - quando o equipamento e' um modulo de calibracao com instalacao aberta em
      `instalacoes_modulo`, `elo` traz o Phoebus correspondente (serie +
      descricao do catalogo); senao `elo` e' None.
    """
    hoje = date.today()
    ecs = (
        db.query(EquipamentoCliente)
        .filter(
            EquipamentoCliente.ativo.is_(True),
            EquipamentoCliente.prox_calibragem.isnot(None),
            EquipamentoCliente.prox_calibragem < hoje,
            EquipamentoCliente.equipamento.notin_(
                [settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_EBS_ID]
            ),
            EquipamentoCliente.cliente != settings.CLIENTE_ESTOQUE_HS_ID,
        )
        .order_by(EquipamentoCliente.id)
        .all()
    )

    linhas = []
    for ec in ecs:
        elo = None
        if ec.equipamento == settings.EQUIPAMENTO_MODULO_ID:
            instalacao = (
                db.query(InstalacaoModulo)
                .filter(InstalacaoModulo.modulo == ec.id, InstalacaoModulo.saiu_em.is_(None))
                .first()
            )
            if instalacao is not None:
                phoebus_ec = db.get(EquipamentoCliente, instalacao.phoebus)
                if phoebus_ec is not None:
                    # Ponte OBRIGATORIA: montar_device(elo=...) espera `.serie`
                    # e `.descricao`, mas a linha ORM real de EquipamentoCliente
                    # expoe a descricao do catalogo como `.equipamento_descricao`
                    # (property via join), NAO `.descricao`. Passar o ORM puro
                    # quebraria com AttributeError bem no caso interessante
                    # (modulo COM elo).
                    elo = SimpleNamespace(
                        serie=phoebus_ec.serie,
                        descricao=phoebus_ec.equipamento_descricao,
                    )

        linhas.append({
            "cliente_id": ec.cliente,
            "cliente": ec.cliente_rel,
            "ec": ec,
            "equipamento_desc": ec.equipamento_descricao,
            "elo": elo,
        })

    return linhas


def _tem_contato(cliente) -> bool:
    return bool((getattr(cliente, "contato", None) or "").strip())


def processar(db: Session, *, enviar: bool, limite: Optional[int] = None) -> dict:
    """Busca -> agrupa por cliente -> (se `enviar`) manda um card por grupo.

    Best-effort POR CLIENTE: uma excecao ao enviar um grupo e' capturada,
    contada em `falhas` e registrada em `pendencias` — o laco segue para o
    proximo grupo, NUNCA aborta a carga inteira por causa de um cliente.

    Devolve um resumo pronto para o `main()` imprimir e gravar em CSV:
    `{grupos, criados, existentes, falhas, pendencias, sem_contato, sem_elo}`.
    """
    linhas = buscar_atrasados(db)
    grupos = agrupar_por_cliente(linhas)
    if limite is not None:
        grupos = grupos[:limite]

    sem_contato = sum(1 for g in grupos if not _tem_contato(g["cliente"]))
    sem_elo = sum(
        1
        for g in grupos
        for item in g["itens"]
        if item["ec"].equipamento == settings.EQUIPAMENTO_MODULO_ID and item.get("elo") is None
    )

    criados = existentes = falhas = 0
    pendencias: list[dict] = []
    data_carga = date.today()

    if enviar:
        for grupo in grupos:
            card = montar_card_atrasados(grupo, data_carga, settings.HSGROWTH_BOARD_COBRANCA)
            try:
                resposta = enviar_card_sync(card)
            except Exception as exc:  # noqa: BLE001 — melhor esforco por cliente, segue pro proximo
                falhas += 1
                pendencias.append({
                    "cliente_id": grupo["cliente_id"],
                    "cliente": getattr(grupo["cliente"], "nome", None) or "",
                    "qtd_equipamentos": len(grupo["itens"]),
                    "motivo": str(exc),
                })
                continue

            if resposta.get("created"):
                criados += 1
            else:
                existentes += 1

    return {
        "grupos": grupos,
        "criados": criados,
        "existentes": existentes,
        "falhas": falhas,
        "pendencias": pendencias,
        "sem_contato": sem_contato,
        "sem_elo": sem_elo,
    }


def _escrever_csv_pendencias(caminho: str, pendencias: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["cliente_id", "cliente", "qtd_equipamentos", "motivo"])
        writer.writeheader()
        for p in pendencias:
            writer.writerow(p)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carga (backfill unico) dos atrasados no board Cobranca do GrowthHS."
    )
    parser.add_argument(
        "--enviar", action="store_true",
        help="Envia de verdade. Sem essa flag o script so simula: monta tudo, "
             "imprime o resumo e grava o CSV, mas NENHUM request e' feito.",
    )
    parser.add_argument("--pendencias", default=None, help="Caminho do CSV de pendencias/falhas")
    parser.add_argument("--limite", type=int, default=None,
                         help="Processa so os N primeiros grupos (clientes) — para um teste real controlado")
    args = parser.parse_args()

    if args.enviar and not integracao_ativa():
        print(
            "ERRO: integracao com o GrowthHS esta DESLIGADA "
            "(configure HSGROWTH_BASE_URL e HSGROWTH_API_KEY) — abortando antes "
            "de tentar enviar para o vazio. Nada foi lido nem gravado."
        )
        return

    caminho_pendencias = args.pendencias or str(
        _RAIZ_REPO / "docs" / f"pendencias-atrasados-growthhs-{date.today().isoformat()}.csv"
    )
    # Cria o diretorio de saida ANTES de qualquer envio: um caminho invalido
    # precisa falhar rapido, nao depois de ja ter criado cards em producao
    # (mesma licao aprendida em `importar_elo_modulos.py`).
    os.makedirs(os.path.dirname(caminho_pendencias) or ".", exist_ok=True)

    db = SessionLocal()
    try:
        resultado = processar(db, enviar=args.enviar, limite=args.limite)
    finally:
        db.close()

    _escrever_csv_pendencias(caminho_pendencias, resultado["pendencias"])

    grupos = resultado["grupos"]
    total_equipamentos = sum(len(g["itens"]) for g in grupos)

    print(f"Clientes com calibracao atrasada: {len(grupos)}")
    print(f"Equipamentos vencidos: {total_equipamentos}")
    print(f"Clientes sem contato cadastrado: {resultado['sem_contato']}")
    print(f"Modulos de calibracao sem elo (Phoebus) encontrado: {resultado['sem_elo']}")

    if not args.enviar:
        print("=" * 70)
        print("MODO SIMULACAO — NADA FOI ENVIADO AO GROWTHHS.")
        print("Nenhum request foi feito. Para enviar de verdade, rode de novo com --enviar.")
        print("=" * 70)
    else:
        print(f"Criados: {resultado['criados']} / Ja existentes: {resultado['existentes']} / "
              f"Falhas: {resultado['falhas']}")

    print(f"Pendencias/falhas gravadas em: {caminho_pendencias}")


if __name__ == "__main__":
    main()
