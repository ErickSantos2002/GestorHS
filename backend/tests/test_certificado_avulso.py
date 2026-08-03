def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _modelo(db_session, os_base, tipo="C", texto="<p>[nomecli] | [serie] | [calibcert] | [os]</p>"):
    from app.models import CertificadoModelo
    db_session.add(CertificadoModelo(equipamento=os_base["equipamento"], tipo=tipo, texto=texto))
    db_session.commit()


def _payload(os_base, **kw):
    base = {
        "equipamento": os_base["equipamento"], "tipo": "C",
        "nomecli": "POC Ltda", "cnpj": "11222333000144", "endcli": "Rua X, 10",
        "serie": "SN-POC-1",
        "datacompra": None, "os": "XXXX", "data_recebimento": "2026-07-14",
        "calib_cert": "AV-001", "data_calibracao": "2026-07-14",
        "calib_temp": "22", "calib_pressao": "1013",
        "calib_teste1": "0,10", "calib_teste2": "0,11", "calib_teste3": "0,12",
        "calib_teste_media": "0,11", "calib_situacao": "Aprovado",
    }
    base.update(kw)
    return base


def test_gerar_avulso_salva_e_preenche_o_html(client, usuario_lab, os_base, db_session):
    _modelo(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-avulsos", json=_payload(os_base), headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["nomecli"] == "POC Ltda"
    assert body["calib_cert"] == "AV-001"

    from app.models import CertificadoAvulso
    av = db_session.query(CertificadoAvulso).filter(CertificadoAvulso.id == body["id"]).first()
    assert "POC Ltda" in av.html and "SN-POC-1" in av.html and "XXXX" in av.html
    assert "[" not in av.html          # nenhum token vazou
    assert av.usuario == usuario_lab.id
    assert av.data_geracao is not None


def test_avulso_salva_teste4_e_teste5_e_calcula_o_erro(client, usuario_lab, os_base, db_session):
    """Blindagem contra o modo de falha do schema: um campo ausente do `In` e
    silenciosamente descartado pelo Pydantic, sem erro — o laboratorio digitaria a
    medicao e ela sumiria sem sinal nenhum."""
    _modelo(db_session, os_base, texto="<p>[calibteste4] [calibteste5] [erro4] [erro5]</p>")
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-avulsos",
                    json=_payload(os_base, calib_teste4="0,15", calib_teste5="0,17"), headers=h)
    assert r.status_code == 201

    from app.models import CertificadoAvulso
    av = db_session.query(CertificadoAvulso).filter(CertificadoAvulso.id == r.json()["id"]).first()
    assert "0,15" in av.html and "0,17" in av.html
    assert "[" not in av.html
    # valor_referencia default e 0,1 (config criada sob demanda com os defaults do
    # modelo) -> erro = medicao - referencia. Sem isto, um [erro4]/[erro5] em branco
    # tambem passaria nas duas asserts acima.
    assert "0,05" in av.html   # erro4: 0,15 - 0,1
    assert "0,07" in av.html   # erro5: 0,17 - 0,1


def test_modelo_e_marca_vem_do_catalogo_e_nao_sao_digitados(client, usuario_lab, os_base, db_session):
    """[modelo]/[marca] saem do cadastro do aparelho do template — como no fluxo da OS.

    Nenhum dos 12 modelos reais usa esses tokens (a marca/modelo estao escritos no proprio
    HTML), entao pedi-los no formulario era um campo morto. Se um modelo novo usar o token,
    ele precisa sair certo sozinho.
    """
    from app.models import Equipamento, Marca
    m = Marca(descricao="Alcoscan")
    db_session.add(m); db_session.flush()
    eq = db_session.get(Equipamento, os_base["equipamento"])
    eq.marca = m.id
    db_session.commit()

    _modelo(db_session, os_base, texto="<p>[modelo] / [marca] / [patrimonio]</p>")
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-avulsos", json=_payload(os_base), headers=h)
    assert r.status_code == 201

    from app.models import CertificadoAvulso
    av = db_session.query(CertificadoAvulso).filter(CertificadoAvulso.id == r.json()["id"]).first()
    assert "Bafômetro" in av.html and "Alcoscan" in av.html
    assert "[" not in av.html      # patrimonio (aparelho de POC nao tem) sai vazio, nao literal


def test_campos_mortos_do_payload_sao_recusados(client, usuario_lab, os_base, db_session):
    """modelo/marca/patrimonio saíram do formulario: nao adianta mandar, nao sao lidos."""
    _modelo(db_session, os_base, texto="<p>[modelo]</p>")
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-avulsos",
                    json=_payload(os_base, modelo="INVENTADO"), headers=h)
    assert r.status_code == 201

    from app.models import CertificadoAvulso
    av = db_session.query(CertificadoAvulso).filter(CertificadoAvulso.id == r.json()["id"]).first()
    assert "INVENTADO" not in av.html
    assert "Bafômetro" in av.html      # o catalogo vence


def test_gerar_avulso_nao_cria_nem_altera_nenhuma_OS(client, usuario_lab, os_base, db_session):
    """O ponto da feature: nada de OS, cliente ou aparelho e tocado."""
    from app.models import Ordem
    _modelo(db_session, os_base)
    antes = db_session.query(Ordem).count()
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.post("/certificados-avulsos", json=_payload(os_base), headers=h).status_code == 201
    assert db_session.query(Ordem).count() == antes


def test_gerar_avulso_sem_template_409(client, usuario_lab, os_base, db_session):
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-avulsos", json=_payload(os_base), headers=h)
    assert r.status_code == 409
    assert "modelo" in r.json()["detail"].lower()


def test_gerar_avulso_exige_laboratorio_403(client, usuario_comercial, os_base, db_session):
    _modelo(db_session, os_base)
    h = _headers(client, "comercial@hs.com", "senha123")
    r = client.post("/certificados-avulsos", json=_payload(os_base), headers=h)
    assert r.status_code == 403


def test_admin_tambem_pode_gerar(client, usuario_admin, os_base, db_session):
    _modelo(db_session, os_base)
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.post("/certificados-avulsos", json=_payload(os_base), headers=h).status_code == 201


def test_listar_avulsos(client, usuario_lab, os_base, db_session):
    _modelo(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    client.post("/certificados-avulsos", json=_payload(os_base, calib_cert="AV-1"), headers=h)
    client.post("/certificados-avulsos", json=_payload(os_base, calib_cert="AV-2"), headers=h)
    itens = client.get("/certificados-avulsos", headers=h).json()
    assert [i["calib_cert"] for i in itens] == ["AV-2", "AV-1"]   # mais recentes primeiro
    assert itens[0]["usuario_nome"] == usuario_lab.nome


def test_baixar_pdf_do_avulso(client, usuario_lab, os_base, db_session, monkeypatch):
    from app.api import certificados_avulsos
    monkeypatch.setattr(certificados_avulsos, "html_para_pdf", lambda html: b"%PDF-fake")
    _modelo(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    cid = client.post("/certificados-avulsos", json=_payload(os_base), headers=h).json()["id"]
    r = client.get(f"/certificados-avulsos/{cid}/pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_baixar_pdf_inexistente_404(client, usuario_lab):
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.get("/certificados-avulsos/9999/pdf", headers=h).status_code == 404
