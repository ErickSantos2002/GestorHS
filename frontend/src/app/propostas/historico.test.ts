import { describe, it, expect } from 'vitest'
import { diffSnapshots, coerceSnapshot, type Snapshot } from './historico'

const ITEM = { descricao: 'Calibração', sku: 'CAL', quantidade: 1, unidade: 'Unid', preco_un: 100, total: 100 }

const BASE: Snapshot = {
  numero: 1,
  data: '2026-07-20',
  cliente_nome: 'Cliente X',
  cliente_documento: '11.111.111/0001-11',
  total: 100,
  total_itens: 100,
  desconto: 0,
  frete: 0,
  itens: [ITEM],
}

describe('diffSnapshots', () => {
  it('detecta mudança de frete', () => {
    const atual: Snapshot = { ...BASE, frete: 250, total: 350 }
    const diff = diffSnapshots({ ...BASE, frete: 200, total: 300 }, atual)
    expect(diff).toContain('Frete: 200,00 → 250,00')
  })

  it('detecta mudança de desconto', () => {
    const diff = diffSnapshots(BASE, { ...BASE, desconto: 30, total: 70 })
    expect(diff).toContain('Desconto: 0,00 → 30,00')
  })

  it('detecta item adicionado', () => {
    const novo = { descricao: 'Manutenção', sku: null, quantidade: 2, unidade: 'Unid', preco_un: 50, total: 100 }
    const diff = diffSnapshots(BASE, { ...BASE, itens: [ITEM, novo], total: 200, total_itens: 200 })
    expect(diff).toContain('Item adicionado: Manutenção ×2')
  })

  it('detecta item removido', () => {
    const diff = diffSnapshots(BASE, { ...BASE, itens: [], total: 0, total_itens: 0 })
    expect(diff).toContain('Item removido: Calibração ×1')
  })

  it('detecta mudança de quantidade de um item existente', () => {
    const diff = diffSnapshots(BASE, {
      ...BASE,
      itens: [{ ...ITEM, quantidade: 3, total: 300 }],
      total: 300,
      total_itens: 300,
    })
    expect(diff).toContain('Quantidade de "Calibração": 1 → 3')
  })

  it('retorna lista vazia quando nada muda', () => {
    expect(diffSnapshots(BASE, { ...BASE })).toEqual([])
  })
})

describe('coerceSnapshot', () => {
  it('normaliza um snapshot cru do backend', () => {
    const raw = { numero: 5, frete: '10', desconto: 0, total: 110, total_itens: 100, itens: [{ descricao: 'A', quantidade: '2', preco_un: '50', total: '100' }] }
    const s = coerceSnapshot(raw)
    expect(s?.numero).toBe(5)
    expect(s?.frete).toBe(10)
    expect(s?.itens[0]).toMatchObject({ descricao: 'A', quantidade: 2, preco_un: 50 })
  })

  it('retorna null para entrada sem dados', () => {
    expect(coerceSnapshot(null)).toBeNull()
  })
})
