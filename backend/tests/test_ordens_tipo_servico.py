"""Correcao do tipo de servico pelo Laboratorio, dentro da fase dele.

A Expedicao registra o tipo na entrada pelo que ve por fora ("so calibracao"); o
tecnico e' quem descobre na bancada que o aparelho tambem precisa de manutencao.
Endpoint proprio em vez de abrir o `/editar`, que e' de Administrador e mexe
tambem em checklist, datas e garantia.
"""
import pytest


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os_na_fase(db, os_base, fase, tipo="C"):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico=tipo, situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o.id


def test_laboratorio_corrige_de_calibracao_para_manutencao(client, usuario_lab, fases_seed, os_base, db_session):
    from app.models import Ordem
    oid = _os_na_fase(db_session, os_base, 5, tipo="C")
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.patch(f"/ordens/{oid}/tipo-servico", json={"tipo_servico": "M"}, headers=h)
    assert r.status_code == 200
    assert r.json()["tipo_servico"] == "M"
    db_session.expire_all()
    assert db_session.get(Ordem, oid).tipo_servico == "M"


def test_a_troca_fica_registrada_no_historico(client, usuario_lab, fases_seed, os_base, db_session):
    """Quem informou o tipo na entrada foi outra pessoa: a troca precisa dizer
    de que para que, senao vira discussao depois."""
    from app.models import LogOS
    oid = _os_na_fase(db_session, os_base, 5, tipo="C")
    h = _headers(client, "lab@hs.com", "senha123")
    client.patch(f"/ordens/{oid}/tipo-servico", json={"tipo_servico": "A"}, headers=h)
    textos = [x.texto for x in db_session.query(LogOS).filter(LogOS.os == oid).all()]
    assert any("Calibração" in t and "Ambas" in t for t in textos), textos


def test_admin_tambem_pode(client, usuario_admin, fases_seed, os_base, db_session):
    oid = _os_na_fase(db_session, os_base, 5)
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.patch(f"/ordens/{oid}/tipo-servico", json={"tipo_servico": "M"}, headers=h).status_code == 200


def test_outra_funcao_nao_pode(client, usuario_financeiro, fases_seed, os_base, db_session):
    from app.models import Ordem
    oid = _os_na_fase(db_session, os_base, 5, tipo="C")
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.patch(f"/ordens/{oid}/tipo-servico", json={"tipo_servico": "M"}, headers=h)
    assert r.status_code == 403
    db_session.expire_all()
    assert db_session.get(Ordem, oid).tipo_servico == "C"


@pytest.mark.parametrize("fase", [4, 6, 7, 8])
def test_fora_da_fase_do_laboratorio_recusa(client, usuario_lab, fases_seed, os_base, db_session, fase):
    """Depois do laboratorio a OS ja gerou certificado e seguiu para cobranca —
    trocar o tipo ali mudaria o que foi cobrado e o que foi emitido."""
    from app.models import Ordem
    oid = _os_na_fase(db_session, os_base, fase, tipo="C")
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.patch(f"/ordens/{oid}/tipo-servico", json={"tipo_servico": "M"}, headers=h)
    assert r.status_code == 409
    db_session.expire_all()
    assert db_session.get(Ordem, oid).tipo_servico == "C"


def test_tipo_invalido_422(client, usuario_lab, fases_seed, os_base, db_session):
    oid = _os_na_fase(db_session, os_base, 5)
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.patch(f"/ordens/{oid}/tipo-servico", json={"tipo_servico": "X"}, headers=h).status_code == 422


def test_os_inexistente_404(client, usuario_lab, fases_seed, os_base):
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.patch("/ordens/999999/tipo-servico", json={"tipo_servico": "M"}, headers=h).status_code == 404
