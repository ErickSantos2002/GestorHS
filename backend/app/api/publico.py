"""Endpoints públicos (sem autenticação). Hoje: download de certificado, nota fiscal e proposta por token."""
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core import (
    certificado_geral_link,
    certificado_link,
    nota_fiscal,
    nota_fiscal_link,
    proposta_link,
    proposta_pdf,
    storage,
)
from app.core.certificado_pdf import html_para_pdf
from app.models import CertificadoGeral, OSCertificado, Ordem, Proposta
from app.models.database import get_db

router = APIRouter(prefix="/publico", tags=["publico"])

SUBDIR_CERT_GERAL = "certificados-gerais"

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


def _servir_nota_fiscal(ordem_id: int, basename: str | None):
    if not basename:
        raise HTTPException(status_code=404, detail="nota fiscal não encontrada")
    try:
        caminho = storage.caminho_arquivo(nota_fiscal.subdir(ordem_id), basename)
    except storage.ArquivoInvalido:
        raise HTTPException(status_code=404, detail="nota fiscal não encontrada")
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    return FileResponse(
        caminho,
        media_type=nota_fiscal.media_type(basename),
        filename=nota_fiscal.nome_download(ordem_id, basename),
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/nota-fiscal/{ordem_id}")
def baixar_nota_fiscal_publica(ordem_id: int, t: str = "", db: Session = Depends(get_db)):
    if not nota_fiscal_link.verificar(ordem_id, t):
        raise HTTPException(status_code=403, detail="link inválido")
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    return _servir_nota_fiscal(ordem_id, o.nota_fiscal if o else None)


@router.get("/nota-fiscal/{ordem_id}/xml")
def baixar_nota_fiscal_xml_publica(ordem_id: int, t: str = "", db: Session = Depends(get_db)):
    """Rota separada, e token separado do PDF: sao dois arquivos distintos."""
    if not nota_fiscal_link.verificar(ordem_id, t, nota_fiscal_link.XML):
        raise HTTPException(status_code=403, detail="link inválido")
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    return _servir_nota_fiscal(ordem_id, o.nota_fiscal_xml if o else None)


@router.get("/proposta/{proposta_id}")
def baixar_proposta_publica(proposta_id: int, t: str = "", db: Session = Depends(get_db)):
    if not proposta_link.verificar(proposta_id, t):
        raise HTTPException(status_code=403, detail="link inválido")
    # Desabilitar tira a proposta de circulação aqui também: o link vive no card do
    # TaskHS e continuaria servindo o PDF de uma proposta que a equipe tirou do ar.
    desabilitada = (
        db.query(Proposta.id)
        .filter(Proposta.id == proposta_id, Proposta.is_deleted.is_(True))
        .first()
    )
    if desabilitada is not None:
        raise HTTPException(status_code=404, detail="proposta não encontrada")
    try:
        conteudo = proposta_pdf.gerar_pdf(db, proposta_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="proposta não encontrada")
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="proposta-{proposta_id}.pdf"'},
    )


@router.get("/certificado-geral/{cert_id}")
def baixar_certificado_geral_publico(cert_id: int, t: str = "", db: Session = Depends(get_db)):
    if not certificado_geral_link.verificar(cert_id, t):
        raise HTTPException(status_code=403, detail="link inválido")
    c = db.query(CertificadoGeral).filter(CertificadoGeral.id == cert_id).first()
    if c is None or not c.arquivo:
        raise HTTPException(status_code=404, detail="certificado não encontrado")
    try:
        caminho = storage.caminho_arquivo(SUBDIR_CERT_GERAL, c.arquivo)
    except storage.ArquivoInvalido:
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    return FileResponse(
        caminho,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="certificado-geral-{cert_id}.pdf"',
            "X-Content-Type-Options": "nosniff",
        },
    )
