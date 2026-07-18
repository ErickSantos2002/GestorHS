from datetime import date

import pytest


def _equip(db_session, os_base, serie, equipamento=None):
    from app.models import EquipamentoCliente
    ec = EquipamentoCliente(cliente=os_base["cliente"],
                            equipamento=equipamento or os_base["equipamento"], serie=serie)
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def test_aplicar_cria_instalacao(db_session, os_base):
    from app.scripts.importar_elo_modulos import aplicar
    from app.models import InstalacaoModulo
    pho = _equip(db_session, os_base, "AP-1"); mod = _equip(db_session, os_base, "MOD-1")
    r = aplicar(db_session, [{"linha": 2, "phoebus_id": pho.id, "modulo_id": mod.id}],
                origem="teste", dry_run=False)
    assert r["criados"] == 1
    inst = db_session.query(InstalacaoModulo).one()
    assert inst.modulo == mod.id and inst.phoebus == pho.id and inst.saiu_em is None


def test_aplicar_e_idempotente(db_session, os_base):
    """Rodar duas vezes a mesma planilha nao duplica nem fecha/reabre à toa."""
    from app.scripts.importar_elo_modulos import aplicar
    from app.models import InstalacaoModulo
    pho = _equip(db_session, os_base, "AP-1"); mod = _equip(db_session, os_base, "MOD-1")
    elos = [{"linha": 2, "phoebus_id": pho.id, "modulo_id": mod.id}]
    aplicar(db_session, elos, origem="t1", dry_run=False)
    r = aplicar(db_session, elos, origem="t2", dry_run=False)
    assert r["criados"] == 0 and r["inalterados"] == 1
    assert db_session.query(InstalacaoModulo).count() == 1


def test_aplicar_fecha_a_anterior_quando_o_modulo_muda_de_aparelho(db_session, os_base):
    from app.scripts.importar_elo_modulos import aplicar
    from app.models import InstalacaoModulo
    pho1 = _equip(db_session, os_base, "AP-1"); pho2 = _equip(db_session, os_base, "AP-2")
    mod = _equip(db_session, os_base, "MOD-1")
    aplicar(db_session, [{"linha": 2, "phoebus_id": pho1.id, "modulo_id": mod.id}], origem="t1", dry_run=False)
    r = aplicar(db_session, [{"linha": 3, "phoebus_id": pho2.id, "modulo_id": mod.id}], origem="t2", dry_run=False)
    assert r["criados"] == 1 and r["fechados"] == 1
    abertas = db_session.query(InstalacaoModulo).filter(InstalacaoModulo.saiu_em.is_(None)).all()
    assert len(abertas) == 1 and abertas[0].phoebus == pho2.id
    fechadas = db_session.query(InstalacaoModulo).filter(InstalacaoModulo.saiu_em.isnot(None)).all()
    assert len(fechadas) == 1 and fechadas[0].phoebus == pho1.id


def test_aplicar_dry_run_nao_grava(db_session, os_base):
    from app.scripts.importar_elo_modulos import aplicar
    from app.models import InstalacaoModulo
    pho = _equip(db_session, os_base, "AP-1"); mod = _equip(db_session, os_base, "MOD-1")
    r = aplicar(db_session, [{"linha": 2, "phoebus_id": pho.id, "modulo_id": mod.id}],
                origem="teste", dry_run=True)
    assert r["criados"] == 1                       # conta o que faria
    assert db_session.query(InstalacaoModulo).count() == 0   # mas nao gravou


def test_aplicar_dois_elos_mesmo_phoebus_no_mesmo_lote_nao_estoura_indice(db_session, os_base):
    """Dois elos no MESMO `aplicar()` apontando pro mesmo phoebus (serie de
    aparelho duplicada/typo entre dois grupos de modulo) nao pode violar o
    indice unico parcial nem abortar o lote inteiro — precisa fechar o
    primeiro elo antes do segundo tentar abrir."""
    from app.scripts.importar_elo_modulos import aplicar
    from app.models import InstalacaoModulo
    pho = _equip(db_session, os_base, "AP-1")
    mod_a = _equip(db_session, os_base, "MOD-A")
    mod_c = _equip(db_session, os_base, "MOD-C")
    elos = [
        {"linha": 2, "phoebus_id": pho.id, "modulo_id": mod_a.id},
        {"linha": 3, "phoebus_id": pho.id, "modulo_id": mod_c.id},
    ]

    r = aplicar(db_session, elos, origem="teste", dry_run=False)

    abertas = (
        db_session.query(InstalacaoModulo)
        .filter(InstalacaoModulo.phoebus == pho.id, InstalacaoModulo.saiu_em.is_(None))
        .all()
    )
    assert len(abertas) == 1
    assert abertas[0].modulo == mod_c.id
    assert r["criados"] == 2 and r["fechados"] == 1


