import io


def test_model_cria_tabela_e_relationship(db_session, caixa_financeiro):
    from app.models import Caixa, NotaFiscal
    nf = NotaFiscal(caixa=caixa_financeiro, numero="12345",
                    arquivo_pdf="a.pdf", arquivo_xml="a.xml")
    db_session.add(nf)
    db_session.commit()
    cx = db_session.query(Caixa).filter(Caixa.id == caixa_financeiro).first()
    assert [n.numero for n in cx.notas_fiscais] == ["12345"]


def _pdf(nome="nf.pdf"):
    return (nome, io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")


def _xml(nome="nf.xml"):
    return (nome, io.BytesIO(b"<nfse/>"), "application/xml")


def _files(n=1):
    """n pares PDF+XML, no formato que o httpx manda como listas paralelas."""
    return [("arquivos_pdf", _pdf(f"nf{i}.pdf")) for i in range(n)] + \
           [("arquivos_xml", _xml(f"nf{i}.xml")) for i in range(n)]


def _arquivos_no_disco(upload_tmp, caixa_id):
    d = upload_tmp / "notas-fiscais" / "caixa" / str(caixa_id)
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


def test_anexar_tres_notas_de_uma_vez(client_fin, caixa_financeiro, upload_tmp, db_session):
    from app.models import NotaFiscal
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(3), data={"numeros": ["1", "2", "3"]})
    assert r.status_code == 200
    assert [n["numero"] for n in r.json()["notas_fiscais"]] == ["1", "2", "3"]
    assert db_session.query(NotaFiscal).filter(NotaFiscal.caixa == caixa_financeiro).count() == 3
    # 3 notas = 6 arquivos, todos no subdir da CAIXA (nao no da OS)
    assert len(_arquivos_no_disco(upload_tmp, caixa_financeiro)) == 6


def test_anexar_de_novo_acumula_em_vez_de_substituir(client_fin, caixa_financeiro, upload_tmp):
    """Inversao do comportamento antigo: `_gravar_par` apagava a nota anterior.
    Com varias notas por caixa, anexar sempre acrescenta."""
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["1"]})
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(1), data={"numeros": ["2"]})
    assert [n["numero"] for n in r.json()["notas_fiscais"]] == ["1", "2"]


def test_listas_de_tamanhos_diferentes_422_sem_gravar_nada(client_fin, caixa_financeiro, upload_tmp):
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(2), data={"numeros": ["1"]})
    assert r.status_code == 422
    assert _arquivos_no_disco(upload_tmp, caixa_financeiro) == []


def test_arquivo_invalido_no_meio_do_lote_nao_grava_nenhuma(client_fin, caixa_financeiro,
                                                            upload_tmp, db_session):
    """Tudo ou nada: a terceira nota invalida nao pode deixar as duas primeiras
    gravadas — o Financeiro reenviaria o lote e duplicaria as boas."""
    from app.models import NotaFiscal
    files = [("arquivos_pdf", _pdf("a.pdf")), ("arquivos_pdf", _pdf("b.pdf")),
             ("arquivos_pdf", ("c.png", io.BytesIO(b"\x89PNG"), "image/png")),
             ("arquivos_xml", _xml("a.xml")), ("arquivos_xml", _xml("b.xml")),
             ("arquivos_xml", _xml("c.xml"))]
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=files, data={"numeros": ["1", "2", "3"]})
    assert r.status_code == 415
    assert db_session.query(NotaFiscal).count() == 0
    assert _arquivos_no_disco(upload_tmp, caixa_financeiro) == []


def test_numero_vazio_422(client_fin, caixa_financeiro, upload_tmp):
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(1), data={"numeros": ["   "]})
    assert r.status_code == 422


# ── Regras herdadas do upload por OS ─────────────────────────────────────────
# Os cinco testes abaixo repoem, no caminho por CAIXA, as regras que morreram
# junto com o `POST /ordens/{id}/nota-fiscal` em `test_nota_fiscal.py`.

def test_grava_pdf_e_xml_em_colunas_separadas(client_fin, caixa_financeiro, upload_tmp,
                                              db_session):
    """Cada arquivo na sua coluna. Antes de existirem dois campos, um campo unico
    aceitava PDF OU XML e dava para o XML nunca chegar sem ninguem notar."""
    from app.models import NotaFiscal
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["77"]})
    nf = db_session.query(NotaFiscal).first()
    assert nf.arquivo_pdf.endswith(".pdf")
    assert nf.arquivo_xml.endswith(".xml")


def test_sem_xml_422(client_fin, caixa_financeiro, upload_tmp):
    """PDF e XML sempre andam juntos: faltando o XML, o lote nem comeca."""
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=[("arquivos_pdf", _pdf())], data={"numeros": ["1"]})
    assert r.status_code == 422


