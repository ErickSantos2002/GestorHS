import { describe, it, expect } from 'vitest'
import { soDigitos, formatarDocumento, mascararCNPJ, mascararCPF } from './documento'

describe('soDigitos', () => {
  it('remove nao-digitos', () => {
    expect(soDigitos('36.312.056/0005-52')).toBe('36312056000552')
    expect(soDigitos(null)).toBe('')
    expect(soDigitos(undefined)).toBe('')
  })
})

describe('formatarDocumento', () => {
  it('formata CNPJ (14) e CPF (11)', () => {
    expect(formatarDocumento('36312056000552')).toBe('36.312.056/0005-52')
    expect(formatarDocumento('12345678901')).toBe('123.456.789-01')
  })
  it('ja formatado -> reformata igual', () => {
    expect(formatarDocumento('36.312.056/0005-52')).toBe('36.312.056/0005-52')
  })
  it('tamanho estranho/vazio -> devolve os digitos', () => {
    expect(formatarDocumento('123')).toBe('123')
    expect(formatarDocumento('')).toBe('')
    expect(formatarDocumento(null)).toBe('')
  })
})

describe('mascaras progressivas', () => {
  it('mascararCNPJ progressivo e capado em 14', () => {
    expect(mascararCNPJ('36')).toBe('36')
    expect(mascararCNPJ('36312')).toBe('36.312')
    expect(mascararCNPJ('363120560005')).toBe('36.312.056/0005')
    expect(mascararCNPJ('3631205600055299')).toBe('36.312.056/0005-52') // capa em 14
  })
  it('mascararCPF progressivo e capado em 11', () => {
    expect(mascararCPF('123')).toBe('123')
    expect(mascararCPF('1234567')).toBe('123.456.7')
    expect(mascararCPF('123456789012')).toBe('123.456.789-01') // capa em 11
  })
})
