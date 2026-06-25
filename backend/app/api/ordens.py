from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status as http_status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, Cliente, Fase, LogOS, EquipamentoCliente, Caixa, OSCertificado
from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import agora, registrar_log, exige_funcao_da_fase, espelhar_calibracao
from app.core import os_workflow as wf
from app.core import recebimento as rec
from app.core import taskhs
from app.core.garantia import garantias as _calc_garantias
from app.core.os_workflow import FASE_FINALIZADA
from app.integrations import taskhs_client
from app.schemas.ordens import OrdemListOut, OrdemPage, QuadroColuna, OrdemOut, LogOut, OrdemAbrirIn, AvancarIn, CancelarIn

router = APIRouter(prefix="/ordens", tags=["ordens"])

LIMITE_FINALIZADAS_QUADRO = 300


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
    fases_ids = list(wf.ATIVAS) + [wf.FASE_FINALIZADA]
    fases = {f.id: f for f in db.query(Fase).filter(Fase.id.in_(fases_ids)).all()}
    colunas: list[QuadroColuna] = []
    for fid in fases_ids:
        query = db.query(Ordem).filter(Ordem.fase == fid)
        if cliente is not None:
            query = query.filter(Ordem.cliente == cliente)
        total = query.count()
        ordenadas = query.order_by(Ordem.id.desc())
        if fid == wf.FASE_FINALIZADA:
            ordenadas = ordenadas.limit(LIMITE_FINALIZADAS_QUADRO)
        ordens = ordenadas.all()
        f = fases.get(fid)
        colunas.append(QuadroColuna(
            fase=fid,
            descricao=f.descricao if f else "",
            cor=f.cor if f else "000000",
            total=total,
            ordens=[OrdemListOut.model_validate(o) for o in ordens],
        ))
    return colunas


def _ultima_manutencao(db: Session, equipamento_cliente_id: int) -> date | None:
    """Data da última manutenção: data_calibracao da OS finalizada mais recente
    com tipo_servico em ('M', 'A') para o aparelho."""
    o = (
        db.query(Ordem)
        .filter(
            Ordem.equipamento_cliente == equipamento_cliente_id,
            Ordem.tipo_servico.in_(("M", "A")),
            Ordem.fase == FASE_FINALIZADA,
            Ordem.data_calibracao.isnot(None),
        )
        .order_by(Ordem.data_calibracao.desc())
        .first()
    )
    return o.data_calibracao.date() if o is not None else None


@router.get("/{ordem_id}", response_model=OrdemOut)
def obter(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    eqc = obj.equipamento_rel
    if eqc is not None:
        obj.garantias = _calc_garantias(
            datacompra=eqc.datacompra,
            ult_calibragem=eqc.ult_calibragem,
            ult_manutencao=_ultima_manutencao(db, eqc.id),
            hoje=date.today(),
        )
    else:
        obj.garantias = None
    return obj


@router.get("/{ordem_id}/logs", response_model=list[LogOut])
def logs(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(Ordem).filter(Ordem.id == ordem_id).first() is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return db.query(LogOS).filter(LogOS.os == ordem_id).order_by(LogOS.id).all()


@router.post("", response_model=OrdemOut, status_code=http_status.HTTP_201_CREATED)
def abrir(dados: OrdemAbrirIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db),
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
    if dados.caixa is None:
        raise HTTPException(status_code=400, detail="É obrigatório vincular uma caixa à OS")
    cx = db.query(Caixa).filter(Caixa.id == dados.caixa).first()
    if cx is None:
        raise HTTPException(status_code=404, detail="caixa não encontrada")
    if dados.condicao_chegada is not None and dados.condicao_chegada not in rec.CONDICOES_CHEGADA:
        raise HTTPException(status_code=400, detail="condição de chegada inválida")
    try:
        checklist_csv = rec.checklist_ids_para_csv(dados.checklist)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if dados.data_chegada is not None:
        data_chegada = datetime(
            dados.data_chegada.year, dados.data_chegada.month, dados.data_chegada.day,
            tzinfo=timezone.utc,
        )
    else:
        data_chegada = agora()
    ordem = Ordem(
        cliente=ec.cliente,
        equipamento_cliente=ec.id,
        fase=wf.FASE_RECEBIDO,
        tipo_servico=dados.tipo_servico,
        condicao_chegada=dados.condicao_chegada,
        checklist=checklist_csv,
        pilhas=dados.pilhas or 0,
        sopradores=dados.bocais or 0,
        obs=dados.observacoes,
        data_chegada=data_chegada,
        recebido=True,
        situacao="E",
        caixa=dados.caixa,
    )
    db.add(ordem)
    db.flush()
    ec.os_atual = ordem.id
    registrar_log(db, ordem, usuario, "OS aberta — Recebido")
    db.commit()
    db.refresh(ordem)
    if taskhs_client.integracao_ativa():
        payload = taskhs.montar_payload(ordem, lista=taskhs.lista_da_fase(ordem.fase), arquivado=False)
        background_tasks.add_task(taskhs_client.enviar_card, payload)
    return ordem


@router.post("/{ordem_id}/avancar", response_model=OrdemOut)
def avancar(ordem_id: int, dados: AvancarIn, background_tasks: BackgroundTasks,
            db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    if not wf.eh_ativa(ordem.fase):
        raise HTTPException(status_code=409, detail="OS já encerrada")
    exige_funcao_da_fase(db, usuario, ordem.fase)
    destino = wf.proxima_fase(ordem.fase)
    origem = ordem.fase

    if origem == 5:                       # Laboratório -> Pós-Vendas
        tem_cert = db.query(OSCertificado).filter(OSCertificado.os == ordem.id).first() is not None
        if not tem_cert:
            raise HTTPException(status_code=409, detail="gere o certificado antes de concluir o laboratório")
        if dados.prox_calibragem is not None:
            ordem.prox_calibragem = dados.prox_calibragem
        espelhar_calibracao(db, ordem)
        texto = "Laboratório concluído"
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
    if taskhs_client.integracao_ativa():
        lista = taskhs.lista_da_fase(ordem.fase)
        if lista is not None:
            payload = taskhs.montar_payload(ordem, lista=lista, arquivado=False)
            background_tasks.add_task(taskhs_client.enviar_card, payload)
    return ordem


@router.post("/{ordem_id}/cancelar", response_model=OrdemOut)
def cancelar(ordem_id: int, dados: CancelarIn, background_tasks: BackgroundTasks,
             db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    if not wf.eh_ativa(ordem.fase):
        raise HTTPException(status_code=409, detail="OS já encerrada")
    exige_funcao_da_fase(db, usuario, ordem.fase)
    origem = ordem.fase
    ordem.fase = wf.FASE_CANCELADA
    ordem.situacao = "C"
    registrar_log(db, ordem, usuario, f"OS cancelada: {dados.motivo}")
    db.commit()
    db.refresh(ordem)
    if taskhs_client.integracao_ativa():
        lista = taskhs.lista_da_fase(origem)
        if lista is not None:
            payload = taskhs.montar_payload(ordem, lista=lista, arquivado=True)
            background_tasks.add_task(taskhs_client.enviar_card, payload)
    return ordem
