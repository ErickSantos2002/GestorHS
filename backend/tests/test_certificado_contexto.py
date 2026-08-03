"""Contexto do certificado: o conjunto de chaves e a fonte unica da verdade.

`preencher()` so substitui as chaves presentes no contexto — um token ausente fica
LITERALMENTE escrito no PDF. Por isso o contexto do avulso tem de ter exatamente as
mesmas chaves do contexto da OS.
"""
from datetime import date

from app.core.certificado_gerar import CAMPOS, montar_contexto, montar_contexto_avulso, preencher


def _seed_fase5_se_necessario(db_session):
    # A Ordem exige uma fase existente (FK) — replica o padrao ja usado em
    # test_certificado_os_api.py para nao depender da fixture fases_seed aqui.
    from app.models import Fase, Funcao
    if db_session.query(Fase).filter(Fase.id == 5).first() is None:
        f = db_session.query(Funcao).filter(Funcao.descricao == "Laboratório").first()
        if f is None:
            f = Funcao(descricao="Laboratório")
            db_session.add(f); db_session.flush()
        db_session.add(Fase(id=5, descricao="Laboratório", cor="6366f1", funcao_responsavel=f.id))
        db_session.flush()


def _os_com_dados(db_session, os_base):
    from app.models import Ordem
    _seed_fase5_se_necessario(db_session)
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=5, situacao="E", tipo_servico="C",
              calib_cert="C-1", calib_temp="22", calib_pressao="1013",
              calib_teste1="0,10", calib_teste2="0,11", calib_teste3="0,12",
              calib_teste_media="0,11", calib_situacao="Aprovado")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def test_avulso_tem_exatamente_as_mesmas_chaves_da_os(db_session, os_base):
    """A regressao que este teste impede: o avulso esquecer uma chave e vazar [token] no PDF."""
    o = _os_com_dados(db_session, os_base)
    ctx_os = montar_contexto(db_session, o)
    ctx_avulso = montar_contexto_avulso(db_session, {})
    assert set(ctx_avulso.keys()) == set(ctx_os.keys())


def test_nenhum_token_conhecido_vaza_no_avulso(db_session):
    """Um modelo que usa TODOS os tokens nao pode sair com nenhum [token] literal."""
    html = " ".join(f"[{campo}]" for campo, _ in CAMPOS)
    saida = preencher(html, montar_contexto_avulso(db_session, {"nomecli": "ACME"}))
    assert "[" not in saida and "]" not in saida


def test_avulso_usa_os_valores_digitados(db_session):
    ctx = montar_contexto_avulso(db_session, {
        "nomecli": "POC Ltda", "serie": "SN-9", "calib_cert": "AV-1",
        "calib_situacao": "Aprovado", "data_calibracao": date(2026, 7, 14),
    })
    assert ctx["nomecli"] == "POC Ltda"
    assert ctx["serie"] == "SN-9"
    assert ctx["calibcert"] == "AV-1"
    assert ctx["situcalib"] == "Aprovado"
    assert ctx["datacali"] == "14/07/2026"      # formatado DD/MM/AAAA


def test_avulso_preenche_vazio_o_que_nao_foi_informado(db_session):
    ctx = montar_contexto_avulso(db_session, {})
    assert ctx["nomecli"] == ""
    assert ctx["proxcalibragem"] == ""      # nenhum modelo real usa, mas a chave existe
    assert ctx["tipocalibragem"] == ""


def test_avulso_nao_inclui_pulapagina_no_contexto(db_session):
    """pulapagina e tratado FORA do laco (HTML estrutural, sem escape).
    No contexto ele seria escapado e a quebra de pagina pararia de funcionar."""
    assert "pulapagina" not in montar_contexto_avulso(db_session, {})


def test_pulapagina_continua_virando_quebra_de_pagina(db_session):
    saida = preencher("<p>a</p>[pulapagina]<p>b</p>", montar_contexto_avulso(db_session, {}))
    assert "page-break-after" in saida
    assert "[pulapagina]" not in saida


