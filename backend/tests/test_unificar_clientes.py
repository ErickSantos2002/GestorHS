"""O script move a frota e o historico inteiro de um cliente e APAGA o cadastro
duplicado — a rede tem que cobrir o plano (o que ele decide), a recusa (quando
desiste) e a completude da lista de referencias (o que ele esqueceria de mover).
"""
import pytest

from app.core.unificacao_cliente import divergencias, escolher_sobrevivente
from app.scripts.unificar_clientes import REFERENCIAS, aplicar, localizar_por_cgc, planejar


CGC = "05571228001127"


def _cliente(db, **campos):
    from app.models import Cliente
    base = dict(nome="FERTILIZANTES TOCANTINS S.A", cgc=CGC, municipio="ARAGUARI",
                estado="MG", cep="38446424", ativo=True)
    base.update(campos)
    c = Cliente(**base)
    db.add(c); db.commit(); db.refresh(c)
    return c


@pytest.fixture
def par(db_session):
    """Dois cadastros identicos do mesmo CNPJ, como 1059 (fica) e 1064 (absorvido)."""
    return _cliente(db_session), _cliente(db_session)


# --- nucleo puro -------------------------------------------------------------

def test_cadastros_identicos_nao_divergem(par):
    assert divergencias(*par) == []


def test_campo_diferente_aparece_com_os_dois_valores(db_session):
    fica = _cliente(db_session)
    vai = _cliente(db_session, contato="Outro Fulano")
    assert divergencias(fica, vai) == [("contato", None, "Outro Fulano")]


def test_id_e_ativo_nao_contam_como_divergencia(db_session):
    """Ids diferem sempre; `ativo` do absorvido nao importa, ele vai sumir."""
    fica = _cliente(db_session)
    vai = _cliente(db_session, ativo=False)
    assert divergencias(fica, vai) == []


def test_sobrevive_quem_tem_caixa_mesmo_com_menos_os():
    escolhido = escolher_sobrevivente([
        {"id": 1059, "caixas": 1, "ordens": 2},
        {"id": 1064, "caixas": 0, "ordens": 9},
    ])
    assert escolhido == 1059


def test_sem_caixa_sobrevive_quem_tem_mais_os():
    assert escolher_sobrevivente([
        {"id": 1059, "caixas": 0, "ordens": 5},
        {"id": 1064, "caixas": 0, "ordens": 9},
    ]) == 1064


def test_empate_fica_com_o_id_menor():
    assert escolher_sobrevivente([
        {"id": 1064, "caixas": 0, "ordens": 0},
        {"id": 1059, "caixas": 0, "ordens": 0},
    ]) == 1059


# --- plano -------------------------------------------------------------------

def _frota(db, cliente_id, serie):
    from app.models import Equipamento, EquipamentoCliente
    eq = db.query(Equipamento).first()
    if eq is None:
        eq = Equipamento(descricao="IBlow 10"); db.add(eq); db.flush()
    ec = EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie=serie)
    db.add(ec); db.commit(); db.refresh(ec)
    return ec


def _ordem(db, cliente_id, ec_id):
    from app.models import Ordem
    o = Ordem(cliente=cliente_id, equipamento_cliente=ec_id)
    db.add(o); db.commit(); db.refresh(o)
    return o


def test_plano_conta_as_linhas_que_vao_mudar_de_dono(db_session, par):
    fica, vai = par
    ec = _frota(db_session, vai.id, "TBLB90237")
    _ordem(db_session, vai.id, ec.id)
    plano, recusas = planejar(db_session, fica.id, [vai.id])
    assert recusas == []
    assert plano["mover"] == [("equipamentos_cliente", "cliente", vai.id, 1),
                              ("ordens", "cliente", vai.id, 1)]
    assert [c.id for c in plano["absorvidos"]] == [vai.id]


def test_plano_ignora_absorvido_que_ja_sumiu(db_session, par):
    """Idempotencia: rodar de novo depois de aplicar nao acha mais nada."""
    fica, vai = par
    plano, recusas = planejar(db_session, fica.id, [vai.id + 999])
    assert recusas == []
    assert plano["absorvidos"] == []


def test_divergencia_recusa_o_plano(db_session):
    fica = _cliente(db_session)
    vai = _cliente(db_session, endereco="OUTRA RUA")
    _, recusas = planejar(db_session, fica.id, [vai.id])
    assert any("endereco" in r for r in recusas)


def test_divergencia_aceita_de_proposito_nao_recusa(db_session):
    fica = _cliente(db_session)
    vai = _cliente(db_session, endereco="OUTRA RUA")
    plano, recusas = planejar(db_session, fica.id, [vai.id], aceitar_divergencia=True)
    assert recusas == []
    assert plano["divergencias"]


