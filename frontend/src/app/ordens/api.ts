import { apiJson, apiFetch, ApiError } from '../../lib/api'
import { formatData } from '../../lib/utils'

export type TipoServico = 'C' | 'M' | 'A'

export const CHECKLIST_ACESSORIOS: { id: number; label: string }[] = [
  { id: 1, label: 'Bobinas' },
  { id: 2, label: 'Bocal' },
  { id: 3, label: 'Cabos USB' },
  { id: 4, label: 'Capa' },
  { id: 5, label: 'Carregador veicular' },
  { id: 6, label: 'Carregadores AC/DC' },
  { id: 7, label: 'Impressora' },
  { id: 8, label: 'Maleta' },
  { id: 9, label: 'Nf de Remessa' },
]

export const CONDICOES_CHEGADA = [
  'Bom estado', 'Com avarias', 'Oxidado', 'Lacrado', 'Sem acessórios',
] as const

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

export { formatData }

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
  caixa: number | null
}

export interface OrdemPage {
  items: OrdemListItem[]
  total: number
}

// Fases ativas (em andamento) da OS — espelha ATIVAS do backend (os_workflow).
export const FASES_ATIVAS = [4, 5, 6, 10, 7]

/** Retorna a OS em andamento (fase ativa) de uma lista; no maximo uma por aparelho. */
export function osAtiva(ordens: OrdemListItem[]): OrdemListItem | undefined {
  return ordens.find((o) => o.fase != null && FASES_ATIVAS.includes(o.fase))
}

export interface QuadroColuna {
  fase: number
  descricao: string
  cor: string
  total: number
  ordens: OrdemListItem[]
}

export type EstadoGarantia = 'em_garantia' | 'fora' | 'sem_registro'

export interface GarantiaItem {
  estado: EstadoGarantia
  data_base: string | null
  vence_em: string | null
}

export interface Garantias {
  em_garantia: boolean
  calibracao: GarantiaItem
  manutencao: GarantiaItem
  compra: GarantiaItem
}

export function garantiaBadge(item: GarantiaItem): { label: string; tone: 'primary' | 'neutral' } {
  if (item.estado === 'em_garantia') {
    return { label: `Em garantia até ${formatData(item.vence_em)}`, tone: 'primary' }
  }
  if (item.estado === 'fora') {
    return { label: 'Fora da garantia', tone: 'neutral' }
  }
  return { label: 'Sem registro', tone: 'neutral' }
}

export const GARANTIA_LABEL: Record<'calibracao' | 'manutencao' | 'compra', string> = {
  calibracao: 'Calibração',
  manutencao: 'Manutenção',
  compra: 'Compra',
}

/** Rótulos das garantias atualmente ativas (estado em_garantia), na ordem fixa. */
export function garantiasAtivas(g: Garantias): string[] {
  return (['calibracao', 'manutencao', 'compra'] as const)
    .filter((k) => g[k].estado === 'em_garantia')
    .map((k) => GARANTIA_LABEL[k])
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
  tipo_calibragem: number | null
  calib_cert: string | null
  calib_temp: string | null
  calib_pressao: string | null
  calib_teste1: string | null
  calib_teste2: string | null
  calib_teste3: string | null
  calib_teste_media: string | null
  calib_situacao: string | null
  pdf_certificado: string | null
  pilhas: number
  bocais: number
  checklist_ids: number[]
  acessorios_presentes: string[]
  garantias: Garantias | null
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
  data_chegada?: string | null
  caixa?: number | null
  condicao_chegada?: string | null
  checklist?: number[] | null
  pilhas?: number | null
  bocais?: number | null
  observacoes?: string | null
}

export interface AvancarPayload {
  obs?: string | null
  cod_retorno?: string | null
  prox_calibragem?: string | null
}

export interface GerarCertificadoPayload {
  data_calibracao?: string | null
  nomecli?: string | null
  cnpj?: string | null
  endcli?: string | null
  modelo?: string | null
  marca?: string | null
  serie?: string | null
  patrimonio?: string | null
  datacompra?: string | null
  calib_cert?: string | null
  calib_temp?: string | null
  calib_pressao?: string | null
  calib_teste1?: string | null
  calib_teste2?: string | null
  calib_teste3?: string | null
  calib_teste_media?: string | null
  calib_situacao?: string | null
}

export interface CertificadoCampos {
  nomecli: string
  cnpj: string
  endcli: string
  modelo: string
  marca: string
  serie: string
  patrimonio: string
  datacompra: string
  calib_cert: string | null
  calib_temp: string | null
  calib_pressao: string | null
  calib_teste1: string | null
  calib_teste2: string | null
  calib_teste3: string | null
  calib_teste_media: string | null
  calib_situacao: string | null
  data_calibracao: string | null
}

export const TRANSICOES: Record<number, { rotulo: string; pedeCodRetorno?: boolean; pedeProxCalibragem?: boolean }> = {
  4: { rotulo: 'Encaminhar ao laboratório' },
  5: { rotulo: 'Concluir laboratório', pedeProxCalibragem: true },
  6: { rotulo: 'Registrar aceite' },
  10: { rotulo: 'Confirmar pagamento' },
  7: { rotulo: 'Fechar OS', pedeCodRetorno: true },
}

export interface Foto {
  id: number
  os: number
  arquivo: string
  legenda: string | null
  url: string
}

// Busca um arquivo protegido (precisa de Bearer) e devolve um object URL.
export async function buscarBlobUrl(path: string): Promise<string> {
  const res = await apiFetch(path)
  if (!res.ok) throw new ApiError(res.status, 'Falha ao carregar arquivo')
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

export const fotosApi = {
  listar: (ordemId: number): Promise<Foto[]> => apiJson<Foto[]>(`/ordens/${ordemId}/fotos`),
  enviar: async (ordemId: number, file: File, legenda?: string): Promise<Foto> => {
    const fd = new FormData()
    fd.append('file', file)
    if (legenda) fd.append('legenda', legenda)
    const res = await apiFetch(`/ordens/${ordemId}/fotos`, { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try { const b = await res.json(); if (b.detail) detail = b.detail } catch { /* sem corpo */ }
      throw new ApiError(res.status, detail)
    }
    return (await res.json()) as Foto
  },
  excluir: async (fotoId: number): Promise<void> => {
    const res = await apiFetch(`/fotos/${fotoId}`, { method: 'DELETE' })
    if (!res.ok) throw new ApiError(res.status, 'Falha ao excluir')
  },
}


export interface OSCertificado {
  tipo: 'C' | 'M'
  html: string | null
  pdf: string | null
  data_geracao: string | null
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
  certificados: (id: number): Promise<OSCertificado[]> => apiJson<OSCertificado[]>(`/ordens/${id}/certificados`),
  gerarCertificado: (id: number, payload?: GerarCertificadoPayload): Promise<OSCertificado[]> =>
    apiJson<OSCertificado[]>(`/ordens/${id}/gerar-certificado`, payload
      ? { method: 'POST', body: JSON.stringify(payload) }
      : { method: 'POST' }),
  certificadoCampos: (id: number): Promise<CertificadoCampos> => apiJson<CertificadoCampos>(`/ordens/${id}/certificado-campos`),
  baixarCertificadoPdf: async (id: number, tipo: 'C' | 'M'): Promise<void> => {
    const res = await apiFetch(`/ordens/${id}/certificado/${tipo}/pdf`)
    if (!res.ok) throw new ApiError(res.status, 'Falha ao baixar PDF')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const nome = tipo === 'C' ? 'calibracao' : 'manutencao'
    const a = document.createElement('a')
    a.href = url
    a.download = `certificado-${id}-${nome}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}
