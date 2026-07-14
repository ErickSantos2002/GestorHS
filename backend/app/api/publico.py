"""Endpoints públicos (sem autenticação). Hoje: download de certificado e de nota fiscal por token."""
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core import certificado_link, nota_fiscal, nota_fiscal_link, storage
from app.core.certificado_pdf import html_para_pdf
from app.models import OSCertificado, Ordem
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


@router.get("/nota-fiscal/{ordem_id}")
def baixar_nota_fiscal_publica(ordem_id: int, t: str = "", db: Session = Depends(get_db)):
    if not nota_fiscal_link.verificar(ordem_id, t):
        raise HTTPException(status_code=403, detail="link inválido")
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None or not o.nota_fiscal:
        raise HTTPException(status_code=404, detail="nota fiscal não encontrada")
    try:
        caminho = storage.caminho_arquivo(nota_fiscal.subdir(ordem_id), o.nota_fiscal)
    except storage.ArquivoInvalido:
        raise HTTPException(status_code=404, detail="nota fiscal não encontrada")
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    media = nota_fiscal.media_type(o.nota_fiscal)
    return FileResponse(
        caminho,
        media_type=media,
        filename=nota_fiscal.nome_download(ordem_id, o.nota_fiscal),
        headers={"X-Content-Type-Options": "nosniff"},
    )