def test_absorver_o_proprio_sobrevivente_e_recusado(db_session, par):
    fica, _ = par
    _, recusas = planejar(db_session, fica.id, [fica.id])
    assert recusas


def test_sobrevivente_inexistente_e_recusado(db_session, par):
    _, vai = par
    _, recusas = planejar(db_session, vai.id + 999, [vai.id])
    assert recusas


def test_login_de_portal_repetido_e_recusado(db_session, par):
    """A unica de (cliente, login) nao pega isto: os dois logins sao de clientes
    diferentes ate a hora do UPDATE, quando viram o mesmo par e estouram."""
    from app.models import UsuarioCliente
    fica, vai = par
    for c in (fica, vai):
        db_session.add(UsuarioCliente(cliente=c.id, login="juliano", senha="x"))
    db_session.commit()
    _, recusas = planejar(db_session, fica.id, [vai.id])
    assert any("juliano" in r for r in recusas)


# --- aplicacao ---------------------------------------------------------------

def test_aplicar_move_tudo_e_apaga_o_duplicado(db_session, par):
    from app.models import Caixa, Cliente, EquipamentoCliente, Ordem
    fica, vai = par
    ec = _frota(db_session, vai.id, "TBLB90237")
    o = _ordem(db_session, vai.id, ec.id)
    cx = Caixa(cliente_principal=vai.id); db_session.add(cx); db_session.commit()

    plano, recusas = planejar(db_session, fica.id, [vai.id])
    assert recusas == []
    assert aplicar(db_session, plano) == 3
    db_session.commit()

    assert db_session.get(EquipamentoCliente, ec.id).cliente == fica.id
    assert db_session.get(Ordem, o.id).cliente == fica.id
    assert db_session.get(Caixa, cx.id).cliente_principal == fica.id
    assert db_session.get(Cliente, vai.id) is None
    assert db_session.get(Cliente, fica.id) is not None


def test_frota_do_sobrevivente_fica_intacta(db_session, par):
    from app.models import EquipamentoCliente
    fica, vai = par
    meu = _frota(db_session, fica.id, "TBMA70108")
    _frota(db_session, vai.id, "TBLB90237")
    plano, _ = planejar(db_session, fica.id, [vai.id])
    aplicar(db_session, plano); db_session.commit()
    assert db_session.get(EquipamentoCliente, meu.id).cliente == fica.id
    assert db_session.query(EquipamentoCliente).filter_by(cliente=fica.id).count() == 2


def test_localizar_por_cgc_ignora_mascara(db_session, par):
    achados = localizar_por_cgc(db_session, "05.571.228/0011-27")
    assert sorted(c.id for c in achados) == sorted(c.id for c in par)


# --- completude da lista -----------------------------------------------------

def test_referencias_cobre_toda_FK_declarada_para_clientes():
    """Esquecer uma coluna aqui deixa linha orfa apontando para cadastro apagado."""
    from app.models.database import Base
    import app.models  # noqa: F401  (registra as tabelas)

    declaradas = {
        (tabela.name, coluna.name)
        for tabela in Base.metadata.tables.values()
        for coluna in tabela.columns
        for fk in coluna.foreign_keys
        if fk.column.table.name == "clientes"
    }
    cobertas = {(t, c) for t, c in REFERENCIAS}
    assert declaradas - cobertas == set()


# --- renumeracao de patrimonio ----------------------------------------------

def test_quem_cede_e_colide_recebe_o_proximo_numero_livre():
    """A frota do sobrevivente fica intacta; so os absorvidos andam."""
    from app.core.unificacao_cliente import renumerar_patrimonios
    frota = [(4148, "1"), (4153, "1"), (5080, "2"), (5067, "2")]
    assert renumerar_patrimonios(frota, ceder={4153, 5067}) == {4153: "3", 5067: "4"}


def test_quem_cede_sem_colidir_fica_onde_esta():
    from app.core.unificacao_cliente import renumerar_patrimonios
    frota = [(4148, "1"), (4153, "9")]
    assert renumerar_patrimonios(frota, ceder={4153}) == {}


def test_numeracao_continua_do_maior_e_nao_preenche_buraco():
    """Reusar numero aposentado confundiria quem conhece a etiqueta antiga."""
    from app.core.unificacao_cliente import renumerar_patrimonios
    frota = [(1, "1"), (2, "5"), (3, "1")]
    assert renumerar_patrimonios(frota, ceder={3}) == {3: "6"}


def test_patrimonio_nao_numerico_ou_vazio_nao_e_tocado():
    """203 aparelhos usam o campo como recado ('SEM CONSERTO') — nao e' numero."""
    from app.core.unificacao_cliente import renumerar_patrimonios
    frota = [(1, "1"), (2, "SEM CONSERTO"), (3, "SEM CONSERTO"), (4, None), (5, "")]
    assert renumerar_patrimonios(frota, ceder={2, 3, 4, 5}) == {}


