"""Job MENSAL: cria um card no board Cobranca do GrowthHS para cada CLIENTE com
aparelhos cuja calibracao vence na competencia — um card por cliente por mes.

Uso: python -m app.scripts.enviar_vencendo_growthhs [--competencia YYYY-MM ...]
     [--dry-run] [--limite N] [--pendencias CAMINHO.csv]

Roda sozinho dentro da API todo dia 1 as 8h (ver app/tarefas/vencendo.py e
docs/operacao-growthhs-job-mensal.md). Sem --competencia, cobre o mes corrente e o
seguinte.

PADRAO E' ENVIAR — ao contrario de `enviar_atrasados_growthhs`, que exige `--enviar`.
Nao e' inconsistencia: a chave daquele script leva a data da carga, entao repetir cria
duplicata irrecuperavel; a chave DESTE e' `{cliente_id}:{YYYY-MM}`, que nao muda com o
dia da execucao — rodar de novo devolve `created: false` e nao cria nada. Alem disso e'
um job agendado: um default que nao envia viraria um agendamento no-op silencioso, o
pior modo de falha possivel aqui.

O job e' BURRO e SEM ESTADO: roda todo mes sobre as duas competencias inteiras e nao
precisa lembrar o que ja mandou, porque a criacao e' idempotente. E' isso que faz a
primeira rodada subir 60 dias e as seguintes so o mes novo da ponta.
"""
import argparse
import csv
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.api.growthhs_cards import buscar_elo
from app.core.config import settings
from app.core.growthhs_vencendo import montar_card_vencendo
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

def _limites_da_competencia(competencia: date) -> tuple[date, date]:
    """Primeiro e ultimo dia do mes da competencia.

    O inicio nunca e' anterior a hoje: se alguem rodar a mao no meio do mes, nao faz
    sentido "avisar" de um aparelho que ja venceu — isso e' backlog da Etapa 1.
    Na rodada automatica (dia 1) o `max` nao corta nada.
    """
    primeiro = competencia.replace(day=1)
    # Primeiro dia do mes seguinte menos um dia — nao depende de o mes ter 28/29/30/31.
    if primeiro.month == 12:
        proximo = primeiro.replace(year=primeiro.year + 1, month=1)
    else:
        proximo = primeiro.replace(month=primeiro.month + 1)
    return max(date.today(), primeiro), proximo - timedelta(days=1)


def _filtros_base(competencia: date):
    """Os filtros comuns a quem VIRA card e a quem foi EXCLUIDO por OS.

    Uma copia divergente destes filtros faria o relatorio de excluidos mentir — por
    isso mora num lugar so.
    """
    inicio, fim = _limites_da_competencia(competencia)
    return [
        EquipamentoCliente.ativo.is_(True),
        EquipamentoCliente.prox_calibragem.isnot(None),
        EquipamentoCliente.prox_calibragem >= inicio,
        EquipamentoCliente.prox_calibragem <= fim,
        EquipamentoCliente.equipamento.notin_(
            [settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_EBS_ID]
        ),
        EquipamentoCliente.cliente != settings.CLIENTE_ESTOQUE_HS_ID,
    ]


def _linhas(db: Session, ecs) -> list[dict]:
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


def buscar_vencendo(db: Session, competencia: date) -> list[dict]:
    """Uma linha por aparelho com calibracao vencendo NO MES da competencia.

    Cada linha: `{cliente_id, cliente, ec, equipamento_desc, elo}` — mesmo formato da
    Etapa 1, de proposito, para compartilhar `buscar_elo`.

    NAO inclui vencidos (`prox_calibragem < hoje`): esse backlog e' da Etapa 1.
    Exclui hospedeiros (Phoebus/EBS), o cliente de estoque interno da HS e aparelhos
    com OS em andamento (`os_atual` preenchido) — se o cliente ja mandou o aparelho,
    "entre em contato" e' ruido.
    """
    ecs = (
        db.query(EquipamentoCliente)
        .filter(*_filtros_base(competencia), EquipamentoCliente.os_atual.is_(None))
        .order_by(EquipamentoCliente.cliente,
                  EquipamentoCliente.prox_calibragem,
                  EquipamentoCliente.id)
        .all()
    )
    return _linhas(db, ecs)


