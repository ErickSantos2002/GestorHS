import { describe, it, expect } from 'vitest'
import { cn, formatData } from './utils'

describe('cn', () => {
  it('junta classes', () => {
    expect(cn('a', 'b')).toBe('a b')
  })
  it('aplica classes condicionais', () => {
    const incluirB: boolean = false
    expect(cn('a', incluirB && 'b', 'c')).toBe('a c')
  })
  it('faz dedupe de conflitos do tailwind (last wins)', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })
})

describe('formatData', () => {
  it('nula -> travessao', () => {
    expect(formatData(null)).toBe('—')
  })
  it('data sem hora nao desloca para o dia anterior', () => {
    expect(formatData('2027-03-12')).toBe('12/03/2027')
  })
  it('datetime com offset e formatada como dd/mm/aaaa', () => {
    expect(formatData('2026-06-16T12:00:00Z')).toMatch(/^\d{2}\/\d{2}\/\d{4}$/)
  })
  it('string invalida -> travessao', () => {
    expect(formatData('nao-e-data')).toBe('—')
  })
})
