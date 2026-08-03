"""Motor de preenchimento do certificado: monta o contexto a partir da OS e
substitui os campos [token] no HTML do modelo."""
import re
from datetime import date, datetime, timezone
from html import escape as _html_escape

from sqlalchemy.orm import Session

from app.core.certificado_calculo import ParametrosCalculo, calcular, formatar_numero
from app.models import Equipamento, Marca, TipoCalibragem, CertificadoModelo, OSCertificado

# Campos suportados (expostos no editor de modelos). Os nomes batem com os
# usados nos modelos legados; há aliases "amigáveis" no contexto para modelos novos.
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
    ("datacali", "Data da calibração"),
    ("dataentr", "Data de recebimento"),
    ("proxcalibragem", "Próxima calibração"),
    ("tipocalibragem", "Tipo de calibragem"),
    ("calibtemp", "Temperatura"),
    ("calibpressao", "Pressão"),
    ("calibteste1", "Teste 1"),
    ("calibteste2", "Teste 2"),
    ("calibteste3", "Teste 3"),
    ("calibteste4", "Teste 4"),
    ("calibteste5", "Teste 5"),
    ("calibtestemedia", "Média dos testes"),
    ("situcalib", "Situação"),
    ("dataemissao", "Data de emissão"),
    ("erro1", "Erro da medição 1"),
    ("erro2", "Erro da medição 2"),
    ("erro3", "Erro da medição 3"),
    ("erro4", "Erro da medição 4"),
    ("erro5", "Erro da medição 5"),
    ("mediamedicoes", "Média das medições (calculada)"),
    ("incertezaexpandida", "Incerteza expandida (U)"),
    ("fatork", "Fator de abrangência (k)"),
    ("drygasppm", "Dry gas ppm (concentração do padrão)"),
    ("limitemin", "Limite mínimo"),
    ("limitemax", "Limite máximo"),
    ("padraocilindro", "Nº do cilindro"),
    ("padraocertificado", "Nº do certificado do cilindro"),
    ("padraoconcentracao", "Concentração do padrão"),
    ("padraoincerteza", "Incerteza da concentração do padrão"),
    ("tecnico", "Técnico responsável"),
    ("tecnicocargo", "Cargo do técnico"),
    ("equipamentosauxiliares", "Equipamentos auxiliares"),
    ("margemtemp", "Margem de temperatura padrão"),
    ("pulapagina", "Quebra de página (impressão)"),
]

# Quebra de página para impressão — HTML estrutural (não é dado, não escapar).
_PAGE_BREAK = '<div style="page-break-after: always;"></div>'


def _fmt(d) -> str:
    if d is None:
        return ""
    if isinstance(d, datetime):
        d = d.date()
    if isinstance(d, date):
        return d.strftime("%d/%m/%Y")
    return str(d)


def _fmt_doc(valor) -> str:
    """CNPJ/CPF com mascara. O que nao tiver 14/11 digitos sai como veio."""
    bruto = str(valor or "").strip()
    d = re.sub(r"\D", "", bruto)
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return bruto


def _fmt_cep(valor) -> str:
    """CEP com mascara. O que nao tiver 8 digitos sai como veio."""
    bruto = str(valor or "").strip()
    d = re.sub(r"\D", "", bruto)
    return f"{d[:5]}-{d[5:]}" if len(d) == 8 else bruto


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
    cep = _fmt_cep(getattr(cli, "cep", None))
    if cep:
        partes.append(f"CEP {cep}")
    return ", ".join(p for p in partes if p)


# Chaves calculadas/derivadas do certificado EPS-LAB-002. Declaradas em UM lugar para
# que todos os caminhos (OS, avulso, venda, geral) emitam exatamente o mesmo conjunto.
_CHAVES_CALCULADAS = (
    "erro1", "erro2", "erro3", "erro4", "erro5",
    "mediamedicoes", "incertezaexpandida", "fatork",
    "drygasppm", "limitemin", "limitemax",
    "padraocilindro", "padraocertificado", "padraoconcentracao", "padraoincerteza",
    "tecnico", "tecnicocargo", "equipamentosauxiliares", "margemtemp",
)


def _bloco_calculado(calc: dict[str, str] | None) -> dict[str, str]:
    """Completa com string vazia toda chave calculada que o caminho nao informou."""
    calc = calc or {}
    return {chave: calc.get(chave, "") for chave in _CHAVES_CALCULADAS}


