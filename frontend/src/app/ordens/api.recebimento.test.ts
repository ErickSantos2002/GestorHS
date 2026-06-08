import { describe, it, expect } from 'vitest'
import { CHECKLIST_ACESSORIOS, CONDICOES_CHEGADA } from './api'

describe('constantes de recebimento', () => {
  it('checklist tem 9 itens com ids 1..9', () => {
    expect(CHECKLIST_ACESSORIOS).toHaveLength(9)
    expect(CHECKLIST_ACESSORIOS[0]).toEqual({ id: 1, label: 'Bobinas' })
    expect(CHECKLIST_ACESSORIOS[8]).toEqual({ id: 9, label: 'Nf de Remessa' })
  })
  it('condições têm 5 opções', () => {
    expect(CONDICOES_CHEGADA).toEqual([
      'Bom estado', 'Com avarias', 'Oxidado', 'Lacrado', 'Sem acessórios',
    ])
  })
})
