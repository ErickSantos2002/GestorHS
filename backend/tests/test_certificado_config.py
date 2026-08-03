from datetime import date

from app.core.certificado_config import obter_config, padrao_vigente, parametros_de
from app.models import CertificadoPadrao


def test_config_e_singleton_e_nasce_com_os_valores_da_planilha(db_session):
    c1 = obter_config(db_session)
    assert float(c1.valor_referencia) == 0.1
    assert float(c1.limite_minimo) == 0.15
    assert float(c1.limite_maximo) == 0.19
    assert float(c1.resolucao_instrumento) == 0.1
    assert float(c1.incerteza_padrao_temp) == 0.052
    assert float(c1.fator_k) == 2
    assert c1.tecnico_nome == "Walbert Santos"

    # segunda chamada devolve a MESMA linha — nao cria outra
    c2 = obter_config(db_session)
    assert c2.id == c1.id
    assert db_session.query(type(c1)).count() == 1


def test_parametros_de_converte_decimal_para_float(db_session):
    p = parametros_de(obter_config(db_session))
    assert p.valor_referencia == 0.1
    assert p.resolucao_instrumento == 0.1
    assert p.incerteza_padrao_temp == 0.052
    assert p.resolucao_pressao is None
    assert p.fator_k == 2.0


def _padrao(db, **kw):
    dados = dict(
        numero_cilindro="CC747704", numero_certificado="202231419",
        concentracao=100.1, incerteza_concentracao=2.0, unidade="µmol/mol",
        vigencia_inicio=date(2025, 1, 1), vigencia_fim=None, ativo=True,
    )
    dados.update(kw)
    obj = CertificadoPadrao(**dados)
    db.add(obj)
    db.commit()
    return obj


def test_padrao_vigente_resolve_pela_data(db_session):
    antigo = _padrao(db_session, numero_cilindro="ANTIGO",
                     vigencia_inicio=date(2024, 1, 1), vigencia_fim=date(2024, 12, 31))
    atual = _padrao(db_session, vigencia_inicio=date(2025, 1, 1), vigencia_fim=None)

    assert padrao_vigente(db_session, date(2024, 6, 1)).id == antigo.id
    assert padrao_vigente(db_session, date(2026, 6, 1)).id == atual.id


def test_padrao_vigente_sem_correspondencia_devolve_none(db_session):
    # OS antiga, anterior a qualquer cilindro cadastrado: nao inventa padrao
    _padrao(db_session, vigencia_inicio=date(2025, 1, 1))
    assert padrao_vigente(db_session, date(2020, 1, 1)) is None
    assert padrao_vigente(db_session, None) is None


def test_padrao_inativo_e_ignorado(db_session):
    _padrao(db_session, ativo=False)
    assert padrao_vigente(db_session, date(2026, 1, 1)) is None


def test_ordem_tem_as_colunas_novas(db_session):
    from app.models import Ordem
    assert hasattr(Ordem, "calib_teste4")
    assert hasattr(Ordem, "calib_teste5")
    assert hasattr(Ordem, "padrao_id")


def test_equipamento_cliente_tem_as_colunas_novas():
    from app.models import EquipamentoCliente
    assert hasattr(EquipamentoCliente, "calib_teste4")
    assert hasattr(EquipamentoCliente, "calib_teste5")


def test_get_config_devolve_os_valores(client_admin):
    r = client_admin.get("/certificado-config")
    assert r.status_code == 200
    # Numeric no SQLite volta como Decimal de precisao imprevisivel: comparar em float
    assert float(r.json()["valor_referencia"]) == 0.1
    assert r.json()["tecnico_nome"] == "Walbert Santos"


def test_put_config_grava_e_continua_singleton(client_admin, db_session):
    from app.models import CertificadoConfig
    r = client_admin.put("/certificado-config", json={
        "valor_referencia": "0.17", "limite_minimo": "0.15", "limite_maximo": "0.19",
        "resolucao_instrumento": "0.01", "incerteza_padrao_temp": "0.052",
        "resolucao_pressao": None, "incerteza_padrao_pressao": None, "fator_k": "2",
        "tecnico_nome": "Outro Tecnico", "tecnico_cargo": "Tecnico em Metrologia",
        "equipamentos_auxiliares": "TESTO 622", "margem_temperatura": "20 ºC ~ 24 ºC",
    })
    assert r.status_code == 200
    assert r.json()["tecnico_nome"] == "Outro Tecnico"
    assert float(r.json()["resolucao_instrumento"]) == 0.01
    assert db_session.query(CertificadoConfig).count() == 1


