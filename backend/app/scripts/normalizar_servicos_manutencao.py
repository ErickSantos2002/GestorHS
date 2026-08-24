"""Normaliza a descricao e escreve o resumo padrao dos servicos de manutencao.

As descricoes vieram do catalogo comercial em CAIXA ALTA. No relatorio elas
saem no campo "Tipo do Problema", que os modelos da Qualidade escrevem em caixa
normal ("Troca da placa mae."), entao ficariam destoando do resto do documento.

O `resumo_padrao` e' a frase que compoe o "Resumo do Servico". Cada uma foi
escrita a mao aqui, no estilo dos tres relatorios reais de referencia: passado,
descritivo, e generico o bastante para servir a qualquer ocorrencia daquele
servico. O tecnico continua podendo ajustar no modal antes de gerar.

SEM RESUMO, de proposito (a tabela abaixo traz `""`):
- as quatro calibracoes com gas rastreado — calibracao nao e' manutencao, tem
  certificado proprio;
- as quatro anuidades e a mensalidade da plataforma web — sao assinatura, nao
  servico executado na bancada.

Estes tres continuam COM resumo, embora sejam itens comerciais, porque a
decisao foi cadastrar os 52: locacao (367), trade-in (49) e servico expresso
(332). Se incomodarem no documento, o caminho e' desativar pela tela.

Casa por CODIGO, entao rodar de novo e' seguro: reescreve os mesmos campos com
os mesmos valores.

    python -m app.scripts.normalizar_servicos_manutencao              # so simula
    python -m app.scripts.normalizar_servicos_manutencao --aplicar    # grava
"""
import argparse

from app.models import ManutencaoServico
from app.models.database import SessionLocal

