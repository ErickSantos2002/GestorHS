"""Padrao da proposta nova (observacao, validade, frete por regiao e os blocos de
"Outros itens"). Fonte UNICA desde nov/2026: a tela e o Guardi leem de
GET /propostas/padrao. Era frontend/src/app/propostas/propostaDefaults.ts — o HTML
tem que sair identico ao que a tela gerava (tests/fixtures/proposta_padrao_ts.json).
Funcao pura: sem I/O.
"""

VALIDADE_DIAS = 30

DEFAULT_NOTES = (
    'Caso, durante o processo de calibração, seja identificado que o aparelho necessita de manutenção, a presente proposta será atualizada para incluir os serviços adicionais necessários, bem como os respectivos valores.'
)

# Mesmos valores do texto "Frete para entrega fixo" do bloco padrao.
FRETE_POR_REGIAO = {"Norte": 200, "Nordeste": 150, "Sul": 250, "Sudeste": 200, "Centro-Oeste": 200}

REGIAO_POR_UF = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste",
    "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}

# Quill descarta <hr>: linha de tracos em texto + linhas em branco.
HR = "<p><br></p><p>──────────────────────────────</p><p><br></p>"


def esc(s: str) -> str:
    """Mesmo escape da tela (o & primeiro). Modelo/serie vem de dado digitado."""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def outros_itens_padrao(modelo: str = "", aparelhos: str = "") -> str:
    return f"""<p><strong>Serviços de Calibração e Manutenção</strong></p>
<p><strong>Modelo:</strong> {esc(modelo)}<br><strong>Aparelhos:</strong> {esc(aparelhos)}</p>{HR}<p><strong>Serviço Realizado:</strong></p>
<ul><li>Calibração</li></ul>
<p><strong>Valor Unitário da Calibração:</strong></p>
<ul><li>R$ 395,00</li></ul>{HR}<p><strong>Método de Envio:</strong></p>
<ul><li>SEDEX</li></ul>
<p><strong>Frete para entrega fixo:</strong></p>
<p>Região Norte: R$ 200,00<br>Região Nordeste: R$ 150,00<br>Região Sul: R$ 250,00<br>Região Sudeste: R$ 200,00<br>Região Centro-Oeste: R$ 200,00</p>{HR}<p><strong>Prazo de Entrega</strong></p>
<p>Norte: 15 a 22 dias úteis<br>Nordeste: 7 a 15 dias úteis<br>Sul: 7 dias úteis<br>Centro-Oeste: 7 a 15 dias úteis<br>Sudeste: 7 dias úteis</p>{HR}<p><strong>Códigos de Serviço – CNAEs Relacionados:</strong></p>
<p>33.12-102 – Manutenção e reparação de aparelhos e instrumentos de medida, teste e controle</p>
<p>14.01 – Lubrificação, limpeza, lubrificação, revisão, carga e recarga, conserto, restauração, blindagem, manutenção e conservação de máquinas, veículos, aparelhos, equipamentos, motores, elevadores ou de qualquer objeto (exceto peças e partes empregadas, que ficam sujeitas ao ICMS)</p>{HR}<p><strong>Endereço para o envio dos Aparelhos:</strong><br>Rua Viscondessa do Livramento, nº 54<br>Bairro: Derby<br>CEP: 52010-065<br>Recife – PE</p>
<p><br></p>
<p><strong>Contato – Setor de Calibração</strong><br>Telefone: (81) 3052-3350</p>"""


def outros_itens_phoebus(serial: str = "", modulo: str = "") -> str:
    modulo_txt = esc(modulo.strip()) if modulo.strip() else "[Inserir número]"
    serial_txt = esc(serial.strip()) if serial.strip() else "[Inserir número]"
    return f"""<p><strong>Calibração Anual e Anuidade da Plataforma do Aparelho Phoebus</strong></p>{HR}<p><strong>1. Informações do Aparelho</strong></p>
<ul><li><strong>Número do Módulo:</strong> {modulo_txt}</li><li><strong>Serial do Aparelho:</strong> {serial_txt}</li></ul>{HR}<p><strong>2. Periodicidade dos Serviços</strong></p>
<ul><li><strong>Calibração:</strong> realizada a cada 12 meses.</li><li><strong>Anuidade da Plataforma:</strong> renovação a cada 12 meses.</li></ul>{HR}<p><strong>3. Valores Referentes</strong></p>
<ul><li><strong>Calibração:</strong> R$ ____ (por unidade) + IPCA anual</li><li><strong>Anuidade Plataforma Web 2025:</strong> R$ ____ (por unidade) + IPCA anual</li></ul>{HR}<p><strong>4. Método de Envio</strong></p>
<ul><li><strong>Sedex</strong> – frete já incluso no valor da calibração.</li></ul>{HR}<p><strong>5. Código dos Serviços</strong></p>
<p><strong>Plataforma:</strong></p>
<ul><li><strong>Código:</strong> 01.05 – Licenciamento ou cessão de direito de uso de programas de computação</li><li><strong>CNAE:</strong> 6203-1/00 – Desenvolvimento e licenciamento de programas de computador não-customizáveis</li></ul>
<p><strong>Calibração:</strong></p>
<ul><li><strong>Código:</strong> 14.01 – Lubrificação, limpeza, lustração, revisão, carga e recarga, conserto, restauração, blindagem, manutenção e conservação de máquinas, veículos, aparelhos, equipamentos, motores, elevadores ou de qualquer objeto (exceto peças e partes empregadas, sujeitas ao ICMS)</li><li><strong>Serviço:</strong> Calibração – Manutenção e reparação de aparelhos e instrumentos de medida, teste e controle</li></ul>{HR}<p><strong>Prazo de Entrega</strong></p>
<p>Norte: 15 a 22 dias úteis<br>Nordeste: 7 a 15 dias úteis<br>Sul: 7 dias úteis<br>Centro-Oeste: 7 a 15 dias úteis<br>Sudeste: 7 dias úteis</p>{HR}<p><strong>Códigos de Serviço – CNAEs Relacionados:</strong></p>
<ul><li><strong>33.12-102</strong> – Manutenção e reparação de aparelhos e instrumentos de medida, teste e controle</li><li><strong>14.01</strong> – Lubrificação, limpeza, lubrificação, revisão, carga e recarga, conserto, restauração, blindagem, manutenção e conservação de máquinas, veículos, aparelhos, equipamentos, motores, elevadores ou de qualquer objeto (exceto peças e partes empregadas, que ficam sujeitas ao ICMS)</li></ul>{HR}<p><strong>Endereço para Devolução dos Aparelhos:</strong><br>Rua Viscondessa do Livramento, nº 54<br>Bairro: Derby<br>CEP: 52010-065<br>Recife – PE</p>{HR}<p><strong>6. Endereço para Envio do Material</strong><br>Rua Viscondessa do Livramento, 54 – Sala G<br>Bairro: Derby<br>CEP: 52010-065<br>Recife – PE</p>"""


def montar_padrao(modelos: str = "", series: str = "") -> dict:
    return {
        "observacoes": DEFAULT_NOTES,
        "validade_dias": VALIDADE_DIAS,
        "frete_por_regiao": dict(FRETE_POR_REGIAO),
        "regiao_por_uf": dict(REGIAO_POR_UF),
        "outros_itens": {
            "padrao": outros_itens_padrao(modelos, series),
            "phoebus": outros_itens_phoebus(series, ""),
        },
    }
