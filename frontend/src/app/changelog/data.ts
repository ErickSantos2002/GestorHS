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
    versao: '1.4.0',
    data: '09/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Certificado gerado no laboratório — ao concluir o laboratório, o sistema preenche o modelo do aparelho com os dados reais (cliente, série, resultados da calibração) e gera o certificado de calibração (e o de manutenção, quando houver). Dá para imprimir/salvar em PDF direto na OS, e há botão para regerar.' },
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
