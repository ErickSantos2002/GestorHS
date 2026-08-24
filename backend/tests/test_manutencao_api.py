"""Manutencao da OS: uma por OS, registrada pelo Laboratorio do laboratorio em diante."""
import pytest


def _os(db, os_base, fase=5, tipo="M"):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico=tipo, situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o.id


def _servico(client, descricao, resumo):
    return client.post("/manutencao-servicos",
                       json={"descricao": descricao, "resumo_padrao": resumo}).json()["id"]


def test_registrar_manutencao(client_lab, os_base, fases_seed, db_session):
    oid = _os(db_session, os_base)
    s1 = _servico(client_lab, "Troca de Pilha interna", "Pilha da placa mãe substituída.")
    s2 = _servico(client_lab, "Troca do Bluetooth Mercury", "Módulo Bluetooth trocado.")
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={
        "numero": "HF00715", "data_manutencao": "2026-08-21",
        "resumo": "Pilha da placa mãe substituída. Módulo Bluetooth trocado.",
        "servicos": [s1, s2],
    })
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["numero"] == "HF00715"
    assert [x["descricao"] for x in corpo["servicos"]] == \
        ["Troca de Pilha interna", "Troca do Bluetooth Mercury"]


def test_registrar_de_novo_atualiza_e_nao_duplica(client_lab, os_base, fases_seed, db_session):
    from app.models import Manutencao
    oid = _os(db_session, os_base)
    s1 = _servico(client_lab, "A", "a.")
    s2 = _servico(client_lab, "B", "b.")
    client_lab.put(f"/ordens/{oid}/manutencao", json={"numero": "1", "servicos": [s1]})
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={"numero": "2", "servicos": [s2]})
    assert r.status_code == 200
    assert r.json()["numero"] == "2"
    assert [x["descricao"] for x in r.json()["servicos"]] == ["B"]
    db_session.expire_all()
    assert db_session.query(Manutencao).filter(Manutencao.os == oid).count() == 1


def test_ordem_dos_servicos_e_preservada(client_lab, os_base, fases_seed, db_session):
    """A ordem escolhida define a ordem no texto do documento."""
    oid = _os(db_session, os_base)
    a = _servico(client_lab, "A", "a.")
    b = _servico(client_lab, "B", "b.")
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={"servicos": [b, a]})
    assert [x["descricao"] for x in r.json()["servicos"]] == ["B", "A"]


def test_servico_inexistente_vira_422(client_lab, os_base, fases_seed, db_session):
    oid = _os(db_session, os_base)
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={"servicos": [99999]})
    assert r.status_code == 422


def test_ler_manutencao(client_lab, os_base, fases_seed, db_session):
    oid = _os(db_session, os_base)
    s1 = _servico(client_lab, "A", "a.")
    client_lab.put(f"/ordens/{oid}/manutencao", json={"numero": "HF1", "servicos": [s1]})
    r = client_lab.get(f"/ordens/{oid}/manutencao")
    assert r.status_code == 200
    assert r.json()["numero"] == "HF1"


def test_ler_sem_manutencao_vira_404(client_lab, os_base, fases_seed, db_session):
    oid = _os(db_session, os_base)
    assert client_lab.get(f"/ordens/{oid}/manutencao").status_code == 404


@pytest.mark.parametrize("fase", [4, 9])
def test_fora_da_janela_recusa(client_lab, os_base, fases_seed, db_session, fase):
    """Antes do laboratorio nao ha o que registrar; cancelada nao se mexe."""
    oid = _os(db_session, os_base, fase=fase)
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={"numero": "1"})
    assert r.status_code == 409


@pytest.mark.parametrize("fase", [5, 6, 10, 7, 8])
def test_dentro_da_janela_aceita(client_lab, os_base, fases_seed, db_session, fase):
    """Inclui o Financeiro (10), que vem logo depois do Pos-Vendas no fluxo."""
    oid = _os(db_session, os_base, fase=fase)
    assert client_lab.put(f"/ordens/{oid}/manutencao", json={"numero": "1"}).status_code == 200


def test_financeiro_aceita_registro(client_lab, os_base, fases_seed, db_session):
    """Regressao: a janela era a lista crua (5, 6, 7, 8) e o id 10 ficava fora,
    travando a manutencao na fase por onde TODA OS passa."""
    oid = _os(db_session, os_base, fase=10)
    s1 = _servico(client_lab, "Troca da placa mãe", "Placa substituída.")
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={
        "numero": "HF00999", "data_manutencao": "2026-08-21", "servicos": [s1]})
    assert r.status_code == 200
    assert r.json()["numero"] == "HF00999"


def test_outra_funcao_nao_registra(client, usuario_financeiro, os_base, fases_seed, db_session):
    oid = _os(db_session, os_base)
    tok = client.post("/auth/login", json={"email": "fin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    assert client.put(f"/ordens/{oid}/manutencao", json={"numero": "1"}, headers=h).status_code == 403


def test_os_inexistente_404(client_lab):
    assert client_lab.put("/ordens/999999/manutencao", json={"numero": "1"}).status_code == 404


def test_resumo_vazio_e_composto_a_partir_dos_servicos(client_lab, os_base, fases_seed, db_session):
    """A composicao tem dono no servidor: a tela so faz preview.

    O texto e' padrao — aparelho e frase de conformidade UMA vez, servicos
    listados. Antes emendava uma frase por servico e ficava longo com tres ou mais.
    """
    oid = _os(db_session, os_base)
    s1 = _servico(client_lab, "Troca da placa mãe", "Placa substituída.")
    s2 = _servico(client_lab, "Troca da bateria", "Bateria trocada.")
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={"servicos": [s1, s2]})
    assert r.status_code == 200
    resumo = r.json()["resumo"]
    assert "referente aos serviços: " in resumo
    assert "Troca da placa mãe" in resumo and "Troca da bateria" in resumo
    assert resumo.count("em conformidade") == 1


def test_resumo_informado_nao_e_sobrescrito(client_lab, os_base, fases_seed, db_session):
    oid = _os(db_session, os_base)
    s1 = _servico(client_lab, "Troca da placa mãe", "Placa substituída.")
    r = client_lab.put(f"/ordens/{oid}/manutencao",
                       json={"servicos": [s1], "resumo": "Texto escrito à mão."})
    assert r.json()["resumo"] == "Texto escrito à mão."