def buscar_excluidos_por_os(db: Session, competencia: date) -> list[dict]:
    """Quem venceria na competencia mas ficou de fora por ter OS em andamento.

    So alimenta o relatorio — nao vira card. Existe porque a rodada e' uma FOTO UNICA
    do dia 1: quem estiver em OS naquele instante nao e' avisado naquele mes, e sem
    isso a omissao seria silenciosa.
    """
    ecs = (
        db.query(EquipamentoCliente)
        .filter(*_filtros_base(competencia), EquipamentoCliente.os_atual.isnot(None))
        .order_by(EquipamentoCliente.cliente,
                  EquipamentoCliente.prox_calibragem,
                  EquipamentoCliente.id)
        .all()
    )
    return _linhas(db, ecs)


def agrupar_por_cliente(linhas: list[dict]) -> list[list[dict]]:
    """Um grupo por cliente, ordenado por cliente e, dentro do grupo, por vencimento.

    Separado da query de proposito: e' regra pura e da' para testar sem banco.
    """
    grupos: dict[int, list[dict]] = {}
    for linha in linhas:
        grupos.setdefault(linha["cliente_id"], []).append(linha)
    return [
        sorted(grupo, key=lambda l: (l["ec"].prox_calibragem, l["ec"].id))
        for _, grupo in sorted(grupos.items())
    ]


def competencias_padrao(hoje: date) -> list[date]:
    """Mes corrente + mes seguinte — a janela de toda rodada.

    Sao dois meses porque o comercial precisa enxergar 2 meses a' frente. Na pratica
    so o mes de tras ja tem card (volta `created: false`), entao cada rodada cria de
    fato o mes novo da ponta. Nao ha env para isso: quem precisar de outra janela usa
    `--competencia` na mao.
    """
    corrente = hoje.replace(day=1)
    if corrente.month == 12:
        seguinte = corrente.replace(year=corrente.year + 1, month=1)
    else:
        seguinte = corrente.replace(month=corrente.month + 1)
    return [corrente, seguinte]


CAMPOS_RELATORIO = [
    "tipo", "competencia", "cliente_id", "equipamento_cliente_id",
    "serie", "prox_calibragem", "motivo",
]


def _linha_relatorio(linha: dict, competencia: date, tipo: str, motivo: str) -> dict:
    ec = linha["ec"]
    return {
        "tipo": tipo,
        "competencia": f"{competencia:%Y-%m}",
        "cliente_id": linha["cliente_id"],
        "equipamento_cliente_id": ec.id,
        "serie": getattr(ec, "serie", "") or "",
        "prox_calibragem": ec.prox_calibragem.isoformat(),
        "motivo": motivo,
    }


def processar(db: Session, *, competencias: list[date], enviar: bool,
              limite: Optional[int] = None) -> dict:
    """Manda um card por CLIENTE por competencia.

    Best-effort POR CLIENTE: uma excecao num card e' contada em `falhas`, cada
    aparelho daquele cliente vira uma linha em `pendencias` e o laco SEGUE para o
    proximo — nunca aborta a rodada inteira.

    `falhas` conta CLIENTES (a unidade de envio); `pendencias` lista APARELHOS, que e'
    o que o operador precisa para saber quem nao foi comunicado.
    """
    clientes = aparelhos = criados = existentes = falhas = 0
    pendencias: list[dict] = []
    excluidos: list[dict] = []

    for competencia in competencias:
        for linha in buscar_excluidos_por_os(db, competencia):
            excluidos.append(_linha_relatorio(
                linha, competencia, "excluido",
                f"OS em andamento (os_atual={linha['ec'].os_atual})",
            ))

        grupos = agrupar_por_cliente(buscar_vencendo(db, competencia))
        if limite is not None:
            grupos = grupos[:limite]

        for grupo in grupos:
            clientes += 1
            aparelhos += len(grupo)

            # Monta SEMPRE, inclusive em dry-run: e' assim que a simulacao cumpre o
            # que promete — validar que o payload de todo cliente consegue ser construido.
            try:
                card = montar_card_vencendo(grupo, competencia,
                                            settings.HSGROWTH_BOARD_COBRANCA)
            except Exception as exc:  # noqa: BLE001 — melhor esforco por cliente
                falhas += 1
                pendencias.extend(
                    _linha_relatorio(l, competencia, "falha",
                                     f"falha ao montar o card: {exc}") for l in grupo
                )
                continue

            if not enviar:
                continue      # dry-run: montou (validou) e para aqui, sem request

            try:
                resposta = enviar_card_sync(card)
            except Exception as exc:  # noqa: BLE001 — segue para o proximo cliente
                falhas += 1
                pendencias.extend(
                    _linha_relatorio(l, competencia, "falha", str(exc)) for l in grupo
                )
                continue

            if resposta.get("created"):
                criados += 1
            else:
                existentes += 1

    return {
        "clientes": clientes,
        "aparelhos": aparelhos,
        "criados": criados,
        "existentes": existentes,
        "falhas": falhas,
        "pendencias": pendencias,
        "excluidos": excluidos,
    }