def test_aplicar_swap_no_mesmo_lote_nao_dobra_fechados(db_session, os_base):
    """Troca dentro do MESMO lote: modX estava com phoA e modY estava com
    phoB; a nova planilha inverte (modX->phoB, modY->phoA). Sem flush entre
    elos, o segundo reprocessaria linhas ja fechadas pelo primeiro e
    dobraria `fechados`."""
    from app.scripts.importar_elo_modulos import aplicar
    from app.models import InstalacaoModulo
    pho_a = _equip(db_session, os_base, "PHO-A")
    pho_b = _equip(db_session, os_base, "PHO-B")
    mod_x = _equip(db_session, os_base, "MOD-X")
    mod_y = _equip(db_session, os_base, "MOD-Y")
    aplicar(db_session, [{"linha": 2, "phoebus_id": pho_a.id, "modulo_id": mod_x.id}],
            origem="t0", dry_run=False)
    aplicar(db_session, [{"linha": 3, "phoebus_id": pho_b.id, "modulo_id": mod_y.id}],
            origem="t0", dry_run=False)

    elos_swap = [
        {"linha": 4, "phoebus_id": pho_b.id, "modulo_id": mod_x.id},
        {"linha": 5, "phoebus_id": pho_a.id, "modulo_id": mod_y.id},
    ]
    r = aplicar(db_session, elos_swap, origem="t1", dry_run=False)

    assert r["fechados"] == 2   # nao pode dobrar (nao e' 4)
    assert r["criados"] == 2

    abertas = {
        row.phoebus: row.modulo
        for row in db_session.query(InstalacaoModulo).filter(InstalacaoModulo.saiu_em.is_(None)).all()
    }
    assert abertas == {pho_b.id: mod_x.id, pho_a.id: mod_y.id}


def test_montar_series_desempata_serie_duplicada_e_reporta_colisao(db_session, os_base):
    """Caso real: duas linhas de equipamentos_cliente com a MESMA serie sob o
    mesmo catalogo (cadastro duplicado). O mapa tem que apontar pro registro
    ativo/mais recente, e a colisao tem que aparecer pra nao ser resolvida em
    silencio (ver escolher_cadastro em app.core.elo_modulos)."""
    from app.scripts.importar_elo_modulos import _montar_series
    from app.models import EquipamentoCliente

    antigo = EquipamentoCliente(cliente=os_base["cliente"], equipamento=os_base["equipamento"],
                                 serie="WATFR01-00155", ativo=False, prox_calibragem=None)
    novo = EquipamentoCliente(cliente=os_base["cliente"], equipamento=os_base["equipamento"],
                               serie="WATFR01-00155", ativo=True, prox_calibragem=None)
    db_session.add_all([antigo, novo]); db_session.commit()
    db_session.refresh(antigo); db_session.refresh(novo)

    mapa, colisoes = _montar_series(db_session, os_base["equipamento"])

    assert mapa["WATFR01-00155"] == novo.id
    assert len(colisoes) == 1
    assert colisoes[0]["serie"] == "WATFR01-00155"
    assert colisoes[0]["escolhido"] == novo.id
    assert colisoes[0]["descartados"] == [antigo.id]


def test_ler_planilha_acha_colunas_pelo_cabecalho(tmp_path):
    """Le um .xlsx minimo gerado na hora (sem dependencia externa)."""
    from app.scripts.importar_elo_modulos import ler_planilha
    caminho = tmp_path / "mini.xlsx"
    _escrever_xlsx_minimo(caminho)
    linhas = ler_planilha(str(caminho))
    assert len(linhas) == 1
    assert linhas[0]["serie_aparelho"] == "WATFR01-00257"
    assert linhas[0]["serie_modulo"] == "F004230"
    assert linhas[0]["empresa"] == "ACME"


def test_ler_planilha_falta_coluna_obrigatoria_falha_com_erro_claro(tmp_path):
    """Se uma coluna esperada nao aparece no cabecalho (planilha renomeada
    numa exportacao futura), tem que falhar alto nomeando a coluna — nunca
    deixar o campo silenciosamente None em toda linha."""
    from app.scripts.importar_elo_modulos import ler_planilha
    caminho = tmp_path / "sem_coluna.xlsx"
    _escrever_xlsx_sem_serie_modulo(caminho)
    with pytest.raises(ValueError, match="Numero de Serie do Modulo"):
        ler_planilha(str(caminho))


def test_col_letra_erro_claro_em_referencia_invalida():
    from app.scripts.importar_elo_modulos import _col_letra
    with pytest.raises(ValueError):
        _col_letra(None)


def _escrever_xlsx_minimo(caminho):
    """xlsx valido minimo com 1 cabecalho + 1 linha, usando inlineStr (sem sharedStrings)."""
    import zipfile
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
    wb = ('<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
          '<sheets><sheet name="devices" sheetId="1" r:id="rId1" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets></workbook>')

    def c(ref, txt):
        return f'<c r="{ref}" t="inlineStr"><is><t>{txt}</t></is></c>'

    sheet = ('<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
             '<row r="1">' + c("A1", "Número de Série") + c("B1", "Número de Série do Módulo")
             + c("C1", "Próxima Calibração") + c("D1", "Nome da Empresa") + '</row>'
             '<row r="2">' + c("A2", "WATFR01-00257") + c("B2", "F004230")
             + c("C2", "2027-04-25 04:01:05") + c("D2", "ACME") + '</row>'
             '</sheetData></worksheet>')
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/worksheets/sheet1.xml", sheet)


def _escrever_xlsx_sem_serie_modulo(caminho):
    """Como `_escrever_xlsx_minimo`, mas omite a coluna 'Numero de Serie do
    Modulo' inteira (cabecalho e celula) — simula planilha com coluna
    renomeada/removida numa exportacao futura."""
    import zipfile
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
    wb = ('<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
          '<sheets><sheet name="devices" sheetId="1" r:id="rId1" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets></workbook>')

    def c(ref, txt):
        return f'<c r="{ref}" t="inlineStr"><is><t>{txt}</t></is></c>'

    sheet = ('<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
             '<row r="1">' + c("A1", "Número de Série")
             + c("C1", "Próxima Calibração") + c("D1", "Nome da Empresa") + '</row>'
             '<row r="2">' + c("A2", "WATFR01-00257")
             + c("C2", "2027-04-25 04:01:05") + c("D2", "ACME") + '</row>'
             '</sheetData></worksheet>')
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
