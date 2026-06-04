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
}
