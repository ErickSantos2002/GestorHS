import io

import pytest
from fastapi import UploadFile

from app.core import storage
from app.core.storage import ArquivoInvalido


def _upload(nome, conteudo, content_type):
    return UploadFile(filename=nome, file=io.BytesIO(conteudo), headers={"content-type": content_type})


def test_salva_e_le_imagem(upload_tmp):
    base = storage.salvar_upload(_upload("x.jpg", b"abc", "image/jpeg"), subdir="os/1", tipos_permitidos=storage.TIPOS_IMAGEM)
    assert base.endswith(".jpg")
    assert storage.caminho_arquivo("os/1", base).read_bytes() == b"abc"


def test_rejeita_tipo(upload_tmp):
    with pytest.raises(ArquivoInvalido) as e:
        storage.salvar_upload(_upload("x.txt", b"abc", "text/plain"), subdir="os/1", tipos_permitidos=storage.TIPOS_IMAGEM)
    assert e.value.status == 415


def test_rejeita_tamanho(upload_tmp):
    grande = b"x" * (storage.MAX_UPLOAD_BYTES + 1)
    with pytest.raises(ArquivoInvalido) as e:
        storage.salvar_upload(_upload("x.pdf", grande, "application/pdf"), subdir="certificados/1", tipos_permitidos=storage.TIPOS_PDF)
    assert e.value.status == 413


def test_remove(upload_tmp):
    base = storage.salvar_upload(_upload("x.pdf", b"p", "application/pdf"), subdir="certificados/1", tipos_permitidos=storage.TIPOS_PDF)
    storage.remover_arquivo("certificados/1", base)
    assert not storage.caminho_arquivo("certificados/1", base).exists()


def test_caminho_bloqueia_escape_para_subdir_irmao(upload_tmp):
    # não pode escapar do subdir 'certificado-imagens' para um irmão ('certificados') dentro do UPLOAD_DIR
    with pytest.raises(ArquivoInvalido):
        storage.caminho_arquivo("certificado-imagens", "../certificados/1/segredo.pdf")


def test_caminho_bloqueia_escape_do_upload_dir(upload_tmp):
    with pytest.raises(ArquivoInvalido):
        storage.caminho_arquivo("certificado-imagens", "../../etc/passwd")
