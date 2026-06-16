import { describe, it, expect } from 'vitest'
import { garantiaBadge, type GarantiaItem } from './api'

describe('garantiaBadge', () => {
  it('em_garantia -> verde com data de vencimento', () => {
    const item: GarantiaItem = { estado: 'em_garantia', data_base: '2026-03-12', vence_em: '2027-03-12' }
    expect(garantiaBadge(item)).toEqual({ label: 'Em garantia até 12/03/2027', tone: 'primary' })
  })

  it('fora -> cinza "Fora da garantia"', () => {
    const item: GarantiaItem = { estado: 'fora', data_base: '2020-01-01', vence_em: '2021-01-01' }
    expect(garantiaBadge(item)).toEqual({ label: 'Fora da garantia', tone: 'neutral' })
  })

  it('sem_registro -> cinza "Sem registro"', () => {
    const item: GarantiaItem = { estado: 'sem_registro', data_base: null, vence_em: null }
    expect(garantiaBadge(item)).toEqual({ label: 'Sem registro', tone: 'neutral' })
  })
})