def test_contexto_da_os_traz_todos_os_tokens_de_CAMPOS(db_session, os_base):
    ordem = _os_com_dados(db_session, os_base)
    ctx = montar_contexto(db_session, ordem)
    # Token que falta no contexto sai LITERALMENTE escrito no PDF do cliente.
    # `pulapagina` fica de fora de proposito: preencher() o trata fora do laco.
    faltando = [nome for nome, _ in CAMPOS if nome not in ctx and nome != "pulapagina"]
    assert faltando == []


def test_contexto_do_avulso_traz_as_mesmas_chaves_do_da_os(db_session, os_base):
    ordem = _os_com_dados(db_session, os_base)
    assert set(montar_contexto(db_session, ordem)) == set(montar_contexto_avulso(db_session, {}))


def test_contexto_calcula_o_erro_e_a_incerteza_da_planilha(db_session, os_base):
    ordem = _os_com_dados(db_session, os_base)
    for i in range(1, 6):
        setattr(ordem, f"calib_teste{i}", "0.16")
    db_session.commit()
    ctx = montar_contexto(db_session, ordem)
    assert ctx["erro1"] == "0,06"
    assert ctx["erro5"] == "0,06"
    assert ctx["mediamedicoes"] == "0,16"
    assert ctx["incertezaexpandida"] == "0,1301"
    assert ctx["fatork"] == "2"


def test_os_antiga_com_tres_medicoes_deixa_erro4_e_erro5_em_branco(db_session, os_base):
    ordem = _os_com_dados(db_session, os_base)   # nasce com 3 medicoes, sem teste4/5
    for i in range(1, 4):
        setattr(ordem, f"calib_teste{i}", "0.16")
    ordem.calib_teste4 = None
    ordem.calib_teste5 = None
    db_session.commit()
    ctx = montar_contexto(db_session, ordem)
    assert ctx["erro1"] == "0,06"
    # nao inventa medicao: erro em branco, nao "-0,1"
    assert ctx["erro4"] == ""
    assert ctx["erro5"] == ""
    assert ctx["calibteste4"] == ""


def test_os_sem_padrao_deixa_os_campos_do_cilindro_vazios(db_session, os_base):
    ordem = _os_com_dados(db_session, os_base)
    ordem.padrao_id = None
    db_session.commit()
    ctx = montar_contexto(db_session, ordem)
    assert ctx["padraocilindro"] == ""
    assert ctx["padraocertificado"] == ""
    assert ctx["drygasppm"] == ""


def test_avulso_calcula_erro_e_incerteza_da_planilha(db_session):
    """O avulso agora calcula o bloco EPS-LAB-002 igual a OS — mesma planilha,
    mesmos numeros: cinco medicoes de 0,16 dao erro 0,06 e U 0,1301."""
    from app.core.certificado_gerar import montar_contexto_avulso

    ctx = montar_contexto_avulso(db_session, {
        "calib_teste1": "0.16", "calib_teste2": "0.16", "calib_teste3": "0.16",
        "calib_teste4": "0.16", "calib_teste5": "0.16",
    })
    assert ctx["erro1"] == "0,06"
    assert ctx["erro2"] == "0,06"
    assert ctx["erro3"] == "0,06"
    assert ctx["erro4"] == "0,06"
    assert ctx["erro5"] == "0,06"
    assert ctx["mediamedicoes"] == "0,16"
    assert ctx["incertezaexpandida"] == "0,1301"
    assert ctx["fatork"] == "2"


