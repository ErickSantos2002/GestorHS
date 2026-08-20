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


def _par():
    """PDF e XML sempre juntos — e' o que o Financeiro recebe da contabilidade."""
    return {"arquivo_pdf": _pdf(), "arquivo_xml": _xml()}


def test_upload_pdf_ok(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files=_par(), data={"numero": "12345"}, headers=h)
    assert r.status_code == 200
    db_session.refresh(o)
    assert o.nota_fiscal.endswith(".pdf")
    assert o.nota_fiscal_numero == "12345"


def test_upload_grava_pdf_e_xml_em_campos_separados(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files=_par(), data={"numero": "77"}, headers=h)
    assert r.status_code == 200
    db_session.refresh(o)
    assert o.nota_fiscal.endswith(".pdf")
    assert o.nota_fiscal_xml.endswith(".xml")


def test_upload_so_com_pdf_422(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    """Os dois sempre vao juntos: faltando o XML, o upload nem comeca."""
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"arquivo_pdf": _pdf()},
                    data={"numero": "1"}, headers=h)
    assert r.status_code == 422


def test_upload_recusa_dois_pdfs(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    """Cada campo aceita so o proprio tipo — antes um campo unico aceitava PDF ou
    XML, e mandar dois PDFs passava sem ninguem notar que o XML nunca chegou."""
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal",
                    files={"arquivo_pdf": _pdf(), "arquivo_xml": _pdf()},
                    data={"numero": "1"}, headers=h)
    assert r.status_code == 415


def test_download_do_xml(client, usuario_financeiro, usuario_admin, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    ha = _headers(client, "admin@hs.com", "senha123")
    assert client.get(f"/ordens/{o.id}/nota-fiscal/xml", headers=ha).status_code == 404
    hf = _headers(client, "fin@hs.com", "senha123")
    client.post(f"/ordens/{o.id}/nota-fiscal", files=_par(), data={"numero": "1"}, headers=hf)
    r = client.get(f"/ordens/{o.id}/nota-fiscal/xml", headers=ha)
    assert r.status_code == 200
    # octet-stream de proposito (ver core/nota_fiscal.media_type): XML servido como
    # application/xml executaria <script> via polyglot XHTML. O nome do arquivo e
    # que carrega a extensao.
    assert r.headers["content-type"] == "application/octet-stream"
    assert r.headers["content-disposition"].endswith('.xml"')


def test_upload_tipo_invalido_415(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    imagem = ("nf.png", io.BytesIO(b"\x89PNG"), "image/png")
    r = client.post(f"/ordens/{o.id}/nota-fiscal",
                    files={"arquivo_pdf": imagem, "arquivo_xml": _xml()},
                    data={"numero": "1"}, headers=h)
    assert r.status_code == 415


def test_upload_sem_numero_422(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files=_par(), headers=h)
    assert r.status_code == 422


def test_upload_numero_em_branco_422(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files=_par(), data={"numero": "   "}, headers=h)
    assert r.status_code == 422


def test_upload_numero_muito_longo_422(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    # String(50) na coluna: sem essa validacao o Postgres levantaria StringDataRightTruncation (500).
    # SQLite (usado nos testes) nao enforca o limite, entao o teste deve checar so o status.
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    numero_longo = "1" * 51
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files=_par(), data={"numero": numero_longo}, headers=h)
    assert r.status_code == 422


def test_substituir_remove_o_arquivo_anterior(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    client.post(f"/ordens/{o.id}/nota-fiscal", files=_par(), data={"numero": "1"}, headers=h)
    db_session.refresh(o)
    pasta = upload_tmp / f"notas-fiscais/{o.id}"
    antigo_pdf = pasta / o.nota_fiscal
    antigo_xml = pasta / o.nota_fiscal_xml
    assert antigo_pdf.exists() and antigo_xml.exists()
    client.post(f"/ordens/{o.id}/nota-fiscal", files=_par(), data={"numero": "2"}, headers=h)
    db_session.refresh(o)
    # os DOIS anteriores saem do disco, nao so o PDF
    assert not antigo_pdf.exists()
    assert not antigo_xml.exists()
    assert o.nota_fiscal_numero == "2"


def test_upload_exige_funcao_financeiro_403(client, usuario_lab, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files=_par(), data={"numero": "1"}, headers=h)
    assert r.status_code == 403


def test_download_ok_e_sem_anexo_404(client, usuario_financeiro, usuario_admin, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    ha = _headers(client, "admin@hs.com", "senha123")
    assert client.get(f"/ordens/{o.id}/nota-fiscal", headers=ha).status_code == 404
    hf = _headers(client, "fin@hs.com", "senha123")
    client.post(f"/ordens/{o.id}/nota-fiscal", files=_par(), data={"numero": "1"}, headers=hf)
    r = client.get(f"/ordens/{o.id}/nota-fiscal", headers=ha)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
