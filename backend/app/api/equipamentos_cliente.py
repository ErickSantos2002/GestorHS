from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, EquipamentoCliente, HistoricoEquipamento, Ordem, OSCertificado, Cliente, TransferenciaEquipamento, CertificadoVenda
from app.api.deps import get_current_usuario, require_funcao, GESTOR_CADASTRO
from app.api.cadastros_common import excluir_protegido
from app.api.ordens_acoes import agora
from app.core import os_workflow as wf
from app.core.config import settings
from app.schemas.frota import (
    FrotaListOut, FrotaPage, EquipamentoClienteOut,
    EquipamentoClienteCreate, EquipamentoClienteUpdate, HistoricoOut, EquipCertItem,
    TransferirIn, TransferenciaOut,
)
from app.schemas.ordens import OrdemListOut

router = APIRouter(prefix="/equipamentos-cliente", tags=["frota"])
ADMIN = "Administrador"


def _normaliza_serie(valor: str | None) -> str | None:
    """Tira espaços das pontas; string vazia vira None (série é opcional)."""
    valor = (valor or "").strip()
    return valor or None


def _serie_em_uso(db: Session, serie: str | None, excluir_id: int | None = None) -> bool:
    """Série é única no sistema inteiro (comparação sem espaços e sem caixa).
    Série vazia/nula não conflita. `excluir_id` ignora o próprio registro na edição."""
    if serie is None:
        return False
    query = db.query(EquipamentoCliente).filter(
        func.lower(func.trim(EquipamentoCliente.serie)) == serie.lower()
    )
    if excluir_id is not None:
        query = query.filter(EquipamentoCliente.id != excluir_id)
    return query.first() is not None


def _anotar_elo(db: Session, obj) -> None:
    """Preenche o elo conforme o PAPEL do equipamento, sem precisar saber ids de catalogo:
    se ha instalacao aberta com phoebus=obj -> ele e um Phoebus e tem modulo instalado;
    se ha instalacao aberta com modulo=obj -> ele e um modulo e esta dentro de um Phoebus."""
    from app.models import InstalacaoModulo
    obj.modulo_instalado = None
    obj.instalado_em = None
    obj.em_estoque = False

    inst = db.query(InstalacaoModulo).filter(
        InstalacaoModulo.phoebus == obj.id, InstalacaoModulo.saiu_em.is_(None)
    ).first()
    if inst is not None:
        mod = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == inst.modulo).first()
        if mod is not None:
            obj.modulo_instalado = {"id": mod.id, "serie": mod.serie,
                                    "entrou_em": inst.entrou_em, "origem": inst.origem}

    inst_como_modulo = db.query(InstalacaoModulo).filter(
        InstalacaoModulo.modulo == obj.id, InstalacaoModulo.saiu_em.is_(None)
    ).first()
    if inst_como_modulo is not None:
        pho = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == inst_como_modulo.phoebus).first()
        if pho is not None:
            obj.instalado_em = {"id": pho.id, "serie": pho.serie,
                                "cliente_nome": pho.cliente_nome,
                                "entrou_em": inst_como_modulo.entrou_em, "origem": inst_como_modulo.origem}

    if obj.equipamento == settings.EQUIPAMENTO_MODULO_ID and inst_como_modulo is None:
        obj.em_estoque = True


