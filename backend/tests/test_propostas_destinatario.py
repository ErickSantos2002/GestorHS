from app.models import Cliente, Empresa, EquipamentoCliente, Proposta

CNPJ_MATRIZ = "08857492000148"
CNPJ_FILIAL = "36312056000552"


def _cliente(db, **kw):
    base = dict(nome="ACME", cgc=CNPJ_MATRIZ, obs="nao mexer", whatsapp="81911112222")
    base.update(kw)
    c = Cliente(**base); db.add(c); db.commit(); db.refresh(c)
    return c


def _aparelho(db, cliente_id):
    from app.models import Equipamento
    equip = Equipamento(descricao="Bafometro X1"); db.add(equip); db.flush()
    ec = EquipamentoCliente(cliente=cliente_id, equipamento=equip.id, serie="SN-1")
    db.add(ec); db.commit(); db.refresh(ec)
    return ec


def _dest(tipo, **kw):
    base = {"tipo": tipo, "nome": "ACME Atualizada", "email": "novo@acme.com", "telefone": "8130001111",
            "cep": "50000-000", "endereco": "Rua Nova", "numero": "S/N", "bairro": "Centro",
            "municipio": "Recife", "estado": "PE"}
    base.update(kw)
    return base


def test_destinatario_cliente_atualiza_so_os_campos_do_modal(client_comercial, db_session):
    cli = _cliente(db_session)
    r = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id), "itens": []})
    assert r.status_code == 201, r.text
    corpo = r.json()
    db_session.refresh(cli)
    assert cli.nome == "ACME Atualizada" and cli.email == "novo@acme.com"
    assert cli.telefones == "8130001111" and cli.cep == "50000000"
    assert cli.numero is None            # "S/N" nao cabe no BigInteger do cliente
    assert cli.obs == "nao mexer" and cli.whatsapp == "81911112222"
    assert corpo["cliente"] == cli.id and corpo["empresa"] is None
    assert corpo["destinatario"]["tipo"] == "cliente"
    assert corpo["destinatario"]["numero"] is None
    assert corpo["cliente_nome"] == "ACME Atualizada"


def test_documento_enviado_para_cliente_existente_e_ignorado(client_comercial, db_session):
    cli = _cliente(db_session)
    r = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id, documento=CNPJ_FILIAL)})
    assert r.status_code == 201
    db_session.refresh(cli)
    assert cli.cgc == CNPJ_MATRIZ


def test_destinatario_empresa_usa_a_matriz_como_cliente(client_comercial, db_session):
    cli = _cliente(db_session)
    emp = Empresa(nome="Filial", cgc=CNPJ_FILIAL, cliente=cli.id); db_session.add(emp); db_session.commit()
    ec = _aparelho(db_session, cli.id)
    r = client_comercial.post("/propostas", json={
        "destinatario": _dest("empresa", id=emp.id, nome="Filial Norte"),
        "aparelhos": [{"equipamento_cliente": ec.id}],
    })
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["empresa"] == emp.id and corpo["cliente"] == cli.id
    assert corpo["destinatario"]["matriz_nome"] == "ACME"
    assert corpo["destinatario"]["numero"] == "S/N"
    db_session.refresh(emp)
    assert emp.nome == "Filial Norte" and emp.telefone == "8130001111"


def test_nova_empresa_e_criada_na_mesma_transacao(client_comercial, db_session):
    cli = _cliente(db_session)
    r = client_comercial.post("/propostas", json={
        "destinatario": _dest("nova_empresa", documento="36.312.056/0005-52", matriz=cli.id, nome="Filial Nova"),
    })
    assert r.status_code == 201, r.text
    emp = db_session.query(Empresa).one()
    assert emp.nome == "Filial Nova" and emp.cgc == CNPJ_FILIAL and emp.cliente == cli.id
    assert r.json()["empresa"] == emp.id


def test_falha_na_proposta_desfaz_a_empresa_nova(client_comercial, db_session):
    outro = _cliente(db_session, nome="Outro", cgc="11222333000181")
    ec = _aparelho(db_session, outro.id)
    r = client_comercial.post("/propostas", json={
        "destinatario": _dest("nova_empresa", documento=CNPJ_FILIAL, matriz=None),
        "aparelhos": [{"equipamento_cliente": ec.id}],   # empresa sem matriz nao tem frota
    })
    assert r.status_code == 422
    assert db_session.query(Empresa).count() == 0
    assert db_session.query(Proposta).count() == 0


def test_falha_na_proposta_desfaz_a_edicao_do_cliente(client_comercial, db_session):
    cli = _cliente(db_session)
    outro = _cliente(db_session, nome="Outro", cgc="11222333000181")
    ec = _aparelho(db_session, outro.id)
    r = client_comercial.post("/propostas", json={
        "destinatario": _dest("cliente", id=cli.id),
        "aparelhos": [{"equipamento_cliente": ec.id}],   # aparelho de outra frota
    })
    assert r.status_code == 422
    db_session.expire_all()
    assert db_session.get(Cliente, cli.id).nome == "ACME"


