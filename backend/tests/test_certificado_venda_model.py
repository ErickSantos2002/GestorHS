import pytest
from sqlalchemy.exc import IntegrityError


def _aparelho(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="ACME"); eq = Equipamento(descricao="Mark X")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1")
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def test_grava_e_le_certificado_de_venda(db_session, usuario_lab):
    from datetime import date
    from app.models import CertificadoVenda
    ec = _aparelho(db_session)
    cv = CertificadoVenda(
        equipamento_cliente=ec.id, html="<p>ok</p>", calib_cert="V-001",
        data_calibracao=date(2026, 7, 20), usuario=usuario_lab.id,
    )
    db_session.add(cv); db_session.commit(); db_session.refresh(cv)
    assert cv.id is not None
    assert cv.calib_cert == "V-001"
    assert cv.usuario_nome == "Lab"


def test_um_certificado_de_venda_por_aparelho(db_session):
    from app.models import CertificadoVenda
    ec = _aparelho(db_session)
    db_session.add(CertificadoVenda(equipamento_cliente=ec.id, html="<p>a</p>"))
    db_session.commit()
    db_session.add(CertificadoVenda(equipamento_cliente=ec.id, html="<p>b</p>"))
    with pytest.raises(IntegrityError):
        db_session.commit()
