"""Integração GestorHS → TaskHS: lógica pura (sem I/O).

Monta o payload do card a partir de uma OS: título, obs por etapa (obs1…obs6)
e mapeia fase → list_id (id da lista no TaskHS, contrato v2).
"""

from app.core import os_workflow as wf

SOURCE = "gestorhs"

# Fase da OS (GestorHS) → id da lista no quadro "Serviço" do TaskHS (contrato v2).
# Ids fixos de produção; a lista tem que existir no TaskHS (senão o upsert dá 404).
FASE_PARA_LIST_ID: dict[int, int] = {
    4: 196,  # 🚚 Expedição (Abrindo caixa)
    5: 197,  # 🔬 Laboratório Calibração
    6: 202,  # 🔬 LIBERADOS DO LABORATÓRIO
    10: 205,  # 💰 Financeiro
    7: 209,  # 🚚 Expedição (Preparando para Envio)
    8: 210,  # 📮 Correios
}

TIPO_SERVICO_LABEL: dict[str, str] = {"C": "Calibração", "M": "Manutenção", "A": "Ambas"}


def list_id_da_fase(fase: int) -> int | None:
    return FASE_PARA_LIST_ID.get(fase)


def montar_titulo(ordem) -> str:
    # A caixa vem na frente: e por ela que a expedicao acha a OS no board.
    # OS sem caixa (nem toda tem) mantem o titulo comecando pela OS.
    caixa = getattr(ordem, "caixa", None)
    partes = [f"CX {caixa}"] if caixa else []
    partes.append(f"OS #{ordem.id}")
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


def _bloco(linhas: list[str | None]) -> str | None:
    """Junta as linhas não-vazias em bullets. Sem título — a obs já é nomeada no TaskHS."""
    conteudo = [f"- {x}" for x in linhas if x]
    if not conteudo:
        return None
    return "\n".join(conteudo)


