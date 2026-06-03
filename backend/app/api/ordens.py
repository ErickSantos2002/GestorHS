from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, Cliente, Fase, LogOS, EquipamentoCliente
from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import agora, registrar_log, exige_funcao_da_fase
from app.core import os_workflow as wf
from app.schemas.ordens import OrdemListOut, OrdemPage, QuadroColuna, OrdemOut, LogOut, OrdemAbrirIn, AvancarIn

router = APIRouter(prefix="/ordens", tags=["ordens"])


@router.get("", response_model=OrdemPage)
def listar(
    fase: int | None = None,
    cliente: int | None = None,
    tipo: str | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Ordem)
    if fase is not None:
        query = query.filter(Ordem.fase == fase)
    if cliente is not None:
        query = query.filter(Ordem.cliente == cliente)
    if tipo:
        query = query.filter(Ordem.tipo_servico == tipo)
    if q:
        if q.strip().isdigit():
            query = query.filter(Ordem.id == int(q.strip()))
        else:
            termo = f"%{q}%"
            query = query.join(Cliente, Ordem.cliente == Cliente.id).filter(
                or_(Ordem.etiqueta.ilike(termo), Cliente.nome.ilike(termo))
            )
    total = query.count()
    items = query.order_by(Ordem.id.desc()).offset(offset).limit(limit).all()
    return OrdemPage(items=[OrdemListOut.model_validate(o) for o in items], total=total)


@router.get("/quadro", response_model=list[QuadroColuna])
def quadro(cliente: int | None = None, db: Session = Depends(get_db),
           _: Usuario = Depends(get_current_usuario)):
    fases = {f.id: f for f in db.query(Fase).filter(Fase.id.in_(wf.ATIVAS)).all()}
    colunas: list[QuadroColuna] = []
    for fid in wf.ATIVAS:
        query = db.query(Ordem).filter(Ordem.fase == fid)
        if cliente is not None:
            query = query.filter(Ordem.cliente == cliente)
        ordens = query.order_by(Ordem.id.desc()).all()
        f = fases.get(fid)
        colunas.append(QuadroColuna(
            fase=fid,
            descricao=f.descricao if f else "",
            cor=f.cor if f else "000000",
            ordens=[OrdemListOut.model_validate(o) for o in ordens],
        ))
    return colunas


@router.get("/{ordem_id}", response_model=OrdemOut)
def obter(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return obj


@router.get("/{ordem_id}/logs", response_model=list[LogOut])
def logs(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(Ordem).filter(Ordem.id == ordem_id).first() is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return db.query(LogOS).filter(LogOS.os == ordem_id).order_by(LogOS.id).all()


@router.post("", response_model=OrdemOut, status_code=http_status.HTTP_201_CREATED)
def abrir(dados: OrdemAbrirIn, db: Session = Depends(get_db),
          usuario: Usuario = Depends(require_funcao("Expedição", "Administrador"))):
    ec = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == dados.equipamento_cliente).first()
    if ec is None:
        raise HTTPException(status_code=404, detail="equipamento do cliente não encontrado")
    ativa = (
        db.query(Ordem)
        .filter(Ordem.equipamento_cliente == ec.id, Ordem.fase.in_(wf.ATIVAS))
        .first()
    )
    if ativa is not None:
        raise HTTPException(status_code=409, detail="aparelho já possui OS ativa")
    ordem = Ordem(
        cliente=ec.cliente,
        equipamento_cliente=ec.id,
        fase=wf.FASE_RECEBIDO,
        tipo_servico=dados.tipo_servico,
        condicao_chegada=dados.condicao_chegada,
        acessorios=dados.acessorios,
        data_chegada=agora(),
        recebido=True,
        situacao="E",
    )
    db.add(ordem)
    db.flush()
    ec.os_atual = ordem.id
    registrar_log(db, ordem, usuario, "OS aberta — Recebido")
    db.commit()
    db.refresh(ordem)
    return ordem


@router.post("/{ordem_id}/avancar", response_model=OrdemOut)
def avancar(ordem_id: int, dados: AvancarIn, db: Session = Depends(get_db),
            usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    if not wf.eh_ativa(ordem.fase):
        raise HTTPException(status_code=409, detail="OS já encerrada")
    exige_funcao_da_fase(db, usuario, ordem.fase)
    destino = wf.proxima_fase(ordem.fase)
    origem = ordem.fase

    if origem == 5:                       # Laboratório -> Pós-Vendas
        ordem.data_calibracao = agora()
        texto = "Calibração/manutenção concluída"
    elif origem == 6:                     # Pós-Vendas -> Preparando Retorno
        ordem.aceite = True
        ordem.data_aceite = agora()
        texto = "Aceite registrado"
    elif origem == 7:                     # Preparando Retorno -> Finalizada
        if not (dados.cod_retorno and dados.cod_retorno.strip()):
            raise HTTPException(status_code=422, detail="cod_retorno é obrigatório para finalizar")
        ordem.cod_retorno = dados.cod_retorno.strip()
        ordem.data_retorno = agora()
        ordem.situacao = "F"
        texto = f"Postado para retorno — Finalizada (rastreio: {ordem.cod_retorno})"
    else:                                 # 4 -> 5 (Recebido -> Laboratório)
        texto = "Encaminhado ao laboratório"

    if dados.obs:
        texto = f"{texto} — {dados.obs}"
    ordem.fase = destino
    registrar_log(db, ordem, usuario, texto)
    db.commit()
    db.refresh(ordem)
    return ordem
