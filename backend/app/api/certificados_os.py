from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, OSCertificado
from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import agora, concluir_laboratorio, registrar_log
from app.core import os_workflow as wf
from app.core.certificado_config import padrao_vigente
from app.core.certificado_gerar import gerar_certificados, tipos_para, tipos_sem_modelo, montar_contexto
from app.core.certificado_pdf import html_para_pdf
from app.schemas.ordens import GerarCertificadoIn, CertificadoCamposOut
from app.schemas.certificados_modelo import OSCertificadoOut

router = APIRouter(tags=["certificados-os"])

_gerar = require_funcao("Laboratório", "Administrador")

_CAMPOS_CALIB = (
    "calib_cert", "calib_temp", "calib_pressao",
    "calib_teste1", "calib_teste2", "calib_teste3", "calib_teste4", "calib_teste5",
    "calib_teste_media", "calib_situacao",
)

_CAMPOS_OVERRIDE = ("nomecli", "cnpj", "endcli", "modelo", "marca", "serie", "patrimonio", "datacompra")


def _os_ou_404(db: Session, ordem_id: int) -> Ordem:
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return o


@router.get("/ordens/{ordem_id}/certificados", response_model=list[OSCertificadoOut])
def listar_os_certificados(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    _os_ou_404(db, ordem_id)
    cs = db.query(OSCertificado).filter(OSCertificado.os == ordem_id).order_by(OSCertificado.tipo).all()
    return [OSCertificadoOut.model_validate(c) for c in cs]


@router.get("/ordens/{ordem_id}/certificado-campos", response_model=CertificadoCamposOut)
def certificado_campos(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    ordem = _os_ou_404(db, ordem_id)
    ctx = montar_contexto(db, ordem)
    return CertificadoCamposOut(
        nomecli=ctx.get("nomecli", ""), cnpj=ctx.get("cnpj", ""), endcli=ctx.get("endcli", ""),
        modelo=ctx.get("modelo", ""), marca=ctx.get("marca", ""), serie=ctx.get("serie", ""),
        patrimonio=ctx.get("patrimonio", ""), datacompra=ctx.get("datacompra", ""),
        calib_cert=ordem.calib_cert, calib_temp=ordem.calib_temp, calib_pressao=ordem.calib_pressao,
        calib_teste1=ordem.calib_teste1, calib_teste2=ordem.calib_teste2, calib_teste3=ordem.calib_teste3,
        calib_teste4=ordem.calib_teste4, calib_teste5=ordem.calib_teste5,
        calib_teste_media=ordem.calib_teste_media, calib_situacao=ordem.calib_situacao,
        data_calibracao=ordem.data_calibracao.date() if ordem.data_calibracao else None,
    )


_LABEL_TIPO = {"C": "Calibração", "M": "Manutenção"}


@router.post("/ordens/{ordem_id}/gerar-certificado", response_model=list[OSCertificadoOut])
def gerar(ordem_id: int, dados: GerarCertificadoIn | None = None, db: Session = Depends(get_db), usuario: Usuario = Depends(_gerar)):
    ordem = _os_ou_404(db, ordem_id)
    # Sem modelo cadastrado para o aparelho não há o que preencher: recusa com mensagem
    # clara em vez de gerar nada e responder 200 (falha silenciosa).
    faltando = tipos_sem_modelo(db, ordem, tipos_para(ordem))
    if faltando:
        nomes = " e ".join(_LABEL_TIPO[t] for t in faltando)
        aparelho = ordem.equipamento_descricao or "este aparelho"
        raise HTTPException(
            status_code=409,
            detail=f"O aparelho {aparelho} não tem modelo de certificado de {nomes} cadastrado. "
                   f"Cadastre o modelo em Certificados antes de gerar.",
        )
    if dados is not None:
        for campo in _CAMPOS_CALIB:
            setattr(ordem, campo, getattr(dados, campo))
        if dados.data_calibracao is not None:
            ordem.data_calibracao = datetime(
                dados.data_calibracao.year, dados.data_calibracao.month, dados.data_calibracao.day,
                tzinfo=timezone.utc,
            )
        elif ordem.data_calibracao is None:
            ordem.data_calibracao = agora()
        # Congela o cilindro usado NESTA calibracao. Sem isso, regerar o certificado
        # meses depois apontaria para o cilindro vigente naquele momento — rastreabilidade
        # falsa num documento da Qualidade.
        data_ref = ordem.data_calibracao.date() if ordem.data_calibracao else None
        padrao = padrao_vigente(db, data_ref)
        ordem.padrao_id = padrao.id if padrao else None
        overrides = {k: getattr(dados, k) for k in _CAMPOS_OVERRIDE if getattr(dados, k)}
        ordem.cert_overrides = overrides or None
        db.flush()
    gerados = gerar_certificados(db, ordem, tipos_para(ordem))
    if ordem.fase == wf.FASE_LABORATORIO and ordem.desfecho_lab == wf.DESFECHO_PENDENTE:
        concluir_laboratorio(db, ordem)
        registrar_log(db, ordem, usuario, "Laboratório concluído — certificado gerado")
    db.commit()
    for g in gerados:
        db.refresh(g)
    return [OSCertificadoOut.model_validate(c) for c in gerados]


_NOME_TIPO = {"C": "calibracao", "M": "manutencao"}


@router.get("/ordens/{ordem_id}/certificado/{tipo}/pdf")
def baixar_pdf(ordem_id: int, tipo: str, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if tipo not in _NOME_TIPO:
        raise HTTPException(status_code=404, detail="tipo inválido")
    _os_ou_404(db, ordem_id)
    osc = db.query(OSCertificado).filter(
        OSCertificado.os == ordem_id, OSCertificado.tipo == tipo
    ).first()
    if osc is None or not osc.html:
        raise HTTPException(status_code=404, detail="certificado não gerado")
    try:
        pdf = html_para_pdf(osc.html)
    except Exception:
        raise HTTPException(status_code=500, detail="falha ao gerar PDF")
    nome = _NOME_TIPO[tipo]
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificado-{ordem_id}-{nome}.pdf"'},
    )
