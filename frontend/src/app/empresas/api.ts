import { apiJson } from '../../lib/api'

export interface Empresa {
  id: number
  cliente: number | null
  matriz_nome: string | null
  nome: string
  cgc: string | null
  cpf: string | null
  cep: string | null
  endereco: string | null
  numero: string | null
  complemento: string | null
  bairro: string | null
  municipio: string | null
  estado: string | null
  email: string | null
  telefone: string | null
  insc_est: string | null
  ativo: boolean
  tiny_id: number | null
  tiny_status: 'pendente' | 'enviada' | 'erro' | null
  tiny_erro: string | null
  tiny_em: string | null
  created_at: string | null
  updated_at: string | null
}

export interface EmpresaPayload {
  documento: string
  cliente: number | null
  nome: string
  cep: string | null
  endereco: string | null
  numero: string | null
  complemento: string | null
  bairro: string | null
  municipio: string | null
  estado: string | null
  email: string | null
  telefone: string | null
  insc_est: string | null
}

export interface EmpresasPage {
  items: Empresa[]
  total: number
}

export interface ListarEmpresasParams {
  q?: string
  cliente?: number
  ativo?: boolean
  tiny_status?: 'pendente' | 'enviada' | 'erro'
  offset?: number
  limit?: number
}

export interface DestinatarioResultado {
  tipo: 'cliente' | 'empresa'
  id: number
  nome: string | null
  documento: string | null
  municipio: string | null
  estado: string | null
  matriz_id: number | null
  matriz_nome: string | null
}

export const empresasApi = {
  listar: (params: ListarEmpresasParams = {}): Promise<EmpresasPage> => {
    const sp = new URLSearchParams()
    if (params.q) sp.set('q', params.q)
    if (params.cliente != null) sp.set('cliente', String(params.cliente))
    if (params.ativo != null) sp.set('ativo', String(params.ativo))
    if (params.tiny_status) sp.set('tiny_status', params.tiny_status)
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<EmpresasPage>(`/empresas?${sp.toString()}`)
  },
  obter: (id: number) => apiJson<Empresa>(`/empresas/${id}`),
  criar: (payload: EmpresaPayload) => apiJson<Empresa>('/empresas', { method: 'POST', body: JSON.stringify(payload) }),
  atualizar: (id: number, payload: EmpresaPayload) =>
    apiJson<Empresa>(`/empresas/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  desativar: (id: number) => apiJson<Empresa>(`/empresas/${id}/desativar`, { method: 'POST' }),
  reativar: (id: number) => apiJson<Empresa>(`/empresas/${id}/reativar`, { method: 'POST' }),
  reenviarTiny: (id: number) => apiJson<Empresa>(`/empresas/${id}/tiny`, { method: 'POST' }),
}

export const destinatariosApi = {
  buscar: (q: string) =>
    apiJson<DestinatarioResultado[]>(`/propostas/destinatarios?q=${encodeURIComponent(q)}`),
}

/** Texto da coluna "Tiny". Vazio = integração desligada ou cadastro anterior a ela. */
export function rotuloTiny(e: Empresa): string {
  if (e.tiny_status === 'enviada') return 'Enviada'
  if (e.tiny_status === 'pendente') return 'Pendente'
  if (e.tiny_status === 'erro') return 'Erro'
  return '—'
}
