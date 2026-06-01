import { describe, it, expect, beforeEach } from 'vitest'
import { getTokens, setTokens, clearTokens } from './auth-storage'

describe('auth-storage', () => {
  beforeEach(() => localStorage.clear())

  it('retorna null quando não há tokens', () => {
    expect(getTokens()).toBeNull()
  })

  it('grava e lê tokens', () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
    expect(getTokens()).toEqual({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
  })

  it('limpa tokens', () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    clearTokens()
    expect(getTokens()).toBeNull()
  })

  it('retorna null quando o valor está corrompido', () => {
    localStorage.setItem('gestorhs-tokens', '{not json')
    expect(getTokens()).toBeNull()
  })
})
