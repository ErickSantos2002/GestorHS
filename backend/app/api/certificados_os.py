from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, OSCertificado
from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import agora
from app.core.certificado_gerar import gerar_certificados, tipos_para
from app.schemas.ordens import GerarCertificadoIn
from app.schemas.certificados_modelo import OSCertificadoOut

router = APIRouter(tags=["certificados-os"])

_gerar = require_funcao("Laboratório", "Administrador")

_CAMPOS_CALIB = (
    "tipo_calibragem", "calib_cert", "calib_temp", "calib_pressao",
    "calib_teste1", "calib_teste2", "calib_teste3", "calib_teste_media", "calib_situacao",
)


def _os_ou_404(db: Session, ordem_id: int) -> Ordem:
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return o


@router.get("/ordens/{ordem_id}/certificados", response_model=list[OSCertificadoOut])
def listar_os_certificados(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    _os_ou_404(db, ordem_id)
    cs = db.query(OSCertificado).filter(OSCertificado.os == ordem_id).order_by(OSCertificado.tipo).all()
    return [OSCertificadoOut.model_validate(c) for c in cs]


@router.post("/ordens/{ordem_id}/gerar-certificado", response_model=list[OSCertificadoOut])
def gerar(ordem_id: int, dados: GerarCertificadoIn | None = None, db: Session = Depends(get_db), _: Usuario = Depends(_gerar)):
    ordem = _os_ou_404(db, ordem_id)
    if dados is not None:
        for campo in _CAMPOS_CALIB:
            setattr(ordem, campo, getattr(dados, campo))
        ordem.data_calibracao = agora()
        db.flush()
    gerados = gerar_certificados(db, ordem, tipos_para(ordem))
    db.commit()
    for g in gerados:
        db.refresh(g)
    return [OSCertificadoOut.model_validate(c) for c in gerados]