def test_nova_empresa_com_documento_de_cliente_409(client_comercial, db_session):
    _cliente(db_session, cgc=CNPJ_FILIAL)
    r = client_comercial.post("/propostas", json={"destinatario": _dest("nova_empresa", documento=CNPJ_FILIAL)})
    assert r.status_code == 409
    assert r.json()["detail"].startswith("Documento já cadastrado como Cliente")


def test_nova_empresa_documento_invalido_422(client_comercial):
    r = client_comercial.post("/propostas", json={"destinatario": _dest("nova_empresa", documento="08857492000149")})
    assert r.status_code == 422


def test_destinatario_desativado_em_proposta_nova_409(client_comercial, db_session):
    cli = _cliente(db_session, ativo=False)
    r = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id)})
    assert r.status_code == 409


def test_proposta_antiga_de_destinatario_desativado_continua_salvando(client_comercial, db_session):
    cli = _cliente(db_session)
    pid = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id)}).json()["id"]
    cli.ativo = False; db_session.commit()
    r = client_comercial.put(f"/propostas/{pid}", json={"destinatario": _dest("cliente", id=cli.id), "desconto": 5})
    assert r.status_code == 200, r.text


def test_destinatario_do_payload_nao_e_gravado_como_copia(client_comercial, db_session):
    cli = _cliente(db_session)
    r = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id)})
    p = db_session.get(Proposta, r.json()["id"])
    # a copia tem as chaves do cadastro (vindas de dados_destinatario), nao o bloco de entrada
    assert "matriz" not in p.destinatario and p.destinatario["documento"] == CNPJ_MATRIZ


def test_put_sem_destinatario_nao_mexe_na_copia(client_comercial, db_session):
    cli = _cliente(db_session)
    pid = client_comercial.post("/propostas", json={"destinatario": _dest("cliente", id=cli.id)}).json()["id"]
    cli.municipio = "Olinda"; db_session.commit()
    r = client_comercial.put(f"/propostas/{pid}", json={"desconto": 10})
    assert r.status_code == 200
    # PUT sem destinatario nao recongela: a copia continua com o municipio de
    # quando a proposta foi criada, mesmo o cadastro tendo mudado depois.
    assert r.json()["destinatario"]["municipio"] == "Recife"


def test_put_sem_destinatario_preserva_override_legado(client_comercial, db_session):
    cli = _cliente(db_session)
    p = Proposta(numero=60, cliente=cli.id,
                 cliente_override={"nome": "ACME Filial", "documento": "99988877000166"})
    db_session.add(p); db_session.commit(); db_session.refresh(p)

    r = client_comercial.put(f"/propostas/{p.id}", json={"desconto": 1})
    assert r.status_code == 200, r.text
    assert r.json()["cliente_nome"] == "ACME Filial"

    db_session.expire_all()
    assert db_session.get(Proposta, p.id).destinatario is None


def test_duplicar_proposta_legada_leva_os_dados_do_override(client_comercial, db_session):
    cli = _cliente(db_session)
    p = Proposta(numero=61, cliente=cli.id,
                 cliente_override={"nome": "ACME Filial", "documento": "99988877000166"})
    db_session.add(p); db_session.commit(); db_session.refresh(p)

    r = client_comercial.post(f"/propostas/{p.id}/duplicar")
    assert r.status_code == 201, r.text
    assert r.json()["cliente_nome"] == "ACME Filial"


def test_trocar_para_empresa_sem_matriz_com_aparelhos_antigos_422(client_comercial, db_session):
    cli = _cliente(db_session)
    ec = _aparelho(db_session, cli.id)
    pid = client_comercial.post("/propostas", json={
        "destinatario": _dest("cliente", id=cli.id), "aparelhos": [{"equipamento_cliente": ec.id}],
    }).json()["id"]
    emp = Empresa(nome="Solta", cgc=CNPJ_FILIAL); db_session.add(emp); db_session.commit()
    r = client_comercial.put(f"/propostas/{pid}", json={"destinatario": _dest("empresa", id=emp.id)})
    assert r.status_code == 422


def test_proposta_sem_destinatario_continua_permitida(client_comercial):
    r = client_comercial.post("/propostas", json={"itens": []})
    assert r.status_code == 201
    assert r.json()["cliente"] is None and r.json()["destinatario"] is None


def test_montar_saida_cai_no_legado_quando_nao_ha_copia(db_session):
    from app.core import proposta_servico as ps
    cli = _cliente(db_session)
    p = Proposta(numero=50, cliente=cli.id, cliente_override={"nome": "ACME Filial", "documento": "99988877000166"})
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    saida = ps.montar_saida(db_session, p)
    assert saida.cliente_nome == "ACME Filial"
    assert saida.cliente_documento == "99988877000166"


