import json

import httpx
import pytest

from app.core.config import settings
from app.integrations import tiny_client


class FakeResp:
    def __init__(self, corpo, status_code=200):
        self.status_code = status_code
        self._corpo = corpo
        self.text = json.dumps(corpo)
        self.headers = {"x-limit-api": "20"}

    def json(self):
        return self._corpo


@pytest.fixture()
def ativa(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")
    monkeypatch.setattr(settings, "TINY_BASE_URL", "https://api.tiny.test/api2")


@pytest.fixture(autouse=True)
def _sem_banco(monkeypatch):
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: None)


def _captura(monkeypatch, corpo):
    capturado = {}

    def fake_post(url, data=None, timeout=None):
        capturado["url"] = url
        capturado["data"] = data
        capturado["timeout"] = timeout
        return FakeResp(corpo)

    monkeypatch.setattr(httpx, "post", fake_post)
    return capturado


def test_a_suite_nasce_com_o_tiny_desligado():
    """Guarda da fixture `_tiny_desligado` do conftest: o TINY_TOKEN do .env e' o
    REAL de producao e o Tiny nao tem sandbox. Se esta falhar, algum teste pode
    estar espelhando contato de verdade."""
    assert settings.TINY_TOKEN == ""


def test_integracao_ativa_depende_do_token(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    assert tiny_client.integracao_ativa() is False
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok")
    assert tiny_client.integracao_ativa() is True


def test_desligado_nao_faz_chamada(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    chamou = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: chamou.append(1))
    r = tiny_client.incluir_contato({"nome": "X"})
    assert chamou == [] and not r.ok


def test_pesquisar_contato_encontrado(monkeypatch, ativa):
    cap = _captura(monkeypatch, {"retorno": {"status": "OK", "contatos": [
        {"contato": {"id": "565052083", "nome": "SUMA BRASIL", "cpf_cnpj": "16.565.111/0020-48"}}]}})
    r = tiny_client.pesquisar_contato("16565111002048")
    assert r.ok and r.id == 565052083
    assert cap["url"] == "https://api.tiny.test/api2/contatos.pesquisa.php"
    assert cap["data"]["token"] == "tok-123" and cap["data"]["formato"] == "json"
    assert cap["data"]["cpf_cnpj"] == "16565111002048"


def test_pesquisar_contato_escolhe_o_de_documento_exato(monkeypatch, ativa):
    """A base tem 7 cadastros na raiz 05571228: adotar `contatos[0]` sem conferir
    o documento gruda a empresa no contato de OUTRA filial."""
    _captura(monkeypatch, {"retorno": {"status": "OK", "contatos": [
        {"contato": {"id": "111", "nome": "Outra filial", "cpf_cnpj": "05.571.228/0002-00"}},
        {"contato": {"id": "222", "nome": "A certa", "cpf_cnpj": "05.571.228/0003-91"}}]}})
    r = tiny_client.pesquisar_contato("05571228000391")
    assert r.ok and r.id == 222


def test_pesquisar_contato_com_documento_diferente_nao_adota(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "OK", "contatos": [
        {"contato": {"id": "111", "nome": "Outra filial", "cpf_cnpj": "05571228000200"}}]}})
    r = tiny_client.pesquisar_contato("05571228000391")
    assert not r.ok and r.id is None
    assert not r.nao_encontrado and not r.deve_tentar_de_novo
    assert "documento diferente" in r.mensagem


def test_pesquisar_contato_sem_documento_na_resposta_nao_adota(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "OK", "contatos": [
        {"contato": {"id": "111", "nome": "Sem documento"}}]}})
    assert not tiny_client.pesquisar_contato("05571228000391").ok


def test_pesquisar_contato_nao_encontrado(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "Erro", "codigo_erro": "20",
                                       "erros": [{"erro": "A consulta não retornou registros"}]}})
    r = tiny_client.pesquisar_contato("36312056000552")
    assert not r.ok and r.nao_encontrado


