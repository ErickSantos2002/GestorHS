from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, Foto
from app.api.deps import get_current_usuario, require_funcao
from app.core import storage
from app.schemas.fotos import FotoOut

router = APIRouter(tags=["fotos"])
GESTOR_FOTOS = ("Expedição", "Administrador")


def _os_ou_404(db: Session, ordem_id: int) -> Ordem:
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None:
        raise HTTPException(404, "OS não encontrada")
    return o


def _to_out(f: Foto) -> FotoOut:
    return FotoOut(id=f.id, os=f.os, arquivo=f.arquivo, legenda=f.legenda,
                   url=f"/ordens/{f.os}/fotos/{f.id}/arquivo")


@router.post("/ordens/{ordem_id}/fotos", response_model=FotoOut, status_code=201)
def enviar_foto(
    ordem_id: int,
    file: UploadFile = File(...),
    legenda: str | None = Form(None),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_funcao(*GESTOR_FOTOS)),
):
    o = _os_ou_404(db, ordem_id)
    try:
        basename = storage.salvar_upload(file, subdir=f"os/{ordem_id}", tipos_permitidos=storage.TIPOS_IMAGEM)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    foto = Foto(os=ordem_id, cliente=o.cliente, arquivo=basename, legenda=legenda, tipo="I")
    db.add(foto); db.commit(); db.refresh(foto)
    return _to_out(foto)


@router.get("/ordens/{ordem_id}/fotos", response_model=list[FotoOut])
def listar_fotos(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    fotos = db.query(Foto).filter(Foto.os == ordem_id).order_by(Foto.id).all()
    return [_to_out(f) for f in fotos]


@router.get("/ordens/{ordem_id}/fotos/{foto_id}/arquivo")
def baixar_foto(ordem_id: int, foto_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    foto = db.query(Foto).filter(Foto.id == foto_id, Foto.os == ordem_id).first()
    if foto is None:
        raise HTTPException(404, "foto não encontrada")
    caminho = storage.caminho_arquivo(f"os/{ordem_id}", foto.arquivo)
    if not caminho.exists():
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(caminho)


@router.delete("/fotos/{foto_id}", status_code=204)
def excluir_foto(foto_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(*GESTOR_FOTOS))):
    foto = db.query(Foto).filter(Foto.id == foto_id).first()
    if foto is None:
        raise HTTPException(404, "foto não encontrada")
    storage.remover_arquivo(f"os/{foto.os}", foto.arquivo)
    db.delete(foto); db.commit()
