from types import SimpleNamespace

from app.core import tiny


def _empresa(**kw):
    base = dict(id=1, nome="ACME Filial Norte", cgc="36312056000552", cpf=None,
                insc_est="123456", endereco="BR 101", numero="S/N", complemento="KM 196",
                bairro="Zona Rural", municipio="Joao Neiva", estado="ES", cep="29680000",
                email="f@acme.com", telefone="2733330000")
    base.update(kw)
    return SimpleNamespace(**base)


def test_montar_contato_mapeia_os_campos():
    c = tiny.montar_contato(_empresa())
    assert c == {
        "nome": "ACME Filial Norte", "cpf_cnpj": "36312056000552", "tipo_pessoa": "J",
        "ie": "123456", "endereco": "BR 101", "numero": "S/N", "complemento": "KM 196",
        "bairro": "Zona Rural", "cidade": "Joao Neiva", "uf": "ES", "cep": "29680000",
        "email": "f@acme.com", "fone": "2733330000",
    }


def test_montar_contato_corta_o_nome_em_50():
    nome = "A" * 80
    assert tiny.montar_contato(_empresa(nome=nome))["nome"] == "A" * 50


def test_montar_contato_deixa_campo_vazio_de_fora():
    c = tiny.montar_contato(_empresa(insc_est=None, bairro="", email="   "))
    assert "ie" not in c and "bairro" not in c and "email" not in c


def test_montar_contato_cpf_vira_pessoa_fisica():
    c = tiny.montar_contato(_empresa(cgc=None, cpf="12345678909"))
    assert c["cpf_cnpj"] == "12345678909" and c["tipo_pessoa"] == "F"


def test_contato_para_criar_marca_como_cliente():
    # Sem tipos_contato o Tiny cria o contato como "Outro" (verificado em 16/09/2026).
    c = tiny.contato_para_criar(_empresa())
    assert c["sequencia"] == 1 and c["situacao"] == "A"
    assert c["tipos_contato"] == [{"tipo": "Cliente"}]
    assert "id" not in c and "codigo" not in c


def test_contato_para_alterar_preserva_o_que_e_do_tiny():
    # `contato.alterar.php` apaga o que nao for enviado: o que veio do Tiny volta inteiro.
    atual = {
        "id": "610661344", "codigo": "12527", "nome": "NOME ANTIGO", "cidade": "Cidade Velha",
        "tipos_contato": [{"tipo": "Cliente"}, {"tipo": "Fornecedor"}],
        "fantasia": "Apelido", "email_nfe": "nfe@acme.com", "obs": "cliente antigo",
        "pessoas_contato": [{"nome": "Maria"}], "nome_vendedor": "Joao",
    }
    c = tiny.contato_para_alterar(_empresa(), atual)
    assert c["id"] == "610661344"
    assert c["sequencia"] == 1 and c["situacao"] == "A"
    assert c["nome"] == "ACME Filial Norte" and c["cidade"] == "Joao Neiva"
    assert c["codigo"] == "12527"
    assert c["tipos_contato"] == [{"tipo": "Cliente"}, {"tipo": "Fornecedor"}]
    assert c["fantasia"] == "Apelido" and c["email_nfe"] == "nfe@acme.com"
    assert c["obs"] == "cliente antigo" and c["pessoas_contato"] == [{"nome": "Maria"}]
    assert c["nome_vendedor"] == "Joao"


def test_contato_para_alterar_nao_acrescenta_tipos():
    c = tiny.contato_para_alterar(_empresa(), {"id": "1", "tipos_contato": [{"tipo": "Outro"}]})
    assert c["tipos_contato"] == [{"tipo": "Outro"}]


def test_contato_para_alterar_sem_tipos_no_tiny_nao_inventa():
    assert "tipos_contato" not in tiny.contato_para_alterar(_empresa(), {"id": "1"})


def test_ler_resposta_sucesso_de_inclusao():
    r = tiny.ler_resposta({"retorno": {"status_processamento": "3", "status": "OK",
                                       "registros": [{"registro": {"sequencia": "1", "status": "OK", "id": 610661344}}]}})
    assert r.ok and r.id == 610661344 and r.codigo_erro is None


def test_ler_resposta_sucesso_de_pesquisa():
    r = tiny.ler_resposta({"retorno": {"status": "OK", "contatos": [
        {"contato": {"id": "565052083", "nome": "SUMA BRASIL"}}]}})
    assert r.ok and r.id == 565052083


def test_ler_resposta_nao_encontrado():
    r = tiny.ler_resposta({"retorno": {"status": "Erro", "codigo_erro": "20",
                                       "erros": [{"erro": "A consulta não retornou registros"}]}})
    assert not r.ok and r.nao_encontrado and r.codigo_erro == 20
    assert not r.deve_tentar_de_novo


def test_ler_resposta_duplicidade_e_validacao():
    dup = tiny.ler_resposta({"retorno": {"status": "Erro", "codigo_erro": "30",
                                         "erros": [{"erro": "Erro de Duplicidade de Registro"}]}})
    assert dup.duplicidade and not dup.ok
    val = tiny.ler_resposta({"retorno": {"status": "Erro", "codigo_erro": "31",
                                         "erros": [{"erro": "Cidade não encontrada"}]}})
    assert not val.ok and val.codigo_erro == 31 and "Cidade" in val.mensagem


def test_ler_resposta_limite_pede_nova_tentativa():
    for codigo in (6, 11):
        r = tiny.ler_resposta({"retorno": {"status": "Erro", "codigo_erro": str(codigo),
                                           "erros": [{"erro": "API bloqueada momentaneamente"}]}})
        assert r.deve_tentar_de_novo and not r.ok


def test_ler_resposta_erro_no_registro():
    # status_processamento 2: a requisicao passou, o registro nao.
    r = tiny.ler_resposta({"retorno": {"status_processamento": "2", "status": "OK", "registros": [
        {"registro": {"sequencia": "1", "status": "Erro", "erros": [{"erro": "Nome é obrigatório"}]}}]}})
    assert not r.ok and "Nome" in r.mensagem


def test_ler_resposta_corpo_estranho_nao_explode():
    r = tiny.ler_resposta({"qualquer": "coisa"})
    assert not r.ok and r.id is None and r.mensagem
