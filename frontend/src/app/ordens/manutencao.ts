import { apiJson, apiFetch, ApiError } from '../../lib/api'

// DELETE/204 não tem corpo — apiJson faz res.json() e quebraria. Mesmo padrão
// usado em propostas/api.ts, caixas/api.ts e cadastros/api.ts.
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

export interface ServicoManutencao {
  id: number
  /** SKU no catálogo comercial (`servicos`); nulo quando cadastrado à mão. */
  codigo: string | null
  descricao: string
  resumo_padrao: string
  ativo: boolean
}

export interface ManutencaoServicoItem {
  servico: number
  descricao: string
  resumo_padrao: string
}

export interface Manutencao {
  id: number
  os: number
  numero: string | null
  data_manutencao: string | null
  resumo: string | null
  servicos: ManutencaoServicoItem[]
}

export interface ManutencaoPayload {
  numero: string | null
  data_manutencao: string | null
  resumo: string | null
  servicos: number[]
}

/** Espelha compor_resumo do backend, para o modal mostrar o texto antes de salvar. */
export function comporResumo(frases: string[]): string {
  const limpas = frases.map((f) => f.trim()).filter((f) => f !== '')
  if (limpas.length === 0) return ''
  return limpas.map((f) => (f.endsWith('.') ? f : `${f}.`)).join(' ')
}

export const manutencaoApi = {
  obter: (osId: number): Promise<Manutencao> =>
    apiJson<Manutencao>(`/ordens/${osId}/manutencao`),
  salvar: (osId: number, payload: ManutencaoPayload): Promise<Manutencao> =>
    apiJson<Manutencao>(`/ordens/${osId}/manutencao`, { method: 'PUT', body: JSON.stringify(payload) }),
  listarServicos: (): Promise<ServicoManutencao[]> =>
    apiJson<ServicoManutencao[]>('/manutencao-servicos'),
  criarServico: (dados: { codigo?: string | null; descricao: string; resumo_padrao: string }): Promise<ServicoManutencao> =>
    apiJson<ServicoManutencao>('/manutencao-servicos', { method: 'POST', body: JSON.stringify(dados) }),
  atualizarServico: (id: number, dados: Partial<ServicoManutencao>): Promise<ServicoManutencao> =>
    apiJson<ServicoManutencao>(`/manutencao-servicos/${id}`, { method: 'PUT', body: JSON.stringify(dados) }),
  excluirServico: (id: number): Promise<void> =>
    apiVoid(`/manutencao-servicos/${id}`, { method: 'DELETE' }),
}
