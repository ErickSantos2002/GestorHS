import csv

import pytest

from app.core import tiny as tiny_core
from app.core.config import settings
from app.integrations import tiny_client
from app.models import Cliente, Empresa, Proposta
from app.scripts import enviar_clientes_tiny as script

CNPJS = ["31790710000196", "11222333000181", "08857492000148", "36312056000552"]


@pytest.fixture(autouse=True)
def sem_pausa_e_ligado(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")
    monkeypatch.setattr(script.time, "sleep", lambda s: None)


@pytest.fixture()
def tiny_falso(monkeypatch):
    estado = {"pesquisa": {}, "pesquisados": [], "incluidos": [],
              "resultado_incluir": tiny_core.Resultado(ok=True, id=555)}
    monkeypatch.setattr(tiny_client, "pesquisar_contato",
                        lambda doc: (estado["pesquisados"].append(doc),
                                     estado["pesquisa"].get(doc, tiny_core.Resultado(ok=False, codigo_erro=20)))[1])
    monkeypatch.setattr(tiny_client, "incluir_contato",
                        lambda c: (estado["incluidos"].append(c), estado["resultado_incluir"])[1])
    return estado


def _com_proposta(db, cgc, **kw):
    c = Cliente(nome=f"Cliente {cgc[:4]}", cgc=cgc, **kw)
    db.add(c); db.flush()
    db.add(Proposta(numero=int(cgc[:6]), cliente=c.id))
    db.commit(); db.refresh(c)
    return c


def test_planejar_pega_quem_tem_proposta_propria_e_nao_tem_tiny_id(db_session):
    alvo = _com_proposta(db_session, CNPJS[0])
    inativo = _com_proposta(db_session, CNPJS[1], ativo=False)
    _com_proposta(db_session, CNPJS[2], tiny_id=999)                 # ja tem
    db_session.add(Cliente(nome="Sem proposta", cgc=CNPJS[3]))       # nunca recebeu proposta
    db_session.commit()
    assert [c.id for c in script.planejar(db_session)] == sorted([alvo.id, inativo.id])


def test_planejar_ignora_matriz_de_proposta_para_empresa(db_session):
    matriz = Cliente(nome="Matriz", cgc=CNPJS[0]); db_session.add(matriz); db_session.flush()
    emp = Empresa(nome="Filial", cgc=CNPJS[1], cliente=matriz.id); db_session.add(emp); db_session.flush()
    db_session.add(Proposta(numero=1, cliente=matriz.id, empresa=emp.id)); db_session.commit()
    assert script.planejar(db_session) == []


def test_planejar_ignora_proposta_desabilitada(db_session):
    c = _com_proposta(db_session, CNPJS[0])
    for p in db_session.query(Proposta).filter(Proposta.cliente == c.id):
        p.is_deleted = True
    db_session.commit()
    assert script.planejar(db_session) == []


def test_planejar_nao_repete_cliente_com_varias_propostas(db_session):
    c = _com_proposta(db_session, CNPJS[0])
    db_session.add(Proposta(numero=2, cliente=c.id)); db_session.commit()
    assert [x.id for x in script.planejar(db_session)] == [c.id]


def test_planejar_respeita_o_limite(db_session):
    _com_proposta(db_session, CNPJS[0]); _com_proposta(db_session, CNPJS[1])
    assert len(script.planejar(db_session, limite=1)) == 1


def test_simulacao_nao_grava_nem_cria(db_session, tiny_falso):
    a = _com_proposta(db_session, CNPJS[0])
    tiny_falso["pesquisa"][CNPJS[1]] = tiny_core.Resultado(ok=True, id=777)
    b = _com_proposta(db_session, CNPJS[1])
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=False, pausa=0)
    db_session.refresh(a); db_session.refresh(b)
    assert a.tiny_id is None and a.tiny_status is None
    assert b.tiny_id is None and b.tiny_status is None
    assert tiny_falso["incluidos"] == []
    assert resumo["criadas"] == 1 and resumo["adotadas"] == 1


