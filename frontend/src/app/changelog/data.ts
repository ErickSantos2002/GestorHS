// Changelog do GestorHS — editado pela equipe a cada release.
// Mantenha a lista em ordem decrescente (versão mais nova primeiro).
// A versão atual exibida na sidebar é sempre a primeira entrada.

export type TipoMudanca = 'novidade' | 'melhoria' | 'correcao'

export interface MudancaItem {
  tipo: TipoMudanca
  texto: string
}

export interface VersaoChangelog {
  versao: string
  data: string // DD/MM/AAAA
  itens: MudancaItem[]
}

export const TIPO_MUDANCA: Record<TipoMudanca, { label: string; tone: 'warning' | 'primary' | 'info' }> = {
  correcao: { label: 'Corrigido', tone: 'warning' },
  melhoria: { label: 'Melhoria', tone: 'primary' },
  novidade: { label: 'Novidade', tone: 'info' },
}

export const CHANGELOG: VersaoChangelog[] = [
  {
    versao: '1.51.0',
    data: '04/09/2026',
    itens: [
      { tipo: 'novidade', texto: 'Uma caixa pode ter mais de uma nota fiscal — o botão "+ Adicionar nota" anexa quantas forem necessárias de uma vez (por exemplo, a nota do serviço e a de remessa). A tela da caixa lista todas, com download de PDF e XML de cada uma.' },
      { tipo: 'melhoria', texto: 'A nota errada pode ser removida e reanexada, no Financeiro e também em Preparando Retorno. A tela da OS passa a mostrar as notas da própria caixa; o card do TaskHS é atualizado sozinho.' },
    ],
  },
  {
    versao: '1.50.0',
    data: '03/09/2026',
    itens: [
      { tipo: 'correcao', texto: 'Concluir o laboratório de uma OS de Manutenção não mexe mais na calibração do aparelho. Antes a conclusão gravava a data do serviço como "última calibração" do aparelho e empurrava a próxima calibração junto — o aparelho aparecia calibrado num dia em que só foi feita manutenção, e quem entrava em garantia era a calibração, não a manutenção. OS de Calibração e de Ambas seguem espelhando normalmente.' },
      { tipo: 'melhoria', texto: 'Mark-X e Mercury tinham dois cadastros cada um no catálogo, separados só pela impressora ("Bafômetro Mark X - Plus" e "Bafômetro Mark X - Plus - COM IMPRESSORA"; "Bafômetro Mercury" e "Mercury com impressora sem fio - Bluetooth"). Viraram um cadastro só cada, com o nome que o certificado já usa: Mark-X e Mercury. Os aparelhos da frota foram todos reapontados, nada se perdeu, e o relatório de manutenção passa a imprimir o mesmo nome do certificado — antes saía a descrição comprida.' },
      { tipo: 'correcao', texto: 'A garantia de manutenção passa a valer assim que o laboratório conclui a OS, do mesmo jeito que a de calibração — antes ela só aparecia depois de a OS ser finalizada, o que na prática deixava a garantia invisível. A data usada é a do relatório de manutenção (a data real do serviço), e OS liberadas, sem conserto ou canceladas não geram garantia, porque nelas não houve serviço.' },
    ],
  },
  {
    versao: '1.49.3',
    data: '03/09/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Telefone e contato seguiram o mesmo caminho do e-mail: não vêm mais preenchidos do cadastro do cliente e passaram a ser obrigatórios, marcados com *. Os três são digitados a cada proposta, para serem conferidos com o cliente na hora — antes o telefone vinha do cadastro e o "aos cuidados de" era copiado do contato cadastrado, e a proposta saía com dado antigo sem ninguém perceber. Tentar salvar sem algum deles avisa quais faltam e destaca os campos em vermelho.' },
    ],
  },
  {
    versao: '1.49.2',
    data: '03/09/2026',
    itens: [
      { tipo: 'correcao', texto: 'Nos Logs de Integração, a coluna "OS" virou "Referência" e o número agora leva ao lugar certo: como o card é da caixa, clicar em "CX 916" abre a caixa 916 — antes abria a OS 916, que é outro registro. As linhas que de fato apontam para uma ordem aparecem como "OS #123" e continuam abrindo a OS.' },
    ],
  },
  {
    versao: '1.49.1',
    data: '02/09/2026',
    itens: [
      { tipo: 'correcao', texto: 'O TaskHS voltou a receber um card por caixa, e só. Corrigir o tipo de serviço no laboratório — e, por um caminho antigo, anexar a nota fiscal — ainda criava um card avulso daquela OS, então a mesma caixa aparecia duas vezes no board da expedição. Agora essas duas ações atualizam o card da própria caixa. Os cards avulsos que já foram parar no board precisam ser arquivados à mão, uma vez.' },
    ],
  },
  {
    versao: '1.49.0',
    data: '02/09/2026',
    itens: [
      { tipo: 'novidade', texto: 'Na proposta, os dados do cliente ficam sempre à vista: ao escolher a empresa, razão social, CNPJ, endereço, município, UF, CEP e telefone já aparecem preenchidos com o cadastro, prontos para ajustar — e o "Aos cuidados de" passou a ficar junto com eles. Antes era preciso clicar no lápis para abrir esse painel, e quem passava direto acabava salvando a proposta sem os ajustes.' },
      { tipo: 'melhoria', texto: 'Saiu o botão "Aplicar" do painel: o que você digita já vale para a proposta, sem passo intermediário. Os campos em cinza e itálico continuam vindo do cadastro do cliente, apagar um campo devolve o valor do cadastro, e "Restaurar do cadastro" desfaz todas as edições de uma vez. Como antes, nada disso altera o cadastro do cliente — vale só naquela proposta.' },
      { tipo: 'melhoria', texto: 'O e-mail não vem mais preenchido do cadastro: é digitado a cada proposta, para ser conferido com o cliente na hora. Junto com ele, razão social, CNPJ, endereço, município, UF e CEP passaram a ser obrigatórios e aparecem marcados com *. Tentar salvar sem algum deles avisa quais faltam e destaca os campos em vermelho, em vez de deixar a proposta sair com dado em branco. Telefone e contato continuam opcionais.' },
    ],
  },
  {
    versao: '1.48.0',
    data: '31/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'Agora dá para entrar no GestorHS com a conta Microsoft da empresa, pelo botão "Entrar com Microsoft" na tela de login — sem precisar de uma senha separada. Quem já tem cadastro no GestorHS entra direto; quem ainda não tem continua precisando ser cadastrado na tela de Usuários antes. O login por e-mail e senha continua funcionando normalmente, do jeito que sempre foi.' },
    ],
  },
  {
    versao: '1.47.0',
    data: '28/08/2026',
    itens: [
      { tipo: 'melhoria', texto: 'O cartão do TaskHS agora traz os dois arquivos da nota fiscal na etapa de Financeiro: "NF em PDF" e "NF em XML", cada um com seu link de download direto, sem precisar entrar no GestorHS. Antes só o PDF virava link. Os cartões que já estão no board ganham o link do XML na próxima atualização da caixa.' },
    ],
  },
  {
    versao: '1.46.0',
    data: '27/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'A caixa que veio de uma proposta ganha do CRM agora mostra essa proposta na própria tela, ao lado do resumo: número, data, cliente, CNPJ e valor. Dali mesmo dá para visualizar o PDF, baixar e — para o Financeiro e o Administrador — marcar como faturada, sem abrir a tela de Propostas.' },
      { tipo: 'melhoria', texto: 'Excluir proposta virou Desabilitar. A proposta sai da lista mas continua inteira no sistema, com itens, histórico de versões e o vínculo com a caixa, e só um Administrador pode reativá-la. Enquanto estiver desabilitada não aceita edição, duplicação nem faturamento, e o link público do PDF para de funcionar.' },
      { tipo: 'novidade', texto: 'Na lista de propostas há um filtro "Mostrar desabilitadas". As propostas desabilitadas aparecem marcadas e, para o Administrador, com o botão de reativar — inclusive as seis que já haviam sido excluídas antes desta versão, que continuam recuperáveis.' },
    ],
  },
  {
    versao: '1.45.0',
    data: '24/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'Os 52 serviços do catálogo comercial foram levados para Certificados › Serviços de manutenção, com o código de cada um. No modal de registro dá para buscar pelo código — é assim que o serviço chega ao técnico — e o código aparece ao lado do nome.' },
      { tipo: 'melhoria', texto: 'O resumo do relatório passou a ser um texto padrão: o aparelho e a frase de conformidade aparecem uma vez só e os serviços são listados em seguida. Antes emendava uma frase por serviço e ficava longo com três ou mais. O texto continua editável antes de gerar.' },
      { tipo: 'melhoria', texto: 'A data da manutenção já vem preenchida com o dia de hoje, e no relatório os rótulos “Tipo do Problema” e “Resumo do Serviço” saem em negrito.' },
      { tipo: 'correcao', texto: 'Concluir o laboratório passa a exigir o certificado do tipo de serviço da OS: Calibração pede o certificado de calibração, Manutenção pede o relatório de manutenção, e Ambas só conclui com os dois. Antes bastava um documento qualquer.' },
    ],
  },
  {
    versao: '1.44.1',
    data: '24/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'Ao abrir uma OS, a caixa passa a ser criada junto, já com a OS dentro e com o próximo número. Só é preciso buscar uma caixa quando a OS vai entrar numa que já existe — nesse caso, marque a opção no topo do formulário.' },
      { tipo: 'correcao', texto: 'Saiu o botão “Remover” da OS dentro da caixa. Uma OS sem caixa não anda, porque quem avança de fase é a caixa: quatro OS estavam paradas assim, a mais antiga havia um mês. Para tirar a OS de uma caixa, use “Mover” para outra.' },
      { tipo: 'correcao', texto: 'Não é mais possível criar caixa pelo formulário de abrir OS. Criar a caixa antes e desistir do cadastro deixava caixa vazia no sistema.' },
      { tipo: 'melhoria', texto: 'O modelo do relatório de manutenção é único para todos os aparelhos, então a opção de cadastrar um modelo de manutenção por aparelho foi removida — ela faria aquele aparelho parar de acompanhar as revisões do formulário sem ninguém perceber.' },
    ],
  },
  {
    versao: '1.44.0',
    data: '21/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'O Relatório de Manutenção agora sai do sistema. O Laboratório registra o que foi feito na bancada — número, data e os serviços executados — e gera o relatório em PDF, com o mesmo formulário padrão FORM-LAB-010 que era preenchido à mão.' },
      { tipo: 'novidade', texto: 'Os serviços saem de uma lista cadastrada em Certificados › Serviços de manutenção, e cada um traz um resumo padrão. Ao escolher os serviços, o resumo do relatório já vem escrito — o técnico só ajusta o que for específico daquele aparelho.' },
      { tipo: 'melhoria', texto: 'Na tela da OS, a seção "Certificados" virou duas: "Certificado de calibração" e "Certificado de manutenção". Aparece só a que o tipo de serviço da OS pedir, e uma OS de manutenção pura deixa de pedir certificado de calibração.' },
    ],
  },
  {
    versao: '1.43.0',
    data: '21/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'Ao selecionar o aparelho para abrir uma OS na caixa, cada resultado da busca agora mostra uma etiqueta de calibração: "Em dia", "Vencendo", "Vencido" ou "Sem data", junto com a data da próxima calibração — assim dá para conferir a situação do aparelho antes de abrir a OS.' },
    ],
  },
  {
    versao: '1.42.0',
    data: '21/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'O Laboratório agora corrige o tipo de serviço da OS enquanto ela está na fase dele — quando o técnico abre o aparelho e vê que, além da calibração, também precisa de manutenção. Antes só o Administrador conseguia alterar.' },
      { tipo: 'melhoria', texto: 'A troca fica registrada no histórico da OS com o de-para (por exemplo, “Calibração → Manutenção”), já que quem informa o tipo na entrada é a Expedição e quem corrige é o Laboratório.' },
    ],
  },
  {
    versao: '1.41.0',
    data: '20/08/2026',
    itens: [
      { tipo: 'correcao', texto: 'Aparelho recém-calibrado continuava aparecendo como “Vencido”. A data da próxima calibração nunca era preenchida ao concluir o laboratório, e o aparelho ficava com a data do ciclo anterior. Agora ela é calculada sozinha: um ano após a calibração.' },
      { tipo: 'correcao', texto: 'Foram corrigidos 232 aparelhos e 157 OS que já estavam com a data antiga — 123 aparelhos ativos deixaram de constar como vencidos no painel, nos alertas e nas cargas de cobrança.' },
      { tipo: 'melhoria', texto: 'A tela da OS passa a mostrar a próxima calibração junto com a data da calibração, em vez de ficar em branco enquanto o aparelho exibia outra data.' },
    ],
  },
  {
    versao: '1.40.0',
    data: '20/08/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Ao anexar a nota fiscal da caixa, agora existem dois campos separados — PDF e XML — e os dois são obrigatórios, já que sempre vêm juntos. Cada campo só aceita o seu tipo, então não dá mais para mandar o PDF duas vezes e o XML acabar não sendo enviado.' },
      { tipo: 'novidade', texto: 'A tela da OS passa a ter os botões “Baixar PDF” e “Baixar XML” da nota fiscal. O botão do XML só aparece quando existe — notas antigas foram anexadas quando havia um arquivo só.' },
      { tipo: 'novidade', texto: 'O Administrador pode avançar uma caixa do Financeiro sem anexar a nota fiscal, para as caixas do modelo antigo que não têm nota. O sistema pede confirmação e registra no histórico das OS que passou sem nota. As demais funções continuam obrigadas a anexar.' },
    ],
  },
  {
    versao: '1.39.1',
    data: '20/08/2026',
    itens: [
      { tipo: 'correcao', texto: 'A aba Equipamentos do cliente mostrava só os 25 primeiros aparelhos e não avisava que havia mais — em clientes grandes o aparelho procurado simplesmente não aparecia, como se não estivesse cadastrado. Agora a lista tem paginação e informa o total. Eram 48 clientes afetados.' },
    ],
  },
  {
    versao: '1.39.0',
    data: '19/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'As listas de Clientes, Equipamentos e Ordens ganharam o botão “Exportar Excel”. A planilha sai com todas as linhas que batem com os filtros da tela — não só as 25 que aparecem — e com mais colunas do que a lista mostra: no aparelho, por exemplo, vêm CNPJ do cliente, marca, patrimônio, data da compra e número do certificado.' },
      { tipo: 'novidade', texto: 'Nova aba “Emitidos” em Certificados: escolhe o período e baixa a relação de todos os certificados já gerados, tanto os que saíram de uma OS quanto os de venda, no mesmo arquivo.' },
      { tipo: 'melhoria', texto: 'As planilhas já vêm prontas para trabalhar: cabeçalho fixo ao rolar, filtro em cada coluna, datas e valores como data e número de verdade (dá para ordenar e somar) e, no rodapé, o registro de quais filtros geraram o arquivo.' },
    ],
  },
  {
    versao: '1.38.0',
    data: '13/08/2026',
    itens: [
      { tipo: 'correcao', texto: 'Em Propostas, fechar “Editar dados nesta proposta” sem clicar em Aplicar descartava em silêncio tudo o que tinha sido digitado — dava para trocar o CNPJ, salvar a proposta e o valor antigo continuar lá. Agora o sistema avisa antes de descartar.' },
      { tipo: 'correcao', texto: 'Ao reabrir uma proposta que já tinha dados editados, os campos não alterados apareciam em branco mesmo o cliente tendo o dado no cadastro. Agora vêm preenchidos, em cinza e itálico, indicando que valem do cadastro; alterar um deles passa a valer só naquela proposta.' },
      { tipo: 'melhoria', texto: 'A busca de CNPJ e CEP na proposta diferencia “muitas consultas seguidas” de “serviço fora do ar”: quando é só limite de consultas, o sistema tenta de novo sozinho e avisa que basta esperar alguns segundos.' },
    ],
  },
  {
    versao: '1.37.1',
    data: '04/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'A lista de Ordens ganhou filtro por data de chegada, com períodos prontos (hoje, últimos 7 e 30 dias, este mês, mês passado) e faixa personalizada de uma data até outra.' },
      { tipo: 'melhoria', texto: 'Ao baixar um certificado, o sistema pergunta em qual pasta salvar em vez de mandar direto para Downloads, e abre o PDF numa aba logo depois para imprimir ou anexar. Vale para o certificado da OS, o de venda e o em branco.' },
    ],
  },
  {
    versao: '1.37.0',
    data: '03/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'Certificado de calibração no formato EPS-LAB-002: cinco medições, erro por medição e incerteza expandida (k = 2, 95% de confiança).' },
      { tipo: 'novidade', texto: 'Nova aba Configurações em Certificados: parâmetros do cálculo, técnico responsável e cadastro dos cilindros de gás com vigência.' },
      { tipo: 'novidade', texto: 'O certificado em branco e o de venda também passam a ter as cinco medições e o cálculo de incerteza, iguais aos da OS.' },
      { tipo: 'melhoria', texto: 'Os modais de certificado destacam medição fora da faixa, mostram o cálculo e informam qual cilindro de gás será registrado antes de gerar.' },
      { tipo: 'melhoria', texto: 'A OS grava qual cilindro foi usado, para que regerar um certificado antigo mantenha a rastreabilidade correta.' },
      { tipo: 'novidade', texto: 'O certificado de calibração passa a trazer QR codes dos certificados do gás, do termohigrômetro e do barômetro — não é mais preciso enviá-los impressos junto. Os documentos são escolhidos em Certificados › Configurações.' },
      { tipo: 'melhoria', texto: 'O Laboratório passa a editar a aba Configurações: parâmetros do cálculo, técnico, documentos anexos e o cadastro de cilindros. Excluir cilindro continua só com o Administrador — para aposentar um cilindro, use "Encerrar vigência".' },
    ],
  },
  {
    versao: '1.36.0',
    data: '31/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'A página da OS ganhou uma seção "Observações", entre Recebimento e Fotos, com um campo de texto que qualquer pessoa da equipe pode preencher — em qualquer fase da OS. A anotação fica na OS, não na fase, e o histórico registra quem alterou.' },
      { tipo: 'melhoria', texto: 'As observações antes só apareciam quando já havia texto e só o Administrador conseguia alterá-las, pelo modal de editar OS. Agora o campo está sempre visível na própria página.' },
    ],
  },
  {
    versao: '1.35.0',
    data: '31/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'O time de Pós-Vendas agora pode corrigir os dados de um cliente (endereço, contato e o resto do cadastro) e editar um aparelho, inclusive marcá-lo como ativo ou inativo. Criar cliente ou aparelho novo e transferir aparelho entre clientes continuam com Administração, Laboratório e Expedição.' },
      { tipo: 'melhoria', texto: 'O controle de ativo do aparelho virou um interruptor, com o estado escrito ao lado — "Ativo" ou "Inativo" — no lugar da antiga caixinha de marcar.' },
    ],
  },
  {
    versao: '1.34.0',
    data: '30/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'A lista de aparelhos agora mostra quais estão inativos: a linha aparece esmaecida e com o selo "Inativo" ao lado do nome. Vale na página de Equipamentos e na aba Equipamentos dentro do cliente.' },
      { tipo: 'novidade', texto: 'Novo filtro "Aparelhos" na página de Equipamentos, para ver só os ativos, só os inativos ou todos. Ele começa em "Todos", então a lista abre como sempre abriu.' },
      { tipo: 'melhoria', texto: 'Aparelho inativo com calibração vencida não aparece mais em vermelho na lista — ele saiu de uso, então não é trabalho pendente. O texto continua lá para consulta.' },
    ],
  },
  {
    versao: '1.33.1',
    data: '30/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'A tela do aparelho tinha dois jeitos de dizer se ele está ativo — o campo "Situação" e a caixinha "Ativo" — e só a caixinha valia de verdade. O campo "Situação" foi removido: continua sendo a caixinha "Ativo" que controla se o aparelho aparece no portal do cliente, no painel, nos alertas e nas cargas de cobrança.' },
    ],
  },
  {
    versao: '1.33.0',
    data: '30/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Nova paginação nas listas: os registros agora aparecem em páginas com números clicáveis, dentro da própria tabela e com a contagem "Mostrando X a Y de Z".' },
      { tipo: 'novidade', texto: 'As telas de Serviços, Produtos, Logs de Integração e Modelos de certificado passam a paginar de 15 em 15.' },
      { tipo: 'melhoria', texto: 'Duplicar uma proposta agora abre a janela já preenchida (com você como responsável e a data de hoje) para conferir e confirmar — nada é criado até clicar em "Criar Proposta", e cancelar não deixa proposta duplicada.' },
      { tipo: 'melhoria', texto: 'As colunas de Ações (Usuários, Cadastros, Cobrança, Propostas) trocaram os textos por ícones coloridos — lápis para editar, lixeira para excluir, olho para visualizar, entre outros.' },
      { tipo: 'melhoria', texto: 'As páginas passam a ocupar toda a largura da tela e a barra de busca ficou padronizada: campo em largura total com o botão Buscar ao lado.' },
      { tipo: 'melhoria', texto: 'Dashboard com cartões maiores e as fases das OS numa única linha; a janela "O que há de novo" ficou mais larga.' },
      { tipo: 'melhoria', texto: 'Os botões de criar ficaram mais claros: em vez de só "Novo", mostram o que será criado — "Novo setor", "Nova marca", "Novo serviço", "Novo produto" e assim por diante.' },
      { tipo: 'melhoria', texto: 'Caixa que contém módulo ou Phoebus não gera mais card no TaskHS nem no GrowthHS — esses equipamentos seguem um fluxo próprio, fora dos boards. Vale para os próximos envios; os cards que já estavam nos boards continuam onde estão.' },
    ],
  },
  {
    versao: '1.32.0',
    data: '29/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Os dados do cliente na proposta agora têm campo CEP, e ele passa a sair no endereço do PDF.' },
      { tipo: 'novidade', texto: 'Duas lupas no painel "Editar dados nesta proposta": a do CNPJ busca razão social e endereço completo na base pública da Receita; a do CEP preenche endereço, município e estado. Um botão Desfazer volta atrás se a busca atropelar algo.' },
      { tipo: 'melhoria', texto: 'Ao editar os dados do cliente numa proposta, só os campos realmente diferentes do cadastro são guardados — o selo "Dados editados" agora aparece apenas quando algo de fato diverge.' },
    ],
  },
  {
    versao: '1.31.0',
    data: '29/07/2026',
    itens: [
      { tipo: 'correcao', texto: 'Não é mais possível criar uma proposta em branco: apertar Enter em um campo de texto não envia mais o formulário, e agora é obrigatório ter cliente, CNPJ/CPF e o bloco "Outros Itens ou Serviços" preenchidos para salvar.' },
      { tipo: 'melhoria', texto: 'A tela de Propostas mostra um selo "Dados editados" nas propostas em que os dados do cliente foram alterados só naquela proposta. Clicando no selo, você vê campo a campo o que está no cadastro e o que está sendo usado na proposta.' },
      { tipo: 'melhoria', texto: 'Clicar fora da janela de proposta não fecha mais o formulário — só o X e o botão Cancelar fecham, para não perder o que já foi digitado.' },
    ],
  },
  {
    versao: '1.30.0',
    data: '29/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Ao dar ganho no GrowthHS, o número da proposta é guardado na caixa e vira um link para baixar o PDF da proposta direto no card do TaskHS (na etapa de Pós-Vendas), do mesmo jeito que já acontece com os certificados.' },
    ],
  },
  {
    versao: '1.29.0',
    data: '28/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'O Financeiro agora pode marcar uma proposta como Faturada direto na lista de Propostas. A proposta faturada ganha um selo; desfazer o faturamento é exclusivo do Administrador.' },
    ],
  },
  {
    versao: '1.28.0',
    data: '28/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Integração com o GrowthHS: quando o pós-vendas dá ganho no negócio pelo GrowthHS, a caixa é movida automaticamente de Pós-Vendas para Financeiro no GestorHS, com a observação do negócio registrada no histórico.' },
    ],
  },
  {
    versao: '1.27.8',
    data: '28/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'A proposta agora tem um campo de Introdução (logo abaixo dos dados do cliente) para o pós-vendas escrever observações — por exemplo, confirmar o endereço de entrega. O texto sai na seção "Introdução" do PDF.' },
    ],
  },
  {
    versao: '1.27.7',
    data: '28/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'A visualização da proposta agora abre em uma janela dentro do sistema (com o PDF na tela), no lugar de abrir uma aba separada do navegador.' },
    ],
  },
  {
    versao: '1.27.6',
    data: '28/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'As ações da lista de Propostas agora são ícones, no mesmo padrão das outras telas, e há uma ação para visualizar a proposta em PDF numa nova aba sem precisar baixar.' },
    ],
  },
  {
    versao: '1.27.5',
    data: '28/07/2026',
    itens: [
      { tipo: 'correcao', texto: 'A busca de clientes e de propostas agora encontra pelo CNPJ/CPF mesmo colado formatado (ex.: 01.899.414/0001-67). A busca de proposta também passou a procurar pelo documento do cliente, não só pelo nome e número.' },
    ],
  },
  {
    versao: '1.27.4',
    data: '28/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'A função Financeiro agora tem acesso completo a Propostas, Serviços e Produtos (ver, criar e editar), igual ao Comercial.' },
    ],
  },
  {
    versao: '1.27.3',
    data: '28/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'CNPJ e CPF agora aparecem formatados (36.312.056/0005-52) em todas as telas, e os campos de digitar aplicam a máscara automaticamente — inclusive quando você cola o número já formatado de outro lugar.' },
    ],
  },
  {
    versao: '1.27.2',
    data: '28/07/2026',
    itens: [
      { tipo: 'correcao', texto: 'As caixas com um único aparelho não mostram mais "+1 outro" cliente. O cliente do aparelho passa a ser definido automaticamente como principal da caixa na abertura; a escolha manual do principal continua só para caixas com aparelhos de clientes diferentes.' },
    ],
  },
  {
    versao: '1.27.1',
    data: '28/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'O Administrador agora pode editar os dados de recebimento de uma OS (tipo de serviço, condição de chegada, acessórios, pilhas, bocais, observações e data de chegada) — útil para corrigir, por exemplo, uma OS aberta como Manutenção que era Calibração.' },
    ],
  },
  {
    versao: '1.27.0',
    data: '27/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Os avisos de calibração vencendo enviados ao GrowthHS agora chegam agrupados: um card por cliente com todos os aparelhos que vencem naquele mês, no lugar de um card separado por aparelho. A verificação passou a ser mensal (todo dia 1) e cobre o mês corrente e o seguinte, então o comercial enxerga sempre dois meses à frente e cobra tudo de uma vez.' },
    ],
  },
  {
    versao: '1.26.0',
    data: '24/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Uma caixa agora pode ter aparelhos de mais de um cliente do mesmo grupo. Ao encaminhar do Recebido para o Laboratório, a expedição escolhe o cliente principal (quando há mais de um), que passa a ser usado nas propostas, cards e nota fiscal.' },
    ],
  },
  {
    versao: '1.25.4',
    data: '24/07/2026',
    itens: [
      { tipo: 'correcao', texto: 'O PDF da Proposta Técnica agora sai com a fonte maior, legível sem precisar dar zoom.' },
    ],
  },
  {
    versao: '1.25.3',
    data: '24/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Na proposta, os aparelhos do cliente agora têm busca (lupa) e a lista rola quando há muitos; cada aparelho mostra a data da próxima calibração e quanto falta para vencer.' },
    ],
  },
  {
    versao: '1.25.2',
    data: '24/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Na proposta, a descrição do item já busca no catálogo enquanto você digita — sem campo separado — e a lista de resultados ficou maior e não corta mais.' },
    ],
  },
  {
    versao: '1.25.1',
    data: '24/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Botão "Liberar do Laboratório": libera um aparelho travado no laboratório quando ainda não há modelo de certificado (ex.: manutenção), sem gerar o certificado, para a caixa poder avançar — com registro no histórico.' },
      { tipo: 'melhoria', texto: 'Janela de criação de proposta mais larga, com mais espaço para a tabela de itens e a lista de aparelhos.' },
    ],
  },
  {
    versao: '1.25.0',
    data: '24/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Nova página de Propostas Técnicas: monte a proposta escolhendo o cliente, os aparelhos da frota (com farol de vencimento) e os itens do catálogo, e gere o PDF.' },
      { tipo: 'novidade', texto: 'Novos cadastros de Serviços (com SKU) e Produtos para compor as propostas.' },
      { tipo: 'melhoria', texto: 'Histórico de alterações da proposta: veja quem mudou o quê e quando, com o PDF de cada versão.' },
    ],
  },
  {
    versao: '1.24.1',
    data: '23/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Gerar o certificado de calibração ou manutenção agora conclui o laboratório do aparelho automaticamente e já libera o avanço da caixa — não é mais preciso um passo separado para marcar o aparelho como concluído.' },
    ],
  },
  {
    versao: '1.24.0',
    data: '23/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'A Caixa agora é a unidade que anda pelas fases: ela só avança de uma fase para a próxima quando todos os aparelhos dela concluem o laboratório — a OS individual não anda mais sozinha.' },
      { tipo: 'melhoria', texto: 'Um aparelho sem conserto pode ser marcado como tal para não travar o avanço do resto do lote no laboratório.' },
      { tipo: 'melhoria', texto: 'TaskHS e GrowthHS agora recebem 1 card por caixa (1 contato, 1 nota fiscal, 1 proposta) em vez de 1 por OS.' },
    ],
  },
  {
    versao: '1.23.0',
    data: '22/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'A Expedição agora também cadastra e edita clientes e aparelhos — útil na hora de dar entrada de módulos novos no estoque. Excluir continua restrito ao Administrador.' },
    ],
  },
  {
    versao: '1.22.0',
    data: '21/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Nova página "Logs de Integração" (só Administrador): mostra tudo que o sistema envia para o GrowthHS e o TaskHS — o que subiu com sucesso, o que deu erro e o que foi pulado (inclusive quando a integração está desligada). Dá para filtrar por integração, status e OS, e reenviar um card que falhou direto pela linha. No topo, um aviso mostra se cada integração está ativa ou desligada.' },
    ],
  },
  {
    versao: '1.21.0',
    data: '20/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Agora dá para emitir o certificado de venda de um aparelho sem precisar abrir uma OS. Na ficha do aparelho, o botão "Gerar certificado de venda" já vem com os dados do cliente e do equipamento preenchidos — basta informar os resultados da calibração e a próxima data. O certificado fica registrado na ficha e o cliente consegue baixá-lo pelo portal.' },
    ],
  },
  {
    versao: '1.20.0',
    data: '20/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Quando o laboratório conclui uma OS, o sistema agora cria automaticamente um card no funil de Serviços do GrowthHS, com os dados do cliente, o aparelho e o resultado da calibração — para o comercial dar seguimento sem ninguém precisar avisar. Se a integração estiver fora do ar, a OS avança normalmente.' },
    ],
  },
  {
    versao: '1.19.0',
    data: '18/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'A ficha de um aparelho agora mostra o elo entre o Phoebus e o módulo de calibração: abrindo um Phoebus você vê qual módulo está instalado nele, e abrindo um módulo vê em qual aparelho (e cliente) ele está — ou que está no estoque. A informação vem de uma carga feita a partir da lista de dispositivos e mostra de quando é aquele retrato.' },
    ],
  },
  {
    versao: '1.18.0',
    data: '17/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Integração com o TaskHS atualizada: os cards de OS agora são posicionados na lista exata (por id) e as informações de cada etapa vão em campos de observação separados (Recebido, Laboratório, Pós-Vendas, Financeiro, Preparando Retorno e Finalizada), em vez de tudo na descrição — que passa a ser livre para anotações da equipe direto no TaskHS.' },
    ],
  },
  {
    versao: '1.17.0',
    data: '16/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Na tela de uma Caixa, agora dá para fechar as OS direto por ali: marque as OS que estão em "Preparando Retorno" e clique em "Fechar OS selecionadas" para finalizá-las juntas com o mesmo código de retorno (ou marque só uma). Útil quando a caixa toda volta com o mesmo rastreio; as que ficam para manutenção é só não marcar.' },
      { tipo: 'melhoria', texto: 'Removido o botão "Vincular OS existente" de dentro da caixa — a caixa já é escolhida na abertura da OS.' },
    ],
  },
  {
    versao: '1.16.0',
    data: '15/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Nova aba "Gerais" na página Certificados: anexe um PDF (ex.: certificado de gás anual), dê um nome e gere um link público e um QR code para o cliente baixar sem precisar de login — economizando papel. Só PDF, até 10 MB.' },
    ],
  },
  {
    versao: '1.15.1',
    data: '15/07/2026',
    itens: [
      { tipo: 'correcao', texto: 'A média dos 3 testes no certificado agora acompanha a precisão dos testes: usa até 3 casas decimais e não mostra zeros à direita (ex.: 0,186 / 0,183 / 0,183 → 0,184; 0,18 / 0,18 / 0,18 → 0,18). Antes a média era sempre cortada em 2 casas (0,18).' },
    ],
  },
  {
    versao: '1.15.0',
    data: '15/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'A página de um cliente agora tem abas Dados e Equipamentos. Em "Equipamentos" você vê a lista de aparelhos daquele cliente e abre o detalhe de cada um sem sair da página, facilitando ir e voltar entre os dados do cliente e os equipamentos dele.' },
    ],
  },
  {
    versao: '1.14.1',
    data: '14/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'No certificado em branco, os campos Modelo, Marca e Patrimônio saíram do formulário: eles não tinham efeito nenhum no PDF. A marca e o modelo já vêm do aparelho do modelo de certificado escolhido — não precisam ser digitados.' },
    ],
  },
  {
    versao: '1.14.0',
    data: '14/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'O laboratório agora pode emitir um certificado em branco, sem OS: na página Certificados, aba "Em branco", escolha um modelo já cadastrado, preencha os dados e gere o PDF. Serve para aparelhos de POC, de empresas que não estão cadastradas no sistema. O certificado fica registrado (com quem emitiu e quando) e pode ser baixado a qualquer momento, sem ficar vinculado a nenhuma empresa ou aparelho.' },
    ],
  },
  {
    versao: '1.13.1',
    data: '14/07/2026',
    itens: [
      { tipo: 'correcao', texto: 'Corrigida a geração de certificado em aparelhos sem modelo cadastrado: antes o sistema respondia como se tivesse gerado, mas nada acontecia e nenhum aviso aparecia. Agora a OS avisa na hora ("Este aparelho não tem modelo de certificado cadastrado"), com link direto para cadastrar o modelo, e a tentativa de gerar é recusada com a mensagem dizendo exatamente qual modelo falta.' },
    ],
  },
  {
    versao: '1.13.0',
    data: '14/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'O Financeiro agora precisa anexar a nota fiscal de serviço (PDF ou XML) e informar o número da NF antes de confirmar o pagamento e liberar a OS para envio. A nota fica disponível para download na própria OS e no cartão do TaskHS.' },
    ],
  },
  {
    versao: '1.12.1',
    data: '14/07/2026',
    itens: [
      { tipo: 'correcao', texto: 'Corrigida a etapa Financeiro na tela da OS: o botão "Confirmar pagamento" não aparecia (impedindo avançar a OS) e a barra de progresso não mostrava a etapa. Também voltou a ser possível gerar/regerar o certificado com a OS em Financeiro.' },
    ],
  },
  {
    versao: '1.12.0',
    data: '13/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'O login agora é feito com o e-mail, no lugar do nome de usuário. Ao cadastrar um usuário, o e-mail passou a ser obrigatório (e único) — ele é a credencial de acesso.' },
      { tipo: 'correcao', texto: 'Corrigido o erro ao remover um usuário. Como o usuário fica ligado ao histórico das Ordens de Serviço (quem fez cada etapa), agora em vez de excluir ele é "Desativado": perde o acesso ao sistema, mas o histórico é preservado. Desativados ficam ocultos na lista (use "Mostrar desativados") e podem ser reativados.' },
    ],
  },
  {
    versao: '1.11.0',
    data: '26/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'As Ordens de Serviço agora passam por uma etapa "Financeiro" entre Pós-Vendas e Preparando Retorno. O setor financeiro confirma o pagamento (botão "Confirmar pagamento") antes de a OS ser liberada para envio; a OS fica marcada como paga com a data. A nova coluna aparece no quadro de Ordens e o cartão no TaskHS reflete a etapa.' },
    ],
  },
  {
    versao: '1.10.0',
    data: '25/06/2026',
    itens: [
      { tipo: 'melhoria', texto: 'O cartao da OS no TaskHS agora mostra um resumo que cresce a cada fase: dados do cliente e do aparelho, recebimento, resultado da calibracao, contato para o Pos-Vendas, endereco de envio e codigo de rastreio. Na fase de Laboratorio, o cartao traz um link para baixar o PDF do certificado direto do TaskHS, sem precisar entrar no GestorHS.' },
    ],
  },
  {
    versao: '1.9.0',
    data: '25/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'As Ordens de Serviço agora são espelhadas automaticamente como cartões no quadro "Serviço" do TaskHS: ao abrir, avançar de fase ou cancelar uma OS, o cartão é criado e movido para a coluna correspondente (Expedição, Laboratório, Pós-Vendas, etc.); ao cancelar, o cartão é arquivado. Quando o GestorHS estiver fora do ar para o TaskHS, a OS segue normalmente — o espelhamento é tolerante a falhas e se reconcilia na próxima atualização.' },
    ],
  },
  {
    versao: '1.8.0',
    data: '18/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Agora é possível transferir um aparelho de uma empresa para outra direto na ficha do aparelho (botão "Transferir"). O histórico de OS antigas continua com a empresa anterior, e cada transferência fica registrada com data, empresas e responsável. Não é permitido transferir enquanto houver uma OS em andamento.' },
    ],
  },
  {
    versao: '1.7.2',
    data: '18/06/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Na ficha do aparelho, quando já existe uma OS em andamento, o botão passa a mostrar "Ver OS #N" e leva direto a ela — evitando abrir uma segunda OS para o mesmo aparelho.' },
    ],
  },
  {
    versao: '1.7.1',
    data: '17/06/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Na fase Preparando Retorno, o botão para concluir a OS agora se chama "Fechar OS" (antes "Postar retorno").' },
      { tipo: 'melhoria', texto: 'Ao abrir uma OS agora é obrigatório vincular uma caixa — o botão "Abrir OS" fica bloqueado até escolher ou criar uma caixa.' },
      { tipo: 'melhoria', texto: 'Na página de Caixas, as caixas já concluídas (com todas as OS finalizadas ou canceladas) ficam ocultas por padrão; ative "Mostrar concluídas" para vê-las.' },
    ],
  },
  {
    versao: '1.7.0',
    data: '17/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'O quadro de Ordens de Serviço agora tem a coluna "Finalizada", mostrando as ordens já concluídas (as 300 mais recentes) com o total no topo. Para ver todas, é só clicar em "Ver todas" e abrir a lista completa filtrada.' },
    ],
  },
  {
    versao: '1.6.0',
    data: '16/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Ao abrir uma Ordem de Serviço agora aparece, no topo, quais garantias do aparelho estão ativas (calibração, manutenção e/ou compra), além de um painel detalhado com as três garantias mostrando até quando cada uma vale.' },
    ],
  },
  {
    versao: '1.5.0',
    data: '10/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'A tela de gerar/regerar certificado agora mostra todos os campos (dados do cliente, do aparelho e da calibração) já preenchidos automaticamente. Dá para ajustar qualquer informação apenas naquele certificado — por exemplo, corrigir o nome ou endereço que sai impresso — sem alterar o cadastro do cliente ou do aparelho. O ajuste fica salvo na OS e vale para as próximas regerações.' },
    ],
  },
  {
    versao: '1.4.3',
    data: '10/06/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Agora é possível corrigir os valores (e a data) de calibração e regerar o certificado mesmo com a OS finalizada — útil quando um certificado sai com algum valor errado. A data de calibração passou a ser um campo do formulário e não é mais redefinida ao regerar.' },
      { tipo: 'melhoria', texto: 'OS antigas (importadas) que ainda não tinham certificado no sistema novo agora podem gerá-lo: em qualquer OS que já passou pelo laboratório (inclusive finalizadas), o botão "Gerar certificado de calibração" fica disponível — dá para preencher os dados de calibração e gerar mesmo que a OS não os tivesse.' },
    ],
  },
  {
    versao: '1.4.2',
    data: '10/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Na ficha do aparelho agora aparecem as ordens de serviço do equipamento e todos os certificados de calibração já gerados, com download do PDF — facilitando o acesso a certificados antigos. O nome do cliente também virou link direto para a ficha do cliente.' },
    ],
  },
  {
    versao: '1.4.1',
    data: '10/06/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Layout das páginas agora preenche a tela e se adapta ao tamanho do monitor — o conteúdo se distribui em colunas em telas grandes e reflui em telas menores, acabando com o espaço vazio à direita nas páginas de detalhe.' },
      { tipo: 'melhoria', texto: 'No detalhe da OS, o nome do cliente e o aparelho viraram links — clicar leva direto à ficha do cliente ou do equipamento.' },
    ],
  },
  {
    versao: '1.4.0',
    data: '09/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Certificado de calibração gerado no laboratório — na fase Laboratório, o botão "Gerar certificado de calibração" abre um formulário com os dados da calibração (Nº do certificado, temperatura, pressão, testes 1/2/3 com média automática, situação). Ao gerar, o sistema preenche o modelo do aparelho com os dados reais (cliente, série, resultados) e produz o certificado, que pode ser revisado e baixado em PDF (gerado automaticamente) direto na OS. Há botão para regerar com o formulário pré-preenchido.' },
      { tipo: 'novidade', texto: 'Download do certificado em PDF com um clique — o sistema gera o PDF no servidor a partir do certificado, no padrão A4 e com a mesma aparência da tela, sem precisar imprimir e reenviar o arquivo manualmente. Removido o envio manual de PDF.' },
      { tipo: 'melhoria', texto: 'Concluir o laboratório agora pede apenas a próxima calibração e uma observação — e é bloqueado enquanto o certificado não for gerado, garantindo que nenhuma OS saia do laboratório sem certificado.' },
      { tipo: 'melhoria', texto: 'Modelos de certificado agora têm dois tipos por aparelho: Calibração e Manutenção.' },
    ],
  },
  {
    versao: '1.3.0',
    data: '08/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Cadastro de Certificados — modelos de certificado por aparelho (edição em HTML com pré-visualização) e biblioteca de imagens para usar nos certificados.' },
    ],
  },
  {
    versao: '1.2.1',
    data: '08/06/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Tela de detalhe da OS repaginada — barra de progresso das fases, seções mais legíveis (acessórios em etiquetas) e histórico em linha do tempo.' },
      { tipo: 'novidade', texto: 'Visualizador de imagem nas fotos da OS — clique na foto para ampliar, com navegação entre as fotos e fechar pelo teclado (Esc/setas).' },
    ],
  },
  {
    versao: '1.2.0',
    data: '08/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Recebimento de OS mais completo — ao abrir a OS agora dá para registrar data de chegada, vincular ou criar uma caixa, condição de chegada, checklist de acessórios que vieram com o aparelho, quantidade de pilhas e bocais, e observações. Tudo aparece no detalhe da OS.' },
      { tipo: 'melhoria', texto: 'Visual do formulário de abrir OS reorganizado em seções, com checklist em etiquetas selecionáveis e modais com rolagem.' },
    ],
  },
  {
    versao: '1.1.1',
    data: '05/06/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Caixas simplificadas — removido o status da caixa (Pendente/Aberta/Finalizada). A caixa agora é só um agrupamento para acessar rapidamente um grupo de OS; o fechamento continua sendo feito por OS.' },
    ],
  },
  {
    versao: '1.1.0',
    data: '05/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Caixas — agrupamento físico de ordens de serviço enviadas juntas (mesma origem), mesmo de clientes diferentes. Crie a caixa, abra ou vincule OS dentro dela, mova/remova entre caixas e acompanhe o status (Pendente → Aberta → Finalizada).' },
    ],
  },
  {
    versao: '1.0.0',
    data: '04/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Lançamento do GestorHS — primeira versão em produção, substituindo o sistema legado.' },
      { tipo: 'novidade', texto: 'Acesso — usuários internos, funções (papéis) e gestão de logins do portal do cliente.' },
      { tipo: 'novidade', texto: 'Clientes e frota — cadastro de clientes, funcionários e aparelhos com status de calibração e histórico.' },
      { tipo: 'novidade', texto: 'Ordens de serviço — quadro kanban, fluxo por fases (recebimento → laboratório → pós-vendas → retorno), calibração e certificado.' },
      { tipo: 'novidade', texto: 'Cobrança — alertas de aparelhos vencidos/vencendo por cliente e registro de contato.' },
      { tipo: 'novidade', texto: 'Portal do cliente — frota, certificados, ordens de serviço e solicitação de recalibração.' },
      { tipo: 'novidade', texto: 'Dashboard — indicadores-chave e ordens ativas por fase.' },
      { tipo: 'novidade', texto: 'Anexos — fotos do recebimento da OS e PDF de certificado de calibração.' },
    ],
  },
]

export const VERSAO_ATUAL = CHANGELOG[0].versao
