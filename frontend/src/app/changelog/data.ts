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
    versao: '1.6.0',
    data: '16/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Ao abrir uma Ordem de Serviço agora aparece, no topo, um selo indicando se o aparelho está em garantia, e um painel detalhado com as três garantias (calibração, manutenção e compra) — cada uma mostrando até quando vale.' },
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
