import { apiJson } from '../lib/api'

export interface PortalMe {
  id: number
  login: string
  nome: string | null
  cliente: number
  cliente_nome: string | null
}

export interface PortalResumo {
  aparelhos: number
  vencidos: number
  os_andamento: number
}

export const portalApi = {
  me: (): Promise<PortalMe> => apiJson<PortalMe>('/portal/me'),
  resumo: (): Promise<PortalResumo> => apiJson<PortalResumo>('/portal/resumo'),
  minhaFrota: (params: { status?: string; q?: string; offset?: number; limit?: number } = {}): Promise<PortalFrotaPage> => {
    const sp = new URLSearchParams()
    if (params.status) sp.set('status', params.status)
    if (params.q) sp.set('q', params.q)
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<PortalFrotaPage>(`/portal/minha-frota?${sp.toString()}`)
  },
  certificados: (params: { offset?: number; limit?: number } = {}): Promise<PortalCertPage> => {
    const sp = new URLSearchParams()
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<PortalCertPage>(`/portal/certificados?${sp.toString()}`)
  },
  minhasOs: (params: { em_andamento?: boolean; offset?: number; limit?: number } = {}): Promise<PortalOSPage> => {
    const sp = new URLSearchParams()
    if (params.em_andamento) sp.set('em_andamento', 'true')
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<PortalOSPage>(`/portal/minhas-os?${sp.toString()}`)
  },
  solicitar: (payload: { equipamento_cliente: number; obs?: string }): Promise<PortalSolicitacaoItem> =>
    apiJson<PortalSolicitacaoItem>('/portal/solicitar-recalibracao', { method: 'POST', body: JSON.stringify(payload) }),
  minhasSolicitacoes: (params: { offset?: number; limit?: number } = {}): Promise<PortalSolicitacaoPage> => {
    const sp = new URLSearchParams()
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<PortalSolicitacaoPage>(`/portal/minhas-solicitacoes?${sp.toString()}`)
  },
}

export function formatData(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('pt-BR')
}

export const STATUS_CALIB: Record<string, { label: string; tone: 'primary' | 'warning' | 'danger' | 'neutral' }> = {
  em_dia: { label: 'Em dia', tone: 'primary' },
  vencendo: { label: 'Vencendo', tone: 'warning' },
  vencido: { label: 'Vencido', tone: 'danger' },
  sem_data: { label: 'Sem data', tone: 'neutral' },
}

export const TIPO_LABEL: Record<string, string> = { C: 'Calibração', M: 'Manutenção', A: 'Ambas' }

export interface PortalFrotaItem {
  id: number
  equipamento_descricao: string | null
  serie: string | null
  patrimonio: string | null
  prox_calibragem: string | null
  status_calibracao: string
}
export interface PortalFrotaPage { items: PortalFrotaItem[]; total: number }

export interface PortalCertItem {
  equipamento_cliente: number
  equipamento_descricao: string | null
  serie: string | null
  calib_cert: string | null
  ult_calibragem: string | null
  prox_calibragem: string | null
  pdf: string | null
}
export interface PortalCertPage { items: PortalCertItem[]; total: number }

export interface PortalOSItem {
  id: number
  equipamento_descricao: string | null
  equipamento_serie: string | null
  fase: number | null
  fase_descricao: string | null
  fase_cor: string | null
  tipo_servico: string | null
  data_chegada: string | null
  prox_calibragem: string | null
  situacao: string
}
export interface PortalOSPage { items: PortalOSItem[]; total: number }

export const STATUS_SOLIC: Record<string, { label: string; tone: 'warning' | 'primary' }> = {
  pendente: { label: 'Pendente', tone: 'warning' },
  atendida: { label: 'Atendida', tone: 'primary' },
}

export interface PortalSolicitacaoItem {
  id: number
  equipamento_cliente: number
  equipamento_descricao: string | null
  status: string
  data_solicitacao: string | null
  data_atendimento: string | null
}
export interface PortalSolicitacaoPage { items: PortalSolicitacaoItem[]; total: number }
