import { apiJson } from '../../lib/api'

export interface ServicoManutencao {
  id: number
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
  criarServico: (dados: { descricao: string; resumo_padrao: string }): Promise<ServicoManutencao> =>
    apiJson<ServicoManutencao>('/manutencao-servicos', { method: 'POST', body: JSON.stringify(dados) }),
  atualizarServico: (id: number, dados: Partial<ServicoManutencao>): Promise<ServicoManutencao> =>
    apiJson<ServicoManutencao>(`/manutencao-servicos/${id}`, { method: 'PUT', body: JSON.stringify(dados) }),
  excluirServico: (id: number): Promise<void> =>
    apiJson<void>(`/manutencao-servicos/${id}`, { method: 'DELETE' }),
}
