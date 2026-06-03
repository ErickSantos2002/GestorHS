import { apiJson, apiFetch, ApiError } from '../../lib/api'

export interface ClienteListItem {
  id: number
  nome: string | null
  cgc: string | null
  cpf: string | null
  municipio: string | null
  estado: string | null
  ativo: boolean
}

export interface ClientesPage {
  items: ClienteListItem[]
  total: number
}

export interface Cliente {
  id: number
  grupo: number | null
  nome: string | null
  cgc: string | null
  cpf: string | null
  endereco: string | null
  numero: number | null
  complemento: string | null
  bairro: string | null
  municipio: string | null
  estado: string | null
  cep: string | null
  contato: string | null
  email: string | null
  telefones: string | null
  celular: string | null
  whatsapp: string | null
  whatsapp1: string | null
  whatsapp2: string | null
  insc_mun: string | null
  insc_est: string | null
  datcad: string | null
  obs: string | null
  ativo: boolean
}

export interface ClientePayload {
  nome: string
  grupo: number | null
  cgc: string | null
  cpf: string | null
  endereco: string | null
  numero: number | null
  complemento: string | null
  bairro: string | null
  municipio: string | null
  estado: string | null
  cep: string | null
  contato: string | null
  email: string | null
  telefones: string | null
  celular: string | null
  whatsapp: string | null
  whatsapp1: string | null
  whatsapp2: string | null
  insc_mun: string | null
  insc_est: string | null
  obs: string | null
  ativo: boolean
}

export interface Funcionario {
  id: number
  cliente: number
  setor: number | null
  matricula: string | null
  centro: string | null
  nome: string | null
  email: string | null
  cargo: string | null
  admissao: string | null
  idade: number | null
  sexo: string | null
  estado: string | null
  cidade: string | null
  ativo: boolean
}

export interface FuncionarioPayload {
  nome: string
  matricula: string | null
  cargo: string | null
  setor: number | null
  email: string | null
  admissao: string | null
  ativo: boolean
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

export interface ListarParams {
  q?: string
  offset?: number
  limit?: number
}

export const clientesApi = {
  listar: (params: ListarParams = {}): Promise<ClientesPage> => {
    const sp = new URLSearchParams()
    if (params.q) sp.set('q', params.q)
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<ClientesPage>(`/clientes?${sp.toString()}`)
  },
  obter: (id: number): Promise<Cliente> => apiJson<Cliente>(`/clientes/${id}`),
  criar: (payload: ClientePayload): Promise<Cliente> => apiJson<Cliente>('/clientes', { method: 'POST', body: JSON.stringify(payload) }),
  atualizar: (id: number, payload: Partial<ClientePayload>): Promise<Cliente> =>
    apiJson<Cliente>(`/clientes/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  excluir: (id: number): Promise<void> => apiVoid(`/clientes/${id}`, { method: 'DELETE' }),
}

export const funcionariosApi = {
  listarPorCliente: (clienteId: number): Promise<Funcionario[]> => apiJson<Funcionario[]>(`/clientes/${clienteId}/funcionarios`),
  criar: (clienteId: number, payload: FuncionarioPayload): Promise<Funcionario> =>
    apiJson<Funcionario>(`/clientes/${clienteId}/funcionarios`, { method: 'POST', body: JSON.stringify(payload) }),
  atualizar: (id: number, payload: Partial<FuncionarioPayload>): Promise<Funcionario> =>
    apiJson<Funcionario>(`/funcionarios/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  excluir: (id: number): Promise<void> => apiVoid(`/funcionarios/${id}`, { method: 'DELETE' }),
}
