"""Acesso a configuracao do certificado e ao padrao (cilindro) vigente.

Toca a Session — por isso fica separado de certificado_calculo.py, que e puro.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.core.certificado_calculo import ParametrosCalculo
from app.core.certificado_geral_link import link_certificado_geral
from app.models import CertificadoConfig, CertificadoGeral, CertificadoPadrao


def _f(valor) -> float | None:
    """Numeric do SQLAlchemy volta como Decimal — o calculo trabalha em float."""
    return None if valor is None else float(valor)


def obter_config(db: Session) -> CertificadoConfig:
    """A linha unica de configuracao, criando-a com os defaults se ainda nao existir.

    Criar sob demanda e o que mantem o singleton verdadeiro nos dois mundos: em
    producao a migracao 0024 ja insere a linha; nos testes, que montam o schema com
    create_all e sem migracao, ela nasce aqui.
    """
    config = db.query(CertificadoConfig).order_by(CertificadoConfig.id).first()
    if config is None:
        config = CertificadoConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def parametros_de(config: CertificadoConfig) -> ParametrosCalculo:
    return ParametrosCalculo(
        valor_referencia=_f(config.valor_referencia),
        resolucao_instrumento=_f(config.resolucao_instrumento),
        incerteza_padrao_temp=_f(config.incerteza_padrao_temp),
        resolucao_pressao=_f(config.resolucao_pressao),
        incerteza_padrao_pressao=_f(config.incerteza_padrao_pressao),
        fator_k=_f(config.fator_k) or 2.0,
    )


def padrao_vigente(db: Session, data: date | None) -> CertificadoPadrao | None:
    """O cilindro ativo cuja vigencia contem `data`. Sem correspondencia -> None.

    Devolver None em vez de cair no cilindro atual e deliberado: preencher um
    certificado de 2024 com o cilindro de 2026 seria rastreabilidade falsa.
    """
    if data is None:
        return None
    return (
        db.query(CertificadoPadrao)
        .filter(
            CertificadoPadrao.ativo.is_(True),
            CertificadoPadrao.vigencia_inicio <= data,
            (CertificadoPadrao.vigencia_fim.is_(None)) | (CertificadoPadrao.vigencia_fim >= data),
        )
        # id como criterio de desempate: sem ele, dois cilindros com a mesma
        # vigencia_inicio devolvem um resultado arbitrario do banco, e a tela
        # (padraoVigente.ts, que espelha esta regra) nao teria como acertar qual.
        .order_by(CertificadoPadrao.vigencia_inicio.desc(), CertificadoPadrao.id.desc())
        .first()
    )


# Rotulo fixo de cada documento, na ordem em que sai no certificado. O nome cadastrado
# do documento nao serve como rotulo: hoje sao "LV09700-06672-26" e afins, numeros de
# certificado que nao dizem ao cliente o que ele esta baixando.
DOCUMENTOS_QR: tuple[tuple[str, str], ...] = (
    ("doc_gas_id", "Certificado do Gás"),
    ("doc_termohigrometro_id", "Certificado do Termohigrômetro Digital"),
    ("doc_barometro_id", "Certificado do Barômetro Digital"),
)


def documentos_qr(db: Session, config: CertificadoConfig) -> list[tuple[str, str]]:
    """(rotulo, link publico) de cada documento auxiliar configurado.

    Descarta EM SILENCIO o que nao da para montar — FK nula, documento excluido do
    cadastro, ou sem CERT_PUBLIC_BASE_URL. Um documento faltando nao pode impedir a
    emissao do certificado: o laboratorio percebe pela ausencia do QR e corrige em
    Configuracoes, sem ninguem ficar sem certificado.
    """
    itens: list[tuple[str, str]] = []
    for campo, rotulo in DOCUMENTOS_QR:
        cert_id = getattr(config, campo, None)
        if not cert_id:
            continue
        doc = db.get(CertificadoGeral, cert_id)
        if doc is None or not doc.arquivo:
            continue
        url = link_certificado_geral(doc.id)
        if not url:
            continue
        itens.append((rotulo, url))
    return itens
