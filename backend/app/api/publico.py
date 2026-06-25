"""Endpoints públicos (sem autenticação). Hoje: download de certificado por token."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core import certificado_link
from app.core.certificado_pdf import html_para_pdf
from app.models import OSCertificado
from app.models.database import get_db

router = APIRouter(prefix="/publico", tags=["publico"])

# nome público -> código do tipo no OSCertificado
_TIPO_POR_NOME = {v: k for k, v in certificado_link.NOME_PUBLICO.items()}  # calibracao->C, manutencao->M


@router.get("/certificado/{ordem_id}/{tipo}")
def baixar_certificado_publico(ordem_id: int, tipo: str, t: str = "", db: Session = Depends(get_db)):
    tipo_codigo = _TIPO_POR_NOME.get(tipo)
    if tipo_codigo is None:
        raise HTTPException(status_code=404, detail="tipo inválido")
    if not certificado_link.verificar(ordem_id, tipo_codigo, t):
        raise HTTPException(status_code=403, detail="link inválido")
    osc = db.query(OSCertificado).filter(
        OSCertificado.os == ordem_id, OSCertificado.tipo == tipo_codigo
    ).first()
    if osc is None or not osc.html:
        raise HTTPException(status_code=404, detail="certificado não encontrado")
    try:
        pdf = html_para_pdf(osc.html)
    except Exception:
        raise HTTPException(status_code=500, detail="falha ao gerar PDF")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="certificado-{ordem_id}-{tipo}.pdf"'},
    )
