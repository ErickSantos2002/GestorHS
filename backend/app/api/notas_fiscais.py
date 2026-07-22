from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, Caixa
from app.api.deps import get_current_usuario, require_funcao
from app.api.espelhamento import agendar_espelhamento as _agendar_espelhamento, agendar_espelhamento_caixa
from app.core import nota_fiscal, storage, taskhs, os_workflow as wf
from app.schemas.caixas import CaixaDetalhe

router = APIRouter(tags=["notas-fiscais"])
GESTOR_NF = ("Financeiro", "Administrador")


def _os_ou_404(db: Session, ordem_id: int) -> Ordem:
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None:
        raise HTTPException(404, "OS não encontrada")
    return o


def _caixa_ou_404(db: Session, caixa_id: int) -> Caixa:
    cx = db.query(Caixa).filter(Caixa.id == caixa_id).first()
    if cx is None:
        raise HTTPException(404, "caixa não encontrada")
    return cx


def _ordens_ativas_caixa(cx: Caixa) -> list[Ordem]:
    return [o for o in cx.ordens if wf.eh_ativa(o.fase)]


@router.post("/ordens/{ordem_id}/nota-fiscal")
def enviar_nota_fiscal(
    ordem_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    numero: str = Form(...),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_funcao(*GESTOR_NF)),
):
    o = _os_ou_404(db, ordem_id)
    num = (numero or "").strip()
    if not num:
        raise HTTPException(422, "número da nota fiscal é obrigatório")
    if len(num) > 50:
        raise HTTPException(422, "número da nota fiscal muito longo (máx. 50)")
    anterior = o.nota_fiscal
    try:
        basename = storage.salvar_upload(
            file, subdir=nota_fiscal.subdir(ordem_id), tipos_permitidos=storage.TIPOS_NOTA_FISCAL
        )
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    if anterior:
        storage.remover_arquivo(nota_fiscal.subdir(ordem_id), anterior)
    o.nota_fiscal = basename
    o.nota_fiscal_numero = num
    db.commit()
    db.refresh(o)
    _agendar_espelhamento(db, background_tasks, o, list_id=taskhs.list_id_da_fase(o.fase), arquivado=False)
    return {"nota_fiscal": basename, "nota_fiscal_numero": num}


@router.get("/ordens/{ordem_id}/nota-fiscal")
def baixar_nota_fiscal(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    o = _os_ou_404(db, ordem_id)
    if not o.nota_fiscal:
        raise HTTPException(404, "sem nota fiscal")
    try:
        caminho = storage.caminho_arquivo(nota_fiscal.subdir(ordem_id), o.nota_fiscal)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    if not caminho.exists():
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(
        caminho,
        media_type=nota_fiscal.media_type(o.nota_fiscal),
        filename=nota_fiscal.nome_download(ordem_id, o.nota_fiscal),
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.post("/caixas/{caixa_id}/nota-fiscal", response_model=CaixaDetalhe)
def enviar_nota_fiscal_caixa(
    caixa_id: int,
    background_tasks: BackgroundTasks,
    arquivo: UploadFile = File(...),
    numero: str = Form(...),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_funcao(*GESTOR_NF)),
):
    cx = _caixa_ou_404(db, caixa_id)
    ativas = _ordens_ativas_caixa(cx)
    if not ativas:
        raise HTTPException(409, "caixa sem OS ativa")
    num = (numero or "").strip()
    if not num:
        raise HTTPException(422, "número da nota fiscal é obrigatório")
    if len(num) > 50:
        raise HTTPException(422, "número da nota fiscal muito longo (máx. 50)")
    # grava uma copia fisica no subdir de CADA OS ativa: o download e por-OS
    # (GET /ordens/{id}/nota-fiscal procura o arquivo no subdir daquela OS), entao
    # so setar o basename sem gravar o arquivo la quebraria o download das demais.
    for o in ativas:
        arquivo.file.seek(0)
        anterior = o.nota_fiscal
        try:
            basename = storage.salvar_upload(
                arquivo, subdir=nota_fiscal.subdir(o.id), tipos_permitidos=storage.TIPOS_NOTA_FISCAL
            )
        except storage.ArquivoInvalido as e:
            raise HTTPException(e.status, e.detail)
        if anterior:
            storage.remover_arquivo(nota_fiscal.subdir(o.id), anterior)
        o.nota_fiscal = basename
        o.nota_fiscal_numero = num
    db.commit()
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx)
    return cx
