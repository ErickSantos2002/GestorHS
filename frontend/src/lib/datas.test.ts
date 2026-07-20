import { describe, it, expect, vi, afterEach } from 'vitest'
import { dataISO, hojeISO, daquiAAnos } from './datas'

describe('datas locais', () => {
  afterEach(() => vi.useRealTimers())

  it('formata a data local como AAAA-MM-DD com zero a esquerda', () => {
    expect(dataISO(new Date(2026, 0, 5))).toBe('2026-01-05')
    expect(dataISO(new Date(2026, 11, 31))).toBe('2026-12-31')
  })

  it('hojeISO usa o dia LOCAL mesmo tarde da noite', () => {
    // Em UTC-3, 22h30 local ja e o dia seguinte em UTC: toISOString erraria aqui.
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 6, 20, 22, 30, 0))
    expect(hojeISO()).toBe('2026-07-20')
  })

  it('daquiAAnos soma no calendario local', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 6, 20, 22, 30, 0))
    expect(daquiAAnos(1)).toBe('2027-07-20')
  })
})
