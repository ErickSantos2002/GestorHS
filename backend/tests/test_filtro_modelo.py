"""Filtro por modelo (frota e clientes) e resumo por modelo — para quem
prospecta responder "quais clientes tem Phoebus?". O estoque da HS e' um
cliente (CLIENTE_ESTOQUE_HS_ID) e fica FORA do filtro de clientes e do resumo,
mas DENTRO da lista de aparelhos."""
import io

import pytest
from openpyxl import load_workbook

from app.core.config import settings


@pytest.fixture()
def cenario(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente
    a = Equipamento(descricao="Modelo A")
    b = Equipamento(descricao="Modelo B")
    x = Cliente(id=101, nome="Xis Ltda")
    y = Cliente(id=102, nome="Ypsilon Ltda")
    z = Cliente(id=103, nome="Zeta Ltda")
    hs = Cliente(id=settings.CLIENTE_ESTOQUE_HS_ID, nome="HS LTDA")
    db_session.add_all([a, b, x, y, z, hs])
    db_session.flush()
    db_session.add_all([
        EquipamentoCliente(cliente=x.id, equipamento=a.id, serie="X1", ativo=True),
        EquipamentoCliente(cliente=x.id, equipamento=a.id, serie="X2", ativo=True),
        EquipamentoCliente(cliente=y.id, equipamento=a.id, serie="Y1", ativo=False),
        EquipamentoCliente(cliente=z.id, equipamento=b.id, serie="Z1", ativo=True),
        EquipamentoCliente(cliente=hs.id, equipamento=a.id, serie="HS1", ativo=True),
    ])
    db_session.commit()
    return {"a": a.id, "b": b.id}


def _xlsx(resp):
    ws = load_workbook(io.BytesIO(resp.content)).active
    valores = [r[0] for r in ws.iter_rows(min_row=2, values_only=True) if r[0] not in (None, "")]
    rodape = [v for v in valores if str(v).startswith("Gerado pelo GestorHS")]
    dados = [v for v in valores if v not in rodape]
    return len(dados), (rodape[0] if rodape else "")


def test_frota_filtra_por_modelo(client_admin, cenario):
    r = client_admin.get(f"/equipamentos-cliente?equipamento={cenario['a']}").json()
    assert r["total"] == 4  # inclui o inativo e o estoque: a visao aqui e' aparelho a aparelho
    assert {i["equipamento"] for i in r["items"]} == {cenario["a"]}


def test_clientes_tem_modelo(client_admin, cenario):
    r = client_admin.get(f"/clientes?equipamento={cenario['a']}").json()
    assert r["total"] == 1
    assert [c["nome"] for c in r["items"]] == ["Xis Ltda"]


def test_clientes_tem_modelo_combina_com_q(client_admin, cenario):
    r = client_admin.get(f"/clientes?equipamento={cenario['a']}&q=Zeta").json()
    assert r["total"] == 0


def test_clientes_sem_filtro_mantem_estoque(client_admin, cenario):
    nomes = {c["nome"] for c in client_admin.get("/clientes?limit=100").json()["items"]}
    assert "HS LTDA" in nomes


def test_exportar_frota_respeita_filtro(client_admin, cenario):
    resp = client_admin.get(f"/equipamentos-cliente/exportar?equipamento={cenario['b']}")
    assert resp.status_code == 200
    n, rodape = _xlsx(resp)
    assert n == 1
    assert "Modelo: Modelo B" in rodape


def test_exportar_clientes_respeita_filtro(client_admin, cenario):
    resp = client_admin.get(f"/clientes/exportar?equipamento={cenario['a']}")
    assert resp.status_code == 200
    n, rodape = _xlsx(resp)
    assert n == 1
    assert "Modelo: Modelo A" in rodape
