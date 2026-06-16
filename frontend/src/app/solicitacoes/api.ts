import { apiJson } from '../../lib/api'

export function formatData(iso: string | null): string {
  if (!iso) return '—'
  // ISO date-only strings (YYYY-MM-DD) are parsed as UTC midnight by spec,
  // which shifts the day backwards in negative-offset timezones.
  // Appending T00:00:00 makes the parser treat it as local midnight.
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T00:00:00` : iso
  const d = new Date(normalized)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('pt-BR')
}

export const STATUS_SOLIC: Record<string, { label: string; tone: 'warning' | 'primary' }> = {
  pendente: { label: 'Pendente', tone: 'warning' },
  atendida: { label: 'Atendida', tone: 'primary' },
}

export interface SolicitacaoItem {
  id: number
  cliente: number
  cliente_nome: string | null
  equipamento_cliente: number
  equipamento_descricao: string | null
  status: string
  data_solicitacao: string | null
  data_atendimento: string | null
  atendido_por: number | null
  atendido_por_nome: string | null
  obs: string | null
}
export interface SolicitacaoPage { items: SolicitacaoItem[]; total: number }

export const solicitacoesApi = {
  listar: (params: { status?: string; offset?: number; limit?: number } = {}): Promise<SolicitacaoPage> => {
    const sp = new URLSearchParams()
    if (params.status) sp.set('status', params.status)
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<SolicitacaoPage>(`/solicitacoes?${sp.toString()}`)
  },
  atender: (id: number): Promise<SolicitacaoItem> =>
    apiJson<SolicitacaoItem>(`/solicitacoes/${id}/atender`, { method: 'POST' }),
}
