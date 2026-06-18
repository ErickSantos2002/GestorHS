import { describe, it, expect } from 'vitest'
import { osAtiva, type OrdemListItem } from './api'

const os = (id: number, fase: number | null): OrdemListItem => ({
  id,
  cliente: 1,
  cliente_nome: null,
  equipamento_cliente: 1,
  equipamento_descricao: null,
  equipamento_serie: null,
  fase,
  fase_descricao: null,
  fase_cor: null,
  tipo_servico: null,
  data_chegada: null,
  prox_calibragem: null,
  situacao: 'E',
  caixa: null,
})

describe('osAtiva', () => {
  it('retorna a OS em fase ativa (4-7)', () => {
    const r = osAtiva([os(10, 8), os(11, 5), os(12, 9)])
    expect(r?.id).toBe(11)
  })

  it('ignora finalizadas (8) e canceladas (9)', () => {
    expect(osAtiva([os(10, 8), os(12, 9)])).toBeUndefined()
  })

  it('ignora fase nula e lista vazia', () => {
    expect(osAtiva([os(10, null)])).toBeUndefined()
    expect(osAtiva([])).toBeUndefined()
  })
})