def test_put_config_negado_para_nao_admin(client_lab):
    r = client_lab.put("/certificado-config", json={"tecnico_nome": "X"})
    assert r.status_code == 403


def test_lab_le_a_config_para_o_modal(client_lab):
    # o modal precisa dos limites para destacar medicao fora da faixa
    assert client_lab.get("/certificado-config").status_code == 200


def test_crud_de_padroes(client_admin):
    r = client_admin.post("/certificado-padroes", json={
        "numero_cilindro": "CC747704", "numero_certificado": "202231419",
        "concentracao": "100.1", "incerteza_concentracao": "2.0",
        "unidade": "µmol/mol", "vigencia_inicio": "2025-01-01",
        "vigencia_fim": None, "ativo": True,
    })
    assert r.status_code == 201
    padrao_id = r.json()["id"]

    assert len(client_admin.get("/certificado-padroes").json()) == 1

    r = client_admin.patch(f"/certificado-padroes/{padrao_id}", json={"vigencia_fim": "2026-12-31"})
    assert r.status_code == 200
    assert r.json()["vigencia_fim"] == "2026-12-31"

    assert client_admin.delete(f"/certificado-padroes/{padrao_id}").status_code == 204
    assert client_admin.get("/certificado-padroes").json() == []


def test_criar_padrao_negado_para_nao_admin(client_lab):
    r = client_lab.post("/certificado-padroes", json={"numero_cilindro": "X"})
    assert r.status_code == 403


def test_previa_de_calculo_devolve_os_numeros_da_planilha(client_lab):
    r = client_lab.post("/certificado-calculo-previa",
                        json={"medicoes": ["0.16", "0.16", "0.16", "0.16", "0.16"]})
    assert r.status_code == 200
    corpo = r.json()
    # Casas fixas, iguais as do PDF: o painel do modal e o certificado nao podem
    # mostrar numeros diferentes para a mesma medicao.
    assert corpo["erros"] == ["0,060"] * 5
    assert corpo["media"] == "0,160"
    assert corpo["incerteza_expandida"] == "0,1301"
    assert corpo["fator_k"] == "2"
    assert corpo["limite_minimo"] == "0,150"
    assert corpo["limite_maximo"] == "0,190"
    assert corpo["fora_da_faixa"] == [False] * 5


def test_previa_marca_medicao_fora_da_faixa(client_lab):
    r = client_lab.post("/certificado-calculo-previa",
                        json={"medicoes": ["0.16", "0.016", "", "", ""]})
    assert r.json()["fora_da_faixa"] == [False, True, False, False, False]
    # medicao em branco nao e "fora da faixa" — e ausencia de medicao
    assert r.json()["erros"][2] == ""


def test_excluir_padrao_em_uso_por_os_devolve_409(client_admin, db_session):
    """ordens.padrao_id e FK sem ON DELETE: sem a guarda, o Postgres estoura
    IntegrityError e o admin recebe um 500 sem explicacao."""
    from app.models import Cliente, EquipamentoCliente, Equipamento, Ordem

    r = client_admin.post("/certificado-padroes", json={
        "numero_cilindro": "CC747704", "vigencia_inicio": "2025-01-01", "ativo": True,
    })
    padrao_id = r.json()["id"]

    cat = Equipamento(descricao="Mark X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id, serie="S1")
    db_session.add(ec); db_session.flush()
    db_session.add(Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5,
                         situacao="E", tipo_servico="C", padrao_id=padrao_id))
    db_session.commit()

    r = client_admin.delete(f"/certificado-padroes/{padrao_id}")
    assert r.status_code == 409
    assert "vigência fim" in r.json()["detail"]
    # e o cilindro continua la — a rastreabilidade dos certificados emitidos depende dele
    assert len(client_admin.get("/certificado-padroes").json()) == 1


def test_atualizar_padrao_negado_para_nao_admin(client_lab):
    r = client_lab.patch("/certificado-padroes/1", json={"vigencia_fim": "2026-12-31"})
    assert r.status_code == 403


