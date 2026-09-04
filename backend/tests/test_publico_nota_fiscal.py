from app.core import nota_fiscal, nota_fiscal_link as nl


def _os_com_nf(db_session, os_base, upload_tmp):
    """Monta o cenario legado gravando as colunas de `ordens` direto.

    O link publico assina `nf:{ordem_id}` e serve o arquivo do subdir da OS —
    comportamento legado que continua no ar para os cards ja publicados no
    TaskHS. O `POST /ordens/{id}/nota-fiscal` que montava isso foi removido.
    """
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=10, tipo_servico="C", situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    d = upload_tmp / nota_fiscal.subdir(o.id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "nf.pdf").write_bytes(b"%PDF-1.4 fake")
    (d / "nf.xml").write_bytes(b"<nfse/>")
    o.nota_fiscal = "nf.pdf"
    o.nota_fiscal_xml = "nf.xml"
    o.nota_fiscal_numero = "999"
    db_session.commit()
    db_session.refresh(o)
    return o


def test_download_publico_ok(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os_com_nf(db_session, os_base, upload_tmp)
    r = client.get(f"/publico/nota-fiscal/{o.id}?t={nl.assinar(o.id)}")   # sem Authorization
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_download_publico_token_errado_403(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os_com_nf(db_session, os_base, upload_tmp)
    assert client.get(f"/publico/nota-fiscal/{o.id}?t=errado").status_code == 403


def test_download_publico_sem_nota_404(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=10, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert client.get(f"/publico/nota-fiscal/{o.id}?t={nl.assinar(o.id)}").status_code == 404


def test_download_publico_xml_ok(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os_com_nf(db_session, os_base, upload_tmp)
    r = client.get(f"/publico/nota-fiscal/{o.id}/xml?t={nl.assinar(o.id, nl.XML)}")   # sem Authorization
    assert r.status_code == 200
    # nunca application/xml: o XML e conteudo de usuario e renderizado inline executaria script
    assert r.headers["content-type"] == "application/octet-stream"


def test_download_publico_xml_token_do_pdf_403(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os_com_nf(db_session, os_base, upload_tmp)
    assert client.get(f"/publico/nota-fiscal/{o.id}/xml?t={nl.assinar(o.id)}").status_code == 403


def test_download_publico_xml_sem_nota_404(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=10, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert client.get(f"/publico/nota-fiscal/{o.id}/xml?t={nl.assinar(o.id, nl.XML)}").status_code == 404


def test_publico_baixa_nota_da_caixa(client, client_fin, caixa_financeiro, upload_tmp, db_session):
    import io
    from app.core import nota_fiscal_link
    from app.models import NotaFiscal
    files = [("arquivos_pdf", ("a.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")),
             ("arquivos_xml", ("a.xml", io.BytesIO(b"<n/>"), "application/xml"))]
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais", files=files,
                    data={"numeros": ["12345"]})
    nid = db_session.query(NotaFiscal).first().id
    tok = nota_fiscal_link.assinar_nota(nid)
    assert client.get(f"/publico/nota-fiscal/nota/{nid}?t={tok}").status_code == 200
    assert client.get(f"/publico/nota-fiscal/nota/{nid}?t=errado").status_code == 403
    # o token do PDF nao serve para o XML
    assert client.get(f"/publico/nota-fiscal/nota/{nid}/xml?t={tok}").status_code == 403
