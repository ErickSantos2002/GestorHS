"""link_pdf: o mesmo link publico assinado dos cards do TaskHS, nas leituras que o
Guardi usa. Para todo usuario; o token de agente, alem disso, nao recebe o html."""
from urllib.parse import parse_qs, urlparse

import pytest

from app.core import certificado_link, proposta_link
from app.core.config import settings
from app.models import (CertificadoVenda, Cliente, Equipamento, EquipamentoCliente,
                        OSCertificado, Ordem, Proposta)


def _token(url):
    return parse_qs(urlparse(url).query)["t"][0]


@pytest.fixture()
def base(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "https://gestorhsapi.exemplo.com")


@pytest.fixture()
def dados(db_session):
    cat = Equipamento(descricao="Mark-X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id, serie="S1")
    db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=8, situacao="E", tipo_servico="A")
    db_session.add(o); db_session.flush()
    db_session.add_all([OSCertificado(os=o.id, tipo="C", html="<p>calib</p>"),
                        OSCertificado(os=o.id, tipo="M", html="<p>manut</p>"),
                        CertificadoVenda(equipamento_cliente=ec.id, html="<p>venda</p>")])
    p = Proposta(numero=777, cliente=cli.id)
    db_session.add(p); db_session.commit()
    return {"ordem": o.id, "ec": ec.id, "proposta": p.id}


def test_certificados_da_os(client_exp, dados, base):
    resp = client_exp.get(f"/ordens/{dados['ordem']}/certificados")
    assert resp.status_code == 200
    por_tipo = {c["tipo"]: c for c in resp.json()}
    for tipo, nome in (("C", "calibracao"), ("M", "manutencao")):
        link = por_tipo[tipo]["link_pdf"]
        assert f"/publico/certificado/{dados['ordem']}/{nome}?t=" in link
        assert certificado_link.verificar(dados["ordem"], tipo, _token(link))
    # a tela continua recebendo o html
    assert por_tipo["C"]["html"] == "<p>calib</p>"


def test_certificados_do_aparelho(client_exp, dados, base):
    itens = client_exp.get(f"/equipamentos-cliente/{dados['ec']}/certificados").json()
    da_os = [i for i in itens if i["origem"] == "os"]
    assert {i["tipo"] for i in da_os} == {"C", "M"}
    for i in da_os:
        assert certificado_link.verificar(i["os"], i["tipo"], _token(i["link_pdf"]))
    [venda] = [i for i in itens if i["origem"] == "venda"]
    assert venda["link_pdf"] is None


def test_proposta_e_listagem(client_exp, dados, base):
    p = client_exp.get(f"/propostas/{dados['proposta']}").json()
    assert proposta_link.verificar(dados["proposta"], _token(p["link_pdf"]))
    [item] = client_exp.get("/propostas").json()["items"]
    assert item["link_pdf"] == p["link_pdf"]


def test_sem_base_url_fica_none(client_exp, dados, monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "")
    assert all(c["link_pdf"] is None for c in client_exp.get(f"/ordens/{dados['ordem']}/certificados").json())
    assert client_exp.get(f"/propostas/{dados['proposta']}").json()["link_pdf"] is None


def test_agente_recebe_link_sem_html(client_agente, dados, base):
    certs = client_agente.get(f"/ordens/{dados['ordem']}/certificados").json()
    assert len(certs) == 2
    for c in certs:
        assert c["html"] is None
        assert certificado_link.verificar(dados["ordem"], c["tipo"], _token(c["link_pdf"]))
    p = client_agente.get(f"/propostas/{dados['proposta']}").json()
    assert proposta_link.verificar(dados["proposta"], _token(p["link_pdf"]))
