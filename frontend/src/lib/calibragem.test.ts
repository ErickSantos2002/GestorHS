import { describe, it, expect } from 'vitest'
import { mediaTestes } from './calibragem'

describe('mediaTestes', () => {
  it('média com 3 casas decimais (caso do certificado)', () => {
    expect(mediaTestes('0,186', '0,183', '0,183')).toBe('0,184')
  })

  it('remove zeros à direita (não força 3 casas)', () => {
    expect(mediaTestes('0,18', '0,18', '0,18')).toBe('0,18')
    expect(mediaTestes('0,10', '0,11', '0,12')).toBe('0,11')
  })

  it('aceita ponto ou vírgula na entrada e devolve com vírgula', () => {
    expect(mediaTestes('0.187', '0.183', '0.183')).toBe('0,184')
  })

  it('vazio quando falta algum teste', () => {
    expect(mediaTestes('0,186', '', '0,183')).toBe('')
  })

  it('vazio quando algum teste não é número', () => {
    expect(mediaTestes('0,186', 'abc', '0,183')).toBe('')
  })
})
