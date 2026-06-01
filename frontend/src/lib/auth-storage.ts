const KEY = 'gestorhs-tokens'

export interface Tokens {
  access_token: string
  refresh_token: string
  token_type?: string
}

export function getTokens(): Tokens | null {
  const raw = localStorage.getItem(KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as Tokens
  } catch {
    return null
  }
}

export function setTokens(tokens: Tokens): void {
  localStorage.setItem(KEY, JSON.stringify(tokens))
}

export function clearTokens(): void {
  localStorage.removeItem(KEY)
}
