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
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // sem corpo JSON — mantém o statusText
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}