def test_incluir_contato_manda_o_json_no_campo_contato(monkeypatch, ativa):
    cap = _captura(monkeypatch, {"retorno": {"status": "OK", "registros": [
        {"registro": {"sequencia": "1", "status": "OK", "id": 610661344}}]}})
    r = tiny_client.incluir_contato({"nome": "Filial", "situacao": "A", "sequencia": 1})
    assert r.ok and r.id == 610661344
    assert cap["url"].endswith("/contato.incluir.php")
    enviado = json.loads(cap["data"]["contato"])
    assert enviado == {"contatos": [{"contato": {"nome": "Filial", "situacao": "A", "sequencia": 1}}]}


def test_alterar_contato_usa_o_endpoint_de_alteracao(monkeypatch, ativa):
    cap = _captura(monkeypatch, {"retorno": {"status": "OK", "registros": [
        {"registro": {"sequencia": "1", "status": "OK", "id": 610661344}}]}})
    r = tiny_client.alterar_contato({"id": 610661344, "nome": "Filial", "situacao": "A", "sequencia": 1})
    assert r.ok and cap["url"].endswith("/contato.alterar.php")


def test_obter_contato_devolve_o_contato_singular(monkeypatch, ativa):
    cap = _captura(monkeypatch, {"retorno": {"status": "OK", "contato": {
        "id": "610661344", "codigo": "12527"}}})
    r = tiny_client.obter_contato(610661344)
    assert r.ok and r.id == 610661344
    assert cap["url"].endswith("/contato.obter.php")


def test_obter_contato_bruto_devolve_o_contato(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "OK", "contato": {
        "id": "610661344", "codigo": "12527", "nome": "Filial"}}})
    atual = tiny_client.obter_contato_bruto(610661344)
    assert atual["codigo"] == "12527"


def test_obter_contato_bruto_devolve_none_quando_falha(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "Erro", "codigo_erro": "20", "erros": []}})
    assert tiny_client.obter_contato_bruto(1) is None


def test_obter_contato_bruto_desligado_registra_pulado_sem_chamar(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    chamou = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: chamou.append(1))
    linhas = []
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: linhas.append(kw))
    assert tiny_client.obter_contato_bruto(1) is None
    assert chamou == []
    assert linhas and linhas[0]["status"] == "pulado" and linhas[0]["motivo"] == "desligado"


def test_obter_contato_bruto_nao_encontrado_tem_motivo_proprio(monkeypatch, ativa):
    """Contato apagado no Tiny nao e' falha da integracao: o log diz o motivo."""
    _captura(monkeypatch, {"retorno": {"status": "Erro", "codigo_erro": "20",
                                       "erros": [{"erro": "A consulta não retornou registros"}]}})
    linhas = []
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: linhas.append(kw))
    assert tiny_client.obter_contato_bruto(1) is None
    assert linhas and linhas[0]["motivo"] == "nao encontrado"


def test_obter_contato_bruto_sucesso_registra_no_log(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "OK", "contato": {
        "id": "610661344", "codigo": "12527"}}})
    linhas = []
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: linhas.append(kw))
    tiny_client.obter_contato_bruto(610661344)
    assert linhas and linhas[0]["status"] == "sucesso"


def test_erro_de_rede_nao_propaga(monkeypatch, ativa):
    def explode(*a, **k):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(httpx, "post", explode)
    r = tiny_client.incluir_contato({"nome": "X"})
    assert not r.ok and r.deve_tentar_de_novo and "sem rede" in r.mensagem
    # Rede caida NAO e' bloqueio do Tiny: fingir o codigo 6 fazia o script dizer
    # "o Tiny bloqueou por excesso de chamadas" quando a internet caiu.
    assert r.tentar_de_novo is True and r.codigo_erro is None


def test_corpo_nao_json_nao_propaga(monkeypatch, ativa):
    class Bruto(FakeResp):
        def json(self):
            raise ValueError("nao e json")

    monkeypatch.setattr(httpx, "post", lambda *a, **k: Bruto({"x": 1}))
    r = tiny_client.pesquisar_contato("1")
    assert not r.ok


def test_registra_no_log_de_integracao(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "OK", "registros": [
        {"registro": {"status": "OK", "id": 7}}]}})
    linhas = []
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: linhas.append(kw))
    tiny_client.incluir_contato({"nome": "Filial"})
    assert linhas and linhas[0]["integracao"] == "tiny" and linhas[0]["status"] == "sucesso"


