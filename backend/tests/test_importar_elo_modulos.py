from datetime import date


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
