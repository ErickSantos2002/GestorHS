"""O que cada planilha do GestorHS mostra.

Puro: nao toca no banco. Recebe objetos ja' carregados e devolve dicionarios no
formato que `core.planilha.gerar_xlsx` espera. Fica separado de `planilha.py` para
que o motor continue sem saber o que e' uma OS.
"""
from datetime import date, datetime

from app.core.planilha import Coluna

STATUS_POR_EXTENSO = {
    "em_dia": "Em dia",
    "vencendo": "Vencendo",
    "vencido": "Vencido",
    "sem_data": "Sem data",
}

# Os codigos de uma letra que o banco guarda. Na planilha vao por extenso: quem abre
# o arquivo nao tem a legenda do sistema por perto.
TIPO_SERVICO_POR_EXTENSO = {"C": "Calibracao", "M": "Manutencao"}
TIPO_CERTIFICADO_POR_EXTENSO = {"C": "Calibracao", "M": "Manutencao"}


COLUNAS_CLIENTES = [
    Coluna("Codigo", "id", 10, "inteiro"),
    Coluna("Nome", "nome", 40),
    Coluna("CNPJ", "cgc", 20),
    Coluna("CPF", "cpf", 16),
    Coluna("Inscr. estadual", "insc_est", 18),
    Coluna("Endereco", "endereco", 40),
    Coluna("Numero", "numero", 10),
    Coluna("Complemento", "complemento", 20),
    Coluna("Bairro", "bairro", 22),
    Coluna("Municipio", "municipio", 24),
    Coluna("UF", "estado", 6),
    Coluna("CEP", "cep", 12),
    Coluna("Contato", "contato", 24),
    Coluna("E-mail", "email", 32),
    Coluna("Telefones", "telefones", 26),
    Coluna("Celular", "celular", 20),
    Coluna("WhatsApp", "whatsapp", 20),
    Coluna("Cadastrado em", "datcad", 16, "data"),
    Coluna("Ativo", "ativo", 8, "sim_nao"),
]

COLUNAS_FROTA = [
    Coluna("Codigo", "id", 10, "inteiro"),
    Coluna("Cliente", "cliente_nome", 34),
    Coluna("CNPJ do cliente", "cliente_cnpj", 20),
    Coluna("Aparelho", "equipamento_descricao", 30),
    Coluna("Marca", "marca", 18),
    Coluna("Serie", "serie", 18),
    Coluna("Patrimonio", "patrimonio", 16),
    Coluna("Data da compra", "datacompra", 16, "data"),
    Coluna("Ultima calibracao", "ult_calibragem", 18, "data"),
    Coluna("Proxima calibracao", "prox_calibragem", 18, "data"),
    Coluna("Status", "status_calibracao", 14),
    Coluna("No. do certificado", "calib_cert", 20),
    Coluna("Situacao da calibracao", "calib_situacao", 22),
    Coluna("OS atual", "os_atual", 12, "inteiro"),
    Coluna("Ativo", "ativo", 8, "sim_nao"),
]

COLUNAS_ORDENS = [
    Coluna("OS", "id", 10, "inteiro"),
    Coluna("Cliente", "cliente_nome", 34),
    Coluna("CNPJ do cliente", "cliente_cnpj", 20),
    Coluna("Aparelho", "equipamento_descricao", 30),
    Coluna("Serie", "equipamento_serie", 18),
    Coluna("Fase", "fase_descricao", 20),
    Coluna("Tipo de servico", "tipo_servico", 16),
    Coluna("Chegada", "data_chegada", 18, "datahora"),
    Coluna("Calibracao", "data_calibracao", 18, "datahora"),
    Coluna("Retorno", "data_retorno", 18, "datahora"),
    Coluna("Entrega", "data_entrega", 18, "datahora"),
    Coluna("Proxima calibracao", "prox_calibragem", 18, "datahora"),
    Coluna("No. do certificado", "calib_cert", 20),
    Coluna("Situacao", "calib_situacao", 18),
    Coluna("Nota fiscal", "nota_fiscal_numero", 14),
    Coluna("Valor", "valor", 12, "numero"),
    Coluna("Frete envio", "frete_envio", 12, "numero"),
    Coluna("Frete retorno", "frete_retorno", 12, "numero"),
    Coluna("Pago", "pago", 8, "sim_nao"),
    Coluna("Caixa", "caixa", 10, "inteiro"),
    Coluna("Garantia", "garantia", 10, "sim_nao"),
]