def _montar_contexto(
    *,
    nomecli: str = "", cnpj: str = "", endcli: str = "",
    modelo: str = "", marca: str = "", serie: str = "", patrimonio: str = "",
    datacompra: str = "", os_num: str = "", calibcert: str = "",
    proxcalibragem: str = "", tipocalibragem: str = "",
    datacali: str = "", dataentr: str = "",
    temp: str = "", pressao: str = "", t1: str = "", t2: str = "", t3: str = "",
    t4: str = "", t5: str = "",
    calc: dict[str, str] | None = None,
    media: str = "", situ: str = "",
) -> dict[str, str]:
    """Fonte UNICA do conjunto de chaves do certificado.

    Usado pelo fluxo da OS (`montar_contexto`) e pelo avulso (`montar_contexto_avulso`).
    Manter os dois caminhos aqui impede que um token novo entre em um e falte no outro —
    e um token que falta no contexto sai LITERALMENTE escrito no PDF.
    NAO inclui `pulapagina`: `preencher()` o trata fora do laco, sem escapar.
    """
    hoje = _fmt(date.today())
    return {
        "nomecli": nomecli,
        "cnpj": _fmt_doc(cnpj),
        "endcli": endcli,
        "modelo": modelo,
        "marca": marca,
        "serie": serie,
        "patrimonio": patrimonio,
        "datacompra": datacompra,
        "os": os_num,
        "calibcert": calibcert,
        "proxcalibragem": proxcalibragem,
        "tipocalibragem": tipocalibragem,
        "dataemissao": hoje,
        # nomes legados (usados nos 12 modelos migrados)
        "datacali": datacali,
        "dataentr": dataentr,
        "calibtemp": temp,
        "calibpressao": pressao,
        "calibteste1": t1,
        "calibteste2": t2,
        "calibteste3": t3,
        "calibtestemedia": media,
        "situcalib": situ,
        # aliases amigáveis (para modelos novos)
        "datacalibracao": datacali,
        "temperatura": temp,
        "pressao": pressao,
        "teste1": t1,
        "teste2": t2,
        "teste3": t3,
        "media": media,
        "situacao": situ,
        "calibteste4": t4,
        "calibteste5": t5,
        # bloco calculado + padrao + config; vazio quando o caminho nao tem calibracao
        # (avulso, venda e certificado geral). Nunca AUSENTE — token ausente sai
        # literalmente escrito no PDF.
        **_bloco_calculado(calc),
        "datacli": hoje,
    }


def modelo_marca(db: Session, equipamento_id: int | None) -> tuple[str, str]:
    """(modelo, marca) do catalogo do aparelho — nunca digitados.

    Fonte unica para o fluxo da OS e para o avulso: o modelo/marca sao um atributo do
    APARELHO, nao algo que o laboratorio informa. No avulso o aparelho vem do template
    escolhido.
    """
    if equipamento_id is None:
        return "", ""
    cat = db.get(Equipamento, equipamento_id)
    if cat is None:
        return "", ""
    marca = ""
    if cat.marca:
        m = db.get(Marca, cat.marca)
        marca = (m.descricao if m else "") or ""
    return cat.descricao or "", marca


