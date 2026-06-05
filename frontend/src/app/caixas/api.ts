import { apiJson, apiFetch, ApiError } from '../../lib/api'

// DELETE/204 não tem corpo — apiJson faz res.json() e quebraria. Mesmo padrão de acesso/api.ts.
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

export function formatData(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('pt-BR')
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
  obs: string | null
  total_os: number
  clientes: string[]
}

export interface CaixaPage { items: CaixaListItem[]; total: number }

export interface CaixaDetalhe extends CaixaListItem {
  ordens: OrdemResumoCaixa[]
}

export interface CaixasParams { q?: string; offset?: number; limit?: number }

export const caixasApi = {
  listar: (params: CaixasParams = {}): Promise<CaixaPage> => {
    const sp = new URLSearchParams()
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
  excluir: (id: number): Promise<void> =>
    apiVoid(`/caixas/${id}`, { method: 'DELETE' }),
  vincularOrdem: (id: number, ordem_id: number): Promise<CaixaDetalhe> =>
    apiJson<CaixaDetalhe>(`/caixas/${id}/ordens`, { method: 'POST', body: JSON.stringify({ ordem_id }) }),
  desvincularOrdem: (id: number, ordem_id: number): Promise<void> =>
    apiVoid(`/caixas/${id}/ordens/${ordem_id}`, { method: 'DELETE' }),
}
