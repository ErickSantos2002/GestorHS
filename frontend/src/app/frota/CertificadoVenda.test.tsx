import { describe, expect, it } from 'vitest'
import { podeGerarCertificadoVenda } from '../../auth/roles'

describe('podeGerarCertificadoVenda', () => {
  it('permite Administrador e Laboratorio', () => {
    expect(podeGerarCertificadoVenda({ funcao: 'Administrador' } as never)).toBe(true)
    expect(podeGerarCertificadoVenda({ funcao: 'Laboratório' } as never)).toBe(true)
  })

  it('bloqueia as demais funcoes e o usuario nulo', () => {
    expect(podeGerarCertificadoVenda({ funcao: 'Comercial Pós-Vendas' } as never)).toBe(false)
    expect(podeGerarCertificadoVenda({ funcao: 'Expedição' } as never)).toBe(false)
    expect(podeGerarCertificadoVenda(null)).toBe(false)
  })
})
