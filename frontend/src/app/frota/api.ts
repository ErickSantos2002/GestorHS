import { apiJson, apiFetch, ApiError } from '../../lib/api'
import type { OrdemListItem } from '../ordens/api'

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

export interface EloModulo {
  id: number
  serie: string | null
  entrou_em: string | null
  origem: string | null
}

export interface EloPhoebus {
  id: number
  serie: string | null
  cliente_nome: string | null
  entrou_em: string | null
  origem: string | null
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
  modulo_instalado: EloModulo | null
  instalado_em: EloPhoebus | null
  em_estoque: boolean
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

export interface EquipCertItem {
  os: number | null            // nulo no certificado de venda (nao ha OS)
  tipo: 'C' | 'M'
  data_geracao: string | null
  origem: 'os' | 'venda'
}

export interface CertificadoVendaCampos {
  nomecli: string
  cnpj: string
  endcli: string
  modelo: string
  marca: string
  serie: string
  patrimonio: string
  datacompra: string | null
  calib_cert: string | null
  data_calibracao: string | null
  prox_calibragem: string | null
  calib_temp: string | null
  calib_pressao: string | null
  calib_teste1: string | null
  calib_teste2: string | null
  calib_teste3: string | null
  calib_teste_media: string | null
  calib_situacao: string | null
  ja_gerado: boolean
}

export interface CertificadoVendaPayload {
  nomecli: string | null
  cnpj: string | null
  endcli: string | null
  serie: string | null
  patrimonio: string | null
  datacompra: string | null
  calib_cert: string | null
  data_calibracao: string | null
  prox_calibragem: string | null
  calib_temp: string | null
  calib_pressao: string | null
  calib_teste1: string | null
  calib_teste2: string | null
  calib_teste3: string | null
  calib_teste_media: string | null
  calib_situacao: string | null
}

export interface Transferencia {
  id: number
  equipamento_cliente: number
  de_cliente: number
  de_cliente_nome: string | null
  para_cliente: number
  para_cliente_nome: string | null
  usuario: number | null
  usuario_nome: string | null
  data: string
  obs: string | null
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
  ordens: (id: number): Promise<OrdemListItem[]> => apiJson<OrdemListItem[]>(`/equipamentos-cliente/${id}/ordens`),
  certificados: (id: number): Promise<EquipCertItem[]> => apiJson<EquipCertItem[]>(`/equipamentos-cliente/${id}/certificados`),
  certificadoVendaCampos: (id: number): Promise<CertificadoVendaCampos> =>
    apiJson<CertificadoVendaCampos>(`/equipamentos-cliente/${id}/certificado-venda-campos`),
  gerarCertificadoVenda: (id: number, body: CertificadoVendaPayload): Promise<unknown> =>
    apiJson<unknown>(`/equipamentos-cliente/${id}/certificado-venda`, { method: 'POST', body: JSON.stringify(body) }),
  baixarCertificadoVendaPdf: async (id: number): Promise<void> => {
    const res = await apiFetch(`/equipamentos-cliente/${id}/certificado-venda/pdf`)
    if (!res.ok) throw new ApiError(res.status, 'Falha ao baixar PDF')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `certificado-venda-${id}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
  transferencias: (id: number): Promise<Transferencia[]> => apiJson<Transferencia[]>(`/equipamentos-cliente/${id}/transferencias`),
  transferir: (id: number, body: { cliente: number; obs?: string | null }): Promise<EquipamentoCliente> =>
    apiJson<EquipamentoCliente>(`/equipamentos-cliente/${id}/transferir`, { method: 'POST', body: JSON.stringify(body) }),
  criar: (payload: EquipamentoClientePayload): Promise<EquipamentoCliente> =>
    apiJson<EquipamentoCliente>('/equipamentos-cliente', { method: 'POST', body: JSON.stringify(payload) }),
  atualizar: (id: number, payload: Partial<Omit<EquipamentoClientePayload, 'cliente'>>): Promise<EquipamentoCliente> =>
    apiJson<EquipamentoCliente>(`/equipamentos-cliente/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  excluir: (id: number): Promise<void> => apiVoid(`/equipamentos-cliente/${id}`, { method: 'DELETE' }),
}
