import { apiJson } from '../../lib/api'

export function formatData(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('pt-BR')
}

export type StatusCaixa = 'P' | 'A' | 'F'

export const STATUS_CAIXA: Record<string, { label: string; tone: 'warning' | 'info' | 'success' }> = {
  P: { label: 'Pendente', tone: 'warning' },
  A: { label: 'Aberta', tone: 'info' },
  F: { label: 'Finalizada', tone: 'success' },
}

export interface OrdemResumoCaixa {
  id: number
  cliente: number
  cliente_nome: string | null
  equipamento_descricao: string | null
  equipamento_serie: string | null
  fase: number | null
  fase_descricao: string | null
  fase_cor: string | null
}

export interface CaixaListItem {
  id: number
  data: string | null
  status: StatusCaixa
  obs: string | null
  total_os: number
  clientes: string[]
}

export interface CaixaPage { items: CaixaListItem[]; total: number }

export interface CaixaDetalhe extends CaixaListItem {
  ordens: OrdemResumoCaixa[]
}

export interface CaixasParams { status?: string; q?: string; offset?: number; limit?: number }

export const caixasApi = {
  listar: (params: CaixasParams = {}): Promise<CaixaPage> => {
    const sp = new URLSearchParams()
    if (params.status) sp.set('status', params.status)
    if (params.q) sp.set('q', params.q)
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<CaixaPage>(`/caixas?${sp.toString()}`)
  },
  obter: (id: number): Promise<CaixaDetalhe> => apiJson<CaixaDetalhe>(`/caixas/${id}`),
  criar: (body: { obs?: string | null }): Promise<CaixaListItem> =>
    apiJson<CaixaListItem>('/caixas', { method: 'POST', body: JSON.stringify(body) }),
  atualizar: (id: number, body: { obs?: string | null }): Promise<CaixaListItem> =>
    apiJson<CaixaListItem>(`/caixas/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  abrir: (id: number): Promise<CaixaListItem> =>
    apiJson<CaixaListItem>(`/caixas/${id}/abrir`, { method: 'POST' }),
  finalizar: (id: number): Promise<CaixaListItem> =>
    apiJson<CaixaListItem>(`/caixas/${id}/finalizar`, { method: 'POST' }),
  excluir: (id: number): Promise<void> =>
    apiJson<void>(`/caixas/${id}`, { method: 'DELETE' }),
  vincularOrdem: (id: number, ordem_id: number): Promise<CaixaDetalhe> =>
    apiJson<CaixaDetalhe>(`/caixas/${id}/ordens`, { method: 'POST', body: JSON.stringify({ ordem_id }) }),
  desvincularOrdem: (id: number, ordem_id: number): Promise<void> =>
    apiJson<void>(`/caixas/${id}/ordens/${ordem_id}`, { method: 'DELETE' }),
}
