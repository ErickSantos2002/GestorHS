import pytest
from pydantic import ValidationError


def test_abrir_in_valida_tipo_servico():
    from app.schemas.ordens import OrdemAbrirIn
    ok = OrdemAbrirIn(equipamento_cliente=1, tipo_servico="C")
    assert ok.tipo_servico == "C"
    with pytest.raises(ValidationError):
        OrdemAbrirIn(equipamento_cliente=1, tipo_servico="X")


def test_cancelar_in_exige_motivo():
    from app.schemas.ordens import CancelarIn
    with pytest.raises(ValidationError):
        CancelarIn(motivo="")


def test_avancar_in_opcional():
    from app.schemas.ordens import AvancarIn
    a = AvancarIn()
    assert a.obs is None and a.cod_retorno is None


def test_funcao_create_exige_descricao():
    from app.schemas.fases import FuncaoCreate
    with pytest.raises(ValidationError):
        FuncaoCreate(descricao="")
