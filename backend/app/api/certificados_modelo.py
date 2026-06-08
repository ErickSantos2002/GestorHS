from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Equipamento, CertificadoModelo
from app.api.deps import get_current_usuario, require_funcao
from app.schemas.certificados_modelo import (
    ModeloItem, ModeloPage, CertificadoModeloOut, CertificadoModeloIn,
)

router = APIRouter(tags=["certificados-modelo"])

_escrita = require_funcao("Administrador", "Laboratório")


def _equipamento_ou_404(db: Session, equipamento_id: int) -> Equipamento:
    eq = db.query(Equipamento).filter(Equipamento.id == equipamento_id).first()
    if eq is None:
        raise HTTPException(status_code=404, detail="modelo de equipamento não encontrado")
    return eq


@router.get("/certificados-modelo", response_model=ModeloPage)
def listar_modelos(
    q: str | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Equipamento)
    if q:
        query = query.filter(Equipamento.descricao.ilike(f"%{q.strip()}%"))
    equipamentos = query.order_by(Equipamento.descricao).all()
    com_cert = set(db.query(CertificadoModelo.equipamento).scalars().all())
    items = [
        ModeloItem(equipamento=e.id, equipamento_descricao=e.descricao, tem_certificado=e.id in com_cert)
        for e in equipamentos
    ]
    return ModeloPage(items=items)


@router.get("/certificados-modelo/{equipamento_id}", response_model=CertificadoModeloOut)
def obter_modelo(equipamento_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    eq = _equipamento_ou_404(db, equipamento_id)
    cert = db.query(CertificadoModelo).filter(CertificadoModelo.equipamento == equipamento_id).first()
    return CertificadoModeloOut(
        equipamento=eq.id,
        equipamento_descricao=eq.descricao,
        descricao=cert.descricao if cert else None,
        texto=cert.texto if cert else "",
    )


@router.put("/certificados-modelo/{equipamento_id}", response_model=CertificadoModeloOut)
def salvar_modelo(
    equipamento_id: int,
    dados: CertificadoModeloIn,
    db: Session = Depends(get_db),
    _: Usuario = Depends(_escrita),
):
    eq = _equipamento_ou_404(db, equipamento_id)
    cert = db.query(CertificadoModelo).filter(CertificadoModelo.equipamento == equipamento_id).first()
    if cert is None:
        cert = CertificadoModelo(equipamento=equipamento_id)
        db.add(cert)
    cert.texto = dados.texto
    cert.descricao = dados.descricao
    db.commit()
    db.refresh(cert)
    return CertificadoModeloOut(
        equipamento=eq.id,
        equipamento_descricao=eq.descricao,
        descricao=cert.descricao,
        texto=cert.texto or "",
    )