def test_excluir_padrao_negado_para_nao_admin(client_lab):
    r = client_lab.delete("/certificado-padroes/1")
    assert r.status_code == 403


def test_padrao_vigente_desempata_pelo_id_quando_a_vigencia_inicio_empata(db_session):
    """Dois cilindros abertos com a mesma data de inicio: vence o cadastrado por
    ultimo. O desempate precisa ser deterministico porque a tela (padraoVigente.ts)
    espelha esta regra para dizer qual cilindro esta em uso."""
    primeiro = _padrao(db_session, numero_cilindro="A", vigencia_inicio=date(2025, 1, 1))
    segundo = _padrao(db_session, numero_cilindro="B", vigencia_inicio=date(2025, 1, 1))
    assert primeiro.id < segundo.id
    assert padrao_vigente(db_session, date(2026, 1, 1)).id == segundo.id


# --- entrada em formato pt-BR ---------------------------------------------------
# O app IMPRIME numero com virgula (formatar_numero devolve "0,1301"), entao o
# laboratorio digita com virgula. Recusar isso com 422 e culpar o usuario por
# seguir o formato do proprio sistema.

def test_criar_padrao_aceita_virgula_decimal(client_admin):
    r = client_admin.post("/certificado-padroes", json={
        "numero_cilindro": "CC747704", "numero_certificado": "202231419",
        "concentracao": "100,1", "incerteza_concentracao": "2,0",
        "unidade": "µmol/mol", "vigencia_inicio": "2025-01-01",
        "vigencia_fim": None, "ativo": True,
    })
    assert r.status_code == 201
    assert float(r.json()["concentracao"]) == 100.1
    assert float(r.json()["incerteza_concentracao"]) == 2.0


def test_criar_padrao_aceita_numerico_e_data_em_branco(client_admin):
    # o formulario manda '' no campo que o usuario deixou vazio, nao null
    r = client_admin.post("/certificado-padroes", json={
        "numero_cilindro": "CC000001", "numero_certificado": "",
        "concentracao": "", "incerteza_concentracao": "",
        "unidade": "µmol/mol", "vigencia_inicio": "", "vigencia_fim": "",
        "ativo": True,
    })
    assert r.status_code == 201
    assert r.json()["concentracao"] is None
    assert r.json()["vigencia_inicio"] is None


def test_gravar_config_aceita_virgula_decimal(client_admin):
    r = client_admin.put("/certificado-config", json={
        "valor_referencia": "0,17", "resolucao_instrumento": "0,01",
    })
    assert r.status_code == 200
    assert float(r.json()["valor_referencia"]) == 0.17
    assert float(r.json()["resolucao_instrumento"]) == 0.01


# --- documentos auxiliares que viram QR no certificado ---------------------------

def _doc_geral(db, nome="Certificado do Gás", arquivo="a.pdf"):
    from app.models import CertificadoGeral
    d = CertificadoGeral(nome=nome, arquivo=arquivo)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def test_documentos_qr_traz_os_tres_configurados(db_session, monkeypatch):
    from app.core import certificado_geral_link
    from app.core.certificado_config import documentos_qr, obter_config
    monkeypatch.setattr(certificado_geral_link.settings, "CERT_PUBLIC_BASE_URL", "https://x.com")

    gas = _doc_geral(db_session, "Gás", "g.pdf")
    termo = _doc_geral(db_session, "Termo", "t.pdf")
    baro = _doc_geral(db_session, "Baro", "b.pdf")
    cfg = obter_config(db_session)
    cfg.doc_gas_id, cfg.doc_termohigrometro_id, cfg.doc_barometro_id = gas.id, termo.id, baro.id
    db_session.commit()

    itens = documentos_qr(db_session, cfg)
    assert [rotulo for rotulo, _ in itens] == [
        "Certificado do Gás",
        "Certificado do Termohigrômetro Digital",
        "Certificado do Barômetro Digital",
    ]
    assert all("/publico/certificado-geral/" in url for _, url in itens)


