from app.models import Cliente, Empresa, Proposta
from app.scripts import migrar_filiais_propostas as mig

MATRIZ = "08857492000148"
FILIAL = "36312056000552"


def _base(db):
    cli = Cliente(nome="ACME", cgc=MATRIZ, endereco="Rua Matriz", municipio="Recife", estado="PE")
    db.add(cli); db.flush()
    ov_filial = {"nome": "ACME Filial", "documento": "36.312.056/0005-52", "endereco": "BR 101",
                 "municipio": "Joao Neiva", "estado": "es", "cep": "29680-000",
                 "email": "f@acme.com", "telefone": "2733330000"}
    p1 = Proposta(numero=1, cliente=cli.id, cliente_override=ov_filial)
    p2 = Proposta(numero=2, cliente=cli.id, cliente_override=dict(ov_filial, telefone="2799990000"))
    p3 = Proposta(numero=3, cliente=cli.id, cliente_override={"nome": "ACME com outro nome"})
    p4 = Proposta(numero=4)
    db.add_all([p1, p2, p3, p4]); db.commit()
    return cli, p1, p2, p3, p4


def test_planejar_nao_grava_nada(db_session):
    _, p1, p2, p3, p4 = _base(db_session)
    plano = mig.planejar(db_session)
    assert sorted(plano.congelar) == sorted([p1.id, p2.id, p3.id, p4.id])
    assert plano.criar == {FILIAL: p1.id}
    assert plano.ligar == {p1.id: FILIAL, p2.id: FILIAL}
    assert db_session.query(Empresa).count() == 0
    assert db_session.get(Proposta, p1.id).destinatario is None


def test_aplicar_cria_uma_empresa_e_liga_as_duas_propostas(db_session):
    cli, p1, p2, p3, p4 = _base(db_session)
    resumo = mig.aplicar(db_session, mig.planejar(db_session))
    emp = db_session.query(Empresa).one()
    assert (emp.nome, emp.cgc, emp.cliente) == ("ACME Filial", FILIAL, cli.id)
    assert (emp.estado, emp.cep) == ("ES", "29680000")
    assert emp.endereco == "BR 101" and emp.bairro is None      # nada herdado da matriz
    db_session.expire_all()
    for p in (db_session.get(Proposta, p1.id), db_session.get(Proposta, p2.id)):
        assert p.empresa == emp.id
        assert p.destinatario["tipo"] == "empresa" and p.destinatario["matriz_nome"] == "ACME"
    # a copia preserva o que o override de cada proposta dizia
    assert db_session.get(Proposta, p2.id).destinatario["telefone"] == "2799990000"
    p3 = db_session.get(Proposta, p3.id)
    assert p3.empresa is None and p3.destinatario["nome"] == "ACME com outro nome"
    assert db_session.get(Proposta, p4.id).destinatario["nome"] is None
    assert resumo["empresas_criadas"] == 1 and resumo["propostas_ligadas"] == 2


def test_documento_de_cliente_e_recusado(db_session):
    cli, p1, *_ = _base(db_session)
    dono = Cliente(nome="Ja E Cliente", cgc=FILIAL); db_session.add(dono); db_session.commit()
    plano = mig.planejar(db_session)
    assert plano.recusados == {FILIAL: (dono.id, "Ja E Cliente")}
    assert plano.ligar == {}
    mig.aplicar(db_session, plano)
    assert db_session.query(Empresa).count() == 0
    assert db_session.get(Proposta, p1.id).destinatario["tipo"] == "cliente"


def test_empresa_existente_e_reaproveitada(db_session):
    cli, p1, p2, *_ = _base(db_session)
    emp = Empresa(nome="Ja Cadastrada", cgc=FILIAL); db_session.add(emp); db_session.commit()
    plano = mig.planejar(db_session)
    assert plano.reaproveitar == {FILIAL: emp.id} and plano.criar == {}
    mig.aplicar(db_session, plano)
    assert db_session.query(Empresa).count() == 1
    assert db_session.get(Proposta, p1.id).empresa == emp.id


def test_documento_invalido_ou_sem_nome_fica_so_congelado(db_session):
    cli = Cliente(nome="ACME", cgc=MATRIZ); db_session.add(cli); db_session.flush()
    ruim = Proposta(numero=9, cliente=cli.id, cliente_override={"nome": "X", "documento": "36312056000559"})
    sem_nome = Proposta(numero=10, cliente=cli.id, cliente_override={"documento": FILIAL})
    db_session.add_all([ruim, sem_nome]); db_session.commit()
    plano = mig.planejar(db_session)
    assert set(plano.invalidos) == {ruim.id, sem_nome.id}
    assert plano.criar == {}


def test_segunda_execucao_nao_faz_nada(db_session):
    _base(db_session)
    mig.aplicar(db_session, mig.planejar(db_session))
    plano = mig.planejar(db_session)
    assert plano.congelar == [] and plano.criar == {} and plano.ligar == {}
    assert db_session.query(Empresa).count() == 1


def test_main_sem_aplicar_so_simula(db_session, monkeypatch, capsys):
    _base(db_session)
    monkeypatch.setattr(mig, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    mig.main([])
    assert "SIMULACAO" in capsys.readouterr().out
    assert db_session.query(Empresa).count() == 0
