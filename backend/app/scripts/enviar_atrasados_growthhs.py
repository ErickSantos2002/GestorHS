"""Carga (backfill unico) dos clientes com calibracao ATRASADA para o board
Cobranca do GrowthHS — um card por cliente, com todos os aparelhos vencidos
dele em `devices[]`.

Uso: python -m app.scripts.enviar_atrasados_growthhs [--enviar] [--ate YYYY-MM-DD]
     [--pendencias CAMINHO.csv] [--limite N]

`--ate` move o corte de vencimento (INCLUSIVO; padrao: ontem). Serve para fechar o vao
com o job mensal de vencendo, que so comeca na competencia do mes seguinte: quem vence
entre hoje e o virar do mes tem que entrar nesta carga, ou nao e' avisado por ninguem.

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
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.api.growthhs_cards import buscar_elo
from app.core.config import settings
from app.core.growthhs_atrasados import agrupar_por_cliente, montar_card_atrasados
from app.integrations.hsgrowth_client import enviar_card_sync, integracao_ativa
from app.models import EquipamentoCliente
from app.models.database import SessionLocal

# backend/app/scripts/<arquivo>.py -> `backend/`, que e' o diretorio montado no
# container (./backend -> /app). Resolver a raiz do REPO (parents[3]) quebra dentro
# do container: la parents[3] e' `/`, entao o CSV ia parar em `/docs/` — sistema de
# arquivos efemero, invisivel no host e perdido quando o container e' recriado.
# Descoberto em 20/07/2026 rodando o job em dry-run de verdade. `parents[2]` da o
# mesmo lugar nos dois mundos: `backend/` no host, `/app` (= ./backend) no container.
def _dir_relatorios() -> Path:
    """Onde gravar o CSV de pendencias.

    Por padrao, uma subpasta do UPLOAD_DIR — o volume PERSISTENTE que ja existe nos
    dois ambientes (`/data/uploads`: volume nomeado do compose em dev, volume do
    Easypanel em producao). Reusar o volume ja configurado evita uma env a mais para
    esquecer no deploy: um caminho dentro de /app seria efemero em producao, onde a
    imagem sobe pelo Dockerfile SEM bind mount, e o relatorio sumiria no redeploy.

    `RELATORIOS_DIR` sobrescreve, se algum dia o relatorio precisar sair de la.

    Nada dentro do UPLOAD_DIR e servido estaticamente (nao ha StaticFiles montado; os
    arquivos saem so por endpoints que resolvem um registro especifico), entao o CSV
    nao fica alcancavel pela web.

    De todo modo as falhas tambem vao para o stdout, que o cron redireciona para o
    log: esse e o canal que sobrevive independente de volume.
    """
    if settings.RELATORIOS_DIR:
        return Path(settings.RELATORIOS_DIR)
    return Path(settings.UPLOAD_DIR) / "relatorios"


def buscar_atrasados(db: Session, ate: Optional[date] = None) -> list[dict]:
    """Uma linha por equipamento com calibracao vencida, elegivel para a carga.

    Cada linha: `{cliente_id, cliente, ec, equipamento_desc, elo}`.

    Regras:
    - `ativo` e `prox_calibragem <= ate` (corte INCLUSIVO; `ate` padrao = ontem,
      que e' o `< hoje` de sempre);
    - exclui aparelhos com OS em andamento (`os_atual` preenchido) — se o cliente
      ja mandou o aparelho, cobrar por ele e' ruido. Mesma regra do job mensal de
      vencendo, para os dois caminhos nao se contradizerem;
    - exclui hospedeiros (Phoebus/EBS) e o cliente de estoque interno da HS;
    - quando o equipamento e' um modulo de calibracao com instalacao aberta em
      `instalacoes_modulo`, `elo` traz o Phoebus correspondente (serie +
      descricao do catalogo); senao `elo` e' None.

    O `ate` existe para fechar o vao com o job mensal: ele comeca na competencia do
    mes seguinte, entao quem vence entre hoje e o virar do mes precisa entrar AQUI,
    ou nao seria avisado por ninguem.
    """
    if ate is None:
        ate = date.today() - timedelta(days=1)
    ecs = (
        db.query(EquipamentoCliente)
        .filter(
            EquipamentoCliente.ativo.is_(True),
            EquipamentoCliente.prox_calibragem.isnot(None),
            EquipamentoCliente.prox_calibragem <= ate,
            EquipamentoCliente.os_atual.is_(None),
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
        elo = buscar_elo(db, ec)

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


def processar(db: Session, *, enviar: bool, limite: Optional[int] = None,
              ate: Optional[date] = None) -> dict:
    """Busca -> agrupa por cliente -> (se `enviar`) manda um card por grupo.

    Best-effort POR CLIENTE: uma excecao ao enviar um grupo e' capturada,
    contada em `falhas` e registrada em `pendencias` — o laco segue para o
    proximo grupo, NUNCA aborta a carga inteira por causa de um cliente.

    Devolve um resumo pronto para o `main()` imprimir e gravar em CSV:
    `{grupos, criados, existentes, falhas, pendencias, sem_contato, sem_elo}`.
    """
    linhas = buscar_atrasados(db, ate=ate)
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

    def _pendencia(grupo, motivo: str) -> None:
        pendencias.append({
            "cliente_id": grupo["cliente_id"],
            "cliente": getattr(grupo["cliente"], "nome", None) or "",
            "qtd_equipamentos": len(grupo["itens"]),
            "motivo": motivo,
        })

    for grupo in grupos:
        # O card e' montado SEMPRE, inclusive em simulacao — e' assim que o modo
        # simulacao cumpre o que promete: validar que o payload de TODO cliente
        # consegue ser construido. Se a montagem ficasse atras do `--enviar`, um
        # cliente com dado ruim passaria limpo na simulacao e so estouraria na
        # carga real, que e' exatamente o que queremos evitar.
        try:
            card = montar_card_atrasados(grupo, data_carga, settings.HSGROWTH_BOARD_COBRANCA)
        except Exception as exc:  # noqa: BLE001 — melhor esforco por cliente
            falhas += 1
            _pendencia(grupo, f"falha ao montar o card: {exc}")
            continue

        if not enviar:
            continue      # simulacao: montou (validou) e para aqui, sem request

        try:
            resposta = enviar_card_sync(card)
        except Exception as exc:  # noqa: BLE001 — melhor esforco por cliente, segue pro proximo
            falhas += 1
            _pendencia(grupo, str(exc))
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


def _data(texto: str) -> date:
    """Converte `YYYY-MM-DD`. Erro de digitacao morre aqui, no argparse — um corte
    errado numa carga irreversivel e' caro demais para passar batido."""
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"data invalida: {texto!r} (use YYYY-MM-DD, ex.: 2026-07-31)")


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
    parser.add_argument("--ate", type=_data, default=None, metavar="YYYY-MM-DD",
                        help="Corte INCLUSIVO do vencimento (padrao: ontem). Use para "
                             "fechar o vao com o job mensal, que so comeca no dia 1.")
    args = parser.parse_args()

    if args.enviar and not integracao_ativa():
        print(
            "ERRO: integracao com o GrowthHS esta DESLIGADA "
            "(configure HSGROWTH_BASE_URL e HSGROWTH_API_KEY) — abortando antes "
            "de tentar enviar para o vazio. Nada foi lido nem gravado."
        )
        return

    caminho_pendencias = args.pendencias or str(
        _dir_relatorios() / f"pendencias-atrasados-growthhs-{date.today().isoformat()}.csv"
    )
    # Cria o diretorio de saida ANTES de qualquer envio: um caminho invalido
    # precisa falhar rapido, nao depois de ja ter criado cards em producao
    # (mesma licao aprendida em `importar_elo_modulos.py`).
    os.makedirs(os.path.dirname(caminho_pendencias) or ".", exist_ok=True)
    # Nao basta criar o diretorio: se ele ja existe mas pertence a outro usuario
    # (o container roda como root, entao `relatorios/` nasce root), o makedirs passa
    # e a falha so aparece no open() la embaixo — DEPOIS de os cards ja terem sido
    # enviados. Abrir agora, em modo append, transforma isso em falha imediata.
    try:
        open(caminho_pendencias, "a", encoding="utf-8").close()
    except OSError as exc:
        print(f"ERRO: nao consigo gravar o relatorio em {caminho_pendencias}: {exc}\n"
              f"Use --pendencias com um caminho gravavel. Nada foi enviado.")
        raise SystemExit(1)

    db = SessionLocal()
    try:
        resultado = processar(db, enviar=args.enviar, limite=args.limite, ate=args.ate)
    finally:
        db.close()

    _escrever_csv_pendencias(caminho_pendencias, resultado["pendencias"])

    grupos = resultado["grupos"]
    total_equipamentos = sum(len(g["itens"]) for g in grupos)

    corte = args.ate or (date.today() - timedelta(days=1))
    print(f"Corte (vencimento ate, inclusive): {corte:%d/%m/%Y}")
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
