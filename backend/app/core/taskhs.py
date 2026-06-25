"""Integração GestorHS → TaskHS: lógica pura (sem I/O).

Monta o payload do card a partir de uma OS e mapeia fase → nome de lista.
As strings de lista são exatas (emoji incluso) — o TaskHS resolve por nome.
"""

SOURCE = "gestorhs"
BOARD = "Serviço"

FASE_PARA_LISTA: dict[int, str] = {
    4: "🚚 Expedição (Abrindo caixa)",
    5: "🔬Laboratório Calibração",
    6: "Serviços 🪛",
    7: "🚚 Expedição (Preparando para Envio)",
    8: "📮Correios",
}

TIPO_SERVICO_LABEL: dict[str, str] = {"C": "Calibração", "M": "Manutenção", "A": "Ambas"}


def lista_da_fase(fase: int) -> str | None:
    return FASE_PARA_LISTA.get(fase)


def montar_titulo(ordem) -> str:
    partes = [f"OS #{ordem.id}"]
    if ordem.cliente_nome:
        partes.append(ordem.cliente_nome)
    descricao = ordem.equipamento_descricao or ordem.equipamento_serie
    if descricao:
        partes.append(descricao)
    return " · ".join(partes)


def _fmt(dt) -> str:
    return dt.date().strftime("%d/%m/%Y") if dt is not None else ""


def _juntar(linhas: list[str | None], sep: str = " · ") -> str:
    return sep.join([x for x in linhas if x])


def _endereco(cli) -> str | None:
    if cli is None:
        return None
    rua = cli.endereco or ""
    if cli.numero:
        rua = f"{rua}, {cli.numero}" if rua else str(cli.numero)
    if cli.complemento:
        rua = f"{rua} {cli.complemento}".strip()
    cidade_uf = "/".join([x for x in (cli.municipio, cli.estado) if x])
    partes = _juntar([rua or None, cli.bairro, cidade_uf or None,
                      f"CEP {cli.cep}" if cli.cep else None])
    return partes or None


def _cabecalho(ordem) -> list[str]:
    linhas: list[str] = []
    if ordem.cliente_nome:
        linhas.append(f"Cliente: {ordem.cliente_nome}")
    patr = getattr(ordem.equipamento_rel, "patrimonio", None) if ordem.equipamento_rel else None
    ids = _juntar([f"Série {ordem.equipamento_serie}" if ordem.equipamento_serie else None,
                   f"Patr. {patr}" if patr else None], sep=" / ")
    aparelho = _juntar([ordem.equipamento_descricao, ids or None])
    if aparelho:
        linhas.append(f"Aparelho: {aparelho}")
    rotulo = TIPO_SERVICO_LABEL.get(ordem.tipo_servico)
    if rotulo:
        linhas.append(f"Serviço: {rotulo}")
    return linhas


def _bloco(titulo: str, linhas: list[str | None]) -> str | None:
    conteudo = [f"- {x}" for x in linhas if x]
    if not conteudo:
        return None
    return "\n".join([titulo, *conteudo])


def _sec_recebido(ordem) -> str | None:
    chegada = _juntar([f"Chegada: {_fmt(ordem.data_chegada)}" if ordem.data_chegada else None,
                       f"Condição: {ordem.condicao_chegada}" if ordem.condicao_chegada else None])
    acess = ", ".join(ordem.acessorios_presentes) if ordem.acessorios_presentes else None
    pilhas_bocais = _juntar([f"Pilhas: {ordem.pilhas}" if ordem.pilhas else None,
                             f"Bocais: {ordem.bocais}" if ordem.bocais else None])
    return _bloco("📋 Recebido", [
        chegada or None,
        f"Acessórios: {acess}" if acess else None,
        pilhas_bocais or None,
        f"Obs: {ordem.obs}" if ordem.obs else None,
    ])


def _sec_laboratorio(ordem, certificados: list[dict]) -> str | None:
    if not certificados:
        return None
    calibrado = _juntar([f"Calibrado em: {_fmt(ordem.data_calibracao)}" if ordem.data_calibracao else None,
                         f"Próxima: {_fmt(ordem.prox_calibragem)}" if ordem.prox_calibragem else None])
    links = [f"Certificado de {TIPO_SERVICO_LABEL.get(c['tipo'], c['tipo'])}: {c['url']}"
             for c in certificados if c.get("url")]
    return _bloco("🔬 Laboratório", [
        f"Resultado: {ordem.calib_situacao}" if ordem.calib_situacao else None,
        calibrado or None,
        f"Certificado: {ordem.calib_cert}" if ordem.calib_cert else None,
        *links,
    ])


def _sec_posvendas(ordem) -> str | None:
    if ordem.fase < 6:
        return None
    cli = ordem.cliente_rel
    telefone = None
    if cli is not None:
        telefone = next((p for p in (cli.celular, cli.whatsapp, cli.telefones) if p), None)
    contato = _juntar([getattr(cli, "contato", None) if cli else None, telefone])
    aceite = None
    if ordem.aceite:
        aceite = f"Aceite: {_fmt(ordem.data_aceite)}" if ordem.data_aceite else "Aceite: sim"
    return _bloco("🤝 Pós-Vendas", [
        f"Contato: {contato}" if contato else None,
        aceite,
    ])


def _sec_preparando(ordem) -> str | None:
    if ordem.fase < 7:
        return None
    end = _endereco(ordem.cliente_rel)
    return _bloco("🚚 Preparando Retorno", [f"Enviar para: {end}" if end else None])


def _sec_finalizada(ordem) -> str | None:
    if not ordem.cod_retorno:
        return None
    linha = _juntar([f"Rastreio: {ordem.cod_retorno}",
                     f"Postado em: {_fmt(ordem.data_retorno)}" if ordem.data_retorno else None])
    return _bloco("📮 Finalizada", [linha or None])


def montar_descricao(ordem, *, certificados: list[dict]) -> str | None:
    cabecalho = "\n".join(_cabecalho(ordem)) or None
    secoes = [
        _sec_recebido(ordem) if ordem.fase >= 4 else None,
        _sec_laboratorio(ordem, certificados),
        _sec_posvendas(ordem),
        _sec_preparando(ordem),
        _sec_finalizada(ordem),
    ]
    blocos = [b for b in [cabecalho, *secoes] if b]
    return "\n\n".join(blocos) if blocos else None


def montar_payload(ordem, *, lista: str, arquivado: bool, descricao: str | None = None) -> dict:
    due_date = ordem.prox_calibragem.date().isoformat() if ordem.prox_calibragem else None
    return {
        "source": SOURCE,
        "external_id": str(ordem.id),
        "board": BOARD,
        "list": lista,
        "title": montar_titulo(ordem),
        "description": descricao if descricao is not None else (ordem.obs or None),
        "due_date": due_date,
        "priority": "medium",
        "archived": arquivado,
    }