def _calcular_para_os(db: Session, ordem) -> dict[str, str]:
    """Bloco calculado do certificado: erros, incerteza, padrao e textos da config.

    Os valores NAO sao persistidos: entram no HTML gerado, que ja e o snapshot do
    documento emitido. Persistir numero calculado criaria uma segunda verdade.
    """
    from app.core.certificado_config import obter_config, parametros_de
    from app.models import CertificadoPadrao

    config = obter_config(db)
    medicoes = [getattr(ordem, f"calib_teste{i}", None) for i in range(1, 6)]
    resultado = calcular(medicoes, parametros_de(config))

    padrao = db.get(CertificadoPadrao, ordem.padrao_id) if ordem.padrao_id else None

    bloco = {
        "mediamedicoes": formatar_numero(resultado.media),
        "incertezaexpandida": formatar_numero(resultado.incerteza_expandida),
        "fatork": formatar_numero(resultado.fator_k, casas=2),
        "limitemin": formatar_numero(None if config.limite_minimo is None else float(config.limite_minimo)),
        "limitemax": formatar_numero(None if config.limite_maximo is None else float(config.limite_maximo)),
        "padraocilindro": (padrao.numero_cilindro if padrao else "") or "",
        "padraocertificado": (padrao.numero_certificado if padrao else "") or "",
        "padraoconcentracao": formatar_numero(
            None if (padrao is None or padrao.concentracao is None) else float(padrao.concentracao)
        ),
        "padraoincerteza": formatar_numero(
            None if (padrao is None or padrao.incerteza_concentracao is None)
            else float(padrao.incerteza_concentracao)
        ),
        "tecnico": config.tecnico_nome or "",
        "tecnicocargo": config.tecnico_cargo or "",
        "equipamentosauxiliares": config.equipamentos_auxiliares or "",
        "margemtemp": config.margem_temperatura or "",
    }
    # DRY GAS PPM e a propria concentracao do padrao (na planilha, A82 = $D$72)
    bloco["drygasppm"] = bloco["padraoconcentracao"]
    for i, erro in enumerate(resultado.erros, start=1):
        bloco[f"erro{i}"] = formatar_numero(erro)
    return bloco


def montar_contexto(db: Session, ordem) -> dict[str, str]:
    cli = ordem.cliente_rel
    ec = ordem.equipamento_rel  # EquipamentoCliente
    modelo, marca = modelo_marca(db, ec.equipamento if ec is not None else None)
    tipocal = ""
    if ordem.tipo_calibragem:
        tc = db.get(TipoCalibragem, ordem.tipo_calibragem)
        tipocal = (tc.descricao if tc else "") or ""
    ctx = _montar_contexto(
        nomecli=(cli.nome if cli else "") or "",
        cnpj=((cli.cgc or cli.cpf) if cli else "") or "",
        endcli=_endereco(cli),
        modelo=modelo,
        marca=marca,
        serie=(ec.serie if ec else "") or "",
        patrimonio=(ec.patrimonio if ec else "") or "",
        datacompra=_fmt(ec.datacompra) if ec else "",
        os_num=str(ordem.id),
        calibcert=ordem.calib_cert or "",
        proxcalibragem=_fmt(ordem.prox_calibragem),
        tipocalibragem=tipocal,
        datacali=_fmt(ordem.data_calibracao),
        dataentr=_fmt(ordem.data_chegada),
        temp=ordem.calib_temp or "",
        pressao=ordem.calib_pressao or "",
        t1=ordem.calib_teste1 or "",
        t2=ordem.calib_teste2 or "",
        t3=ordem.calib_teste3 or "",
        t4=ordem.calib_teste4 or "",
        t5=ordem.calib_teste5 or "",
        calc=_calcular_para_os(db, ordem),
        media=ordem.calib_teste_media or "",
        situ=ordem.calib_situacao or "",
    )
    for chave, valor in (ordem.cert_overrides or {}).items():
        if valor:
            ctx[chave] = valor
    # o override do CNPJ e digitado a mao — mascara aqui tambem, senao sai cru no PDF
    ctx["cnpj"] = _fmt_doc(ctx["cnpj"])
    return ctx


def montar_contexto_avulso(db: Session, valores: dict) -> dict[str, str]:
    """Contexto de um certificado sem OS (aparelho de POC): os valores sao DIGITADOS.

    Exceto `modelo`/`marca`, que saem do catalogo do aparelho do template (o laboratorio
    nao os digita), e `patrimonio`, que nao existe para um aparelho de POC.

    Delega ao mesmo `_montar_contexto` do fluxo da OS — e por isso emite exatamente o
    mesmo conjunto de chaves, sem risco de um token vazar como [token] no PDF.
    """
    modelo, marca = modelo_marca(db, valores.get("equipamento"))
    return _montar_contexto(
        nomecli=valores.get("nomecli") or "",
        cnpj=valores.get("cnpj") or "",
        endcli=valores.get("endcli") or "",
        modelo=modelo,
        marca=marca,
        serie=valores.get("serie") or "",
        datacompra=_fmt(valores.get("datacompra")),
        os_num=valores.get("os") or "",
        calibcert=valores.get("calib_cert") or "",
        datacali=_fmt(valores.get("data_calibracao")),
        dataentr=_fmt(valores.get("data_recebimento")),
        temp=valores.get("calib_temp") or "",
        pressao=valores.get("calib_pressao") or "",
        t1=valores.get("calib_teste1") or "",
        t2=valores.get("calib_teste2") or "",
        t3=valores.get("calib_teste3") or "",
        media=valores.get("calib_teste_media") or "",
        situ=valores.get("calib_situacao") or "",
    )


