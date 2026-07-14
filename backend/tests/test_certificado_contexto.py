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
