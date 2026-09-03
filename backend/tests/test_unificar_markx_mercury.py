"""O script move centenas de aparelhos e APAGA cadastro do catalogo — a rede
tem que cobrir o plano (o que ele decide) e a recusa (quando ele desiste).
"""
import pytest

from app.scripts.unificar_markx_mercury import planejar, aplicar


@pytest.fixture
def catalogo(db_session):
    """Dois cadastros do mesmo aparelho, como Mark X id 3 (fica) e id 1 (absorvido)."""
    from app.models import Cliente, Equipamento, EquipamentoCliente
    fica = Equipamento(descricao="Bafômetro Mark X - Plus")
    vai = Equipamento(descricao="Bafômetro Mark X - Plus - COM IMPRESSORA")
    cli = Cliente(nome="ACME")
    db_session.add_all([fica, vai, cli]); db_session.flush()
    for i in range(3):
        db_session.add(EquipamentoCliente(cliente=cli.id, equipamento=vai.id, serie=f"COM{i}"))
    db_session.add(EquipamentoCliente(cliente=cli.id, equipamento=fica.id, serie="SEM0"))
    db_session.commit()
    return fica, vai, cli


def _modelo(db_session, equipamento_id, tipo, texto):
    from app.models import CertificadoModelo
    m = CertificadoModelo(equipamento=equipamento_id, tipo=tipo, texto=texto)
    db_session.add(m); db_session.commit(); db_session.refresh(m)
    return m


def test_plano_move_a_frota_do_absorvido(db_session, catalogo):
    fica, vai, _ = catalogo
    plano, recusas = planejar(db_session, fica.id, "Mark-X", (vai.id,))
    assert recusas == []
    assert plano["mover_frota"] == [(vai.id, 3)]
    assert [e.id for e in plano["absorvidos"]] == [vai.id]


def test_modelo_identico_e_apagado_e_nao_movido(db_session, catalogo):
    fica, vai, _ = catalogo
    _modelo(db_session, fica.id, "C", "<html>igual</html>")
    redundante = _modelo(db_session, vai.id, "C", "<html>igual</html>")
    plano, recusas = planejar(db_session, fica.id, "Mark-X", (vai.id,))
    assert recusas == []
    assert [m.id for m in plano["apagar_modelos"]] == [redundante.id]
    assert plano["mover_modelos"] == []


def test_modelo_que_o_sobrevivente_nao_tem_e_movido_nao_apagado(db_session, catalogo):
    """Apagar aqui perderia o unico modelo daquele tipo."""
    fica, vai, _ = catalogo
    orfao = _modelo(db_session, vai.id, "M", "<html>relatorio</html>")
    plano, recusas = planejar(db_session, fica.id, "Mark-X", (vai.id,))
    assert recusas == []
    assert [m.id for m in plano["mover_modelos"]] == [orfao.id]
    assert plano["apagar_modelos"] == []


def test_modelo_divergente_recusa_o_par(db_session, catalogo):
    """Textos diferentes = decisao humana; o script nao escolhe no escuro."""
    fica, vai, _ = catalogo
    _modelo(db_session, fica.id, "C", "<html>A</html>")
    _modelo(db_session, vai.id, "C", "<html>B — outro layout</html>")
    _plano, recusas = planejar(db_session, fica.id, "Mark-X", (vai.id,))
    assert len(recusas) == 1
    assert "DIFERE" in recusas[0]


def test_aplicar_unifica_frota_nome_e_apaga_o_cadastro(db_session, catalogo):
    from app.models import Equipamento, EquipamentoCliente
    fica, vai, _ = catalogo
    redundante = _modelo(db_session, fica.id, "C", "<html>igual</html>")
    _modelo(db_session, vai.id, "C", "<html>igual</html>")
    vai_id = vai.id

    plano, recusas = planejar(db_session, fica.id, "Mark-X", (vai_id,))
    assert recusas == []
    assert aplicar(db_session, plano) == 3
    db_session.commit()

    assert db_session.get(Equipamento, fica.id).descricao == "Mark-X"
    assert db_session.get(Equipamento, vai_id) is None
    assert db_session.query(EquipamentoCliente).filter(
        EquipamentoCliente.equipamento == vai_id).count() == 0
    assert db_session.query(EquipamentoCliente).filter(
        EquipamentoCliente.equipamento == fica.id).count() == 4
    # o modelo que fica e o do sobrevivente, e sobrou apenas ele
    from app.models import CertificadoModelo
    restantes = db_session.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento == fica.id).all()
    assert [m.id for m in restantes] == [redundante.id]


