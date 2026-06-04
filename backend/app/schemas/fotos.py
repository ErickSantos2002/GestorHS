from pydantic import BaseModel


class FotoOut(BaseModel):
    id: int
    os: int
    arquivo: str
    legenda: str | None = None
    url: str
