import pytest
from app.core import recebimento as rec


def test_listas_fixas():
    assert rec.CHECKLIST_ACESSORIOS[1] == "Bobinas"
    assert rec.CHECKLIST_ACESSORIOS[9] == "Nf de Remessa"
    assert len(rec.CHECKLIST_ACESSORIOS) == 9
    assert "Bom estado" in rec.CONDICOES_CHEGADA
    assert len(rec.CONDICOES_CHEGADA) == 5


def test_ids_para_csv_ordena_e_dedup():
    assert rec.checklist_ids_para_csv([3, 1, 3]) == "1,3"
    assert rec.checklist_ids_para_csv([]) is None
    assert rec.checklist_ids_para_csv(None) is None


def test_ids_para_csv_invalido():
    with pytest.raises(ValueError):
        rec.checklist_ids_para_csv([1, 99])


def test_csv_para_ids_defensivo():
    assert rec.checklist_csv_para_ids("1,3,5") == [1, 3, 5]
    assert rec.checklist_csv_para_ids(" ") == []
    assert rec.checklist_csv_para_ids(None) == []
    assert rec.checklist_csv_para_ids("1,x,99,2") == [1, 2]
