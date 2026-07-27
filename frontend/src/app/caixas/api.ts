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

export { formatData } from '../../lib/utils'

export interface OrdemResumoCaixa {
  id: number
  cliente: number
  cliente_nome: string | null
  equipamento_descricao: string | null
  equipamento_serie: string | null
  fase: number | null
  fase_descricao: string | null
  fase_cor: string | null
  desfecho_lab: string
  desfecho_lab_obs: string | null
}

export interface CaixaListItem {
  id: number
  data: string | null
  obs: string | null
  total_os: number
  clientes: string[]
  fase: number | null
  fase_descricao: string | null
  fase_cor: string | null
  cliente_principal?: number | null
  cliente_principal_nome?: string | null
  outros_clientes?: number
}

export interface CaixaPage { items: CaixaListItem[]; total: number }

export interface CaixaDetalhe extends CaixaListItem {
  ordens: OrdemResumoCaixa[]
}

export interface CaixasParams { q?: string; incluir_concluidas?: boolean; offset?: number; limit?: number }

export interface CaixaQuadroItem {
  id: number
  cliente_nome: string | null
  total_os: number
  prontos: number
  pendentes: number
  cliente_principal_nome?: string | null
  outros_clientes?: number
}

export interface QuadroCaixaColuna {
  fase: number
  descricao: string
  cor: string
  total: number
  caixas: CaixaQuadroItem[]
}

export interface CaixaAvancarPayload { obs?: string | null; cod_retorno?: string | null; cliente_principal?: number | null }

export const caixasApi = {
  listar: (params: CaixasParams = {}): Promise<CaixaPage> => {
    const sp = new URLSearchParams()
    if (params.q) sp.set('q', params.q)
    if (params.incluir_concluidas) sp.set('incluir_concluidas', 'true')
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
  quadro: (params: { cliente?: number } = {}): Promise<QuadroCaixaColuna[]> => {
    const sp = new URLSearchParams()
    if (params.cliente != null) sp.set('cliente', String(params.cliente))
    const qs = sp.toString()
    return apiJson<QuadroCaixaColuna[]>(`/caixas/quadro${qs ? `?${qs}` : ''}`)
  },
  avancar: (id: number, payload: CaixaAvancarPayload): Promise<CaixaDetalhe> =>
    apiJson<CaixaDetalhe>(`/caixas/${id}/avancar`, { method: 'POST', body: JSON.stringify(payload) }),
  cancelar: (id: number, payload: { motivo: string }): Promise<CaixaDetalhe> =>
    apiJson<CaixaDetalhe>(`/caixas/${id}/cancelar`, { method: 'POST', body: JSON.stringify(payload) }),
  desfechoLab: (osId: number, payload: { desfecho: 'concluido' | 'sem_conserto' | 'liberado'; obs: string | null }): Promise<unknown> =>
    apiJson(`/ordens/${osId}/desfecho-lab`, { method: 'POST', body: JSON.stringify(payload) }),
  // Anexa a mesma nota fiscal para todas as OS ativas da caixa (evita anexar aparelho-por-aparelho).
  // Mirror de ordensApi.enviarNotaFiscal em ../ordens/api.ts — mas o campo do arquivo é `arquivo`
  // (não `file`), espelhando o Form do backend em app/api/notas_fiscais.py.
  enviarNotaFiscalCaixa: async (id: number, arquivo: File, numero: string): Promise<CaixaDetalhe> => {
    const fd = new FormData()
    fd.append('arquivo', arquivo)
    fd.append('numero', numero)
    const res = await apiFetch(`/caixas/${id}/nota-fiscal`, { method: 'POST', body: fd })
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
    return (await res.json()) as CaixaDetalhe
  },
}
