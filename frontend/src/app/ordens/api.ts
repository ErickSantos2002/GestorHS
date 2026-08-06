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
  { id: 10, label: 'Financeiro' },
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

/**
 * Fluxo linear da OS, na ordem LOGICA (nao na ordem dos ids!).
 * O Financeiro tem id 10, numericamente maior que Preparando Retorno (7) e
 * Finalizada (8) — por isso comparar fase com `>=`/`<=` esta SEMPRE errado.
 * Use `posicaoFase` para qualquer nocao de "antes/depois". Espelha a ordem de
 * ORDEM_FASES do backend (os_workflow.py) — mas o sentinela de "fase fora do
 * fluxo" diverge entre os dois lados: aqui `posicaoFase` devolve -1 (ex.: fase
 * 9 = cancelada), enquanto o backend usa 99 em `os_workflow.posicao()`. Cada
 * lado usa seu proprio sentinela para o mesmo significado ("nao pertence ao
 * fluxo linear") — nao compare os dois valores entre si.
 */
export const FLUXO_FASES: { id: number; nome: string }[] = [
  { id: 4, nome: 'Recebido' },
  { id: 5, nome: 'Laboratório' },
  { id: 6, nome: 'Pós-Vendas' },
  { id: 10, nome: 'Financeiro' },
  { id: 7, nome: 'Preparando Retorno' },
  { id: 8, nome: 'Finalizada' },
]

/** Posicao da fase na sequencia logica; -1 se nao pertence ao fluxo linear (ex.: 9 = cancelada). */
export function posicaoFase(fase: number | null): number {
  if (fase == null) return -1
  return FLUXO_FASES.findIndex((f) => f.id === fase)
}

/** A OS esta em andamento (fase ativa)? */
export function faseAtiva(fase: number | null): boolean {
  return fase != null && FASES_ATIVAS.includes(fase)
}

/** Do laboratorio em diante (a calibracao ja ocorre/ocorreu) — inclui Financeiro. */
export function posLaboratorio(fase: number | null): boolean {
  const p = posicaoFase(fase)
  return p > -1 && p >= posicaoFase(5)
}

/** Retorna a OS em andamento (fase ativa) de uma lista; no maximo uma por aparelho. */
export function osAtiva(ordens: OrdemListItem[]): OrdemListItem | undefined {
  return ordens.find((o) => faseAtiva(o.fase))
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
  calib_teste4: string | null
  calib_teste5: string | null
  calib_teste_media: string | null
  calib_situacao: string | null
  pdf_certificado: string | null
  nota_fiscal: string | null
  nota_fiscal_numero: string | null
  /** Tipos ("C"/"M") sem modelo de certificado cadastrado para o aparelho. Vazio = pode gerar. */
  certificado_modelos_faltantes: string[]
  /** Desfecho do laboratorio: 'pendente' | 'concluido' | 'sem_conserto' | 'liberado'. */
  desfecho_lab: string | null
  desfecho_lab_obs: string | null
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
  /** Faixa de data de chegada, em ISO (AAAA-MM-DD). Inclusiva nas duas pontas. */
  chegadaDe?: string
  chegadaAte?: string
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

export interface EditarPayload {
  tipo_servico?: TipoServico
  condicao_chegada?: string | null
  checklist?: number[] | null
  pilhas?: number | null
  bocais?: number | null
  observacoes?: string | null
  data_chegada?: string | null
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
  calib_teste4?: string | null
  calib_teste5?: string | null
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
  calib_teste4: string | null
  calib_teste5: string | null
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
    if (params.chegadaDe) sp.set('chegada_de', params.chegadaDe)
    if (params.chegadaAte) sp.set('chegada_ate', params.chegadaAte)
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
  editar: (id: number, payload: EditarPayload): Promise<OrdemDetalhe> =>
    apiJson<OrdemDetalhe>(`/ordens/${id}/editar`, { method: 'PUT', body: JSON.stringify(payload) }),
  editarObservacoes: (id: number, observacoes: string | null): Promise<OrdemDetalhe> =>
    apiJson<OrdemDetalhe>(`/ordens/${id}/observacoes`, { method: 'PATCH', body: JSON.stringify({ observacoes }) }),
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
  enviarNotaFiscal: async (ordemId: number, file: File, numero: string): Promise<void> => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('numero', numero)
    const res = await apiFetch(`/ordens/${ordemId}/nota-fiscal`, { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try { const b = await res.json(); if (b.detail) detail = b.detail } catch { /* sem corpo */ }
      throw new ApiError(res.status, detail)
    }
  },
  // Nunca abrir o arquivo numa aba (blob: herda a origem do app — um XML malicioso
  // executaria <script>). Forca download via link com atributo `download`, como o PDF do certificado.
  // `basename` (os.nota_fiscal) ja traz a extensao real — evita depender de Content-Disposition,
  // que so e legivel via JS em requisicoes cross-origin se o backend expor o header no CORS.
  baixarNotaFiscal: async (ordemId: number, basename: string): Promise<void> => {
    const res = await apiFetch(`/ordens/${ordemId}/nota-fiscal`)
    if (!res.ok) throw new ApiError(res.status, 'Falha ao baixar nota fiscal')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const ext = basename.toLowerCase().endsWith('.xml') ? '.xml' : '.pdf'
    const a = document.createElement('a')
    a.href = url
    a.download = `nota-fiscal-${ordemId}${ext}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}