def test_classificar_tipo_do_tiny():
    from app.core.log_integracao import classificar_tipo
    assert classificar_tipo("tiny", None) == "empresa_contato"


from app.core import tiny as tiny_core
from app.models import Empresa


def _empresa(db, **kw):
    base = dict(nome="Filial Norte", cgc="36312056000552", municipio="Joao Neiva", estado="ES")
    base.update(kw)
    e = Empresa(**base)
    db.add(e); db.commit(); db.refresh(e)
    return e


@pytest.fixture()
def falso_tiny(monkeypatch, ativa):
    """Substitui as 4 chamadas HTTP por respostas controladas."""
    chamadas = {"pesquisa": [], "incluir": [], "alterar": [], "obter": []}
    respostas = {
        "pesquisa": tiny_core.Resultado(ok=False, codigo_erro=20, mensagem="sem registros"),
        "incluir": tiny_core.Resultado(ok=True, id=999),
        "alterar": tiny_core.Resultado(ok=True, id=999),
        "obter": {"id": "999", "codigo": "12527", "tipos_contato": [{"tipo": "Cliente"}]},
    }
    monkeypatch.setattr(tiny_client, "pesquisar_contato",
                        lambda doc: (chamadas["pesquisa"].append(doc), respostas["pesquisa"])[1])
    monkeypatch.setattr(tiny_client, "incluir_contato",
                        lambda c: (chamadas["incluir"].append(c), respostas["incluir"])[1])
    monkeypatch.setattr(tiny_client, "alterar_contato",
                        lambda c: (chamadas["alterar"].append(c), respostas["alterar"])[1])
    monkeypatch.setattr(tiny_client, "obter_contato_bruto",
                        lambda i: (chamadas["obter"].append(i), respostas["obter"])[1])
    return chamadas, respostas


def test_sincronizar_cria_quando_nao_existe_no_tiny(db_session, falso_tiny):
    chamadas, _ = falso_tiny
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_id == 999 and e.tiny_status == "enviada" and e.tiny_erro is None
    assert e.tiny_em is not None
    assert chamadas["pesquisa"] == ["36312056000552"]
    assert chamadas["incluir"][0]["tipos_contato"] == [{"tipo": "Cliente"}]
    assert chamadas["alterar"] == []


def test_sincronizar_adota_contato_que_ja_existe(db_session, falso_tiny):
    chamadas, respostas = falso_tiny
    respostas["pesquisa"] = tiny_core.Resultado(ok=True, id=565052083)
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_id == 565052083 and e.tiny_status == "enviada"
    assert chamadas["incluir"] == []  # nada criado: adotou


def test_sincronizar_com_tiny_id_le_antes_de_alterar(db_session, falso_tiny):
    chamadas, _ = falso_tiny
    e = _empresa(db_session, tiny_id=999, tiny_status="enviada")
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert chamadas["obter"] == [999]
    enviado = chamadas["alterar"][0]
    assert enviado["id"] == "999" and enviado["codigo"] == "12527"      # preservados
    assert enviado["tipos_contato"] == [{"tipo": "Cliente"}]            # sem acumular
    assert enviado["nome"] == "Filial Norte"                            # nosso campo por cima
    assert e.tiny_status == "enviada"


def test_sincronizar_contato_sumiu_do_tiny_recria(db_session, falso_tiny):
    chamadas, respostas = falso_tiny
    respostas["obter"] = None
    respostas["incluir"] = tiny_core.Resultado(ok=True, id=1001)
    e = _empresa(db_session, tiny_id=999)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert chamadas["alterar"] == [] and chamadas["incluir"]
    assert e.tiny_id == 1001 and e.tiny_status == "enviada"


def test_sincronizar_tiny_id_sem_documento_obter_falha_fica_pendente(db_session, falso_tiny):
    """`obter` devolve None por 4 motivos (apagado, rede, corpo invalido,
    limite). Sem documento para pesquisar, criar as cegas geraria um SEGUNDO
    contato para a mesma empresa — melhor ficar pendente."""
    chamadas, respostas = falso_tiny
    respostas["obter"] = None
    e = _empresa(db_session, tiny_id=999, cgc="", cpf=None)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_status == "pendente" and e.tiny_id == 999
    assert chamadas["incluir"] == []


