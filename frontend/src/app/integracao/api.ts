import { apiJson } from '../../lib/api'

export type StatusLog = 'sucesso' | 'erro' | 'pulado'

export interface LogIntegracao {
  id: number
  criado_em: string | null
  integracao: string
  tipo: string
  external_id: string | null
  referencia_os: number | null
  // Para onde a referencia aponta: o card e' da caixa, mas os pulos por modulo
  // guardam o id da OS. Null quando a linha nao tem referencia.
  referencia_tipo: 'os' | 'caixa' | null
  status: StatusLog
  motivo: string | null
  http_status: number | null
  resposta: string | null
  payload: unknown | null
}

export interface EstadoIntegracoes {
  taskhs_ativo: boolean
  growthhs_ativo: boolean
}

export interface LogsPage {
  items: LogIntegracao[]
  total: number
  estado: EstadoIntegracoes
}

export interface FiltrosLogs {
  integracao?: string
  status?: string
  tipo?: string
  os?: string
  q?: string
  offset?: number
  limit?: number
}

export const logsIntegracaoApi = {
  listar(f: FiltrosLogs = {}): Promise<LogsPage> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(f)) {
      if (v !== undefined && v !== '' && v !== null) qs.set(k, String(v))
    }
    const query = qs.toString()
    return apiJson<LogsPage>(`/logs-integracao${query ? `?${query}` : ''}`)
  },
  reenviar(id: number): Promise<{ ok: boolean; mensagem?: string }> {
    return apiJson(`/logs-integracao/${id}/reenviar`, { method: 'POST' })
  },
}

// Linha elegivel para reenvio: tem payload e nao foi sucesso.
export function podeReenviar(log: LogIntegracao): boolean {
  return log.payload != null && log.status !== 'sucesso'
}

export const TONE_STATUS: Record<StatusLog, 'primary' | 'danger' | 'neutral'> = {
  sucesso: 'primary',
  erro: 'danger',
  pulado: 'neutral',
}