def test_rodar_de_novo_nao_acha_nada(db_session, catalogo):
    """Idempotencia: o absorvido deixou de existir."""
    fica, vai, _ = catalogo
    vai_id = vai.id
    plano, _ = planejar(db_session, fica.id, "Mark-X", (vai_id,))
    aplicar(db_session, plano)
    db_session.commit()

    plano2, recusas2 = planejar(db_session, fica.id, "Mark-X", (vai_id,))
    assert recusas2 == []
    assert plano2["absorvidos"] == []
    assert plano2["mover_frota"] == []


def test_sobrevivente_inexistente_recusa(db_session, catalogo):
    _, vai, _ = catalogo
    _, recusas = planejar(db_session, 999999, "Mark-X", (vai.id,))
    assert len(recusas) == 1
    assert "nao existe" in recusas[0]


# ── Tabelas legadas (documentos / links) ─────────────────────────────────────
# Sao FK de verdade em `equipamentos.id` e nao tem model no GestorHS. Foram
# esquecidas na primeira tentativa e o --aplicar morreu em
# `documentos_equipamento_fkey`, com rollback de tudo.

def _criar_tabela_legada(db_session, nome, coluna):
    from sqlalchemy import text
    db_session.execute(text(
        f"create table {nome} (id integer primary key, {coluna} integer, "
        f"posicao integer, titulo varchar, arquivo varchar)"))
    db_session.commit()


def test_linhas_legadas_sao_movidas_e_nao_apagadas(db_session, catalogo):
    """Os PDFs vivem no volume do EasyPanel — apagar a linha perderia o ponteiro."""
    from sqlalchemy import text
    fica, vai, _ = catalogo
    _criar_tabela_legada(db_session, "documentos", "equipamento")
    db_session.execute(text(
        "insert into documentos (id, equipamento, posicao, titulo, arquivo) values "
        "(1, :vai, 1, 'Manual MARK-X', 'a.pdf'), (2, :fica, 1, 'Lâmina', 'b.pdf')"),
        {"vai": vai.id, "fica": fica.id})
    db_session.commit()

    plano, recusas = planejar(db_session, fica.id, "Mark-X", (vai.id,))
    assert recusas == []
    assert plano["mover_legadas"] == [("documentos", "equipamento", vai.id, 1)]
    assert plano["titulos_repetidos"] == []

    aplicar(db_session, plano); db_session.commit()
    donos = [r[0] for r in db_session.execute(text("select equipamento from documentos order by id")).all()]
    assert donos == [fica.id, fica.id], "nenhuma linha apagada, as duas no sobrevivente"


def test_titulo_que_o_sobrevivente_ja_tem_e_avisado_sem_recusar(db_session, catalogo):
    from sqlalchemy import text
    fica, vai, _ = catalogo
    _criar_tabela_legada(db_session, "documentos", "equipamento")
    db_session.execute(text(
        "insert into documentos (id, equipamento, posicao, titulo, arquivo) values "
        "(1, :vai, 1, 'Manual MARK-X', 'a.pdf'), (2, :fica, 2, 'Manual MARK-X', 'b.pdf')"),
        {"vai": vai.id, "fica": fica.id})
    db_session.commit()

    plano, recusas = planejar(db_session, fica.id, "Mark-X", (vai.id,))
    assert recusas == [], "titulo repetido avisa, nao trava a unificacao"
    assert plano["titulos_repetidos"] == [("documentos", "Manual MARK-X")]


def test_tabela_legada_ausente_nao_quebra_o_plano(db_session, catalogo):
    """O banco de teste nasce dos models e nao tem `documentos`/`links`."""
    fica, vai, _ = catalogo
    plano, recusas = planejar(db_session, fica.id, "Mark-X", (vai.id,))
    assert recusas == []
    assert plano["mover_legadas"] == []
