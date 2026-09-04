import { apiJson, apiFetch, ApiError } from '../../lib/api'
import type { Proposta } from '../propostas/api'

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
  /** Numero da proposta do CRM, gravado pelo inbound do GrowthHS ao marcar "Ganho".
   *  A proposta em si vem de `caixasApi.proposta` — pode nao existir aqui. */
  numero_proposta?: number | null
}

export interface CaixaPage { items: CaixaListItem[]; total: number }

export interface NotaFiscalCaixa {
  id: number
  numero: string
  criado_em: string | null
}

/** Um bloco do modal: numero + o par de arquivos. O par e' obrigatorio — a nota
 *  so esta completa com os dois, regra que vem da migracao 0026. */
export interface NotaParaEnviar {
  numero: string
  pdf: File
  xml: File
}

export interface CaixaDetalhe extends CaixaListItem {
  ordens: OrdemResumoCaixa[]
  notas_fiscais: NotaFiscalCaixa[]
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

export interface CaixaAvancarPayload {
  obs?: string | null
  cod_retorno?: string | null
  cliente_principal?: number | null
  /** Dispensa a nota fiscal ao sair do Financeiro. O backend so aceita de Administrador. */
  sem_nota_fiscal?: boolean
}

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
  /** Proposta comercial da caixa (resolvida pelo numero). 404 quando a caixa nao tem
   *  numero ou o numero e de proposta que so existe no CRM antigo. */
  proposta: (id: number): Promise<Proposta> => apiJson<Proposta>(`/caixas/${id}/proposta`),
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
  // Anexa N notas da caixa numa chamada so — a caixa pode levar a nota do servico
  // e a de remessa. As tres listas vao PARALELAS (numero[i] casa com pdf[i] e
  // xml[i]), espelhando o Form do backend em app/api/notas_fiscais.py.
  enviarNotasFiscaisCaixa: async (id: number, notas: NotaParaEnviar[]): Promise<CaixaDetalhe> => {
    const fd = new FormData()
    for (const n of notas) {
      fd.append('numeros', n.numero)
      fd.append('arquivos_pdf', n.pdf)
      fd.append('arquivos_xml', n.xml)
    }
    const res = await apiFetch(`/caixas/${id}/notas-fiscais`, { method: 'POST', body: fd })
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
  removerNotaFiscalCaixa: (id: number, notaId: number): Promise<CaixaDetalhe> =>
    apiJson<CaixaDetalhe>(`/caixas/${id}/notas-fiscais/${notaId}`, { method: 'DELETE' }),
  // Nunca abrir o arquivo numa aba (blob: herda a origem do app — um XML malicioso
  // executaria <script>). Forca download via link com atributo `download`, como o
  // PDF do certificado. A extensao vem do `tipo`, nao do Content-Disposition, que
  // so e legivel via JS cross-origin se o backend expuser o header no CORS.
  baixarNotaFiscalCaixa: async (id: number, notaId: number, numero: string, tipo: 'pdf' | 'xml'): Promise<void> => {
    const res = await apiFetch(`/caixas/${id}/notas-fiscais/${notaId}/${tipo}`)
    if (!res.ok) throw new ApiError(res.status, 'Falha ao baixar nota fiscal')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `nota-fiscal-${numero}.${tipo}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}