def _escrever_csv_relatorio(caminho: str, linhas: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_RELATORIO)
        writer.writeheader()
        for linha in linhas:
            writer.writerow(linha)


def _competencia(texto: str) -> date:
    """Converte `YYYY-MM` num `date` no dia 1. Erro de digitacao morre aqui, no
    argparse — nao pode virar uma rodada vazia silenciosa."""
    try:
        return datetime.strptime(texto, "%Y-%m").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"competencia invalida: {texto!r} (use YYYY-MM, ex.: 2026-08)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Job mensal: cards de calibracao vencendo, um por cliente, "
                    "no board Cobranca do GrowthHS."
    )
    parser.add_argument("--competencia", type=_competencia, action="append", default=None,
                        metavar="YYYY-MM",
                        help="Mes de vencimento a cobrir; repetivel. "
                             "Padrao: mes corrente + mes seguinte.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula: monta tudo e imprime o resumo, sem NENHUM request.")
    parser.add_argument("--limite", type=int, default=None,
                        help="Processa so os N primeiros CLIENTES — para um teste controlado")
    parser.add_argument("--pendencias", default=None, help="Caminho do CSV do relatorio")
    args = parser.parse_args()

    enviar = not args.dry_run
    competencias = args.competencia or competencias_padrao(date.today())

    if enviar and not integracao_ativa():
        print("ERRO: integracao com o GrowthHS esta DESLIGADA "
              "(configure HSGROWTH_BASE_URL e HSGROWTH_API_KEY) — abortando. "
              "Nada foi lido nem enviado.")
        raise SystemExit(1)

    caminho_relatorio = args.pendencias or str(
        _dir_relatorios() / f"pendencias-vencendo-growthhs-{date.today().isoformat()}.csv"
    )
    # Cria o diretorio ANTES de qualquer envio: um caminho invalido precisa falhar
    # rapido, nao depois de ja ter criado cards em producao.
    os.makedirs(os.path.dirname(caminho_relatorio) or ".", exist_ok=True)
    # Nao basta criar o diretorio: se ele ja existe mas pertence a outro usuario
    # (o container roda como root, entao `relatorios/` nasce root), o makedirs passa
    # e a falha so aparece no open() la embaixo — DEPOIS de os cards ja terem sido
    # enviados. Abrir agora, em modo append, transforma isso em falha imediata.
    try:
        open(caminho_relatorio, "a", encoding="utf-8").close()
    except OSError as exc:
        print(f"ERRO: nao consigo gravar o relatorio em {caminho_relatorio}: {exc}\n"
              f"Use --pendencias com um caminho gravavel. Nada foi enviado.")
        raise SystemExit(1)

    db = SessionLocal()
    try:
        r = processar(db, competencias=competencias, enviar=enviar, limite=args.limite)
    finally:
        db.close()

    _escrever_csv_relatorio(caminho_relatorio, r["pendencias"] + r["excluidos"])

    print(f"Competencias: {', '.join(f'{c:%Y-%m}' for c in competencias)}")
    print(f"Clientes: {r['clientes']} / Aparelhos: {r['aparelhos']}")
    if enviar:
        print(f"Criados: {r['criados']} / Ja existentes: {r['existentes']} / "
              f"Falhas: {r['falhas']}")
    else:
        print("MODO DRY-RUN — NADA FOI ENVIADO. Rode sem --dry-run para valer.")
    print(f"Excluidos por OS em andamento: {len(r['excluidos'])}")
    print(f"Relatorio gravado em: {caminho_relatorio}")

    # As falhas vao TAMBEM para o stdout, nao so para o CSV. Em producao a imagem
    # sobe pelo Dockerfile sem bind mount: se RELATORIOS_DIR nao apontar para um
    # volume persistente, o CSV some no redeploy. O stdout, que vai para o log do
    # servico, e' o unico canal que sobrevive sempre — e a falha e' a unica diagnose
    # que este job produz.
    for p in r["pendencias"]:
        print(f"  FALHA aparelho={p['equipamento_cliente_id']} cliente={p['cliente_id']} "
              f"serie={p['serie']} vence={p['prox_calibragem']}: {p['motivo']}")

    # Saida !=0 quando houve falha, para conseguir alertar. Excluido por OS NAO e'
    # falha: e' informacao operacional, o job funcionou como projetado.
    if r["falhas"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
