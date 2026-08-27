import { describe, it, expect } from 'vitest'
import { formatarMoeda } from './moeda'

describe('formatarMoeda', () => {
  it('usa separador de milhar e duas casas', () => {
    expect(formatarMoeda(1234.5)).toBe('1.234,50')
  })

  it('mantem as duas casas em valor redondo', () => {
    expect(formatarMoeda(790)).toBe('790,00')
  })

  it('arredonda para duas casas', () => {
    expect(formatarMoeda(0.125)).toBe('0,13')
  })
})
