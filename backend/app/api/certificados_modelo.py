from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status as http_status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Equipamento, CertificadoModelo, CertificadoImagem
from app.api.deps import get_current_usuario, require_funcao
from app.core import storage
from app.schemas.certificados_modelo import (
    ModeloItem, ModeloPage, CertificadoModeloOut, CertificadoModeloIn,
    ImagemOut, ImagemPage,
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
    com_cert = {row[0] for row in db.query(CertificadoModelo.equipamento).all()}
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


# ---------------------------------------------------------------------------
# Imagens
# ---------------------------------------------------------------------------

_SUBDIR_IMG = "certificado-imagens"


@router.get("/certificado-imagens", response_model=ImagemPage)
def listar_imagens(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    imgs = db.query(CertificadoImagem).order_by(CertificadoImagem.id.desc()).all()
    return ImagemPage(items=[ImagemOut.model_validate(i) for i in imgs])


@router.post("/certificado-imagens", response_model=ImagemOut, status_code=http_status.HTTP_201_CREATED)
def enviar_imagem(
    file: UploadFile = File(...),
    nome: str | None = Form(None),
    db: Session = Depends(get_db),
    _: Usuario = Depends(_escrita),
):
    try:
        basename = storage.salvar_upload(file, subdir=_SUBDIR_IMG, tipos_permitidos=storage.TIPOS_IMAGEM)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    img = CertificadoImagem(arquivo=basename, nome=nome, datacad=datetime.now(timezone.utc))
    db.add(img)
    db.commit()
    db.refresh(img)
    return ImagemOut.model_validate(img)


@router.delete("/certificado-imagens/{img_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def excluir_imagem(img_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    img = db.query(CertificadoImagem).filter(CertificadoImagem.id == img_id).first()
    if img is None:
        raise HTTPException(404, "imagem não encontrada")
    arquivo = img.arquivo
    db.delete(img)
    db.commit()
    storage.remover_arquivo(_SUBDIR_IMG, arquivo)


@router.get("/certificado-imagens/arquivo/{nome}")
def servir_imagem(nome: str):
    # PÚBLICO (sem auth) — assets de certificado embutidos via <img src>
    try:
        caminho = storage.caminho_arquivo(_SUBDIR_IMG, nome)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    if not caminho.exists():
        raise HTTPException(404, "imagem não encontrada")
    return FileResponse(caminho)
