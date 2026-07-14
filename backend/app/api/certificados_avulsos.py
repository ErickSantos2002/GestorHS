from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario, require_funcao
from app.core.certificado_gerar import montar_contexto_avulso, preencher
from app.core.certificado_pdf import html_para_pdf
from app.models import CertificadoAvulso, CertificadoModelo, Usuario
from app.models.database import get_db
from app.schemas.certificado_avulso import CertificadoAvulsoIn, CertificadoAvulsoOut

router = APIRouter(prefix="/certificados-avulsos", tags=["certificados-avulsos"])

_GERAR = require_funcao("Laboratório", "Administrador")
_LABEL_TIPO = {"C": "Calibração", "M": "Manutenção"}


@router.post("", response_model=CertificadoAvulsoOut, status_code=status.HTTP_201_CREATED)
def gerar(dados: CertificadoAvulsoIn, db: Session = Depends(get_db),
          usuario: Usuario = Depends(_GERAR)):
    modelo = db.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento == dados.equipamento,
        CertificadoModelo.tipo == dados.tipo,
    ).first()
    if modelo is None or not modelo.texto:
        rotulo = _LABEL_TIPO.get(dados.tipo, dados.tipo)
        raise HTTPException(
            status_code=409,
            detail=f"O aparelho escolhido não tem modelo de certificado de {rotulo} cadastrado.",
        )
    html = preencher(modelo.texto, montar_contexto_avulso(dados.model_dump()))
    av = CertificadoAvulso(
        tipo=dados.tipo,
        html=html,
        nomecli=dados.nomecli,
        serie=dados.serie,
        calib_cert=dados.calib_cert,
        data_calibracao=dados.data_calibracao,
        usuario=usuario.id,
        data_geracao=datetime.now(timezone.utc),
    )
    db.add(av)
    db.commit()
    db.refresh(av)
    return av


@router.get("", response_model=list[CertificadoAvulsoOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(CertificadoAvulso).order_by(CertificadoAvulso.id.desc()).all()


@router.get("/{avulso_id}/pdf")
def baixar_pdf(avulso_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    av = db.query(CertificadoAvulso).filter(CertificadoAvulso.id == avulso_id).first()
    if av is None:
        raise HTTPException(status_code=404, detail="certificado não encontrado")
    try:
        pdf = html_para_pdf(av.html)
    except Exception:
        raise HTTPException(status_code=500, detail="falha ao gerar PDF")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificado-avulso-{av.id}.pdf"'},
    )