def test_listar_encontra_pelo_nome_e_documento_da_empresa(client_comercial, db_session):
    emp = Empresa(nome="Filial Busca", cgc=CNPJ_FILIAL); db_session.add(emp); db_session.commit()
    client_comercial.post("/propostas", json={"destinatario": _dest("empresa", id=emp.id, nome="Filial Busca")})
    assert client_comercial.get("/propostas", params={"q": "Filial Busca"}).json()["total"] == 1
    assert client_comercial.get("/propostas", params={"q": "36.312.056/0005-52"}).json()["total"] == 1


def test_duplicar_copia_o_vinculo_com_a_empresa(client_comercial, db_session):
    cli = _cliente(db_session)
    emp = Empresa(nome="Filial", cgc=CNPJ_FILIAL, cliente=cli.id); db_session.add(emp); db_session.commit()
    ec = _aparelho(db_session, cli.id)
    pid = client_comercial.post("/propostas", json={
        "destinatario": _dest("empresa", id=emp.id), "aparelhos": [{"equipamento_cliente": ec.id}],
    }).json()["id"]
    r = client_comercial.post(f"/propostas/{pid}/duplicar")
    assert r.status_code == 201, r.text
    nova = r.json()
    assert nova["empresa"] == emp.id and nova["cliente"] == cli.id
    assert nova["destinatario"]["tipo"] == "empresa"
    assert len(nova["aparelhos"]) == 1


def test_busca_de_destinatario_mistura_clientes_e_empresas_ativos(client_lab, db_session):
    cli = _cliente(db_session, nome="Rumo Matriz")
    _cliente(db_session, nome="Rumo Inativo", cgc="11222333000181", ativo=False)
    db_session.add(Empresa(nome="Rumo Filial PR", cgc=CNPJ_FILIAL, cliente=cli.id, municipio="Curitiba", estado="PR"))
    db_session.commit()
    r = client_lab.get("/propostas/destinatarios", params={"q": "rumo"})
    assert r.status_code == 200
    itens = r.json()
    assert [(i["tipo"], i["nome"]) for i in itens] == [("cliente", "Rumo Matriz"), ("empresa", "Rumo Filial PR")]
    assert itens[1]["matriz_id"] == cli.id and itens[1]["matriz_nome"] == "Rumo Matriz"


def test_busca_de_destinatario_por_documento_com_mascara(client_lab, db_session):
    db_session.add(Empresa(nome="Filial", cgc=CNPJ_FILIAL)); db_session.commit()
    itens = client_lab.get("/propostas/destinatarios", params={"q": "36.312.056/0005-52"}).json()
    assert len(itens) == 1 and itens[0]["documento"] == CNPJ_FILIAL


def test_busca_de_destinatario_sem_resultado(client_lab):
    assert client_lab.get("/propostas/destinatarios", params={"q": "36312056000552"}).json() == []


def test_busca_de_destinatario_exige_termo(client_lab):
    assert client_lab.get("/propostas/destinatarios", params={"q": "a"}).status_code == 422


def test_get_proposta_legada_traz_o_contato_do_override(client_comercial, db_session):
    cli = _cliente(db_session)
    p = Proposta(numero=62, cliente=cli.id, contato=None,
                 cliente_override={"nome": "ACME", "contato": "Tatiane"})
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    r = client_comercial.get(f"/propostas/{p.id}")
    assert r.status_code == 200, r.text
    assert r.json()["contato"] == "Tatiane"


def test_get_proposta_prefere_o_contato_da_coluna(client_comercial, db_session):
    cli = _cliente(db_session)
    p = Proposta(numero=64, cliente=cli.id, contato="Joana",
                 cliente_override={"nome": "ACME", "contato": "Tatiane"})
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    assert client_comercial.get(f"/propostas/{p.id}").json()["contato"] == "Joana"


def test_duplicar_proposta_legada_leva_o_contato_do_override(client_comercial, db_session):
    cli = _cliente(db_session)
    p = Proposta(numero=63, cliente=cli.id, contato="",
                 cliente_override={"nome": "ACME", "contato": "Tatiane"})
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    r = client_comercial.post(f"/propostas/{p.id}/duplicar")
    assert r.status_code == 201, r.text
    assert r.json()["contato"] == "Tatiane"


def test_busca_de_destinatario_so_espacos_e_422(client_lab):
    r = client_lab.get("/propostas/destinatarios", params={"q": "   "})
    assert r.status_code == 422
    assert client_lab.get("/propostas/destinatarios", params={"q": " a "}).status_code == 422


def test_busca_de_destinatario_termo_com_letra_nao_casa_documento(client_lab, db_session):
    """A busca do modal e' onde o falso positivo de 16/09/2026 apareceu."""
    _cliente(db_session, nome="Dono da Serie", cgc="30069314006576")
    assert client_lab.get("/propostas/destinatarios", params={"q": "WAO4O0065"}).json() == []
    assert len(client_lab.get("/propostas/destinatarios", params={"q": "300.693.14"}).json()) == 1
