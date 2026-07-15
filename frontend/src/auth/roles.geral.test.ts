import { describe, it, expect } from 'vitest'
import { podeGerenciarCertificadosGerais } from './roles'

const u = (funcao: string | null) => ({ funcao }) as never

describe('podeGerenciarCertificadosGerais', () => {
  it('libera admin, laboratorio e qualidade', () => {
    expect(podeGerenciarCertificadosGerais(u('Administrador'))).toBe(true)
    expect(podeGerenciarCertificadosGerais(u('Laboratório'))).toBe(true)
    expect(podeGerenciarCertificadosGerais(u('Qualidade'))).toBe(true)
  })
  it('bloqueia outras funcoes e null', () => {
    expect(podeGerenciarCertificadosGerais(u('Comercial Pós-Vendas'))).toBe(false)
    expect(podeGerenciarCertificadosGerais(null)).toBe(false)
  })
})