def _sec_recebido(ordem) -> str | None:
    chegada = _juntar([f"Chegada: {_fmt(ordem.data_chegada)}" if ordem.data_chegada else None,
                       f"Condição: {ordem.condicao_chegada}" if ordem.condicao_chegada else None])
    acess = ", ".join(ordem.acessorios_presentes) if ordem.acessorios_presentes else None
    pilhas_bocais = _juntar([f"Pilhas: {ordem.pilhas}" if ordem.pilhas else None,
                             f"Bocais: {ordem.bocais}" if ordem.bocais else None])
    return _bloco([
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
    return _bloco([
        f"Resultado: {ordem.calib_situacao}" if ordem.calib_situacao else None,
        calibrado or None,
        f"Certificado: {ordem.calib_cert}" if ordem.calib_cert else None,
        *links,
    ])


def _sec_posvendas(ordem) -> str | None:
    if wf.posicao(ordem.fase) < wf.posicao(6):
        return None
    cli = ordem.cliente_rel
    telefone = None
    if cli is not None:
        telefone = next((p for p in (cli.celular, cli.whatsapp, cli.telefones) if p), None)
    contato = _juntar([getattr(cli, "contato", None) if cli else None, telefone])
    aceite = None
    if ordem.aceite:
        aceite = f"Aceite: {_fmt(ordem.data_aceite)}" if ordem.data_aceite else "Aceite: sim"
    return _bloco([
        f"Contato: {contato}" if contato else None,
        aceite,
    ])


def _sec_financeiro(ordem, nota_fiscal_url: str | None = None) -> str | None:
    if wf.posicao(ordem.fase) < wf.posicao(10):
        return None
    if ordem.pago:
        pagamento = f"Pagamento: confirmado em {_fmt(ordem.data_pagamento)}" if ordem.data_pagamento else "Pagamento: confirmado"
    else:
        pagamento = "Pagamento: pendente"
    nota = None
    if ordem.nota_fiscal_numero:
        nota = f"Nota fiscal: {ordem.nota_fiscal_numero}"
        if nota_fiscal_url:
            nota = f"{nota} — {nota_fiscal_url}"
    return _bloco([pagamento, nota])


def _sec_preparando(ordem) -> str | None:
    if wf.posicao(ordem.fase) < wf.posicao(7):
        return None
    end = _endereco(ordem.cliente_rel)
    return _bloco([f"Enviar para: {end}" if end else None])


def _sec_finalizada(ordem) -> str | None:
    if not ordem.cod_retorno:
        return None
    linha = _juntar([f"Rastreio: {ordem.cod_retorno}",
                     f"Postado em: {_fmt(ordem.data_retorno)}" if ordem.data_retorno else None])
    return _bloco([linha or None])


def montar_obs(ordem, *, certificados: list[dict], nota_fiscal_url: str | None = None) -> dict:
    """Monta as 6 obs por etapa. Sempre retorna as 6 chaves (None quando a etapa não se aplica).

    obs1 leva o cabeçalho (Cliente/Aparelho/Serviço) no topo, seguido da seção Recebido.
    """
    cabecalho = "\n".join(_cabecalho(ordem)) or None
    recebido = _sec_recebido(ordem) if wf.posicao(ordem.fase) >= wf.posicao(4) else None
    obs1 = "\n".join([x for x in (cabecalho, recebido) if x]) or None
    return {
        "obs1": obs1,
        "obs2": _sec_laboratorio(ordem, certificados),
        "obs3": _sec_posvendas(ordem),
        "obs4": _sec_financeiro(ordem, nota_fiscal_url),
        "obs5": _sec_preparando(ordem),
        "obs6": _sec_finalizada(ordem),
    }


def montar_payload(ordem, *, list_id: int, arquivado: bool, obs: dict) -> dict:
    due_date = ordem.prox_calibragem.date().isoformat() if ordem.prox_calibragem else None
    return {
        "source": SOURCE,
        "external_id": str(ordem.id),
        "list_id": list_id,
        "title": montar_titulo(ordem),
        "obs1": obs.get("obs1"),
        "obs2": obs.get("obs2"),
        "obs3": obs.get("obs3"),
        "obs4": obs.get("obs4"),
        "obs5": obs.get("obs5"),
        "obs6": obs.get("obs6"),
        "due_date": due_date,
        "priority": "medium",
        "archived": arquivado,
    }


# --- Caixa (agregado de N ordens) ---------------------------------------


def montar_titulo_caixa(caixa, ordens) -> str:
    cliente = next((o.cliente_nome for o in ordens if o.cliente_nome), None)
    n = len(ordens)
    partes = [f"CX {caixa.id}"]
    if cliente:
        partes.append(cliente)
    partes.append(f"{n} aparelho" + ("s" if n != 1 else ""))
    return " · ".join(partes)


def _linha_aparelho_lab(ordem, certificados: list[dict]) -> str:
    ident = ordem.equipamento_serie or ordem.equipamento_descricao or f"OS #{ordem.id}"
    if ordem.desfecho_lab == "sem_conserto":
        motivo = getattr(ordem, "desfecho_lab_obs", None) or "sem detalhe"
        return f"{ident}: sem conserto — {motivo}"
    if ordem.desfecho_lab == "liberado":
        motivo = getattr(ordem, "desfecho_lab_obs", None)
        return f"{ident}: liberado sem certificado" + (f" — {motivo}" if motivo else "")
    partes = [ident + ":", ordem.calib_situacao or "calibrado"]
    if ordem.calib_cert:
        partes.append(f"cert {ordem.calib_cert}")
    for c in certificados:
        if c.get("url"):
            partes.append(c["url"])
    return " ".join(partes)


def montar_obs_caixa(caixa, ordens, *, certificados_por_os: dict, nota_fiscal_url=None) -> dict:
    cliente_os = next((o for o in ordens if o.cliente_nome), ordens[0] if ordens else None)
    cabecalho = "\n".join(_cabecalho(cliente_os)) if cliente_os else None
    aparelhos = _bloco([
        _juntar([o.equipamento_descricao, o.equipamento_serie], sep=" / ") or f"OS #{o.id}"
        for o in ordens
    ])
    obs1 = "\n".join([x for x in (cabecalho, aparelhos) if x]) or None
    obs2 = _bloco([_linha_aparelho_lab(o, certificados_por_os.get(o.id, [])) for o in ordens]) or None
    # obs3..obs6 (nível lote) reusam a lógica de uma OS representativa
    rep = ordens[0] if ordens else None
    return {
        "obs1": obs1,
        "obs2": obs2,
        "obs3": _sec_posvendas(rep) if rep else None,
        "obs4": _sec_financeiro(rep, nota_fiscal_url) if rep else None,
        "obs5": _sec_preparando(rep) if rep else None,
        "obs6": _sec_finalizada(rep) if rep else None,
    }


def montar_payload_caixa(caixa, ordens, *, list_id: int, arquivado: bool, obs: dict) -> dict:
    prox = next((o.prox_calibragem for o in ordens if o.prox_calibragem), None)
    return {
        "source": SOURCE,
        "external_id": str(caixa.id),
        "list_id": list_id,
        "title": montar_titulo_caixa(caixa, ordens),
        **{f"obs{i}": obs.get(f"obs{i}") for i in range(1, 7)},
        "due_date": prox.date().isoformat() if prox else None,
        "priority": "medium",
        "archived": arquivado,
    }
