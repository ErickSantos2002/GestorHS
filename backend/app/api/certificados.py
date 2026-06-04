from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem
from app.api.deps import get_current_usuario, require_funcao
from app.core import storage

router = APIRouter(tags=["certificados"])
GESTOR_CERT = ("Laboratório", "Administrador")


def _os_ou_404(db: Session, ordem_id: int) -> Ordem:
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None:
        raise HTTPException(404, "OS não encontrada")
    return o


def servir_certificado(ordem: Ordem):
    pdf = ordem.pdf_certificado
    if not pdf:
        raise HTTPException(404, "sem certificado")
    if pdf.startswith("http"):
        return RedirectResponse(pdf)
    caminho = storage.caminho_arquivo(f"certificados/{ordem.id}", pdf)
    if not caminho.exists():
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(caminho, media_type="application/pdf")


@router.post("/ordens/{ordem_id}/certificado")
def enviar_certificado(
    ordem_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_funcao(*GESTOR_CERT)),
):
    o = _os_ou_404(db, ordem_id)
    anterior = o.pdf_certificado
    try:
        basename = storage.salvar_upload(file, subdir=f"certificados/{ordem_id}", tipos_permitidos=storage.TIPOS_PDF)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    if anterior and not anterior.startswith("http"):
        storage.remover_arquivo(f"certificados/{ordem_id}", anterior)
    o.pdf_certificado = basename
    db.commit()
    return {"pdf_certificado": basename}


@router.get("/ordens/{ordem_id}/certificado")
def baixar_certificado(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return servir_certificado(_os_ou_404(db, ordem_id))
