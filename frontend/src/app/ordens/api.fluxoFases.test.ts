import { describe, it, expect } from 'vitest'
import { FLUXO_FASES, posicaoFase, faseAtiva, posLaboratorio } from './api'

// A fase Financeiro tem id 10 — numericamente MAIOR que Preparando Retorno (7) e
// Finalizada (8). Qualquer comparacao de faixa (fase >= 4 && fase <= 7) quebra.
// Estes testes travam a ordem LOGICA, nao a numerica.

describe('FLUXO_FASES', () => {
  it('inclui o Financeiro entre Pos-Vendas e Preparando Retorno', () => {
    expect(FLUXO_FASES.map((f) => f.id)).toEqual([4, 5, 6, 10, 7, 8])
  })
})

describe('posicaoFase', () => {
  it('ordena pela sequencia logica, nao pelo id', () => {
    expect(posicaoFase(4)).toBeLessThan(posicaoFase(5))
    expect(posicaoFase(5)).toBeLessThan(posicaoFase(6))
    expect(posicaoFase(6)).toBeLessThan(posicaoFase(10)) // Pos-Vendas -> Financeiro
    expect(posicaoFase(10)).toBeLessThan(posicaoFase(7)) // Financeiro -> Preparando (10 vem ANTES do 7)
    expect(posicaoFase(7)).toBeLessThan(posicaoFase(8))
  })

  it('devolve -1 para fase desconhecida ou nula', () => {
    expect(posicaoFase(9)).toBe(-1) // cancelada nao esta no fluxo linear
    expect(posicaoFase(null)).toBe(-1)
    expect(posicaoFase(999)).toBe(-1)
  })
})

describe('faseAtiva', () => {
  it('considera o Financeiro uma fase ativa (bug: a faixa 4..7 excluia o 10)', () => {
    expect(faseAtiva(10)).toBe(true)
  })

  it('cobre as demais ativas e exclui as terminais', () => {
    expect([4, 5, 6, 7].every(faseAtiva)).toBe(true)
    expect(faseAtiva(8)).toBe(false) // finalizada
    expect(faseAtiva(9)).toBe(false) // cancelada
    expect(faseAtiva(null)).toBe(false)
  })
})

describe('posLaboratorio', () => {
  it('inclui o Financeiro (bug: a faixa 5..8 excluia o 10)', () => {
    expect(posLaboratorio(10)).toBe(true)
  })

  it('vale do laboratorio em diante e nao antes', () => {
    expect(posLaboratorio(4)).toBe(false) // recebido: ainda nao calibrou
    expect(posLaboratorio(5)).toBe(true)
    expect(posLaboratorio(6)).toBe(true)
    expect(posLaboratorio(7)).toBe(true)
    expect(posLaboratorio(8)).toBe(true)
    expect(posLaboratorio(9)).toBe(false) // cancelada
    expect(posLaboratorio(null)).toBe(false)
  })
})