COLUNAS_CERTIFICADOS = [
    Coluna("Cliente", "cliente_nome", 34),
    Coluna("CNPJ", "cliente_cnpj", 20),
    Coluna("Aparelho", "equipamento_descricao", 30),
    Coluna("Serie", "serie", 18),
    Coluna("Origem", "origem", 12),
    Coluna("OS", "os", 10, "inteiro"),
    Coluna("Tipo", "tipo", 16),
    Coluna("No. do certificado", "calib_cert", 20),
    Coluna("Data da calibracao", "data_calibracao", 18, "data"),
    Coluna("Gerado em", "data_geracao", 18, "datahora"),
    Coluna("Gerado por", "usuario_nome", 24),
]


def _cnpj_do_cliente(obj):
    rel = getattr(obj, "cliente_rel", None)
    return rel.cgc if rel else None


def linha_cliente(c) -> dict:
    return {
        "id": c.id, "nome": c.nome, "cgc": c.cgc, "cpf": c.cpf,
        "insc_est": c.insc_est, "endereco": c.endereco, "numero": c.numero,
        "complemento": c.complemento, "bairro": c.bairro, "municipio": c.municipio,
        "estado": c.estado, "cep": c.cep, "contato": c.contato, "email": c.email,
        "telefones": c.telefones, "celular": c.celular, "whatsapp": c.whatsapp,
        "datcad": c.datcad, "ativo": c.ativo,
    }


def linha_frota(e) -> dict:
    # `marca` nao tem property no modelo (diferente de `equipamento_descricao`), entao
    # o endpoint anexa `_marca_nome` no objeto antes de chamar aqui — ver a query do
    # exportar, que ja' faz o join com `marcas`.
    return {
        "id": e.id, "cliente_nome": e.cliente_nome, "cliente_cnpj": _cnpj_do_cliente(e),
        "equipamento_descricao": e.equipamento_descricao,
        "marca": getattr(e, "_marca_nome", None),
        "serie": e.serie, "patrimonio": e.patrimonio, "datacompra": e.datacompra,
        "ult_calibragem": e.ult_calibragem, "prox_calibragem": e.prox_calibragem,
        "status_calibracao": STATUS_POR_EXTENSO.get(e.status_calibracao, e.status_calibracao),
        "calib_cert": e.calib_cert, "calib_situacao": e.calib_situacao,
        "os_atual": e.os_atual, "ativo": e.ativo,
    }


def linha_ordem(o) -> dict:
    return {
        "id": o.id, "cliente_nome": o.cliente_nome, "cliente_cnpj": _cnpj_do_cliente(o),
        "equipamento_descricao": o.equipamento_descricao,
        "equipamento_serie": o.equipamento_serie, "fase_descricao": o.fase_descricao,
        "tipo_servico": TIPO_SERVICO_POR_EXTENSO.get(o.tipo_servico, o.tipo_servico),
        "data_chegada": o.data_chegada, "data_calibracao": o.data_calibracao,
        "data_retorno": o.data_retorno, "data_entrega": o.data_entrega,
        "prox_calibragem": o.prox_calibragem, "calib_cert": o.calib_cert,
        "calib_situacao": o.calib_situacao, "nota_fiscal_numero": o.nota_fiscal_numero,
        "valor": o.valor, "frete_envio": o.frete_envio,
        "frete_retorno": o.frete_retorno, "pago": o.pago, "caixa": o.caixa,
        "garantia": o.garantia,
    }


def montar_rodape(filtros: dict, gerado_em: datetime) -> str:
    """A linha que vai depois dos dados. Quem recebe a planilha por e-mail nao sabe
    que filtro a gerou — sem isso, uma exportacao parcial passa por base completa."""
    usados = [f"{k}: {v}" for k, v in filtros.items() if v not in (None, "")]
    parte = " | ".join(usados) if usados else "sem filtros"
    return f"Gerado pelo GestorHS em {gerado_em.strftime('%d/%m/%Y %H:%M')} — Filtros: {parte}"


def nome_arquivo(base: str, hoje: date) -> str:
    return f"{base}-{hoje.isoformat()}.xlsx"


MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