def test_aplicar_adota_quem_existe_e_cria_o_resto(db_session, tiny_falso):
    tiny_falso["pesquisa"][CNPJS[0]] = tiny_core.Resultado(ok=True, id=610662219)
    a = _com_proposta(db_session, CNPJS[0])
    b = _com_proposta(db_session, CNPJS[1], numero=643, complemento="-")
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    db_session.refresh(a); db_session.refresh(b)
    assert a.tiny_id == 610662219 and a.tiny_status == "enviada"
    assert b.tiny_id == 555 and b.tiny_status == "enviada"
    assert len(tiny_falso["incluidos"]) == 1
    assert tiny_falso["incluidos"][0]["numero"] == "643"
    assert "complemento" not in tiny_falso["incluidos"][0]
    assert resumo["adotadas"] == 1 and resumo["criadas"] == 1


def test_sem_documento_vai_para_pendencias_sem_chamar(db_session, tiny_falso):
    c = _com_proposta(db_session, CNPJS[0])
    c.cgc = None; db_session.commit()
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    assert tiny_falso["pesquisados"] == []
    assert resumo["sem_documento"] == 1
    assert resumo["pendencias"][0]["motivo"] == "sem CNPJ/CPF"
    db_session.refresh(c)
    assert c.tiny_status == "erro"


def test_pesquisa_inconclusiva_pula_e_segue(db_session, tiny_falso):
    tiny_falso["pesquisa"][CNPJS[0]] = tiny_core.Resultado(ok=False, mensagem="contato encontrado com documento diferente")
    _com_proposta(db_session, CNPJS[0]); b = _com_proposta(db_session, CNPJS[1])
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    db_session.refresh(b)
    assert resumo["puladas"] == 1 and b.tiny_id == 555
    assert resumo["pendencias"][0]["motivo"] == "contato encontrado com documento diferente"


def test_recusa_na_inclusao_marca_erro_e_segue(db_session, tiny_falso):
    tiny_falso["resultado_incluir"] = tiny_core.Resultado(ok=False, codigo_erro=31, mensagem="Cidade nao encontrada")
    a = _com_proposta(db_session, CNPJS[0])
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    db_session.refresh(a)
    assert a.tiny_status == "erro" and a.tiny_erro == "Cidade nao encontrada"
    assert resumo["erros"] == 1


def test_aplicar_pula_quem_ja_ganhou_tiny_id_durante_a_carga(db_session, tiny_falso):
    """I2: a carga leva ~25 min e nesse tempo a rota da proposta ou o worker de
    pendentes podem ter resolvido o cliente por fora. `processar` reconfere sob
    trava logo antes de pesquisar — achando `tiny_id`, pula sem gastar chamada
    nem arriscar duplicar."""
    a = _com_proposta(db_session, CNPJS[0])
    b = _com_proposta(db_session, CNPJS[1])
    clientes = script.planejar(db_session)
    a.tiny_id = 424242; a.tiny_status = "enviada"; db_session.commit()   # resolvido por fora
    resumo = script.processar(db_session, clientes, aplicar=True, pausa=0)
    db_session.refresh(a); db_session.refresh(b)
    assert resumo["ja_feitos"] == 1
    assert tiny_falso["pesquisados"] == [CNPJS[1]]                       # so o b foi pesquisado
    assert a.tiny_id == 424242                                           # nao mexeu no que ja tinha
    assert b.tiny_id == 555 and b.tiny_status == "enviada"


def test_aplicar_duplicidade_na_inclusao_pesquisa_de_novo_e_adota(db_session, tiny_falso):
    tiny_falso["resultado_incluir"] = tiny_core.Resultado(ok=False, codigo_erro=30, mensagem="duplicado")
    a = _com_proposta(db_session, CNPJS[0])
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    db_session.refresh(a)
    # a segunda pesquisa (rede de seguranca) do falso_tiny cai no default: nao encontrado.
    assert resumo["erros"] == 1 and a.tiny_status == "erro"
    assert tiny_falso["pesquisados"] == [CNPJS[0], CNPJS[0]]


def test_aplicar_duplicidade_adota_quando_a_segunda_pesquisa_acha(db_session, tiny_falso, monkeypatch):
    tiny_falso["resultado_incluir"] = tiny_core.Resultado(ok=False, codigo_erro=30, mensagem="duplicado")
    a = _com_proposta(db_session, CNPJS[0])
    chamadas = {"n": 0}
    original = tiny_client.pesquisar_contato

    def pesquisar_com_segunda_chamada(doc):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            return tiny_core.Resultado(ok=False, codigo_erro=20)
        return tiny_core.Resultado(ok=True, id=888)

    monkeypatch.setattr(tiny_client, "pesquisar_contato", pesquisar_com_segunda_chamada)
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    db_session.refresh(a)
    assert resumo["adotadas"] == 1
    assert a.tiny_id == 888 and a.tiny_status == "enviada"


