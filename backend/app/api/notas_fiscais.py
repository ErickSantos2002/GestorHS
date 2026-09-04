from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, Caixa, NotaFiscal
from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import agora, registrar_log
from app.api.espelhamento import agendar_espelhamento_caixa
from app.core import nota_fiscal, storage, os_workflow as wf
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


def _validar_numero(numero: str) -> str:
    num = (numero or "").strip()
    if not num:
        raise HTTPException(422, "número da nota fiscal é obrigatório")
    if len(num) > 50:
        raise HTTPException(422, "número da nota fiscal muito longo (máx. 50)")
    return num


# Anexar e remover valem no Financeiro (10) e em Preparando Retorno (7): e' a
# janela em que o Financeiro ainda consegue corrigir a nota errada. Lista
# explicita, NUNCA `fase >= 7` — o ID 10 e' maior que o 7 mas vem antes dele.
FASES_NOTA = (wf.FASE_FINANCEIRO, wf.FASE_PREPARANDO)


def _exigir_fase_de_nota(cx: Caixa) -> None:
    if cx.fase not in FASES_NOTA:
        raise HTTPException(
            409, "a nota fiscal só pode ser anexada ou removida no Financeiro ou em Preparando Retorno")


def _nota_ou_404(db: Session, cx: Caixa, nota_id: int) -> NotaFiscal:
    nf = db.query(NotaFiscal).filter(NotaFiscal.id == nota_id,
                                     NotaFiscal.caixa == cx.id).first()
    if nf is None:
        raise HTTPException(404, "nota fiscal não encontrada")
    return nf


@router.post("/caixas/{caixa_id}/notas-fiscais", response_model=CaixaDetalhe)
def anexar_notas_fiscais(
    caixa_id: int,
    background_tasks: BackgroundTasks,
    arquivos_pdf: list[UploadFile] = File(...),
    arquivos_xml: list[UploadFile] = File(...),
    numeros: list[str] = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_funcao(*GESTOR_NF)),
):
    """Anexa N notas de uma vez — a caixa pode levar a nota do servico e a de
    remessa. ACUMULA: as notas ja anexadas continuam.

    As tres listas sao paralelas (numero[i] casa com pdf[i] e xml[i]) e o lote e'
    tudo-ou-nada: se a terceira nota tiver um arquivo invalido, as duas primeiras
    nao ficam gravadas — senao o Financeiro reenviaria o lote e duplicaria as boas.
    """
    cx = _caixa_ou_404(db, caixa_id)
    _exigir_fase_de_nota(cx)
    ativas = _ordens_ativas_caixa(cx)
    if not ativas:
        raise HTTPException(409, "caixa sem OS ativa")
    if not numeros or not (len(arquivos_pdf) == len(arquivos_xml) == len(numeros)):
        raise HTTPException(422, "informe número, PDF e XML para cada nota")
    nums = [_validar_numero(n) for n in numeros]

    sub = nota_fiscal.subdir_caixa(cx.id)
    gravados: list[str] = []
    pares: list[tuple[str, str]] = []
    try:
        for pdf, xml in zip(arquivos_pdf, arquivos_xml):
            pdf.file.seek(0)
            base_pdf = storage.salvar_upload(pdf, subdir=sub, tipos_permitidos=storage.TIPOS_PDF)
            gravados.append(base_pdf)
            xml.file.seek(0)
            base_xml = storage.salvar_upload(xml, subdir=sub, tipos_permitidos=storage.TIPOS_XML)
            gravados.append(base_xml)
            pares.append((base_pdf, base_xml))
    except storage.ArquivoInvalido as e:
        for b in gravados:
            storage.remover_arquivo(sub, b)
        raise HTTPException(e.status, e.detail)

    for num, (base_pdf, base_xml) in zip(nums, pares):
        db.add(NotaFiscal(caixa=cx.id, numero=num, arquivo_pdf=base_pdf,
                          arquivo_xml=base_xml, criado_em=agora(), criado_por=usuario.id))
        for o in ativas:
            registrar_log(db, o, usuario, f"Nota fiscal {num} anexada")
    db.commit()
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx)
    return cx