@router.get("", response_model=FrotaPage)
def listar(
    cliente: int | None = None,
    status: str | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(EquipamentoCliente)
    if cliente is not None:
        query = query.filter(EquipamentoCliente.cliente == cliente)
    if status:
        hoje = date.today()
        if status == "vencido":
            query = query.filter(EquipamentoCliente.prox_calibragem < hoje)
        elif status == "vencendo":
            query = query.filter(
                EquipamentoCliente.prox_calibragem >= hoje,
                EquipamentoCliente.prox_calibragem <= hoje + timedelta(days=90),
            )
        elif status == "em_dia":
            query = query.filter(EquipamentoCliente.prox_calibragem > hoje + timedelta(days=90))
        elif status == "sem_data":
            query = query.filter(EquipamentoCliente.prox_calibragem.is_(None))
    if q:
        termo = f"%{q}%"
        query = query.filter(or_(EquipamentoCliente.serie.ilike(termo), EquipamentoCliente.patrimonio.ilike(termo)))
    total = query.count()
    items = query.order_by(EquipamentoCliente.id).offset(offset).limit(limit).all()
    return FrotaPage(items=[FrotaListOut.model_validate(e) for e in items], total=total)


@router.get("/{item_id}", response_model=EquipamentoClienteOut)
def obter(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    _anotar_elo(db, obj)
    return obj


@router.get("/{item_id}/historico", response_model=list[HistoricoOut])
def historico(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first() is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return (
        db.query(HistoricoEquipamento)
        .filter(HistoricoEquipamento.equipamento_cliente == item_id)
        .order_by(HistoricoEquipamento.id)
        .all()
    )


@router.get("/{item_id}/ordens", response_model=list[OrdemListOut])
def ordens_do_aparelho(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first() is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    rows = db.query(Ordem).filter(Ordem.equipamento_cliente == item_id).order_by(Ordem.id.desc()).all()
    return [OrdemListOut.model_validate(o) for o in rows]


@router.get("/{item_id}/certificados", response_model=list[EquipCertItem])
def certificados_do_aparelho(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first() is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    rows = (
        db.query(OSCertificado)
        .join(Ordem, OSCertificado.os == Ordem.id)
        .filter(Ordem.equipamento_cliente == item_id)
        .order_by(OSCertificado.os.desc(), OSCertificado.tipo)
        .all()
    )
    itens = [EquipCertItem(os=c.os, tipo=c.tipo, data_geracao=c.data_geracao, origem="os")
             for c in rows]
    # O de venda e cronologicamente o PRIMEIRO da vida do aparelho, entao fecha a lista
    # (que esta em ordem decrescente). Sempre tipo "C".
    venda = db.query(CertificadoVenda).filter(
        CertificadoVenda.equipamento_cliente == item_id).first()
    if venda is not None:
        itens.append(EquipCertItem(os=None, tipo="C",
                                   data_geracao=venda.data_geracao, origem="venda"))
    return itens


@router.post("", response_model=EquipamentoClienteOut, status_code=http_status.HTTP_201_CREATED)
def criar(dados: EquipamentoClienteCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(*GESTOR_CADASTRO))):
    campos = dados.model_dump()
    campos["serie"] = _normaliza_serie(campos.get("serie"))
    if _serie_em_uso(db, campos["serie"]):
        raise HTTPException(status_code=409, detail="já existe um equipamento com este número de série")
    obj = EquipamentoCliente(**campos)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    _anotar_elo(db, obj)
    return obj


@router.patch("/{item_id}", response_model=EquipamentoClienteOut)
def atualizar(item_id: int, dados: EquipamentoClienteUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(*GESTOR_CADASTRO))):
    obj = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    campos = dados.model_dump(exclude_unset=True)
    if "serie" in campos:
        campos["serie"] = _normaliza_serie(campos["serie"])
        # só valida quando a série muda: não trava a edição de duplicados legados
        if campos["serie"] != _normaliza_serie(obj.serie) and _serie_em_uso(db, campos["serie"], excluir_id=obj.id):
            raise HTTPException(status_code=409, detail="já existe um equipamento com este número de série")
    for chave, valor in campos.items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    _anotar_elo(db, obj)
    return obj


@router.delete("/{item_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)


@router.post("/{item_id}/transferir", response_model=EquipamentoClienteOut)
def transferir(item_id: int, dados: TransferirIn, db: Session = Depends(get_db),
               usuario: Usuario = Depends(require_funcao(*GESTOR_CADASTRO))):
    obj = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    destino = db.query(Cliente).filter(Cliente.id == dados.cliente).first()
    if destino is None:
        raise HTTPException(status_code=404, detail="cliente destino não encontrado")
    if destino.id == obj.cliente:
        raise HTTPException(status_code=400, detail="aparelho já pertence a este cliente")
    ativa = (
        db.query(Ordem)
        .filter(Ordem.equipamento_cliente == obj.id, Ordem.fase.in_(wf.ATIVAS))
        .first()
    )
    if ativa is not None:
        raise HTTPException(status_code=409, detail="finalize ou cancele a OS ativa antes de transferir")
    db.add(TransferenciaEquipamento(
        equipamento_cliente=obj.id,
        de_cliente=obj.cliente,
        para_cliente=destino.id,
        data=agora(),
        usuario=usuario.id,
        obs=dados.obs,
    ))
    obj.cliente = destino.id
    obj.os_atual = None
    db.commit()
    db.refresh(obj)
    _anotar_elo(db, obj)
    return obj


@router.get("/{item_id}/transferencias", response_model=list[TransferenciaOut])
def transferencias(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first() is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return (
        db.query(TransferenciaEquipamento)
        .filter(TransferenciaEquipamento.equipamento_cliente == item_id)
        .order_by(TransferenciaEquipamento.data.desc(), TransferenciaEquipamento.id.desc())
        .all()
    )
