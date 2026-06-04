from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import UsuarioCliente, Cliente, EquipamentoCliente, Ordem, Solicitacao
from app.api.deps import get_current_cliente
from app.api.ordens_acoes import agora
from app.schemas.portal import (
    PortalMeOut, PortalResumoOut,
    PortalFrotaItem, PortalFrotaPage,
    PortalCertItem, PortalCertPage,
    PortalOSItem, PortalOSPage,
)
from app.schemas.solicitacoes import SolicitarIn, PortalSolicitacaoItem, PortalSolicitacaoPage

router = APIRouter(prefix="/portal", tags=["portal"])
_FASES_ATIVAS = (4, 5, 6, 7)


@router.get("/me", response_model=PortalMeOut)
def me(cli: UsuarioCliente = Depends(get_current_cliente), db: Session = Depends(get_db)):
    empresa = db.query(Cliente).filter(Cliente.id == cli.cliente).first()
    return PortalMeOut(
        id=cli.id, login=cli.login, nome=cli.nome, cliente=cli.cliente,
        cliente_nome=empresa.nome if empresa else None,
    )


@router.get("/resumo", response_model=PortalResumoOut)
def resumo(cli: UsuarioCliente = Depends(get_current_cliente), db: Session = Depends(get_db)):
    hoje = date.today()
    base = db.query(EquipamentoCliente).filter(
        EquipamentoCliente.cliente == cli.cliente,
        EquipamentoCliente.ativo.is_(True),
    )
    aparelhos = base.count()
    vencidos = base.filter(EquipamentoCliente.prox_calibragem < hoje).count()
    os_andamento = (
        db.query(Ordem)
        .filter(Ordem.cliente == cli.cliente, Ordem.fase.in_(_FASES_ATIVAS))
        .count()
    )
    return PortalResumoOut(aparelhos=aparelhos, vencidos=vencidos, os_andamento=os_andamento)


@router.get("/minha-frota", response_model=PortalFrotaPage)
def minha_frota(
    status: str | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    cli: UsuarioCliente = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    hoje = date.today()
    limite = hoje + timedelta(days=90)
    query = db.query(EquipamentoCliente).filter(
        EquipamentoCliente.cliente == cli.cliente,
        EquipamentoCliente.ativo.is_(True),
    )
    if status == "vencido":
        query = query.filter(EquipamentoCliente.prox_calibragem < hoje)
    elif status == "vencendo":
        query = query.filter(EquipamentoCliente.prox_calibragem >= hoje, EquipamentoCliente.prox_calibragem <= limite)
    elif status == "em_dia":
        query = query.filter(EquipamentoCliente.prox_calibragem > limite)
    elif status == "sem_data":
        query = query.filter(EquipamentoCliente.prox_calibragem.is_(None))
    if q:
        termo = f"%{q}%"
        query = query.filter(or_(EquipamentoCliente.serie.ilike(termo), EquipamentoCliente.patrimonio.ilike(termo)))
    total = query.count()
    items = query.order_by(EquipamentoCliente.id).offset(offset).limit(limit).all()
    return PortalFrotaPage(items=[PortalFrotaItem.model_validate(e) for e in items], total=total)


@router.get("/certificados", response_model=PortalCertPage)
def certificados(
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    cli: UsuarioCliente = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    base = (
        db.query(EquipamentoCliente, Ordem.pdf_certificado)
        .outerjoin(Ordem, EquipamentoCliente.os_atual == Ordem.id)
        .filter(
            EquipamentoCliente.cliente == cli.cliente,
            EquipamentoCliente.calib_cert.isnot(None),
            EquipamentoCliente.calib_cert != "",
        )
    )
    total = base.count()
    linhas = base.order_by(EquipamentoCliente.ult_calibragem.desc()).offset(offset).limit(limit).all()
    items = [
        PortalCertItem(
            equipamento_cliente=ec.id,
            equipamento_descricao=ec.equipamento_descricao,
            serie=ec.serie,
            calib_cert=ec.calib_cert,
            ult_calibragem=ec.ult_calibragem,
            prox_calibragem=ec.prox_calibragem,
            pdf=pdf,
        )
        for ec, pdf in linhas
    ]
    return PortalCertPage(items=items, total=total)


@router.get("/minhas-os", response_model=PortalOSPage)
def minhas_os(
    em_andamento: bool = False,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    cli: UsuarioCliente = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    query = db.query(Ordem).filter(Ordem.cliente == cli.cliente)
    if em_andamento:
        query = query.filter(Ordem.fase.in_(_FASES_ATIVAS))
    total = query.count()
    items = query.order_by(Ordem.id.desc()).offset(offset).limit(limit).all()
    return PortalOSPage(items=[PortalOSItem.model_validate(o) for o in items], total=total)


@router.post("/solicitar-recalibracao", response_model=PortalSolicitacaoItem, status_code=201)
def solicitar(dados: SolicitarIn, cli: UsuarioCliente = Depends(get_current_cliente), db: Session = Depends(get_db)):
    ec = (
        db.query(EquipamentoCliente)
        .filter(EquipamentoCliente.id == dados.equipamento_cliente, EquipamentoCliente.cliente == cli.cliente)
        .first()
    )
    if ec is None:
        raise HTTPException(status_code=404, detail="aparelho não encontrado")
    pendente = (
        db.query(Solicitacao)
        .filter(Solicitacao.equipamento_cliente == ec.id, Solicitacao.status == "pendente")
        .first()
    )
    if pendente is not None:
        raise HTTPException(status_code=409, detail="já há uma solicitação pendente para este aparelho")
    s = Solicitacao(cliente=cli.cliente, equipamento_cliente=ec.id, status="pendente", data_solicitacao=agora(), obs=dados.obs)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get("/minhas-solicitacoes", response_model=PortalSolicitacaoPage)
def minhas_solicitacoes(
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    cli: UsuarioCliente = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    query = db.query(Solicitacao).filter(Solicitacao.cliente == cli.cliente)
    total = query.count()
    items = query.order_by(Solicitacao.id.desc()).offset(offset).limit(limit).all()
    return PortalSolicitacaoPage(items=[PortalSolicitacaoItem.model_validate(s) for s in items], total=total)