def test_dois_que_cedem_o_mesmo_numero_nao_recebem_o_mesmo_novo():
    from app.core.unificacao_cliente import renumerar_patrimonios
    frota = [(1, "1"), (2, "1"), (3, "1")]
    assert renumerar_patrimonios(frota, ceder={2, 3}) == {2: "2", 3: "3"}


def test_ordem_de_entrada_decide_quem_pega_o_numero_menor():
    from app.core.unificacao_cliente import renumerar_patrimonios
    frota = [(9, "1"), (2, "1"), (7, "1")]
    assert renumerar_patrimonios(frota, ceder={7, 2}) == {2: "2", 7: "3"}


def test_renumerar_grava_so_quem_cede(db_session, par):
    """A frota do sobrevivente nao pode andar — a etiqueta dela o cliente ja conhece."""
    from app.models import EquipamentoCliente
    from app.scripts.renumerar_patrimonios import aplicar as aplicar_num
    from app.scripts.renumerar_patrimonios import planejar as planejar_num
    fica, vai = par
    meu = _frota(db_session, fica.id, "TBMA70108"); meu.patrimonio = "1"
    dele = _frota(db_session, fica.id, "TBLB90237"); dele.patrimonio = "1"
    db_session.commit()

    _, mudancas, recusas = planejar_num(db_session, fica.id, {dele.id})
    assert recusas == []
    assert mudancas == {dele.id: ("TBLB90237", "1", "2")}
    aplicar_num(db_session, mudancas); db_session.commit()
    assert db_session.get(EquipamentoCliente, meu.id).patrimonio == "1"
    assert db_session.get(EquipamentoCliente, dele.id).patrimonio == "2"


def test_renumerar_recusa_aparelho_de_outro_cliente(db_session, par):
    from app.scripts.renumerar_patrimonios import planejar as planejar_num
    fica, vai = par
    de_outro = _frota(db_session, vai.id, "XX1")
    _, _, recusas = planejar_num(db_session, fica.id, {de_outro.id})
    assert any(str(de_outro.id) in r for r in recusas)


def test_renumerar_e_idempotente(db_session, par):
    from app.scripts.renumerar_patrimonios import aplicar as aplicar_num
    from app.scripts.renumerar_patrimonios import planejar as planejar_num
    fica, _ = par
    a = _frota(db_session, fica.id, "A"); a.patrimonio = "1"
    b = _frota(db_session, fica.id, "B"); b.patrimonio = "1"
    db_session.commit()
    _, mudancas, _ = planejar_num(db_session, fica.id, {b.id})
    aplicar_num(db_session, mudancas); db_session.commit()
    _, denovo, _ = planejar_num(db_session, fica.id, {b.id})
    assert denovo == {}


def test_sem_lista_cede_quem_entrou_depois(db_session, par):
    from app.scripts.renumerar_patrimonios import planejar as planejar_num
    fica, _ = par
    a = _frota(db_session, fica.id, "A"); a.patrimonio = "1"
    b = _frota(db_session, fica.id, "B"); b.patrimonio = "1"
    db_session.commit()
    _, mudancas, _ = planejar_num(db_session, fica.id, None)
    assert list(mudancas) == [b.id]


def test_unificar_com_renumeracao_resolve_a_colisao_no_mesmo_passo(db_session, par):
    """O caminho de ponta a ponta: mover a frota E acertar o patrimonio que colide."""
    from app.models import EquipamentoCliente
    fica, vai = par
    meu = _frota(db_session, fica.id, "TBMA70108"); meu.patrimonio = "1"
    dele = _frota(db_session, vai.id, "TBLB90237"); dele.patrimonio = "1"
    db_session.commit()

    plano, recusas = planejar(db_session, fica.id, [vai.id])
    assert recusas == []
    assert plano["frota_absorvida"] == [dele.id]
    aplicar(db_session, plano, renumerar_patrimonio=True)
    db_session.commit()

    assert db_session.get(EquipamentoCliente, meu.id).patrimonio == "1"
    assert db_session.get(EquipamentoCliente, dele.id).patrimonio == "2"


def test_unificar_sem_a_flag_deixa_o_patrimonio_repetido(db_session, par):
    """O padrao nao mexe na etiqueta do cliente — so avisa."""
    from app.models import EquipamentoCliente
    fica, vai = par
    meu = _frota(db_session, fica.id, "TBMA70108"); meu.patrimonio = "1"
    dele = _frota(db_session, vai.id, "TBLB90237"); dele.patrimonio = "1"
    db_session.commit()

    plano, _ = planejar(db_session, fica.id, [vai.id])
    assert plano["patrimonios_repetidos"] == ["1"]
    aplicar(db_session, plano)
    db_session.commit()
    assert db_session.get(EquipamentoCliente, dele.id).patrimonio == "1"
