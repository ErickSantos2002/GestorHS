import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

TIPOS_IMAGEM = {"image/jpeg", "image/png", "image/webp"}
TIPOS_PDF = {"application/pdf"}

_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


class ArquivoInvalido(Exception):
    """content-type não permitido ou arquivo grande demais."""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _base() -> Path:
    return Path(settings.UPLOAD_DIR)


def salvar_upload(file: UploadFile, *, subdir: str, tipos_permitidos: set[str]) -> str:
    if file.content_type not in tipos_permitidos:
        raise ArquivoInvalido(415, "tipo de arquivo não suportado")
    conteudo = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(conteudo) > MAX_UPLOAD_BYTES:
        raise ArquivoInvalido(413, "arquivo acima do limite de 10 MB")
    ext = _EXT.get(file.content_type, "")
    basename = uuid.uuid4().hex[:16] + ext
    destino = _base() / subdir
    destino.mkdir(parents=True, exist_ok=True)
    (destino / basename).write_bytes(conteudo)
    return basename


def caminho_arquivo(subdir: str, basename: str) -> Path:
    base = _base().resolve()
    alvo = (base / subdir / basename).resolve()
    if base not in alvo.parents:
        raise ArquivoInvalido(400, "caminho inválido")
    return alvo


def remover_arquivo(subdir: str, basename: str) -> None:
    try:
        caminho_arquivo(subdir, basename).unlink(missing_ok=True)
    except ArquivoInvalido:
        pass
