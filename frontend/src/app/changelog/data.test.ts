import { describe, it, expect } from 'vitest'
import { CHANGELOG, VERSAO_ATUAL, TIPO_MUDANCA } from './data'

describe('app/changelog/data', () => {
  it('VERSAO_ATUAL é a primeira (mais nova) entrada', () => {
    expect(VERSAO_ATUAL).toBe(CHANGELOG[0].versao)
  })

  it('toda versão tem ao menos um item e versão/data preenchidas', () => {
    for (const v of CHANGELOG) {
      expect(v.versao).toBeTruthy()
      expect(v.data).toMatch(/^\d{2}\/\d{2}\/\d{4}$/)
      expect(v.itens.length).toBeGreaterThan(0)
    }
  })

  it('todo item usa um tipo de mudança válido', () => {
    const validos = Object.keys(TIPO_MUDANCA)
    for (const v of CHANGELOG) {
      for (const item of v.itens) {
        expect(validos).toContain(item.tipo)
        expect(item.texto.trim().length).toBeGreaterThan(0)
      }
    }
  })
})