def test_sincronizar_duplicidade_adota(db_session, falso_tiny, monkeypatch):
    chamadas, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=30, mensagem="duplicidade")
    saidas = iter([tiny_core.Resultado(ok=False, codigo_erro=20),          # 1a pesquisa: nao achou
                   tiny_core.Resultado(ok=True, id=777)])                  # apos o 30: achou
    monkeypatch.setattr(tiny_client, "pesquisar_contato",
                        lambda doc: (chamadas["pesquisa"].append(doc), next(saidas))[1])
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_id == 777 and e.tiny_status == "enviada"


def test_sincronizar_pesquisa_indefinida_nao_cria(db_session, falso_tiny):
    """Pesquisa que nao disse "nao encontrado" (corpo estranho, 502, erro sem
    codigo) NAO autoriza criacao: cair na inclusao duplica o contato no ERP."""
    chamadas, respostas = falso_tiny
    respostas["pesquisa"] = tiny_core.Resultado(ok=False, codigo_erro=None,
                                                mensagem="resposta do Tiny nao e' JSON")
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_status == "pendente" and e.tiny_id is None and e.tiny_erro is None
    assert chamadas["incluir"] == []


def test_sincronizar_documento_diferente_nao_cria(db_session, falso_tiny):
    chamadas, respostas = falso_tiny
    respostas["pesquisa"] = tiny_core.Resultado(ok=False,
                                                mensagem="contato encontrado com documento diferente")
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_status == "pendente" and chamadas["incluir"] == []


def test_sincronizar_sem_documento_nao_cria(db_session, falso_tiny):
    """Sem CNPJ nem CPF nao ha pesquisa: criar as cegas duplicaria."""
    chamadas, _ = falso_tiny
    e = _empresa(db_session, cgc="", cpf=None)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_status == "pendente" and chamadas["incluir"] == []


def test_sincronizar_validacao_marca_erro_com_a_mensagem(db_session, falso_tiny):
    _, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=31, mensagem="Cidade não encontrada")
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_status == "erro" and e.tiny_erro == "Cidade não encontrada"
    assert e.tiny_id is None


def test_sincronizar_limite_fica_pendente_sem_erro(db_session, falso_tiny):
    _, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=6, mensagem="API bloqueada")
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_status == "pendente" and e.tiny_erro is None


def test_sincronizar_desligado_nao_marca_nada(db_session, monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)
    db_session.refresh(e)
    assert e.tiny_status is None and e.tiny_id is None


def test_sincronizar_empresa_inexistente_nao_explode(db_session, falso_tiny):
    chamadas, _ = falso_tiny
    tiny_client.sincronizar_empresa(99999, db=db_session)  # sem excecao
    assert chamadas["pesquisa"] == []


def test_sincronizar_nao_propaga_excecao(db_session, falso_tiny, monkeypatch):
    def explode(_doc):
        raise RuntimeError("boom")

    monkeypatch.setattr(tiny_client, "pesquisar_contato", explode)
    e = _empresa(db_session)
    tiny_client.sincronizar_empresa(e.id, db=db_session)   # nao levanta
    db_session.refresh(e)
    assert e.tiny_status is None and e.tiny_id is None


def test_trava_da_empresa_nao_pega_o_lado_anulavel_do_join():
    """O Postgres recusa `FOR UPDATE` sobre o LEFT JOIN que `matriz_rel`
    (lazy="joined") acrescenta a toda leitura de Empresa:

        FOR UPDATE cannot be applied to the nullable side of an outer join

    Em producao isso derrubava TODO espelhamento em tempo real (criar, editar,
    botao Reenviar) e a empresa ficava `pendente` para sempre. O SQLite ignora
    `FOR UPDATE`, entao nenhum teste de comportamento pega — so o SQL compilado
    no dialeto do Postgres.
    """
    from sqlalchemy.dialects import postgresql

    sql = str(tiny_client.stmt_travar_empresa(1).compile(dialect=postgresql.dialect()))
    assert "LEFT OUTER JOIN clientes" in sql        # a causa continua la
    assert sql.rstrip().endswith("FOR UPDATE OF empresas")
