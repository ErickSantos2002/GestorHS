def test_models_proposta_basico(db_session):
    from app.models import Cliente, Proposta, PropostaItem
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    p = Proposta(numero=1, cliente=cli.id, vendedor="Fulano")
    p.itens.append(PropostaItem(descricao="Calibracao", quantidade=2, preco_un=395, total=790))
    db_session.add(p); db_session.flush()
    assert p.numero == 1
    assert p.itens[0].total == 790
    assert p.is_deleted is False


def test_schema_proposta_create_valida():
    from app.schemas.proposta import PropostaCreate, PropostaItemCreate, PropostaAparelhoCreate

    payload = PropostaCreate(
        cliente=1,
        itens=[PropostaItemCreate(descricao="Calibracao de bafometro", quantidade=2, preco_un=395)],
        aparelhos=[PropostaAparelhoCreate(equipamento_cliente=10)],
    )
    assert payload.cliente == 1
    assert payload.itens[0].descricao == "Calibracao de bafometro"
    assert payload.aparelhos[0].equipamento_cliente == 10
    # itens/aparelhos tem default_factory=list quando omitidos
    assert PropostaCreate(cliente=1).itens == []
    assert PropostaCreate(cliente=1).aparelhos == []


def test_schema_proposta_update_todos_campos_opcionais():
    from app.schemas.proposta import PropostaUpdate

    # nenhum campo obrigatorio: instanciar vazio nao deve levantar
    vazio = PropostaUpdate()
    assert vazio.cliente is None
    assert vazio.itens is None
    assert vazio.aparelhos is None

    parcial = PropostaUpdate(desconto=10, observacoes="ajustado")
    assert parcial.desconto == 10
    assert parcial.observacoes == "ajustado"
    assert parcial.vendedor is None


def test_schema_proposta_out_from_attributes(db_session):
    from app.models import Cliente, Proposta, PropostaItem, PropostaAparelho
    from app.schemas.proposta import PropostaOut

    cli = Cliente(nome="ACME", cgc="12345678000199")
    db_session.add(cli); db_session.flush()

    p = Proposta(numero=42, cliente=cli.id, vendedor="Fulano")
    p.itens.append(PropostaItem(descricao="Calibracao", quantidade=1, preco_un=100, total=100))
    p.aparelhos.append(PropostaAparelho(equipamento_cliente=None, serie="ABC123", modelo="X1"))
    db_session.add(p); db_session.flush()

    out = PropostaOut.model_validate(p)
    assert out.id == p.id
    assert out.numero == 42
    assert out.itens[0].descricao == "Calibracao"
    assert out.aparelhos[0].serie == "ABC123"


def test_schema_proposta_versao_out_from_attributes(db_session):
    from app.models import Proposta, PropostaVersao
    from app.schemas.proposta import PropostaVersaoOut

    p = Proposta(numero=99, vendedor="Fulano")
    db_session.add(p); db_session.flush()

    v = PropostaVersao(proposta=p.id, numero_versao=1, alterado_por="Fulano", snapshot={"a": 1})
    db_session.add(v); db_session.flush()

    # has_pdf nao existe na model (so pdf_path); o campo derivado cai no default
    # (False) quando validado direto do objeto do model — quem monta o card real
    # (router, fora do escopo desta task) passa has_pdf explicito via dict/dump.
    out = PropostaVersaoOut.model_validate(v)
    assert out.numero_versao == 1
    assert out.alterado_por == "Fulano"
    assert out.has_pdf is False
    assert out.snapshot == {"a": 1}
