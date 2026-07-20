from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import espelhar_calibracao_valores
from app.core.certificado_gerar import modelo_marca, montar_contexto_venda, preencher, _endereco, _fmt_doc
from app.core.certificado_pdf import html_para_pdf
from app.models import CertificadoModelo, CertificadoVenda, EquipamentoCliente, Usuario
from app.models.database import get_db
from app.schemas.certificado_venda import (CertificadoVendaCamposOut, CertificadoVendaIn,
                                           CertificadoVendaOut)

router = APIRouter(prefix="/equipamentos-cliente", tags=["certificado-venda"])

_GERAR = require_funcao("Laboratório", "Administrador")
SITUACAO_PADRAO_VENDA = "Aparelho inicial"


def _aparelho_ou_404(db: Session, item_id: int) -> EquipamentoCliente:
    ec = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first()
    if ec is None:
        raise HTTPException(status_code=404, detail="aparelho não encontrado")
    return ec


def _venda_de(db: Session, item_id: int) -> CertificadoVenda | None:
    return db.query(CertificadoVenda).filter(
        CertificadoVenda.equipamento_cliente == item_id).first()


@router.get("/{item_id}/certificado-venda-campos", response_model=CertificadoVendaCamposOut)
def campos(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    ec = _aparelho_ou_404(db, item_id)
    cli = ec.cliente_rel
    modelo, marca = modelo_marca(db, ec.equipamento)
    cv = _venda_de(db, item_id)
    return CertificadoVendaCamposOut(
        nomecli=(cli.nome if cli else "") or "",
        cnpj=_fmt_doc(((cli.cgc or cli.cpf) if cli else "") or ""),
        endcli=_endereco(cli),
        modelo=modelo,
        marca=marca,
        serie=ec.serie or "",
        patrimonio=ec.patrimonio or "",
        datacompra=ec.datacompra,
        calib_cert=ec.calib_cert,
        data_calibracao=cv.data_calibracao if cv else date.today(),
        prox_calibragem=ec.prox_calibragem,
        calib_temp=ec.calib_temp,
        calib_pressao=ec.calib_pressao,
        calib_teste1=ec.calib_teste1,
        calib_teste2=ec.calib_teste2,
        calib_teste3=ec.calib_teste3,
        calib_teste_media=ec.calib_teste_media,
        calib_situacao=ec.calib_situacao or SITUACAO_PADRAO_VENDA,
        ja_gerado=cv is not None,
    )


@router.post("/{item_id}/certificado-venda", response_model=CertificadoVendaOut,
             status_code=status.HTTP_201_CREATED)
def gerar(item_id: int, dados: CertificadoVendaIn, db: Session = Depends(get_db),
          usuario: Usuario = Depends(_GERAR)):
    ec = _aparelho_ou_404(db, item_id)
    modelo = db.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento == ec.equipamento,
        CertificadoModelo.tipo == "C",
    ).first()
    if modelo is None or not modelo.texto:
        aparelho = ec.equipamento_descricao or "este aparelho"
        raise HTTPException(
            status_code=409,
            detail=f"O aparelho {aparelho} não tem modelo de certificado de Calibração "
                   f"cadastrado. Cadastre o modelo em Certificados antes de gerar.",
        )
    valores = dados.model_dump()
    html = preencher(modelo.texto, montar_contexto_venda(db, ec, valores))

    cv = _venda_de(db, item_id)
    if cv is None:                       # upsert: um por aparelho, regeravel
        cv = CertificadoVenda(equipamento_cliente=item_id)
        db.add(cv)
    cv.html = html
    cv.calib_cert = dados.calib_cert
    cv.data_calibracao = dados.data_calibracao
    cv.usuario = usuario.id
    cv.data_geracao = datetime.now(timezone.utc)

    espelhar_calibracao_valores(db, ec, valores,
                                ult=dados.data_calibracao, prox=dados.prox_calibragem)
    db.commit()
    db.refresh(cv)
    return CertificadoVendaOut.model_validate(cv)


@router.get("/{item_id}/certificado-venda/pdf")
def baixar_pdf(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    _aparelho_ou_404(db, item_id)
    cv = _venda_de(db, item_id)
    if cv is None or not cv.html:
        raise HTTPException(status_code=404, detail="certificado não gerado")
    try:
        pdf = html_para_pdf(cv.html)
    except Exception:
        raise HTTPException(status_code=500, detail="falha ao gerar PDF")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificado-venda-{item_id}.pdf"'},
    )
