import { describe, it, expect } from 'vitest'
import { comporResumo } from './manutencao'

// Espelha compor_resumo do backend (app/core/manutencao.py): o modal precisa
// mostrar o resumo composto ANTES de salvar, sem ida ao servidor.
describe('comporResumo', () => {
  it('junta as frases na ordem, com ponto entre elas', () => {
    expect(comporResumo(['Primeira frase', 'Segunda frase'])).toBe('Primeira frase. Segunda frase.')
  })

  it('nao duplica o ponto que ja existe', () => {
    expect(comporResumo(['Primeira frase.', 'Segunda frase.'])).toBe('Primeira frase. Segunda frase.')
  })

  it('ignora frases vazias', () => {
    expect(comporResumo(['', '  ', 'Única.'])).toBe('Única.')
  })

  it('sem frases devolve vazio', () => {
    expect(comporResumo([])).toBe('')
  })
})