def test_documentos_qr_pula_o_que_nao_foi_configurado(db_session, monkeypatch):
    from app.core import certificado_geral_link
    from app.core.certificado_config import documentos_qr, obter_config
    monkeypatch.setattr(certificado_geral_link.settings, "CERT_PUBLIC_BASE_URL", "https://x.com")

    gas = _doc_geral(db_session, "Gás", "g.pdf")
    cfg = obter_config(db_session)
    cfg.doc_gas_id = gas.id          # os outros dois ficam nulos
    db_session.commit()

    itens = documentos_qr(db_session, cfg)
    assert [rotulo for rotulo, _ in itens] == ["Certificado do Gás"]


def test_documentos_qr_pula_documento_excluido_do_cadastro(db_session, monkeypatch):
    from sqlalchemy import text
    from app.core import certificado_geral_link
    from app.core.certificado_config import documentos_qr, obter_config
    monkeypatch.setattr(certificado_geral_link.settings, "CERT_PUBLIC_BASE_URL", "https://x.com")

    cfg = obter_config(db_session)
    # O FK normalmente protege esse estado (nao da pra gravar um id que nao existe em
    # certificados_gerais), entao pra forcar o dado aqui desligamos a checagem so'
    # durante o UPDATE — igual test_growthhs_elo.py faz pro mesmo tipo de cenario.
    db_session.execute(text("PRAGMA foreign_keys=OFF"))
    cfg.doc_gas_id = 9999            # id que nao existe mais
    db_session.commit()
    db_session.execute(text("PRAGMA foreign_keys=ON"))

    # Nao levanta: um documento excluido nao pode impedir a emissao do certificado.
    assert documentos_qr(db_session, cfg) == []


def test_documentos_qr_vazio_sem_base_url_publica(db_session, monkeypatch):
    from app.core import certificado_geral_link
    from app.core.certificado_config import documentos_qr, obter_config
    monkeypatch.setattr(certificado_geral_link.settings, "CERT_PUBLIC_BASE_URL", "")

    gas = _doc_geral(db_session, "Gás", "g.pdf")
    cfg = obter_config(db_session)
    cfg.doc_gas_id = gas.id
    db_session.commit()

    # Sem base publica nao ha link para o QR apontar — sai sem bloco, sem erro.
    assert documentos_qr(db_session, cfg) == []


def test_documentos_qr_pula_documento_sem_arquivo(db_session, monkeypatch):
    """Um `arquivo` vazio (nao ha constraint de banco contra string vazia) geraria um
    QR apontando para um link que o endpoint publico responde com 404 — pior que
    nao ter QR nenhum."""
    from app.core import certificado_geral_link
    from app.core.certificado_config import documentos_qr, obter_config
    monkeypatch.setattr(certificado_geral_link.settings, "CERT_PUBLIC_BASE_URL", "https://x.com")

    sem_arquivo = _doc_geral(db_session, "Gás", arquivo="")
    cfg = obter_config(db_session)
    cfg.doc_gas_id = sem_arquivo.id
    db_session.commit()

    assert documentos_qr(db_session, cfg) == []


def test_put_config_id_de_documento_apagado_devolve_422(client_admin, db_session):
    """Corrida: admin A tem a tela aberta, admin B apaga o documento ainda nao
    selecionado, admin A escolhe esse id e salva. Sem a validacao, o FK sem ON DELETE
    estoura IntegrityError e vira 500 sem explicacao."""
    gas = _doc_geral(db_session, "Gás", "g.pdf")
    id_apagado = gas.id
    db_session.delete(gas)
    db_session.commit()

    r = client_admin.put("/certificado-config", json={"doc_gas_id": id_apagado})
    assert r.status_code == 422
    assert "não existe mais" in r.json()["detail"]


def test_config_api_grava_os_tres_documentos(client_admin, db_session):
    gas = _doc_geral(db_session, "Gás", "g.pdf")
    termo = _doc_geral(db_session, "Termo", "t.pdf")
    baro = _doc_geral(db_session, "Baro", "b.pdf")
    r = client_admin.put("/certificado-config", json={
        "doc_gas_id": gas.id,
        "doc_termohigrometro_id": termo.id,
        "doc_barometro_id": baro.id,
    })
    assert r.status_code == 200
    assert r.json()["doc_gas_id"] == gas.id
    assert r.json()["doc_termohigrometro_id"] == termo.id
    assert r.json()["doc_barometro_id"] == baro.id