def test_pdf_no_lugar_do_xml_415(client_fin, caixa_financeiro, upload_tmp):
    """Cada campo aceita so o proprio tipo — mandar dois PDFs passaria batido e a
    caixa ficaria sem o XML da nota."""
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=[("arquivos_pdf", _pdf()), ("arquivos_xml", _pdf("outro.pdf"))],
                        data={"numeros": ["1"]})
    assert r.status_code == 415


def test_sem_numeros_422(client_fin, caixa_financeiro, upload_tmp):
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais", files=_files(1))
    assert r.status_code == 422


def test_numero_muito_longo_422(client_fin, caixa_financeiro, upload_tmp):
    # String(50) na coluna: sem essa validacao o Postgres levantaria
    # StringDataRightTruncation (500). O SQLite dos testes nao enforca o limite,
    # entao aqui so o status importa.
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(1), data={"numeros": ["1" * 51]})
    assert r.status_code == 422


def test_anexar_em_preparando_retorno_ok(client_fin, caixa_preparando, upload_tmp):
    """A janela de correcao vai ate a fase 7: o Financeiro descobre a nota errada
    quando a expedicao reclama, ja fora do Financeiro."""
    r = client_fin.post(f"/caixas/{caixa_preparando}/notas-fiscais",
                        files=_files(1), data={"numeros": ["9"]})
    assert r.status_code == 200


def test_anexar_em_pos_vendas_409(client_fin, caixa_posvendas, upload_tmp):
    r = client_fin.post(f"/caixas/{caixa_posvendas}/notas-fiscais",
                        files=_files(1), data={"numeros": ["9"]})
    assert r.status_code == 409


def test_anexar_em_caixa_finalizada_409(client_fin, caixa_financeiro, db_session, upload_tmp):
    from app.models import Caixa
    cx = db_session.query(Caixa).filter(Caixa.id == caixa_financeiro).first()
    cx.fase = 8
    db_session.commit()
    r = client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(1), data={"numeros": ["9"]})
    assert r.status_code == 409


def test_anexar_sem_funcao_403(client_com, caixa_financeiro, upload_tmp):
    r = client_com.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                        files=_files(1), data={"numeros": ["9"]})
    assert r.status_code == 403


def test_remover_apaga_registro_e_arquivos(client_fin, caixa_financeiro, upload_tmp, db_session):
    from app.models import NotaFiscal
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["1"]})
    nota_id = db_session.query(NotaFiscal).first().id
    assert len(_arquivos_no_disco(upload_tmp, caixa_financeiro)) == 2
    r = client_fin.delete(f"/caixas/{caixa_financeiro}/notas-fiscais/{nota_id}")
    assert r.status_code == 200
    assert r.json()["notas_fiscais"] == []
    assert db_session.query(NotaFiscal).count() == 0
    assert _arquivos_no_disco(upload_tmp, caixa_financeiro) == []


def test_remover_nota_de_outra_caixa_404(client_fin, caixa_financeiro, caixa_preparando,
                                          upload_tmp, db_session):
    from app.models import NotaFiscal
    client_fin.post(f"/caixas/{caixa_preparando}/notas-fiscais",
                    files=_files(1), data={"numeros": ["1"]})
    nota_id = db_session.query(NotaFiscal).first().id
    r = client_fin.delete(f"/caixas/{caixa_financeiro}/notas-fiscais/{nota_id}")
    assert r.status_code == 404


def test_baixar_pdf_e_xml_da_nota(client_fin, caixa_financeiro, upload_tmp, db_session):
    from app.models import NotaFiscal
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["12345"]})
    nota_id = db_session.query(NotaFiscal).first().id
    rp = client_fin.get(f"/caixas/{caixa_financeiro}/notas-fiscais/{nota_id}/pdf")
    assert rp.status_code == 200
    assert rp.headers["content-type"] == "application/pdf"
    assert "nota-fiscal-12345.pdf" in rp.headers["content-disposition"]
    rx = client_fin.get(f"/caixas/{caixa_financeiro}/notas-fiscais/{nota_id}/xml")
    assert rx.status_code == 200
    # octet-stream de proposito (core/nota_fiscal.media_type): XML de usuario
    # servido como application/xml executaria <script> via polyglot XHTML.
    assert rx.headers["content-type"] == "application/octet-stream"
    assert rx.headers["x-content-type-options"] == "nosniff"


def test_anexar_registra_log_em_todas_as_os_ativas(client_fin, caixa_financeiro,
                                                   upload_tmp, db_session):
    """A correcao precisa deixar rastro — e' a pergunta que o Financeiro faz depois."""
    from app.models import LogOS
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["12345"]})
    textos = [l.texto for l in db_session.query(LogOS).all()]
    assert textos.count("Nota fiscal 12345 anexada") == 2  # a fixture tem 2 OS ativas