@router.delete("/caixas/{caixa_id}/notas-fiscais/{nota_id}", response_model=CaixaDetalhe)
def remover_nota_fiscal(
    caixa_id: int,
    nota_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_funcao(*GESTOR_NF)),
):
    """Remove a nota e APAGA os arquivos. E' o caminho de correcao: a nota errada
    nao pode continuar baixavel por ninguem."""
    cx = _caixa_ou_404(db, caixa_id)
    _exigir_fase_de_nota(cx)
    nf = _nota_ou_404(db, cx, nota_id)
    sub = nota_fiscal.subdir_nota(nf.ordem, nf.caixa)
    storage.remover_arquivo(sub, nf.arquivo_pdf)
    storage.remover_arquivo(sub, nf.arquivo_xml)
    numero = nf.numero
    db.delete(nf)
    for o in _ordens_ativas_caixa(cx):
        registrar_log(db, o, usuario, f"Nota fiscal {numero} removida")
    db.commit()
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx)
    return cx


def _servir_nota(nf: NotaFiscal, basename: str):
    try:
        caminho = storage.caminho_arquivo(nota_fiscal.subdir_nota(nf.ordem, nf.caixa), basename)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    if not caminho.exists():
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(
        caminho,
        media_type=nota_fiscal.media_type(basename),
        filename=nota_fiscal.nome_download_nota(nf.numero, basename),
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/caixas/{caixa_id}/notas-fiscais/{nota_id}/pdf")
def baixar_nota_pdf(caixa_id: int, nota_id: int, db: Session = Depends(get_db),
                    _: Usuario = Depends(get_current_usuario)):
    cx = _caixa_ou_404(db, caixa_id)
    nf = _nota_ou_404(db, cx, nota_id)
    return _servir_nota(nf, nf.arquivo_pdf)


@router.get("/caixas/{caixa_id}/notas-fiscais/{nota_id}/xml")
def baixar_nota_xml(caixa_id: int, nota_id: int, db: Session = Depends(get_db),
                    _: Usuario = Depends(get_current_usuario)):
    cx = _caixa_ou_404(db, caixa_id)
    nf = _nota_ou_404(db, cx, nota_id)
    return _servir_nota(nf, nf.arquivo_xml)


# ── Leitura legada por OS ────────────────────────────────────────────────────
# Os dois GET abaixo servem o par PDF/XML gravado nas colunas de `ordens`. Os
# POST que ESCREVIAM nessas colunas (`/ordens/{id}/nota-fiscal` e o
# `/caixas/{id}/nota-fiscal` singular) foram removidos junto com o `_gravar_par`:
# a nota agora nasce na tabela `notas_fiscais`, por caixa. As colunas viraram
# so' leitura de dado legado e continuam aqui porque os cards ja publicados no
# TaskHS apontam para estas rotas e para o link publico `nf:{ordem_id}`.
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


@router.get("/ordens/{ordem_id}/nota-fiscal/xml")
def baixar_nota_fiscal_xml(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    """Rota separada em vez de `?tipo=xml` para nao mexer no contrato do PDF, que
    ja e' usado pelo link publico assinado do card do TaskHS."""
    o = _os_ou_404(db, ordem_id)
    if not o.nota_fiscal_xml:
        raise HTTPException(404, "sem XML da nota fiscal")
    try:
        caminho = storage.caminho_arquivo(nota_fiscal.subdir(ordem_id), o.nota_fiscal_xml)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    if not caminho.exists():
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(
        caminho,
        media_type=nota_fiscal.media_type(o.nota_fiscal_xml),
        filename=nota_fiscal.nome_download(ordem_id, o.nota_fiscal_xml),
        headers={"X-Content-Type-Options": "nosniff"},
    )
