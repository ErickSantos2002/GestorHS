import { describe, it, expect } from 'vitest'
import { podeCancelarOS, podeGerenciarCertificadosGerais } from './roles'

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

describe('podeCancelarOS', () => {
  it('libera so o Administrador', () => {
    expect(podeCancelarOS(u('Administrador'), 5)).toBe(true)
    expect(podeCancelarOS(u('Laboratório'), 5)).toBe(false)
    expect(podeCancelarOS(u('Expedição'), 5)).toBe(false)
    expect(podeCancelarOS(null, 5)).toBe(false)
  })
  it('so em fase ativa — cancelada e finalizada ja passaram do ponto', () => {
    expect(podeCancelarOS(u('Administrador'), 10)).toBe(true)
    expect(podeCancelarOS(u('Administrador'), 9)).toBe(false)
    expect(podeCancelarOS(u('Administrador'), 8)).toBe(false)
    expect(podeCancelarOS(u('Administrador'), null)).toBe(false)
  })
})