def montar_contexto_venda(db: Session, ec, valores: dict) -> dict[str, str]:
    """Contexto do certificado de VENDA: sem OS, mas com o aparelho ja cadastrado.

    Cliente e aparelho saem do cadastro; `valores` (o que o laboratorio digitou no
    modal) sobrepoe o que for informado, permitindo corrigir na hora sem alterar o
    cadastro. `modelo`/`marca` vem sempre do catalogo — sao atributo do aparelho.

    Delega ao mesmo `_montar_contexto` da OS e do avulso: e o que garante que o
    conjunto de chaves seja identico e nenhum token vaze como [token] no PDF.
    """
    cli = ec.cliente_rel
    modelo, marca = modelo_marca(db, ec.equipamento)

    def _v(chave, padrao=""):
        valor = valores.get(chave)
        return valor if valor not in (None, "") else padrao

    # Nao ha "data de recebimento" numa venda: usa a data de compra do cadastro,
    # caindo em hoje quando o cadastro nao tem.
    dataentr = _fmt(ec.datacompra) if ec.datacompra else _fmt(date.today())

    return _montar_contexto(
        nomecli=_v("nomecli", (cli.nome if cli else "") or ""),
        cnpj=_v("cnpj", ((cli.cgc or cli.cpf) if cli else "") or ""),
        endcli=_v("endcli", _endereco(cli)),
        modelo=modelo,
        marca=marca,
        serie=_v("serie", ec.serie or ""),
        patrimonio=_v("patrimonio", ec.patrimonio or ""),
        datacompra=_fmt(valores.get("datacompra")) or _fmt(ec.datacompra),
        os_num="XXXX",                       # sem OS — convencao ja usada no avulso
        calibcert=_v("calib_cert"),
        proxcalibragem=_fmt(valores.get("prox_calibragem")),
        tipocalibragem="",                   # nao se aplica a uma venda
        datacali=_fmt(valores.get("data_calibracao")),
        dataentr=dataentr,
        temp=_v("calib_temp"),
        pressao=_v("calib_pressao"),
        t1=_v("calib_teste1"),
        t2=_v("calib_teste2"),
        t3=_v("calib_teste3"),
        media=_v("calib_teste_media"),
        situ=_v("calib_situacao"),
    )


def preencher(html: str, contexto: dict[str, str]) -> str:
    # O template é HTML confiável (editado só por admin/laboratório), mas os
    # VALORES vêm de dados (cliente, série, etc.) e são escapados para evitar
    # injeção de HTML/script no certificado renderizado.
    if not html:
        return html or ""
    for campo, valor in contexto.items():
        html = html.replace(f"[{campo}]", _html_escape(valor or "", quote=True))
    # token estrutural (quebra de página): HTML confiável, inserido sem escapar
    html = html.replace("[pulapagina]", _PAGE_BREAK)
    return html


def tipos_para(ordem) -> list[str]:
    tipos = ["C"]
    if ordem.tipo_servico in ("M", "A"):
        tipos.append("M")
    return tipos


def tipos_sem_modelo(db: Session, ordem, tipos: list[str]) -> list[str]:
    """Dos tipos pedidos, quais o aparelho NÃO tem modelo de certificado cadastrado.

    Existe para que a falta de modelo vire um aviso explícito: antes, `gerar_certificados`
    apenas ignorava o tipo sem modelo e devolvia lista vazia, e o endpoint respondia 200 —
    o usuário clicava em "Gerar certificado" e nada acontecia, sem explicação.
    """
    ec = ordem.equipamento_rel
    if ec is None:
        return list(tipos)
    faltando = []
    for tipo in tipos:
        modelo = db.query(CertificadoModelo).filter(
            CertificadoModelo.equipamento == ec.equipamento, CertificadoModelo.tipo == tipo
        ).first()
        if modelo is None or not modelo.texto:
            faltando.append(tipo)
    return faltando


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
