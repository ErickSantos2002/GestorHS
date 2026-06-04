import { apiJson } from '../../lib/api'

export interface OsPorFaseItem {
  fase: number
  descricao: string
  cor: string
  total: number
}

export interface DashboardResumo {
  aparelhos_vencidos: number
  aparelhos_vencendo: number
  solicitacoes_pendentes: number
  clientes_a_cobrar: number
  os_por_fase: OsPorFaseItem[]
}

export const dashboardApi = {
  resumo: (): Promise<DashboardResumo> => apiJson<DashboardResumo>('/dashboard'),
}
