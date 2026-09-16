import pytest

from app.core import tiny as tiny_core
from app.core.config import settings
from app.integrations import tiny_client
from app.models import Empresa
from app.scripts import enviar_empresas_tiny as script

CNPJS = ["36312056000552", "11222333000181", "08857492000148"]


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


def _empresas(db, quantos=2, **kw):
    criadas = []
    for i in range(quantos):
        e = Empresa(nome=f"Filial {i}", cgc=CNPJS[i], municipio="Recife", estado="PE", **kw)
        db.add(e); criadas.append(e)
    db.commit()
    return criadas


def test_planejar_pega_so_ativa_sem_tiny_id(db_session):
    a, b = _empresas(db_session)
    b.tiny_id = 999
    db_session.add(Empresa(nome="Inativa", cgc=CNPJS[2], ativo=False))
    db_session.commit()
    assert [e.id for e in script.planejar(db_session)] == [a.id]


def test_planejar_respeita_o_limite(db_session):
    _empresas(db_session, 2)
    assert len(script.planejar(db_session, limite=1)) == 1


def test_simulacao_nao_grava_nem_cria(db_session, tiny_falso):
    a, _ = _empresas(db_session)
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=False)
    db_session.refresh(a)
    assert a.tiny_id is None and a.tiny_status is None
    assert tiny_falso["incluidos"] == []
    assert resumo["candidatas"] == 2


def test_simulacao_pesquisa_e_conta_o_que_faria(db_session, tiny_falso, capsys):
    """A simulacao precisa responder "vai criar alguma?" — a pesquisa e' leitura
    pura, entao ela roda de verdade; so a inclusao fica de fora."""
    a, b = _empresas(db_session)
    tiny_falso["pesquisa"][CNPJS[0]] = tiny_core.Resultado(ok=True, id=565052083)
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=False)
    saida = capsys.readouterr().out
    assert tiny_falso["pesquisados"] == [CNPJS[0], CNPJS[1]]
    assert tiny_falso["incluidos"] == []
    assert resumo["adotadas"] == 1 and resumo["criadas"] == 1
    assert "565052083" in saida                 # diz qual contato adotaria
    db_session.refresh(a); db_session.refresh(b)
    assert a.tiny_id is None and b.tiny_id is None


def test_simulacao_respeita_a_pausa(db_session, tiny_falso, monkeypatch):
    pausas = []
    monkeypatch.setattr(script.time, "sleep", lambda s: pausas.append(s))
    _empresas(db_session, 2)
    script.processar(db_session, script.planejar(db_session), aplicar=False, pausa=7.0)
    assert pausas == [7.0]


def test_pesquisa_indefinida_pula_sem_criar(db_session, tiny_falso, monkeypatch):
    """Pesquisa que nao e' `ok` nem `nao_encontrado` deixa em aberto se o contato
    ja existe: criar geraria um duplicado no ERP."""
    a, b = _empresas(db_session)
    monkeypatch.setattr(tiny_client, "pesquisar_contato",
                        lambda doc: tiny_core.Resultado(ok=False, codigo_erro=None,
                                                        mensagem="resposta do Tiny nao e' JSON"))
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True)
    db_session.refresh(a); db_session.refresh(b)
    assert tiny_falso["incluidos"] == []
    assert resumo["puladas"] == 2 and resumo["criadas"] == 0 and resumo["erros"] == 0
    assert resumo["interrompido"] is False
    assert a.tiny_id is None


def test_pesquisa_indefinida_segue_para_a_proxima(db_session, tiny_falso):
    a, b = _empresas(db_session)
    tiny_falso["pesquisa"][CNPJS[0]] = tiny_core.Resultado(ok=False, mensagem="corpo estranho")
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True)
    db_session.refresh(a); db_session.refresh(b)
    assert resumo["puladas"] == 1 and resumo["criadas"] == 1
    assert a.tiny_id is None and b.tiny_id == 555


def test_aplicar_adota_quem_ja_existe_e_cria_o_resto(db_session, tiny_falso):
    a, b = _empresas(db_session)
    tiny_falso["pesquisa"][CNPJS[0]] = tiny_core.Resultado(ok=True, id=565052083)
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True)
    db_session.refresh(a); db_session.refresh(b)
    assert a.tiny_id == 565052083 and a.tiny_status == "enviada"
    assert b.tiny_id == 555 and b.tiny_status == "enviada"
    assert len(tiny_falso["incluidos"]) == 1              # so a que faltava
    assert resumo == {"candidatas": 2, "adotadas": 1, "criadas": 1, "erros": 0,
                      "puladas": 0, "interrompido": False}


def test_erro_de_validacao_marca_erro_e_segue(db_session, tiny_falso):
    a, b = _empresas(db_session)
    tiny_falso["resultado_incluir"] = tiny_core.Resultado(ok=False, codigo_erro=31,
                                                          mensagem="Cidade não encontrada")
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True)
    db_session.refresh(a)
    assert a.tiny_status == "erro" and a.tiny_erro == "Cidade não encontrada"
    assert resumo["erros"] == 2 and resumo["interrompido"] is False


def test_bloqueio_por_limite_interrompe(db_session, tiny_falso):
    _empresas(db_session, 2)
    tiny_falso["resultado_incluir"] = tiny_core.Resultado(ok=False, codigo_erro=6,
                                                          mensagem="API bloqueada")
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True)
    assert resumo["interrompido"] is True and resumo["criadas"] == 0


def test_bloqueio_na_pesquisa_interrompe(db_session, tiny_falso, monkeypatch):
    _empresas(db_session, 2)
    monkeypatch.setattr(tiny_client, "pesquisar_contato",
                        lambda doc: tiny_core.Resultado(ok=False, codigo_erro=11, mensagem="API bloqueada"))
    resumo = script.processar(db_session, script.planejar(db_session), aplicar=True)
    assert resumo["interrompido"] is True
    assert resumo["adotadas"] == 0 and resumo["criadas"] == 0


def test_idempotente(db_session, tiny_falso):
    _empresas(db_session)
    script.processar(db_session, script.planejar(db_session), aplicar=True)
    assert script.planejar(db_session) == []


def test_main_sem_aplicar_so_simula(db_session, tiny_falso, monkeypatch, capsys):
    _empresas(db_session)
    monkeypatch.setattr(script, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    script.main([])
    assert "SIMULACAO" in capsys.readouterr().out
    assert tiny_falso["incluidos"] == []


def test_main_recusa_com_integracao_desligada(db_session, monkeypatch, capsys):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    monkeypatch.setattr(script, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    with pytest.raises(SystemExit):
        script.main([])