def test_avulso_com_cilindro_vigente_preenche_padrao_e_drygasppm(db_session):
    """O cilindro do avulso e resolvido pela DATA DE CALIBRACAO digitada (nao ha OS
    com padrao_id gravado). Assercao de nao-vazio explicita — "" == "" passaria
    vazio e nao provaria nada, essa armadilha ja pegou um teste nesta branch."""
    from app.models import CertificadoPadrao
    from app.core.certificado_gerar import montar_contexto_avulso

    padrao = CertificadoPadrao(
        numero_cilindro="CC747704", numero_certificado="202231419",
        concentracao=100.1, incerteza_concentracao=2.0, unidade="µmol/mol",
        vigencia_inicio=date(2020, 1, 1), vigencia_fim=None, ativo=True,
    )
    db_session.add(padrao)
    db_session.commit()

    ctx = montar_contexto_avulso(db_session, {"data_calibracao": date(2026, 7, 14)})
    assert ctx["padraocilindro"] == "CC747704"
    assert ctx["padraocertificado"] == "202231419"
    assert ctx["padraoconcentracao"] == "100,1"
    assert ctx["padraoconcentracao"] != ""
    assert ctx["drygasppm"] == ctx["padraoconcentracao"]
    assert ctx["drygasppm"] != ""


def test_avulso_sem_cilindro_para_a_data_deixa_campos_vazios_sem_erro(db_session):
    """Sem cilindro cobrindo a data (ou sem data digitada), os campos do cilindro
    saem vazios — nao e um caso de erro, e o comportamento correto."""
    from app.core.certificado_gerar import montar_contexto_avulso

    ctx = montar_contexto_avulso(db_session, {"data_calibracao": date(2026, 7, 14)})
    assert ctx["padraocilindro"] == ""
    assert ctx["padraocertificado"] == ""
    assert ctx["drygasppm"] == ""

    ctx_sem_data = montar_contexto_avulso(db_session, {})
    assert ctx_sem_data["padraocilindro"] == ""
    assert ctx_sem_data["drygasppm"] == ""


def test_avulso_traz_tecnico_e_campos_de_config_nao_da_os(db_session):
    """tecnico, cargo, equipamentos auxiliares, margem de temperatura e limites
    vem da CONFIG do laboratorio, nao da OS — nao ha razao para saírem vazios."""
    from app.core.certificado_config import obter_config
    from app.core.certificado_gerar import montar_contexto_avulso

    config = obter_config(db_session)
    config.equipamentos_auxiliares = "TESTO 622"
    db_session.commit()

    ctx = montar_contexto_avulso(db_session, {})
    assert ctx["tecnico"] == "Walbert Santos"
    assert ctx["tecnicocargo"] == "Técnico em Metrologia"
    assert ctx["equipamentosauxiliares"] == "TESTO 622"
    assert ctx["margemtemp"] == "20 ºC ~ 24 ºC"
    assert ctx["limitemin"] == "0,15"
    assert ctx["limitemax"] == "0,19"


def test_os_com_padrao_preenche_cilindro_e_espelha_drygasppm(db_session, os_base):
    """drygasppm e a PROPRIA concentracao do padrao (na planilha, A82 = $D$72).

    Os outros testes deste arquivo nunca vinculam um padrao a OS, entao essa igualdade
    so era exercitada com os dois lados vazios ("" == "") — prova vazia. Aqui o padrao
    tem valores reais, e o teste checa que drygasppm nao so bate com padraoconcentracao
    como tambem NAO esta vazio, o que descarta um calculo a partir de outro campo.
    """
    from datetime import date
    from app.models import CertificadoPadrao

    padrao = CertificadoPadrao(
        numero_cilindro="CC747704", numero_certificado="202231419",
        concentracao=100.1, incerteza_concentracao=2.0, unidade="µmol/mol",
        vigencia_inicio=date(2020, 1, 1), vigencia_fim=None, ativo=True,
    )
    db_session.add(padrao)
    db_session.commit()

    ordem = _os_com_dados(db_session, os_base)
    ordem.padrao_id = padrao.id
    db_session.commit()

    ctx = montar_contexto(db_session, ordem)
    assert ctx["padraocilindro"] == "CC747704"
    assert ctx["padraocertificado"] == "202231419"
    assert ctx["padraoconcentracao"] == "100,1"
    assert ctx["padraoincerteza"] == "2"
    assert ctx["drygasppm"] == ctx["padraoconcentracao"]
    assert ctx["drygasppm"] != ""
