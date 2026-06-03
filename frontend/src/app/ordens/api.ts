import { apiJson } from '../../lib/api'

export type TipoServico = 'C' | 'M' | 'A'

export const TIPO_SERVICO: Record<TipoServico, { label: string; tone: 'primary' | 'warning' | 'neutral' }> = {
  C: { label: 'Calibração', tone: 'primary' },
  M: { label: 'Manutenção', tone: 'warning' },
  A: { label: 'Ambas', tone: 'neutral' },
}

export const FASES_FILTRO: { id: number; label: string }[] = [
  { id: 4, label: 'Recebido' },
  { id: 5, label: 'Laboratório' },
  { id: 6, label: 'Pós-Vendas' },
  { id: 7, label: 'Preparando Retorno' },
  { id: 8, label: 'Finalizada' },
  { id: 9, label: 'Cancelada' },
]

export function formatData(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('pt-BR')
}

export interface OrdemListItem {
  id: number
  cliente: number
  cliente_nome: string | null
  equipamento_cliente: number | null
  equipamento_descricao: string | null
  equipamento_serie: string | null
  fase: number | null
  fase_descricao: string | null
  fase_cor: string | null
  tipo_servico: string | null
  data_chegada: string | null
  prox_calibragem: string | null
  situacao: string
}

export interface OrdemPage {
  items: OrdemListItem[]
  total: number
}

export interface QuadroColuna {
  fase: number
  descricao: string
  cor: string
  ordens: OrdemListItem[]
}

export interface OrdemDetalhe extends OrdemListItem {
  condicao_chegada: string | null
  acessorios: string | null
  aceite: boolean
  recebido: boolean
  etiqueta: string | null
  cod_retorno: string | null
  obs: string | null
  data_calibracao: string | null
  data_retorno: string | null
  data_aceite: string | null
  calib_cert: string | null
  calib_temp: string | null
  calib_pressao: string | null
  calib_teste_media: string | null
  calib_situacao: string | null
  pdf_certificado: string | null
}

export interface LogOS {
  id: number
  os: number
  usuario: number | null
  autor: string
  datalog: string | null
  texto: string | null
}

export interface OrdensParams {
  fase?: number
  cliente?: number
  tipo?: string
  q?: string
  offset?: number
  limit?: number
}

export interface AbrirPayload {
  equipamento_cliente: number
  tipo_servico: TipoServico
  condicao_chegada?: string | null
  acessorios?: string | null
}

export interface AvancarPayload {
  obs?: string | null
  cod_retorno?: string | null
}

export const TRANSICOES: Record<number, { rotulo: string; pedeCodRetorno?: boolean }> = {
  4: { rotulo: 'Encaminhar ao laboratório' },
  5: { rotulo: 'Concluir laboratório' },
  6: { rotulo: 'Registrar aceite' },
  7: { rotulo: 'Postar retorno', pedeCodRetorno: true },
}

export const ordensApi = {
  listar: (params: OrdensParams = {}): Promise<OrdemPage> => {
    const sp = new URLSearchParams()
    if (params.fase != null) sp.set('fase', String(params.fase))
    if (params.cliente != null) sp.set('cliente', String(params.cliente))
    if (params.tipo) sp.set('tipo', params.tipo)
    if (params.q) sp.set('q', params.q)
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<OrdemPage>(`/ordens?${sp.toString()}`)
  },
  quadro: (params: { cliente?: number } = {}): Promise<QuadroColuna[]> => {
    const sp = new URLSearchParams()
    if (params.cliente != null) sp.set('cliente', String(params.cliente))
    const qs = sp.toString()
    return apiJson<QuadroColuna[]>(`/ordens/quadro${qs ? `?${qs}` : ''}`)
  },
  obter: (id: number): Promise<OrdemDetalhe> => apiJson<OrdemDetalhe>(`/ordens/${id}`),
  logs: (id: number): Promise<LogOS[]> => apiJson<LogOS[]>(`/ordens/${id}/logs`),
  abrir: (payload: AbrirPayload): Promise<OrdemDetalhe> =>
    apiJson<OrdemDetalhe>('/ordens', { method: 'POST', body: JSON.stringify(payload) }),
  avancar: (id: number, payload: AvancarPayload): Promise<OrdemDetalhe> =>
    apiJson<OrdemDetalhe>(`/ordens/${id}/avancar`, { method: 'POST', body: JSON.stringify(payload) }),
  cancelar: (id: number, payload: { motivo: string }): Promise<OrdemDetalhe> =>
    apiJson<OrdemDetalhe>(`/ordens/${id}/cancelar`, { method: 'POST', body: JSON.stringify(payload) }),
}
