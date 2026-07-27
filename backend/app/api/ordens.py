from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status as http_status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, Cliente, Fase, LogOS, EquipamentoCliente, Caixa, OSCertificado
from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import agora, registrar_log, exige_funcao_da_fase, concluir_laboratorio
from app.core import os_workflow as wf
from app.core import recebimento as rec
from app.core.garantia import garantias as _calc_garantias
from app.core.certificado_gerar import tipos_para, tipos_sem_modelo
from app.core.os_workflow import FASE_FINALIZADA
from app.api.espelhamento import agendar_espelhamento_caixa
from app.schemas.ordens import (
    OrdemListOut, OrdemPage, QuadroColuna, OrdemOut, LogOut, OrdemAbrirIn, AvancarIn,
    CancelarIn, DesfechoLabIn,
)

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


def _anotar_modelos_faltantes(db: Session, ordem) -> None:
    """Anota na OS quais tipos de certificado o aparelho não tem modelo cadastrado.

    A tela usa isso para avisar ANTES de o usuário tentar gerar. Precisa ser aplicado em
    TODA resposta `OrdemOut` — se ficar só no `obter`, o default `[]` do schema faz o
    aviso sumir (e o botão "Gerar" reaparecer) depois de avançar/cancelar a OS.
    """
    ordem.certificado_modelos_faltantes = tipos_sem_modelo(db, ordem, tipos_para(ordem))


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
    _anotar_modelos_faltantes(db, obj)
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
    fase_inicial = cx.fase if cx.fase is not None else wf.FASE_RECEBIDO
    ordem = Ordem(
        cliente=ec.cliente,
        equipamento_cliente=ec.id,
        fase=fase_inicial,
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
    cx.fase = fase_inicial
    registrar_log(db, ordem, usuario, "OS aberta — Recebido")
    db.commit()
    db.refresh(ordem)
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx)
    _anotar_modelos_faltantes(db, ordem)
    return ordem


@router.post("/{ordem_id}/avancar", response_model=OrdemOut)
def avancar(ordem_id: int, dados: AvancarIn, background_tasks: BackgroundTasks,
            db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    raise HTTPException(status_code=409, detail="a OS anda pela caixa; use /caixas/{id}/avancar")


@router.post("/{ordem_id}/desfecho-lab", response_model=OrdemOut)
def marcar_desfecho_lab(ordem_id: int, dados: DesfechoLabIn, db: Session = Depends(get_db),
                        usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    if ordem.fase != wf.FASE_LABORATORIO:
        raise HTTPException(status_code=409, detail="desfecho só no laboratório")
    exige_funcao_da_fase(db, usuario, ordem.fase)
    if dados.desfecho == wf.DESFECHO_CONCLUIDO:
        tem_cert = db.query(OSCertificado).filter(OSCertificado.os == ordem.id).first() is not None
        if not tem_cert:
            raise HTTPException(status_code=409, detail="gere o certificado antes de concluir")
        concluir_laboratorio(db, ordem)
        texto = "Laboratório concluído (aparelho)"
    elif dados.desfecho == wf.DESFECHO_SEM_CONSERTO:
        if not (dados.obs and dados.obs.strip()):
            raise HTTPException(status_code=400, detail="justificativa obrigatória para sem conserto")
        ordem.desfecho_lab = wf.DESFECHO_SEM_CONSERTO
        ordem.desfecho_lab_obs = dados.obs.strip()
        texto = f"Sem conserto: {ordem.desfecho_lab_obs}"
    else:  # liberado — sai do laboratorio sem certificado; justificativa opcional
        ordem.desfecho_lab = wf.DESFECHO_LIBERADO
        ordem.desfecho_lab_obs = (dados.obs or "").strip() or None
        texto = f"Liberado do laboratorio sem certificado: {ordem.desfecho_lab_obs or '(sem motivo)'}"
    registrar_log(db, ordem, usuario, texto)
    db.commit()
    db.refresh(ordem)
    return ordem


@router.post("/{ordem_id}/cancelar", response_model=OrdemOut)
def cancelar(ordem_id: int, dados: CancelarIn, background_tasks: BackgroundTasks,
             db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    raise HTTPException(status_code=409, detail="a OS anda pela caixa; use /caixas/{id}/avancar")