def test_aplicar_incluido_sem_id_vira_pendente_nao_erro(db_session, tiny_falso):
    tiny_falso["resultado_incluir"] = tiny_core.Resultado(ok=True, id=None)
    a = _com_proposta(db_session, CNPJS[0])
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    db_session.refresh(a)
    assert resumo["erros"] == 0 and resumo["puladas"] == 1
    assert a.tiny_status == "pendente" and a.tiny_id is None
    assert resumo["pendencias"][0]["motivo"] == "incluido sem id; conferir no Tiny"


def test_bloqueio_interrompe(db_session, tiny_falso):
    tiny_falso["pesquisa"][CNPJS[0]] = tiny_core.Resultado(ok=False, codigo_erro=6)
    _com_proposta(db_session, CNPJS[0]); _com_proposta(db_session, CNPJS[1])
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    assert resumo["interrompido"] is True
    assert tiny_falso["pesquisados"] == [CNPJS[0]]


def test_idempotente(db_session, tiny_falso):
    _com_proposta(db_session, CNPJS[0])
    script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=0)
    assert script.planejar(db_session) == []


def test_main_simula_e_grava_o_csv(db_session, tiny_falso, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(script, "SessionLocal", lambda: db_session)
    c = _com_proposta(db_session, CNPJS[0])
    cliente_id = c.id
    c.cgc = None; db_session.commit()
    caminho = tmp_path / "p.csv"
    script.main(["--pendencias", str(caminho)])
    assert "SIMULACAO" in capsys.readouterr().out
    recarregado = db_session.get(Cliente, cliente_id)
    assert recarregado.tiny_status is None                          # simulacao nao grava
    linhas = list(csv.DictReader(caminho.open(encoding="utf-8")))
    assert linhas[0]["cliente_id"] == str(cliente_id) and linhas[0]["motivo"] == "sem CNPJ/CPF"


def test_main_recusa_com_integracao_desligada(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    with pytest.raises(SystemExit):
        script.main([])


def test_aplicar_reconfere_o_banco_e_nao_o_objeto_em_memoria(db_session, tiny_falso):
    """O `planejar` carrega os clientes e nada commita antes da primeira trava:
    sem `populate_existing`, a releitura travada devolvia o objeto do identity
    map com o `tiny_id` VELHO — o primeiro cliente da carga escapava da checagem
    e podia ganhar um segundo contato no Tiny."""
    from sqlalchemy import text

    c = _com_proposta(db_session, CNPJS[0])
    fila = script.planejar(db_session)
    # Outro processo (rota/worker) grava o tiny_id direto no banco; o objeto em
    # memoria continua com tiny_id=None.
    db_session.execute(text("update clientes set tiny_id = 777 where id = :i"), {"i": c.id})
    resumo = script.processar(db_session, fila, aplicar=True, pausa=0)
    assert resumo["ja_feitos"] == 1
    assert tiny_falso["pesquisados"] == [] and tiny_falso["incluidos"] == []


def test_aplicar_pausa_antes_de_travar_o_proximo_cliente(db_session, tiny_falso, monkeypatch):
    """A pausa de 7s entre clientes nao pode acontecer com a linha travada: uma
    proposta salva para aquele cliente nesse meio tempo esperaria a pausa inteira."""
    eventos = []
    original = tiny_client.stmt_travar_cliente
    monkeypatch.setattr(tiny_client, "stmt_travar_cliente",
                        lambda cid: (eventos.append("trava"), original(cid))[1])
    monkeypatch.setattr(script.time, "sleep", lambda s: eventos.append("pausa"))
    pesquisar = tiny_client.pesquisar_contato
    monkeypatch.setattr(tiny_client, "pesquisar_contato",
                        lambda doc: (eventos.append("pesquisa"), pesquisar(doc))[1])
    _com_proposta(db_session, CNPJS[0]); _com_proposta(db_session, CNPJS[1])
    script.processar(db_session, script.planejar(db_session), aplicar=True, pausa=7)
    assert eventos == ["trava", "pesquisa", "pausa", "trava", "pesquisa"]
