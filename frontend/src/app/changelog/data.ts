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
