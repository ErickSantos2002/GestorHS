import io

from app.core import nota_fiscal_link as nl


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os_com_nf(client, db_session, os_base, upload_tmp):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=10, tipo_servico="C", situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "fin@hs.com", "senha123")
    client.post(f"/ordens/{o.id}/nota-fiscal",
                files={"arquivo_pdf": ("nf.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"),
                       "arquivo_xml": ("nf.xml", io.BytesIO(b"<nfse/>"), "application/xml")},
                data={"numero": "999"}, headers=h)
    db_session.refresh(o)
    return o


def test_download_publico_ok(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os_com_nf(client, db_session, os_base, upload_tmp)
    r = client.get(f"/publico/nota-fiscal/{o.id}?t={nl.assinar(o.id)}")   # sem Authorization
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_download_publico_token_errado_403(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os_com_nf(client, db_session, os_base, upload_tmp)
    assert client.get(f"/publico/nota-fiscal/{o.id}?t=errado").status_code == 403


def test_download_publico_sem_nota_404(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=10, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert client.get(f"/publico/nota-fiscal/{o.id}?t={nl.assinar(o.id)}").status_code == 404
