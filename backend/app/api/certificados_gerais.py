from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario, require_funcao
from app.core import certificado_geral_link, storage
from app.models import CertificadoGeral, Usuario
from app.models.database import get_db
from app.schemas.certificado_geral import CertificadoGeralOut

router = APIRouter(prefix="/certificados-gerais", tags=["certificados-gerais"])

GESTOR_CERT_GERAL = ("Administrador", "Laboratório", "Qualidade")
SUBDIR = "certificados-gerais"


def _out(c: CertificadoGeral) -> CertificadoGeralOut:
    dto = CertificadoGeralOut.model_validate(c)
    dto.link = certificado_geral_link.link_certificado_geral(c.id)
    return dto


@router.post("", response_model=CertificadoGeralOut, status_code=status.HTTP_201_CREATED)
def anexar(nome: str = Form(...), arquivo: UploadFile = File(...),
           db: Session = Depends(get_db),
           usuario: Usuario = Depends(require_funcao(*GESTOR_CERT_GERAL))):
    nome_limpo = (nome or "").strip()
    if not nome_limpo:
        raise HTTPException(422, "nome é obrigatório")
    if len(nome_limpo) > 200:
        raise HTTPException(422, "nome muito longo (máx. 200)")
    try:
        basename = storage.salvar_upload(arquivo, subdir=SUBDIR, tipos_permitidos=storage.TIPOS_PDF)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    c = CertificadoGeral(nome=nome_limpo, arquivo=basename, usuario=usuario.id,
                         data_upload=datetime.now(timezone.utc))
    db.add(c); db.commit(); db.refresh(c)
    return _out(c)


@router.get("", response_model=list[CertificadoGeralOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    itens = db.query(CertificadoGeral).order_by(CertificadoGeral.id.desc()).all()
    return [_out(c) for c in itens]


@router.delete("/{cert_id}")
def excluir(cert_id: int, db: Session = Depends(get_db),
            _: Usuario = Depends(require_funcao(*GESTOR_CERT_GERAL))):
    c = db.query(CertificadoGeral).filter(CertificadoGeral.id == cert_id).first()
    if c is None:
        raise HTTPException(404, "certificado não encontrado")
    storage.remover_arquivo(SUBDIR, c.arquivo)
    db.delete(c); db.commit()
    return {"ok": True}
