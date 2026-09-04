"""Rotas de LEITURA legadas da nota fiscal por OS.

O `POST /ordens/{id}/nota-fiscal` foi removido: a nota agora nasce por CAIXA, na
tabela `notas_fiscais` (ver `test_notas_fiscais_caixa.py`). O que sobrou aqui sao
os dois GET, que continuam servindo o par PDF/XML das colunas de `ordens` porque
os cards ja publicados no TaskHS apontam para eles.
"""


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os(db_session, os_base, fase=10):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico="C", situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def _anexar_legado(db_session, upload_tmp, ordem, numero="12345"):
    """Grava o par direto nas colunas legadas e no subdir da OS.

    O `POST /ordens/{id}/nota-fiscal` foi removido: era o ultimo caminho que
    escrevia nessas colunas. Elas continuam existindo so para servir as rotas de
    leitura ja publicadas nos cards do TaskHS, e e' isso que estes testes cobrem.
    """
    from app.core import nota_fiscal
    d = upload_tmp / nota_fiscal.subdir(ordem.id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "nf.pdf").write_bytes(b"%PDF-1.4 fake")
    (d / "nf.xml").write_bytes(b"<nfse/>")
    ordem.nota_fiscal = "nf.pdf"
    ordem.nota_fiscal_xml = "nf.xml"
    ordem.nota_fiscal_numero = numero
    db_session.commit()
    return ordem


def test_download_do_xml(client, usuario_admin, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    ha = _headers(client, "admin@hs.com", "senha123")
    assert client.get(f"/ordens/{o.id}/nota-fiscal/xml", headers=ha).status_code == 404
    _anexar_legado(db_session, upload_tmp, o, numero="1")
    r = client.get(f"/ordens/{o.id}/nota-fiscal/xml", headers=ha)
    assert r.status_code == 200
    # octet-stream de proposito (ver core/nota_fiscal.media_type): XML servido como
    # application/xml executaria <script> via polyglot XHTML. O nome do arquivo e
    # que carrega a extensao.
    assert r.headers["content-type"] == "application/octet-stream"
    assert r.headers["content-disposition"].endswith('.xml"')


def test_download_ok_e_sem_anexo_404(client, usuario_admin, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    ha = _headers(client, "admin@hs.com", "senha123")
    assert client.get(f"/ordens/{o.id}/nota-fiscal", headers=ha).status_code == 404
    _anexar_legado(db_session, upload_tmp, o, numero="1")
    r = client.get(f"/ordens/{o.id}/nota-fiscal", headers=ha)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
