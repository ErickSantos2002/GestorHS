import { describe, it, expect } from 'vitest'
import { cn } from './utils'

describe('cn', () => {
  it('junta classes', () => {
    expect(cn('a', 'b')).toBe('a b')
  })
  it('aplica classes condicionais', () => {
    expect(cn('a', false && 'b', 'c')).toBe('a c')
  })
  it('faz dedupe de conflitos do tailwind (last wins)', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })
})