def test_avancar_sem_nota_409(client_fin, caixa_financeiro, upload_tmp):
    r = client_fin.post(f"/caixas/{caixa_financeiro}/avancar",
                        json={"obs": None, "cod_retorno": None})
    assert r.status_code == 409


def test_avancar_com_nota_na_tabela_nova_passa(client_fin, caixa_financeiro, upload_tmp):
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["1"]})
    r = client_fin.post(f"/caixas/{caixa_financeiro}/avancar",
                        json={"obs": None, "cod_retorno": None})
    assert r.status_code == 200
    assert r.json()["fase"] == 7


def test_avancar_com_caixa_antiga_so_na_coluna_legada_passa(client_fin, caixa_financeiro_com_nf,
                                                            upload_tmp):
    """Caixa antiga com PDF e sem XML ficou de fora do backfill da 0029. Sem o
    segundo termo do guard ela travaria no Financeiro sem ter o que corrigir."""
    r = client_fin.post(f"/caixas/{caixa_financeiro_com_nf}/avancar",
                        json={"obs": None, "cod_retorno": None})
    assert r.status_code == 200


def test_avancar_com_uma_so_das_os_com_nota_legada_passa(client_fin, db_session, fases_seed,
                                                         upload_tmp):
    """Caso MISTO: a semantica e' "ALGUMA OS tem nota", nao "todas".

    A nota e' da CAIXA, entao basta uma das OS ativas ter a coluna legada
    preenchida para a caixa inteira sair do Financeiro. A regra MUDOU com a 0029:
    o gate antigo rodava dentro do laco (`if not o.nota_fiscal`, por OS) e uma
    unica OS sem nota travava a caixa toda. Hoje quem decide e' `_tem_nota_fiscal`,
    com `any(...)` — trocar esse `any` por `all` faria a suite continuar verde e
    voltaria a travar caixa antiga no Financeiro sem ter o que corrigir (o
    backfill da 0029 exige XML, que a caixa antiga nao tem).
    """
    from app.models import Cliente, Caixa, Ordem
    cli = Cliente(nome="Cliente Financeiro NF Mista")
    cx = Caixa(obs="Caixa financeiro nf mista", fase=10)
    db_session.add_all([cli, cx])
    db_session.flush()
    com_nota = Ordem(cliente=cli.id, fase=10, situacao="E", caixa=cx.id,
                     nota_fiscal="nf.pdf", nota_fiscal_numero="123")
    sem_nota = Ordem(cliente=cli.id, fase=10, situacao="E", caixa=cx.id)
    db_session.add_all([com_nota, sem_nota])
    db_session.commit()
    caixa_id = cx.id

    r = client_fin.post(f"/caixas/{caixa_id}/avancar",
                        json={"obs": None, "cod_retorno": None})
    assert r.status_code == 200
    assert r.json()["fase"] == 7


def test_dispensa_do_admin_nao_carimba_caixa_que_tem_nota(client, usuario_admin, fases_seed,
                                                          caixa_financeiro, upload_tmp,
                                                          db_session):
    """O log de dispensa tambem parou de olhar a coluna: senao a caixa COM nota
    nova ganharia o carimbo de 'sem nota fiscal' por a coluna legada estar vazia."""
    from app.models import LogOS
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    client.post(f"/caixas/{caixa_financeiro}/notas-fiscais", files=_files(1),
                data={"numeros": ["1"]}, headers=h)
    client.post(f"/caixas/{caixa_financeiro}/avancar",
                json={"obs": None, "cod_retorno": None, "sem_nota_fiscal": True}, headers=h)
    textos = [l.texto for l in db_session.query(LogOS).all()]
    assert not any("dispensada pelo Administrador" in t for t in textos)


def test_nota_de_outra_caixa_nao_libera_o_avanco(client_fin, caixa_financeiro, caixa_preparando,
                                                 upload_tmp):
    """O guard filtra por `NotaFiscal.caixa == cx.id`. Sem isso, qualquer nota no
    sistema destravaria qualquer caixa no Financeiro."""
    client_fin.post(f"/caixas/{caixa_preparando}/notas-fiscais",
                    files=_files(1), data={"numeros": ["1"]})
    r = client_fin.post(f"/caixas/{caixa_financeiro}/avancar",
                        json={"obs": None, "cod_retorno": None})
    assert r.status_code == 409


def test_detalhe_da_os_traz_as_notas_da_caixa(client_fin, caixa_financeiro, upload_tmp, db_session):
    from app.models import Ordem
    client_fin.post(f"/caixas/{caixa_financeiro}/notas-fiscais",
                    files=_files(1), data={"numeros": ["12345"]})
    os_id = db_session.query(Ordem).filter(Ordem.caixa == caixa_financeiro).first().id
    r = client_fin.get(f"/ordens/{os_id}")
    assert r.status_code == 200
    assert [n["numero"] for n in r.json()["notas_fiscais"]] == ["12345"]
