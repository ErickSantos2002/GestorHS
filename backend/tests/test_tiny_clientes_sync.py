import pytest

from app.core import tiny as tiny_core
from app.core.config import settings
from app.integrations import tiny_client
from app.models import Cliente

CNPJ = "31790710000196"


@pytest.fixture(autouse=True)
def _sem_log(monkeypatch):
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: None)


@pytest.fixture()
def falso_tiny(monkeypatch):
    """Substitui as chamadas HTTP; `alterar`/`obter` explodem se alguem chamar."""
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")
    chamadas = {"pesquisa": [], "incluir": []}
    respostas = {
        "pesquisa": [tiny_core.Resultado(ok=False, codigo_erro=20, mensagem="sem registros")],
        "incluir": tiny_core.Resultado(ok=True, id=999),
    }

    def pesquisar(doc):
        chamadas["pesquisa"].append(doc)
        fila = respostas["pesquisa"]
        return fila.pop(0) if len(fila) > 1 else fila[0]

    def proibido(*a, **k):
        raise AssertionError("Cliente nunca e' alterado no Tiny")

    monkeypatch.setattr(tiny_client, "pesquisar_contato", pesquisar)
    monkeypatch.setattr(tiny_client, "incluir_contato",
                        lambda c: (chamadas["incluir"].append(c), respostas["incluir"])[1])
    monkeypatch.setattr(tiny_client, "alterar_contato", proibido)
    monkeypatch.setattr(tiny_client, "obter_contato_bruto", proibido)
    return chamadas, respostas


def _cliente(db, **kw):
    base = dict(nome="IMETAME METALMECANICA LTDA", cgc=CNPJ, numero=643, complemento="-",
                municipio="ARACRUZ", estado="ES", telefones="27 99619-1347")
    base.update(kw)
    c = Cliente(**base); db.add(c); db.commit(); db.refresh(c)
    return c


def test_cria_quando_nao_existe_no_tiny(db_session, falso_tiny):
    chamadas, _ = falso_tiny
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_id == 999 and c.tiny_status == "enviada" and c.tiny_erro is None
    assert c.tiny_em is not None
    assert chamadas["pesquisa"] == [CNPJ]
    assert chamadas["incluir"][0]["fone"] == "27 99619-1347"
    assert chamadas["incluir"][0]["tipos_contato"] == [{"tipo": "Cliente"}]


def test_adota_o_que_existe_sem_mandar_nada(db_session, falso_tiny):
    chamadas, respostas = falso_tiny
    respostas["pesquisa"] = [tiny_core.Resultado(ok=True, id=610662219)]
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_id == 610662219 and c.tiny_status == "enviada"
    assert chamadas["incluir"] == []


def test_com_tiny_id_nao_chama_o_tiny(db_session, falso_tiny):
    """Segundo sync do mesmo cliente (duplo agendamento): a checagem vem DEPOIS
    da trava, entao quem chega por ultimo ve o tiny_id e sai."""
    chamadas, _ = falso_tiny
    c = _cliente(db_session, tiny_id=123, tiny_status="enviada")
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    assert chamadas["pesquisa"] == [] and chamadas["incluir"] == []


def test_sem_documento_marca_erro_sem_chamar(db_session, falso_tiny):
    chamadas, _ = falso_tiny
    c = _cliente(db_session, cgc=None, cpf=None)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_status == "erro" and c.tiny_erro == "cliente sem CNPJ/CPF"
    assert chamadas["pesquisa"] == []


@pytest.mark.parametrize("pesquisa", [
    tiny_core.Resultado(ok=False, codigo_erro=6, mensagem="bloqueado"),
    tiny_core.Resultado(ok=False, tentar_de_novo=True, mensagem="timeout"),
    tiny_core.Resultado(ok=False, mensagem="contato encontrado com documento diferente"),
    tiny_core.Resultado(ok=False, mensagem="resposta do Tiny nao e' JSON"),
])
def test_pesquisa_que_nao_e_erro_20_fica_pendente_e_nao_cria(db_session, falso_tiny, pesquisa):
    chamadas, respostas = falso_tiny
    respostas["pesquisa"] = [pesquisa]
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_status == "pendente" and c.tiny_id is None
    assert chamadas["incluir"] == []


def test_recusa_na_inclusao_marca_erro_com_a_mensagem(db_session, falso_tiny):
    _, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=31, mensagem="Cidade nao encontrada")
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_status == "erro" and c.tiny_erro == "Cidade nao encontrada"


def test_cliente_sem_nome_vira_erro_sem_excecao(db_session, falso_tiny):
    """`clientes.nome` e' nullable no legado e o Tiny exige nome: a recusa vira
    `erro` visivel, nao excecao."""
    chamadas, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=31, mensagem="nome obrigatorio")
    c = _cliente(db_session, nome=None)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert "nome" not in chamadas["incluir"][0]
    assert c.tiny_status == "erro" and c.tiny_erro == "nome obrigatorio"


def test_limite_na_inclusao_fica_pendente(db_session, falso_tiny):
    _, respostas = falso_tiny
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=6, mensagem="bloqueado")
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_status == "pendente" and c.tiny_erro is None


def test_duplicidade_pesquisa_de_novo_e_adota(db_session, falso_tiny):
    chamadas, respostas = falso_tiny
    respostas["pesquisa"] = [tiny_core.Resultado(ok=False, codigo_erro=20),
                             tiny_core.Resultado(ok=True, id=777)]
    respostas["incluir"] = tiny_core.Resultado(ok=False, codigo_erro=30, mensagem="duplicado")
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_id == 777 and c.tiny_status == "enviada"
    assert len(chamadas["pesquisa"]) == 2


def test_cliente_inativo_tambem_e_sincronizado(db_session, falso_tiny):
    c = _cliente(db_session, ativo=False)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_id == 999 and c.tiny_status == "enviada"


def test_desligado_nao_marca_nada(db_session, monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)
    db_session.refresh(c)
    assert c.tiny_status is None


def test_cliente_inexistente_nao_explode(db_session, falso_tiny):
    tiny_client.sincronizar_cliente(99999, db=db_session)


def test_nao_propaga_excecao(db_session, falso_tiny, monkeypatch):
    def explode(doc):
        raise RuntimeError("boom")
    monkeypatch.setattr(tiny_client, "pesquisar_contato", explode)
    c = _cliente(db_session)
    tiny_client.sincronizar_cliente(c.id, db=db_session)   # nao levanta


def test_trava_do_cliente_e_for_update_of_clientes():
    """Mesma licao de 17/09 (empresas): o SQLite ignora FOR UPDATE, so o SQL
    compilado no dialeto do Postgres pega uma trava errada."""
    from sqlalchemy.dialects import postgresql

    sql = str(tiny_client.stmt_travar_cliente(1).compile(dialect=postgresql.dialect()))
    assert sql.rstrip().endswith("FOR UPDATE OF clientes")
