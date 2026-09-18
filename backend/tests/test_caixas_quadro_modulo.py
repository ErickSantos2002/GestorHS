"""O quadro de Ordens marca a caixa que carrega Phoebus/Modulo.

A caixa deles chega ao Financeiro SEM ter passado pelo Pos-Vendas (`PROXIMA_MODULO`),
e quem recebe precisa saber por que. O aviso distingue os tres casos porque sao reais:
so o aparelho, so o modulo, ou os dois juntos na mesma caixa.
"""
import pytest

from app.core.config import settings
from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, Ordem


def _caixa(db, *, catalogos, fase=10):
    """Caixa na fase informada com uma OS por id de catalogo em `catalogos`."""
    cli = Cliente(nome="Cliente Quadro")
    cx = Caixa(obs="Caixa quadro", fase=fase)
    db.add_all([cli, cx]); db.flush()
    for cat in catalogos:
        eq = db.query(Equipamento).filter(Equipamento.id == cat).one_or_none()
        if eq is None:
            eq = Equipamento(id=cat, descricao=f"Equipamento {cat}")
            db.add(eq); db.flush()
        ec = EquipamentoCliente(cliente=cli.id, equipamento=cat, serie=f"S{cat}-{cx.id}")
        db.add(ec); db.flush()
        db.add(Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=fase,
                     situacao="E", caixa=cx.id, desfecho_lab="concluido"))
    db.commit(); db.refresh(cx)
    return cx.id


def _item(colunas, caixa_id):
    for col in colunas:
        for item in col["caixas"]:
            if item["id"] == caixa_id:
                return item
    return None


@pytest.mark.parametrize("catalogos,esperado", [
    ([settings.EQUIPAMENTO_PHOEBUS_ID], "phoebus"),
    ([settings.EQUIPAMENTO_MODULO_ID], "modulo"),
    ([settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_MODULO_ID], "ambos"),
])
def test_quadro_marca_o_tipo_de_modulo_da_caixa(client_exp, db_session, catalogos, esperado):
    cx_id = _caixa(db_session, catalogos=catalogos)
    item = _item(client_exp.get("/caixas/quadro").json(), cx_id)
    assert item is not None
    assert item["modulo"] == esperado


def test_quadro_nao_marca_caixa_de_aparelho_comum(client_exp, db_session):
    """Controle positivo: sem ele, o campo poderia vir preenchido para todo mundo."""
    cx_id = _caixa(db_session, catalogos=[1])
    item = _item(client_exp.get("/caixas/quadro").json(), cx_id)
    assert item is not None
    assert item["modulo"] is None


def test_quadro_marca_caixa_mista(client_exp, db_session):
    """Caixa com Phoebus e aparelho comum: o aviso e' sobre o Phoebus que esta ali."""
    cx_id = _caixa(db_session, catalogos=[1, settings.EQUIPAMENTO_PHOEBUS_ID])
    item = _item(client_exp.get("/caixas/quadro").json(), cx_id)
    assert item["modulo"] == "phoebus"
