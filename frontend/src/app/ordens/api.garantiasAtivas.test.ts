import { describe, it, expect } from 'vitest'
import { garantiasAtivas, type Garantias } from './api'

const item = (estado: 'em_garantia' | 'fora' | 'sem_registro') => ({
  estado,
  data_base: null,
  vence_em: null,
})

describe('garantiasAtivas', () => {
  it('retorna so as ativas, na ordem fixa', () => {
    const g: Garantias = {
      em_garantia: true,
      calibracao: item('em_garantia'),
      manutencao: item('fora'),
      compra: item('em_garantia'),
    }
    expect(garantiasAtivas(g)).toEqual(['Calibração', 'Compra'])
  })

  it('todas ativas -> os tres rotulos', () => {
    const g: Garantias = {
      em_garantia: true,
      calibracao: item('em_garantia'),
      manutencao: item('em_garantia'),
      compra: item('em_garantia'),
    }
    expect(garantiasAtivas(g)).toEqual(['Calibração', 'Manutenção', 'Compra'])
  })

  it('nenhuma ativa -> lista vazia', () => {
    const g: Garantias = {
      em_garantia: false,
      calibracao: item('fora'),
      manutencao: item('sem_registro'),
      compra: item('fora'),
    }
    expect(garantiasAtivas(g)).toEqual([])
  })
})
