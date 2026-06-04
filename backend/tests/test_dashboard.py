from datetime import date, timedelta


def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _setup(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem, Solicitacao
    hoje = date.today()
    cliA = Cliente(nome="Alfa Ltda")
    cliB = Cliente(nome="Beta SA")
    cliC = Cliente(nome="Gama ME")
    eq = Equipamento(descricao="Bafômetro")
    db_session.add_all([cliA, cliB, cliC, eq])
    db_session.flush()

    def ec(cli, prox, ativo=True):
        return EquipamentoCliente(cliente=cli, equipamento=eq.id, prox_calibragem=prox, ativo=ativo)

    ecA_vencido  = ec(cliA.id, hoje - timedelta(days=10))             # vencido
    ecA_vencendo = ec(cliA.id, hoje + timedelta(days=30))             # vencendo
    ecA_emdia    = ec(cliA.id, hoje + timedelta(days=200))            # em_dia (ignorado)
    ecA_inativo  = ec(cliA.id, hoje - timedelta(days=1), ativo=False) # inativo (ignorado)
    ecB_vencido  = ec(cliB.id, hoje - timedelta(days=2))              # vencido
    ecB_hoje     = ec(cliB.id, hoje)                                  # prox==hoje -> vencendo (não vencido)
    ecC_emdia    = ec(cliC.id, hoje + timedelta(days=300))            # em_dia só -> C fora da cobrança
    db_session.add_all([
        ecA_vencido, ecA_vencendo, ecA_emdia, ecA_inativo,
        ecB_vencido, ecB_hoje, ecC_emdia,
    ])
    db_session.flush()  # popula ids antes das FKs nas Solicitações

    # OS: fase 4 (x2), fase 5 (x1), fase 8 (finalizada, não conta)
    db_session.add_all([
        Ordem(cliente=cliA.id, fase=4),
        Ordem(cliente=cliA.id, fase=4),
        Ordem(cliente=cliB.id, fase=5),
        Ordem(cliente=cliB.id, fase=8),
    ])
    # Solicitações: 1 pendente (aparelho vencido de A) + 1 atendida (aparelho vencido de B)
    db_session.add_all([
        Solicitacao(cliente=cliA.id, equipamento_cliente=ecA_vencido.id, status="pendente"),
        Solicitacao(cliente=cliB.id, equipamento_cliente=ecB_vencido.id, status="atendida"),
    ])
    db_session.commit()
    return {"A": cliA.id, "B": cliB.id, "C": cliC.id}


def test_contagens(client, usuario_comum, fases_seed, db_session):
    _setup(db_session)
    r = client.get("/dashboard", headers=_headers(client, "comum", "senha123"))
    assert r.status_code == 200
    body = r.json()
    assert body["aparelhos_vencidos"] == 2       # A + B vencidos (ecB_hoje é vencendo, não vencido; inativo ignorado)
    assert body["aparelhos_vencendo"] == 2        # A (30 dias) + B (prox==hoje: fronteira vencendo)
    assert body["solicitacoes_pendentes"] == 1
    assert body["clientes_a_cobrar"] == 2         # A e B (C só em_dia)


def test_os_por_fase(client, usuario_comum, fases_seed, db_session):
    _setup(db_session)
    r = client.get("/dashboard", headers=_headers(client, "comum", "senha123"))
    fases = r.json()["os_por_fase"]
    assert [f["fase"] for f in fases] == [4, 5, 6, 7]   # ordem, só fases ativas
    por_fase = {f["fase"]: f["total"] for f in fases}
    assert por_fase == {4: 2, 5: 1, 6: 0, 7: 0}          # fase 8 não aparece
    assert fases[0]["descricao"] == "Recebido" and fases[0]["cor"] == "3b82f6"


def test_exige_autenticacao(client, db_session):
    assert client.get("/dashboard").status_code == 401
