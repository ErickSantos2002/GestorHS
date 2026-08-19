"""Relatorio de certificados EMITIDOS.

Nao existe tela de lista para isso: os certificados vivem em duas tabelas separadas
(`os_certificados`, gerados a partir de uma OS, e `certificados_venda`, gerados na
venda de um aparelho) e so' aparecem picados no detalhe da OS e do aparelho. Aqui as
duas origens viram um conjunto unico, ordenado por data de geracao.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario
from app.api.exportar_common import carregar_ate_o_teto, resposta_xlsx
from app.core.exportacoes import COLUNAS_CERTIFICADOS, TIPO_CERTIFICADO_POR_EXTENSO
from app.models import (CertificadoVenda, Cliente, Equipamento, EquipamentoCliente,
                        Ordem, OSCertificado, Usuario)
from app.models.database import get_db

router = APIRouter(prefix="/certificados-emitidos", tags=["certificados-emitidos"])


def _inicio(dia: date) -> datetime:
    return datetime.combine(dia, datetime.min.time(), tzinfo=timezone.utc)


def _linhas_de_os(db: Session, cliente, de, ate) -> list[dict]:
    q = (
        db.query(OSCertificado, Ordem, Cliente, EquipamentoCliente, Equipamento)
        .join(Ordem, OSCertificado.os == Ordem.id)
        .join(Cliente, Ordem.cliente == Cliente.id)
        .outerjoin(EquipamentoCliente, Ordem.equipamento_cliente == EquipamentoCliente.id)
        .outerjoin(Equipamento, EquipamentoCliente.equipamento == Equipamento.id)
    )
    if cliente is not None:
        q = q.filter(Ordem.cliente == cliente)
    if de is not None:
        q = q.filter(OSCertificado.data_geracao >= _inicio(de))
    if ate is not None:
        # Fim de faixa inclusivo: `data_geracao` e' DateTime, entao "< dia seguinte"
        # em vez de "<= o dia" — senao um certificado gerado as 14h do ultimo dia
        # ficaria de fora do proprio filtro que o inclui.
        q = q.filter(OSCertificado.data_geracao < _inicio(ate) + timedelta(days=1))
    return [
        {
            "cliente_nome": cli.nome,
            "cliente_cnpj": cli.cgc,
            "equipamento_descricao": equip.descricao if equip else None,
            "serie": ec.serie if ec else None,
            "origem": "OS",
            "os": ordem.id,
            "tipo": TIPO_CERTIFICADO_POR_EXTENSO.get(cert.tipo, cert.tipo),
            "calib_cert": ordem.calib_cert,
            "data_calibracao": ordem.data_calibracao,
            "data_geracao": cert.data_geracao,
            # `os_certificados` nao guarda quem gerou — so' os de venda guardam.
            "usuario_nome": None,
        }
        for cert, ordem, cli, ec, equip in carregar_ate_o_teto(q)
    ]


def _linhas_de_venda(db: Session, cliente, de, ate) -> list[dict]:
    q = (
        db.query(CertificadoVenda, EquipamentoCliente, Cliente, Equipamento, Usuario)
        .join(EquipamentoCliente, CertificadoVenda.equipamento_cliente == EquipamentoCliente.id)
        .join(Cliente, EquipamentoCliente.cliente == Cliente.id)
        .outerjoin(Equipamento, EquipamentoCliente.equipamento == Equipamento.id)
        .outerjoin(Usuario, CertificadoVenda.usuario == Usuario.id)
    )
    if cliente is not None:
        q = q.filter(EquipamentoCliente.cliente == cliente)
    if de is not None:
        q = q.filter(CertificadoVenda.data_geracao >= _inicio(de))
    if ate is not None:
        q = q.filter(CertificadoVenda.data_geracao < _inicio(ate) + timedelta(days=1))
    return [
        {
            "cliente_nome": cli.nome,
            "cliente_cnpj": cli.cgc,
            "equipamento_descricao": equip.descricao if equip else None,
            "serie": ec.serie,
            "origem": "Venda",
            "os": None,
            "tipo": TIPO_CERTIFICADO_POR_EXTENSO.get("C", "C"),
            "calib_cert": cert.calib_cert,
            "data_calibracao": cert.data_calibracao,
            "data_geracao": cert.data_geracao,
            "usuario_nome": usr.nome if usr else None,
        }
        for cert, ec, cli, equip, usr in carregar_ate_o_teto(q)
    ]


@router.get("/exportar")
def exportar(
    cliente: int | None = None,
    de: date | None = None,
    ate: date | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    linhas = _linhas_de_os(db, cliente, de, ate) + _linhas_de_venda(db, cliente, de, ate)
    # Sem data de geracao vai para o fim, e nao quebra a ordenacao.
    linhas.sort(key=lambda l: (l["data_geracao"] is None, l["data_geracao"]), reverse=False)
    return resposta_xlsx(
        "certificados-emitidos", "Certificados", COLUNAS_CERTIFICADOS, linhas,
        {"Cliente": cliente, "De": de, "Ate": ate,
         "Observacao": "'Gerado por' so' existe nos certificados de venda"},
    )
