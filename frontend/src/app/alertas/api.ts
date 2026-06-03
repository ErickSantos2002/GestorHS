import { apiJson } from '../../lib/api'

export function formatData(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('pt-BR')
}

export interface AlertaItem {
  cliente: number
  cliente_nome: string | null
  vencidos: number
  vencendo: number
  prox_antiga: string | null
  ult_contato: string | null
}

export interface AlertaPage {
  items: AlertaItem[]
  total: number
}

export interface ContatoOut {
  cliente: number
  atualizados: number
  ult_contato: string | null
}

export interface AlertasParams {
  q?: string
  ocultar_recentes?: boolean
  offset?: number
  limit?: number
}

export const alertasApi = {
  listar: (params: AlertasParams = {}): Promise<AlertaPage> => {
    const sp = new URLSearchParams()
    if (params.q) sp.set('q', params.q)
    if (params.ocultar_recentes) sp.set('ocultar_recentes', 'true')
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<AlertaPage>(`/alertas?${sp.toString()}`)
  },
  registrarContato: (clienteId: number): Promise<ContatoOut> =>
    apiJson<ContatoOut>(`/alertas/${clienteId}/contato`, { method: 'POST' }),
}
