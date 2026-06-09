"""Motor de preenchimento do certificado: monta o contexto a partir da OS e
substitui os campos [token] no HTML do modelo."""
from datetime import date, datetime, timezone
from html import escape as _html_escape

from sqlalchemy.orm import Session

from app.models import Equipamento, Marca, TipoCalibragem, CertificadoModelo, OSCertificado

# Campos suportados (expostos no editor de modelos)
CAMPOS: list[tuple[str, str]] = [
    ("nomecli", "Nome do cliente"),
    ("cnpj", "CNPJ/CPF do cliente"),
    ("endcli", "Endereço do cliente"),
    ("modelo", "Modelo do equipamento"),
    ("marca", "Marca do equipamento"),
    ("serie", "Número de série"),
    ("patrimonio", "Patrimônio"),
    ("datacompra", "Data de compra"),
    ("os", "Número da OS"),
    ("calibcert", "Nº do certificado de calibração"),
    ("datacalibracao", "Data da calibração"),
    ("proxcalibragem", "Próxima calibração"),
    ("tipocalibragem", "Tipo de calibragem"),
    ("temperatura", "Temperatura"),
    ("pressao", "Pressão"),
    ("teste1", "Teste 1"),
    ("teste2", "Teste 2"),
    ("teste3", "Teste 3"),
    ("media", "Média dos testes"),
    ("situacao", "Situação"),
    ("dataemissao", "Data de emissão"),
    ("datacli", "Data (emissão)"),
]


def _fmt(d) -> str:
    if d is None:
        return ""
    if isinstance(d, datetime):
        d = d.date()
    if isinstance(d, date):
        return d.strftime("%d/%m/%Y")
    return str(d)


def _endereco(cli) -> str:
    if cli is None:
        return ""
    partes = [cli.endereco]
    if getattr(cli, "numero", None):
        partes.append(str(cli.numero))
    if getattr(cli, "bairro", None):
        partes.append(cli.bairro)
    cidade = " - ".join(p for p in [getattr(cli, "municipio", None), getattr(cli, "estado", None)] if p)
    if cidade:
        partes.append(cidade)
    return ", ".join(p for p in partes if p)


def montar_contexto(db: Session, ordem) -> dict[str, str]:
    cli = ordem.cliente_rel
    ec = ordem.equipamento_rel  # EquipamentoCliente
    modelo = marca = ""
    if ec is not None:
        cat = db.get(Equipamento, ec.equipamento)
        if cat is not None:
            modelo = cat.descricao or ""
            if cat.marca:
                m = db.get(Marca, cat.marca)
                marca = (m.descricao if m else "") or ""
    tipocal = ""
    if ordem.tipo_calibragem:
        tc = db.get(TipoCalibragem, ordem.tipo_calibragem)
        tipocal = (tc.descricao if tc else "") or ""
    hoje = _fmt(date.today())
    return {
        "nomecli": (cli.nome if cli else "") or "",
        "cnpj": ((cli.cgc or cli.cpf) if cli else "") or "",
        "endcli": _endereco(cli),
        "modelo": modelo,
        "marca": marca,
        "serie": (ec.serie if ec else "") or "",
        "patrimonio": (ec.patrimonio if ec else "") or "",
        "datacompra": _fmt(ec.datacompra) if ec else "",
        "os": str(ordem.id),
        "calibcert": ordem.calib_cert or "",
        "datacalibracao": _fmt(ordem.data_calibracao),
        "proxcalibragem": _fmt(ordem.prox_calibragem),
        "tipocalibragem": tipocal,
        "temperatura": ordem.calib_temp or "",
        "pressao": ordem.calib_pressao or "",
        "teste1": ordem.calib_teste1 or "",
        "teste2": ordem.calib_teste2 or "",
        "teste3": ordem.calib_teste3 or "",
        "media": ordem.calib_teste_media or "",
        "situacao": ordem.calib_situacao or "",
        "dataemissao": hoje,
        "datacli": hoje,
    }


def preencher(html: str, contexto: dict[str, str]) -> str:
    # O template é HTML confiável (editado só por admin/laboratório), mas os
    # VALORES vêm de dados (cliente, série, etc.) e são escapados para evitar
    # injeção de HTML/script no certificado renderizado.
    if not html:
        return html or ""
    for campo, valor in contexto.items():
        html = html.replace(f"[{campo}]", _html_escape(valor or "", quote=True))
    return html


def tipos_para(ordem) -> list[str]:
    tipos = ["C"]
    if ordem.tipo_servico in ("M", "A"):
        tipos.append("M")
    return tipos


def gerar_certificados(db: Session, ordem, tipos: list[str]) -> list:
    """Para cada tipo pedido, preenche o modelo do aparelho e upserta em os_certificados.
    Sem modelo p/ o tipo → ignora. Retorna os OSCertificado gerados/atualizados."""
    ec = ordem.equipamento_rel
    if ec is None:
        return []
    contexto = montar_contexto(db, ordem)
    gerados = []
    for tipo in tipos:
        modelo = db.query(CertificadoModelo).filter(
            CertificadoModelo.equipamento == ec.equipamento, CertificadoModelo.tipo == tipo
        ).first()
        if modelo is None or not modelo.texto:
            continue
        html = preencher(modelo.texto, contexto)
        osc = db.query(OSCertificado).filter(
            OSCertificado.os == ordem.id, OSCertificado.tipo == tipo
        ).first()
        if osc is None:
            osc = OSCertificado(os=ordem.id, tipo=tipo)
            db.add(osc)
        osc.html = html
        osc.data_geracao = datetime.now(timezone.utc)
        gerados.append(osc)
    return gerados
