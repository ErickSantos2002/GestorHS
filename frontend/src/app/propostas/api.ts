import { apiJson, apiFetch, ApiError } from '../../lib/api'
import { crudClient } from '../cadastros/api'

// DELETE/204 não tem corpo — apiJson faz res.json() e quebraria. Mesmo padrão
// usado em caixas/api.ts e cadastros/api.ts.
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

// Mesma resolução de base usada em lib/api.ts (window.__API_URL__ → VITE_API_URL
// → localhost:8000), replicada aqui porque BASE_URL não é exportado de lá — só
// precisamos dela para montar a URL absoluta de download/preview do PDF (ver
// certificados/ImagensTab.tsx `apiBase()` para o mesmo padrão local).
function apiBase(): string {
  const w = typeof window !== 'undefined' ? (window as unknown as { __API_URL__?: string }) : undefined
  const base = w?.__API_URL__ && w.__API_URL__.trim().length
    ? w.__API_URL__.trim()
    : (import.meta.env.VITE_API_URL ?? 'http://localhost:8000')
  return base.replace(/\/$/, '')
}

export interface PropostaItem {
  id: number
  descricao: string
  sku: string | null
  quantidade: number
  unidade: string | null
  preco_un: number
  total: number
}

export interface PropostaItemCreate {
  descricao: string
  sku?: string | null
  quantidade?: number
  unidade?: string | null
  preco_un?: number
}

export interface PropostaAparelho {
  id: number
  equipamento_cliente: number | null
  serie: string | null
  modelo: string | null
  patrimonio: string | null
  prox_calibragem: string | null
}

export interface PropostaAparelhoCreate {
  equipamento_cliente: number
}

export interface PropostaBase {
  cliente: number | null
  contato: string | null
  vendedor: string | null
  data: string | null
  intro: string | null
  outros_itens: string | null
  desconto: number
  frete: number
  forma_envio: string | null
  forma_frete: string | null
  transportador: string | null
  condicao_pagamento: string | null
  validade_dias: number | null
  data_entrega: string | null
  descricao_entrega: string | null
  endereco_entrega_diferente: boolean
  endereco_entrega: Record<string, unknown> | null
  cliente_override: Record<string, unknown> | null
  observacoes: string | null
  assinatura: string | null
}

export interface PropostaCreate extends PropostaBase {
  itens: PropostaItemCreate[]
  aparelhos: PropostaAparelhoCreate[]
}

export type PropostaUpdate = Partial<PropostaCreate>

export interface Proposta extends PropostaBase {
  id: number
  numero: number
  itens: PropostaItem[]
  aparelhos: PropostaAparelho[]
  total_itens: number
  total: number
  cliente_nome: string | null
  cliente_documento: string | null
  created_at: string | null
  updated_at: string | null
  faturada: boolean
  faturada_em: string | null
  faturada_por: string | null
}

export interface PropostaPage {
  items: Proposta[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface PropostaVersao {
  id: number
  numero_versao: number
  alterado_por: string | null
  created_at: string | null
  has_pdf: boolean
  snapshot: Record<string, unknown> | null
}

export interface PropostasParams {
  page?: number
  page_size?: number
  q?: string
}

export const propostasApi = {
  listar: (params: PropostasParams = {}): Promise<PropostaPage> => {
    const sp = new URLSearchParams()
    if (params.page != null) sp.set('page', String(params.page))
    if (params.page_size != null) sp.set('page_size', String(params.page_size))
    if (params.q) sp.set('q', params.q)
    const qs = sp.toString()
    return apiJson<PropostaPage>(`/propostas${qs ? `?${qs}` : ''}`)
  },
  obter: (id: number): Promise<Proposta> => apiJson<Proposta>(`/propostas/${id}`),
  criar: (payload: PropostaCreate): Promise<Proposta> =>
    apiJson<Proposta>('/propostas', { method: 'POST', body: JSON.stringify(payload) }),
  atualizar: (id: number, payload: PropostaUpdate): Promise<Proposta> =>
    apiJson<Proposta>(`/propostas/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  excluir: (id: number): Promise<void> => apiVoid(`/propostas/${id}`, { method: 'DELETE' }),
  duplicar: (id: number): Promise<Proposta> =>
    apiJson<Proposta>(`/propostas/${id}/duplicar`, { method: 'POST' }),
  faturar: (id: number): Promise<Proposta> =>
    apiJson<Proposta>(`/propostas/${id}/faturar`, { method: 'POST' }),
  desfaturar: (id: number): Promise<Proposta> =>
    apiJson<Proposta>(`/propostas/${id}/desfaturar`, { method: 'POST' }),
  listarVersoes: (id: number): Promise<PropostaVersao[]> =>
    apiJson<PropostaVersao[]>(`/propostas/${id}/versoes`),
  // Retorna a URL absoluta (não faz o fetch) — quem consome decide se abre
  // inline, baixa via fetch autenticado (padrão certificados/api.ts) etc.
  pdfUrl: (id: number, download = false): string =>
    `${apiBase()}/propostas/${id}/pdf${download ? '?download=1' : ''}`,
  versaoPdfUrl: (id: number, versaoId: number, download = false): string =>
    `${apiBase()}/propostas/${id}/versoes/${versaoId}/pdf${download ? '?download=1' : ''}`,
  // O endpoint de PDF exige JWT — `<a href>` cru dá 401. Buscamos via fetch
  // autenticado (apiFetch injeta o Bearer) e devolvemos o Blob; quem consome
  // decide se abre inline (window.open) ou força download (<a download>).
  baixarPdf: async (id: number): Promise<Blob> => {
    const res = await apiFetch(`/propostas/${id}/pdf`)
    if (!res.ok) throw new ApiError(res.status, 'Falha ao carregar PDF')
    return res.blob()
  },
  baixarVersaoPdf: async (id: number, versaoId: number): Promise<Blob> => {
    const res = await apiFetch(`/propostas/${id}/versoes/${versaoId}/pdf`)
    if (!res.ok) throw new ApiError(res.status, 'Falha ao carregar PDF')
    return res.blob()
  },
}

export interface EquipamentoClienteFrota {
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
  status_calibracao: string
}

export interface FrotaPage {
  items: EquipamentoClienteFrota[]
  total: number
}

export async function frotaDoCliente(clienteId: number): Promise<EquipamentoClienteFrota[]> {
  const res = await apiJson<FrotaPage>(`/equipamentos-cliente?cliente=${clienteId}&limit=100`)
  return res.items
}

export interface Servico {
  id: number
  sku: string | null
  nome: string
  descricao: string | null
  unidade: string | null
  preco: number
  codigo_servico: string | null
  ativo: boolean
}

export interface ServicoPayload {
  nome: string
  sku?: string | null
  descricao?: string | null
  unidade?: string | null
  preco?: number
  codigo_servico?: string | null
  ativo?: boolean
}

export const servicosApi = crudClient<Servico, ServicoPayload, Partial<ServicoPayload>>('/servicos')

export interface Produto {
  id: number
  sku: string | null
  nome: string
  descricao: string | null
  unidade: string | null
  preco: number
  ncm: string | null
  ativo: boolean
}

export interface ProdutoPayload {
  nome: string
  sku?: string | null
  descricao?: string | null
  unidade?: string | null
  preco?: number
  ncm?: string | null
  ativo?: boolean
}

export const produtosApi = crudClient<Produto, ProdutoPayload, Partial<ProdutoPayload>>('/produtos')
