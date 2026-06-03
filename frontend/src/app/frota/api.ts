import { apiJson, apiFetch, ApiError } from '../../lib/api'

export type StatusCalibracao = 'em_dia' | 'vencendo' | 'vencido' | 'sem_data'

export const STATUS_CALIBRACAO: Record<StatusCalibracao, { label: string; tone: 'primary' | 'warning' | 'danger' | 'neutral' }> = {
  em_dia: { label: 'Em dia', tone: 'primary' },
  vencendo: { label: 'Vencendo', tone: 'warning' },
  vencido: { label: 'Vencido', tone: 'danger' },
  sem_data: { label: 'Sem data', tone: 'neutral' },
}

export interface FrotaItem {
  id: number
  cliente: number
  cliente_nome: string | null
  equipamento: number
  equipamento_descricao: string | null
  serie: string | null
  patrimonio: string | null
  prox_calibragem: string | null
  ativo: boolean
  status: string
  status_calibracao: StatusCalibracao
}

export interface FrotaPage {
  items: FrotaItem[]
  total: number
}

export interface EquipamentoCliente {
  id: number
  cliente: number
  cliente_nome: string | null
  equipamento: number
  equipamento_descricao: string | null
  modulo: number
  serie: string | null
  patrimonio: string | null
  datacompra: string | null
  ult_calibragem: string | null
  prox_calibragem: string | null
  ativo: boolean
  status: string
  status_calibracao: StatusCalibracao
  os_atual: number | null
  calib_cert: string | null
  calib_temp: string | null
  calib_pressao: string | null
  calib_teste1: string | null
  calib_teste2: string | null
  calib_teste3: string | null
  calib_teste_media: string | null
  calib_situacao: string | null
}

export interface EquipamentoClientePayload {
  cliente: number
  equipamento: number
  modulo: number
  serie: string | null
  patrimonio: string | null
  datacompra: string | null
  ult_calibragem: string | null
  prox_calibragem: string | null
  ativo: boolean
  status: 'A' | 'I' | 'M'
}

export interface Historico {
  id: number
  equipamento_cliente: number
  datamov: string | null
  saida: number | null
  entrada: number | null
}

async function apiVoid(path: string, options: RequestInit = {}): Promise<void> {
  const res = await apiFetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers as Record<string, string>) },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // sem corpo JSON
    }
    throw new ApiError(res.status, detail)
  }
}

export interface FrotaParams {
  cliente?: number
  status?: string
  q?: string
  offset?: number
  limit?: number
}

export const equipamentosClienteApi = {
  listar: (params: FrotaParams = {}): Promise<FrotaPage> => {
    const sp = new URLSearchParams()
    if (params.cliente != null) sp.set('cliente', String(params.cliente))
    if (params.status) sp.set('status', params.status)
    if (params.q) sp.set('q', params.q)
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<FrotaPage>(`/equipamentos-cliente?${sp.toString()}`)
  },
  obter: (id: number): Promise<EquipamentoCliente> => apiJson<EquipamentoCliente>(`/equipamentos-cliente/${id}`),
  historico: (id: number): Promise<Historico[]> => apiJson<Historico[]>(`/equipamentos-cliente/${id}/historico`),
  criar: (payload: EquipamentoClientePayload): Promise<EquipamentoCliente> =>
    apiJson<EquipamentoCliente>('/equipamentos-cliente', { method: 'POST', body: JSON.stringify(payload) }),
  atualizar: (id: number, payload: Partial<Omit<EquipamentoClientePayload, 'cliente'>>): Promise<EquipamentoCliente> =>
    apiJson<EquipamentoCliente>(`/equipamentos-cliente/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  excluir: (id: number): Promise<void> => apiVoid(`/equipamentos-cliente/${id}`, { method: 'DELETE' }),
}
