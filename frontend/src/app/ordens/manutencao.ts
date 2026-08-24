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
  codigo: string | null
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

/** Modelo e série do aparelho, aguentando cadastro incompleto.
 *  Sem isso, aparelho sem série produziria "equipamento Mercury / nº de série ,". */
function descreverAparelho(modelo: string | null, serie: string | null): string {
  const partes = [
    (modelo ?? '').trim(),
    (serie ?? '').trim() ? `nº de série ${(serie ?? '').trim()}` : '',
  ].filter((p) => p !== '')
  return partes.length ? partes.join(' / ') : 'não identificado'
}

/** Espelha `compor_resumo` do backend (app/core/manutencao.py), para o modal
 *  mostrar o texto antes de salvar. Quem decide o valor final é a API.
 *
 *  O aparelho e a frase de conformidade aparecem UMA vez; só os serviços se
 *  repetem — emendar uma frase completa por serviço repetia os dois a cada item
 *  e ficava longo e confuso com três ou mais. */
export function comporResumo(
  modelo: string | null,
  serie: string | null,
  servicos: { codigo: string | null; descricao: string }[],
): string {
  const itens = servicos
    .map((s) => ({ codigo: (s.codigo ?? '').trim(), descricao: s.descricao.trim() }))
    .filter((s) => s.descricao !== '')
  if (itens.length === 0) return ''
  const lista = itens
    .map((s) => (s.codigo ? `${s.codigo} – ${s.descricao}` : s.descricao))
    .join('; ')
  const rotulo = itens.length === 1 ? 'referente ao serviço' : 'referente aos serviços'
  return `Foi realizada a manutenção no equipamento ${descreverAparelho(modelo, serie)}, `
    + `em conformidade com os procedimentos técnicos da Health & Safety, `
    + `${rotulo}: ${lista}.`
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
