import io


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os(db_session, os_base, fase=10):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico="C", situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def _pdf():
    return ("nf.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")


def _xml():
    return ("nf.xml", io.BytesIO(b"<nfse/>"), "application/xml")


def test_upload_pdf_ok(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, data={"numero": "12345"}, headers=h)
    assert r.status_code == 200
    db_session.refresh(o)
    assert o.nota_fiscal.endswith(".pdf")
    assert o.nota_fiscal_numero == "12345"


def test_upload_xml_ok(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _xml()}, data={"numero": "77"}, headers=h)
    assert r.status_code == 200
    db_session.refresh(o)
    assert o.nota_fiscal.endswith(".xml")


def test_upload_tipo_invalido_415(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    imagem = ("nf.png", io.BytesIO(b"\x89PNG"), "image/png")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": imagem}, data={"numero": "1"}, headers=h)
    assert r.status_code == 415


def test_upload_sem_numero_422(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, headers=h)
    assert r.status_code == 422


def test_upload_numero_em_branco_422(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, data={"numero": "   "}, headers=h)
    assert r.status_code == 422


def test_substituir_remove_o_arquivo_anterior(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, data={"numero": "1"}, headers=h)
    db_session.refresh(o)
    antigo = upload_tmp / f"notas-fiscais/{o.id}" / o.nota_fiscal
    assert antigo.exists()
    client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _xml()}, data={"numero": "2"}, headers=h)
    db_session.refresh(o)
    assert not antigo.exists()          # o anterior foi apagado do disco
    assert o.nota_fiscal_numero == "2"


def test_upload_exige_funcao_financeiro_403(client, usuario_lab, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, data={"numero": "1"}, headers=h)
    assert r.status_code == 403


def test_download_ok_e_sem_anexo_404(client, usuario_financeiro, usuario_admin, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    ha = _headers(client, "admin@hs.com", "senha123")
    assert client.get(f"/ordens/{o.id}/nota-fiscal", headers=ha).status_code == 404
    hf = _headers(client, "fin@hs.com", "senha123")
    client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, data={"numero": "1"}, headers=hf)
    r = client.get(f"/ordens/{o.id}/nota-fiscal", headers=ha)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
