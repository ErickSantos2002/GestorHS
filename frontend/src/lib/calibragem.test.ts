import { describe, it, expect } from 'vitest'
import { mediaTestes, mediaTestesPreenchidas } from './calibragem'

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

describe('mediaTestesPreenchidas', () => {
  it('ignora as medições em branco — OS antiga com 3 das 5 continua tendo média', () => {
    expect(mediaTestesPreenchidas('0,10', '0,20', '0,30', '', '')).toBe('0,2')
  })

  it('usa as cinco quando as cinco estão preenchidas', () => {
    expect(mediaTestesPreenchidas('0,16', '0,16', '0,16', '0,16', '0,16')).toBe('0,16')
  })

  it('vazio quando não há nenhuma medição', () => {
    expect(mediaTestesPreenchidas('', '', '', '', '')).toBe('')
  })

  it('vazio quando uma das preenchidas não é número', () => {
    expect(mediaTestesPreenchidas('0,16', 'abc', '', '', '')).toBe('')
  })
})