# codigo -> (descricao normalizada, resumo padrao)
TABELA: dict[str, tuple[str, str]] = {
    "48": ("Cabo flat - Phoebus",
           "Foi identificada falha na comunicação interna do equipamento, causada por dano no cabo flat. "
           "Realizada a substituição do componente, restabelecendo a comunicação entre as placas."),
    "49": ("Troca de bafômetro - Programa Trade-in",
           "O equipamento foi substituído por outro dentro do Programa Trade-in. O aparelho anterior foi "
           "recolhido e o substituto entregue em condições de uso."),
    "54": ("Recuperação da placa mãe - iBlow 10",
           "Foram identificadas falhas na placa mãe do equipamento. Realizados os reparos dos componentes "
           "afetados, com testes de funcionamento após a intervenção."),
    "66": ("Conserto da caixa de pilha",
           "O compartimento de pilhas apresentava mau contato, comprometendo a alimentação do equipamento. "
           "Realizado o conserto do compartimento, restabelecendo o contato elétrico."),
    "70": ("Troca do botão ON/OFF",
           "O dispositivo apresentou falhas na interação devido a problemas no botão de liga/desliga. "
           "Foi realizada a substituição do mesmo."),
    "130": ("Recuperação da placa mãe - Mercury",
            "Foram identificadas falhas na placa mãe do equipamento. Realizados os reparos dos componentes "
            "afetados, com testes de funcionamento após a intervenção."),
    "142": ("Troca do sensor do fluxo de ar - AL8800",
            "Foi identificada leitura irregular no sistema de amostragem, decorrente de falha no sensor de "
            "fluxo de ar. Realizada a substituição do sensor e verificado o funcionamento."),
    "149": ("Recuperação da placa mãe - Mark X",
            "Foram identificadas falhas na placa mãe do equipamento. Realizados os reparos dos componentes "
            "afetados, com testes de funcionamento após a intervenção."),
    "150": ("Troca da placa mãe - Mercury",
            "Foram identificadas falhas na placa mãe sem possibilidade de reparo. Realizada a substituição "
            "da placa, garantindo o pleno funcionamento do equipamento e a restauração de sua performance original."),
    "151": ("Troca do display",
            "O display apresentou falha de exibição, comprometendo a leitura dos resultados. Realizada a "
            "substituição do componente."),
    "174": ("Troca da célula de combustível",
            "A célula de combustível apresentou perda de sensibilidade, comprometendo a medição. Realizada "
            "a substituição da célula, seguida da calibração do equipamento."),
    "178": ("Manutenção preventiva - Phoebus",
            "Realizada manutenção preventiva do equipamento, com limpeza interna, verificação dos "
            "componentes e testes de funcionamento."),
    "192": ("Mensalidade plataforma web 2024 - Phoebus", ""),
    "209": ("Troca de cabo para acionamento de pulso 12V (relê) - Catraca do Phoebus",
            "O acionamento da catraca apresentou falha por dano no cabo de pulso 12V. Realizada a "
            "substituição do cabo e testado o acionamento."),
    "211": ("Placa mãe - Phoebus",
            "Realizados o fornecimento e a instalação da placa mãe do equipamento, com testes de "
            "funcionamento após a substituição."),
    "212": ("Cooler - Phoebus",
            "O sistema de ventilação apresentou falha, comprometendo a refrigeração interna. Realizada a "
            "substituição do cooler."),
    "213": ("Troca de mecanismo interno - iBlow 10-C",
            "Foi identificada falha no mecanismo interno do equipamento. Realizada a substituição do "
            "conjunto, com testes de funcionamento."),
    "214": ("Troca de solenoide/bomba",
            "O sistema de amostragem apresentou falha no acionamento da bomba. Realizada a substituição do "
            "solenoide/bomba e verificado o fluxo."),
    "215": ("Troca de sensor de fluxo de ar - iBlow 10",
            "Foi identificada leitura irregular no sistema de amostragem, decorrente de falha no sensor de "
            "fluxo de ar. Realizada a substituição do sensor e verificado o funcionamento."),
    "218": ("Calibração com gás rastreado - Módulo EBS-010", ""),
    "222": ("Troca da estrutura/gabinete",
            "A estrutura externa do equipamento apresentava dano que comprometia a proteção dos componentes "
            "internos. Realizada a substituição do gabinete."),
    "224": ("Placa módulo barramento USB + rede",
            "Realizados o fornecimento e a instalação da placa de barramento USB e rede, com testes de "
            "comunicação após a substituição."),
    "225": ("Troca da célula de combustível - AL8800",
            "A célula de combustível apresentou perda de sensibilidade, comprometendo a medição. Realizada "
            "a substituição da célula, seguida da calibração do equipamento."),
    "226": ("Manutenção da placa mãe - Phoebus",
            "Foram identificadas falhas na placa mãe do equipamento. Realizados os ajustes e reparos "
            "necessários, com testes de funcionamento após a intervenção."),
    "227": ("Troca da célula de CO2",
            "A célula de CO2 apresentou perda de sensibilidade, comprometendo a verificação do sopro. "
            "Realizada a substituição da célula."),
    "290": ("Troca da coifa",
            "A coifa apresentava desgaste que comprometia a vedação do sopro. Realizada a substituição do "
            "componente."),
    "292": ("Troca do display - Phoebus",
            "O display apresentou falha de exibição, comprometendo a leitura dos resultados. Realizada a "
            "substituição do componente."),
    "293": ("Recuperação da placa USB - Phoebus",
            "Foi identificada falha na comunicação USB do equipamento. Realizado o reparo da placa, "
            "restabelecendo a conexão."),
    "294": ("Troca de pilha interna",
            "Foi identificado que o equipamento não estava mantendo a data e a hora corretamente. Realizada "
            "a substituição da pilha da placa mãe, restabelecendo o relógio interno."),
    "306": ("Calibração com gás rastreado - Módulo Phoebus 2025 (1)", ""),
    "307": ("Anuidade plataforma web 2025 - Phoebus (tarifa única) (2)", ""),
    "308": ("Troca da placa mãe - iBlow10",
            "Foram identificadas falhas na placa mãe sem possibilidade de reparo. Realizada a substituição "
            "da placa, garantindo o pleno funcionamento do equipamento e a restauração de sua performance original."),
    "309": ("Calibração com gás rastreado - Módulo Phoebus 2025 (2)", ""),
    "310": ("Anuidade plataforma web 2025 - Phoebus (tarifa única) (1)", ""),
    "311": ("Anuidade plataforma web 2025 - Phoebus (tarifa única) (3)", ""),
    "312": ("Calibração com gás rastreado 2025", ""),
    "314": ("Troca da tampa da impressora",
            "A tampa da impressora apresentava dano que impedia o fechamento adequado. Realizada a "
            "substituição da tampa."),
    "315": ("Troca do Bluetooth - Mercury",
            "Na tentativa de pareamento com a impressora, foi identificado problema de conexão no Bluetooth "
            "do equipamento. Realizada a substituição do módulo, garantindo a comunicação e a impressão dos resultados."),
    "316": ("Troca da tampa de pilha",
            "A tampa do compartimento de pilhas apresentava dano, comprometendo a fixação. Realizada a "
            "substituição da tampa."),
    "331": ("Vidro - Phoebus",
            "O vidro do equipamento apresentava dano. Realizada a substituição do componente."),
    "332": ("Serviço expresso",
            "Atendimento realizado em regime expresso, com prioridade na execução dos serviços e devolução "
            "do equipamento em prazo reduzido."),
    "336": ("Anuidade plataforma web (pendência) - Phoebus (tarifa única) (4)", ""),
    "343": ("Manutenção corretiva",
            "Realizada manutenção corretiva no equipamento, com identificação da falha, substituição dos "
            "componentes necessários e testes de funcionamento."),
    "358": ("Manutenção preventiva",
            "Realizada manutenção preventiva do equipamento, com limpeza interna, verificação dos "
            "componentes e testes de funcionamento."),
    "367": ("Locação - Bafômetro Phoebus",
            "Equipamento disponibilizado em regime de locação, entregue em condições de uso e devidamente "
            "calibrado."),
    "368": ("Troca da tampa de proteção (micro - USB) - Mark X",
            "A tampa de proteção do conector micro-USB apresentava dano, expondo o conector. Realizada a "
            "substituição da tampa."),
    "374": ("Tampa de acesso ao módulo - Phoebus",
            "A tampa de acesso ao módulo apresentava dano que comprometia a proteção interna. Realizada a "
            "substituição do componente."),
    "376": ("Módulo placa USB mais rede",
            "Realizados o fornecimento e a instalação do módulo de placa USB e rede, com testes de "
            "comunicação após a substituição."),
    "377": ("Manutenção placa módulo barramento USB + rede",
            "Foi identificada falha na comunicação USB e de rede do equipamento. Realizados os reparos na "
            "placa de barramento, com testes de comunicação."),
    "378": ("Pilha relógio placa mãe",
            "Realizada a substituição da pilha do relógio da placa mãe, restabelecendo a manutenção de data "
            "e hora do equipamento."),
    "379": ("Troca do botão ON/OFF da impressora",
            "O botão de liga/desliga da impressora apresentou falha de acionamento. Realizada a "
            "substituição do componente."),
    "380": ("Bateria de lítio",
            "Realizada a substituição da bateria de lítio do equipamento, restabelecendo a autonomia de "
            "funcionamento."),
}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true", help="grava de fato (sem isso, so simula)")
    args = p.parse_args()

    db = SessionLocal()
    try:
        servicos = db.query(ManutencaoServico).order_by(ManutencaoServico.codigo).all()
        por_codigo = {s.codigo: s for s in servicos if s.codigo}

        sem_tabela = [s for s in servicos if s.codigo not in TABELA]
        sem_servico = [c for c in TABELA if c not in por_codigo]

        alterados, com_resumo, sem_resumo = [], 0, 0
        for codigo, (descricao, resumo) in TABELA.items():
            s = por_codigo.get(codigo)
            if s is None:
                continue
            if s.descricao != descricao or s.resumo_padrao != resumo:
                alterados.append((codigo, s.descricao, descricao, bool(resumo)))
            if resumo:
                com_resumo += 1
            else:
                sem_resumo += 1

        print(f"servicos no catalogo:      {len(servicos)}")
        print(f"cobertos pela tabela:      {len(TABELA) - len(sem_servico)}")
        print(f"a alterar:                 {len(alterados)}")
        print(f"receberao resumo:          {com_resumo}")
        print(f"ficarao SEM resumo:        {sem_resumo}  (calibracoes, anuidades e mensalidade)")
        if sem_tabela:
            print(f"AVISO - no catalogo mas fora da tabela: {[s.codigo for s in sem_tabela]}")
        if sem_servico:
            print(f"AVISO - na tabela mas fora do catalogo: {sem_servico}")
        print()
        for codigo, antes, depois, tem_resumo in alterados:
            marca = "resumo" if tem_resumo else "SEM resumo"
            print(f"   {codigo:>4}  {antes}")
            print(f"         -> {depois}   [{marca}]")

        if not args.aplicar:
            print("\n(simulacao — rode com --aplicar para gravar)")
            return

        for codigo, (descricao, resumo) in TABELA.items():
            s = por_codigo.get(codigo)
            if s is None:
                continue
            s.descricao = descricao
            s.resumo_padrao = resumo
        db.commit()
        print(f"\ngravados: {len(alterados)} alterados")
    finally:
        db.close()


if __name__ == "__main__":
    main()
