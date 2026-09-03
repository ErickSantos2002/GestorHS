from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, LogIntegracao, Ordem, Caixa
from app.api.deps import require_funcao
from app.core import fluxo_modulo
from app.core.caixa import ordens_do_card
from app.core.log_integracao import referencia_e_de_caixa
from app.integrations import taskhs_client, hsgrowth_client
from app.schemas.logs_integracao import LogsPage, LogIntegracaoOut, EstadoIntegracoes, ReenvioOut

router = APIRouter(prefix="/logs-integracao", tags=["integracao"])
ADMIN = "Administrador"


def _payload_de_modulo(db: Session, payload: dict) -> bool:
    """True se o payload reenviado aponta para uma OS ou caixa de modulo/phoebus.

    O `external_id` do payload e' string e o MESMO source/tipo serve tanto para
    card de OS quanto de caixa -- nao da pra saber, so pelo payload, qual das
    duas interpretacoes o numero representa. Por isso testamos as DUAS: existe
    uma Ordem com esse id que e' de modulo, OU existe uma Caixa com esse id cujas
    OS ativas sao de modulo. Custo assimetrico e' proposital: recusar de mais
    custa um clique perdido; deixar passar ressuscita um card que a equipe
    arquivou a mao.
    """
    external_id = payload.get("external_id") if payload else None
    if external_id is None:
        return False
    try:
        ident = int(external_id)
    except (TypeError, ValueError):
        return False
    ordem = db.query(Ordem).filter(Ordem.id == ident).first()
    if ordem is not None and fluxo_modulo.os_de_modulo(ordem):
        return True
    caixa = db.query(Caixa).filter(Caixa.id == ident).first()
    if caixa is not None and fluxo_modulo.caixa_de_modulo(ordens_do_card(caixa)):
        return True
    return False


def _saida(row: LogIntegracao) -> LogIntegracaoOut:
    """Linha do banco -> linha da tela, com o tipo da referencia resolvido."""
    out = LogIntegracaoOut.model_validate(row)
    if out.referencia_os is not None:
        out.referencia_tipo = "caixa" if referencia_e_de_caixa(row.payload) else "os"
    return out


@router.get("", response_model=LogsPage)
def listar(
    integracao: str | None = None,
    status: str | None = None,
    tipo: str | None = None,
    os: int | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_funcao(ADMIN)),
):
    query = db.query(LogIntegracao)
    if integracao:
        query = query.filter(LogIntegracao.integracao == integracao)
    if status:
        query = query.filter(LogIntegracao.status == status)
    if tipo:
        query = query.filter(LogIntegracao.tipo == tipo)
    if os is not None:
        query = query.filter(LogIntegracao.referencia_os == os)
    if q:
        termo = f"%{q}%"
        query = query.filter(or_(LogIntegracao.external_id.ilike(termo),
                                 LogIntegracao.resposta.ilike(termo)))
    total = query.count()
    items = query.order_by(LogIntegracao.id.desc()).offset(offset).limit(limit).all()
    estado = EstadoIntegracoes(
        taskhs_ativo=taskhs_client.integracao_ativa(),
        growthhs_ativo=hsgrowth_client.integracao_ativa(),
    )
    return LogsPage(items=[_saida(i) for i in items], total=total, estado=estado)


@router.post("/{log_id}/reenviar", response_model=ReenvioOut)
def reenviar(log_id: int, db: Session = Depends(get_db),
             _: Usuario = Depends(require_funcao(ADMIN))):
    row = db.query(LogIntegracao).filter(LogIntegracao.id == log_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="log nao encontrado")
    if not row.payload:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT,
                            detail="linha sem payload, nao e reenviavel")
    if _payload_de_modulo(db, row.payload):
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT,
                            detail="caixa de modulo/phoebus nao vai para as integracoes")
    cliente = taskhs_client if row.integracao == "taskhs" else hsgrowth_client
    try:
        cliente.enviar_card_sync(row.payload)  # loga a nova linha de resultado
        return ReenvioOut(ok=True, mensagem="reenviado")
    except Exception as e:
        return ReenvioOut(ok=False, mensagem=str(e)[:500])
