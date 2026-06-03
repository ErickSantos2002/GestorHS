import { apiJson, apiFetch, ApiError } from '../../lib/api'

export interface Setor { id: number; descricao: string }
export interface Marca { id: number; descricao: string; imagem: string | null }
export interface Grupo { id: number; descricao: string; texto: string | null }
export interface Categoria { id: number; descricao: string | null; setor: number | null; posicao: number }
export interface Equipamento {
  id: number
  descricao: string | null
  categoria: number | null
  marca: number | null
  detalhes: string | null
  especificacao: string | null
  preco_cod: number
  preco_por: number
  custo: number
  peso_calibragem: number
  peso: number
  estoque: number
  estoque_min: number
  ativo: boolean
  destaque: boolean
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

export interface CrudClient<TOut, TCreate, TUpdate> {
  listar: () => Promise<TOut[]>
  obter: (id: number) => Promise<TOut>
  criar: (payload: TCreate) => Promise<TOut>
  atualizar: (id: number, payload: TUpdate) => Promise<TOut>
  excluir: (id: number) => Promise<void>
}

function crudClient<TOut, TCreate, TUpdate>(base: string): CrudClient<TOut, TCreate, TUpdate> {
  return {
    listar: () => apiJson<TOut[]>(base),
    obter: (id) => apiJson<TOut>(`${base}/${id}`),
    criar: (payload) => apiJson<TOut>(base, { method: 'POST', body: JSON.stringify(payload) }),
    atualizar: (id, payload) => apiJson<TOut>(`${base}/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
    excluir: (id) => apiVoid(`${base}/${id}`, { method: 'DELETE' }),
  }
}

export const setoresApi = crudClient<Setor, { descricao: string }, { descricao?: string }>('/setores')
export const marcasApi = crudClient<Marca, { descricao: string }, { descricao?: string }>('/marcas')
export const gruposApi = crudClient<Grupo, { descricao: string; texto?: string | null }, { descricao?: string; texto?: string | null }>('/grupos')
export const categoriasApi = crudClient<
  Categoria,
  { descricao: string; setor?: number | null; posicao?: number },
  { descricao?: string; setor?: number | null; posicao?: number }
>('/categorias')
export interface EquipamentoPayload {
  descricao: string
  categoria: number | null
  marca: number | null
  detalhes: string | null
  especificacao: string | null
  preco_cod: number
  preco_por: number
  custo: number
  peso_calibragem: number
  peso: number
  estoque: number
  estoque_min: number
  ativo: boolean
  destaque: boolean
}
export const equipamentosApi = crudClient<Equipamento, EquipamentoPayload, Partial<EquipamentoPayload>>('/equipamentos')

export interface Funcao {
  id: number
  descricao: string
}

export const funcoesApi = crudClient<Funcao, { descricao: string }, { descricao?: string }>('/funcoes')

export interface Fase {
  id: number
  descricao: string
  cor: string
  funcao_responsavel: number | null
  funcao_nome: string | null
}

export const fasesApi = {
  listar: (): Promise<Fase[]> => apiJson<Fase[]>('/fases'),
  atualizar: (id: number, payload: { funcao_responsavel: number | null }): Promise<Fase> =>
    apiJson<Fase>(`/fases/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
}
