import { getTokens, setTokens, clearTokens, type Tokens } from './auth-storage'

// Prioridade da URL da API:
//   1. window.__API_URL__  → injetado em runtime pelo /config.js (produção; sem rebuild)
//   2. VITE_API_URL        → embutido no build (dev/local via .env)
//   3. http://localhost:8000 (fallback de desenvolvimento)
const runtimeApiUrl =
  typeof window !== 'undefined'
    ? (window as unknown as { __API_URL__?: string }).__API_URL__
    : undefined

const BASE_URL =
  runtimeApiUrl && runtimeApiUrl.trim()
    ? runtimeApiUrl.trim()
    : import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** URL absoluta da API. O botão do SSO é uma âncora e precisa do mesmo
 *  BASE_URL que o apiFetch usa — que em produção vem do /config.js em runtime.
 *  Duplicar essa cascata numa segunda função seria pedir para as duas discordarem. */
export function apiUrl(path: string): string {
  return `${BASE_URL}${path}`
}

let onUnauthorized: (() => void) | null = null
export function setOnUnauthorized(cb: (() => void) | null) {
  onUnauthorized = cb
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// Rotulo dos campos que aparecem no 422. O que nao estiver aqui sai com o
// nome cru do campo — feio, mas ainda aponta o culpado.
const ROTULOS: Record<string, string> = {
  destinatario: 'Destinatário', nome: 'Nome', documento: 'Documento', cep: 'CEP',
  endereco: 'Endereço', numero: 'Número', complemento: 'Complemento', bairro: 'Bairro',
  municipio: 'Município', estado: 'UF', email: 'E-mail', telefone: 'Telefone',
}

type ErroValidacao = { type?: string; loc?: (string | number)[]; msg?: string; ctx?: Record<string, unknown> }

function textoDoErro(e: ErroValidacao): string {
  const ctx = e.ctx ?? {}
  switch (e.type) {
    case 'missing': return 'campo obrigatório'
    case 'string_too_long': return `no máximo ${ctx.max_length} caracteres`
    case 'string_too_short': return `no mínimo ${ctx.min_length} caractere${ctx.min_length === 1 ? '' : 's'}`
    case 'value_error': return (e.msg ?? '').replace(/^Value error, /, '')
    default: return `valor inválido (${e.msg ?? e.type})`
  }
}

function campoDoErro(loc: (string | number)[]): string {
  // `body` e' o envelope do FastAPI; um indice numerico e' a posicao numa lista.
  const partes = loc.filter((p) => p !== 'body')
  const out: string[] = []
  partes.forEach((p, i) => {
    if (typeof p === 'number') {
      const lista = partes[i - 1]
      out[out.length - 1] = lista === 'itens' ? `Item ${p + 1}` : `${out[out.length - 1]} ${p + 1}`
    } else {
      out.push(ROTULOS[p] ?? p)
    }
  })
  // Pai + campo e' contexto demais para o destinatario, onde todo campo e' dele.
  if (out[0] === 'Destinatário' && out.length > 1) out.shift()
  return out.join(' › ')
}

/** Converte o `detail` de uma resposta de erro em texto para a tela. O FastAPI
 *  manda string nos HTTPException, mas uma LISTA de objetos no 422 de validacao
 *  — e jogar a lista em `new Error()` virava "[object Object]" para o usuario. */
export function mensagemDeErro(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail || fallback
  if (Array.isArray(detail)) {
    const partes = detail.map((e: ErroValidacao) => {
      const campo = campoDoErro(e.loc ?? [])
      return campo ? `${campo}: ${textoDoErro(e)}` : textoDoErro(e)
    })
    return partes.length ? partes.join(' · ') : fallback
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return fallback
}

let refreshPromise: Promise<boolean> | null = null

async function doRefresh(): Promise<boolean> {
  const tokens = getTokens()
  if (!tokens?.refresh_token) return false
  const res = await fetch(`${BASE_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  })
  if (!res.ok) return false
  const data = (await res.json()) as Tokens
  setTokens(data)
  return true
}

function refreshOnce(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = doRefresh()
      .catch(() => false)
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

export async function apiFetch(path: string, options: RequestInit = {}, retry = true): Promise<Response> {
  const tokens = getTokens()
  const headers = new Headers(options.headers)
  if (tokens?.access_token) headers.set('Authorization', `Bearer ${tokens.access_token}`)

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers })

  // só tenta refresh se já havia refresh_token no início desta request
  if (res.status === 401 && retry && tokens?.refresh_token) {
    const ok = await refreshOnce()
    if (ok) return apiFetch(path, options, false)
    clearTokens()
    onUnauthorized?.()
  }
  return res
}

export async function apiJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers as Record<string, string>) },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: unknown }
      detail = mensagemDeErro(body.detail, detail)
    } catch {
      // sem corpo JSON — mantém o statusText
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}
