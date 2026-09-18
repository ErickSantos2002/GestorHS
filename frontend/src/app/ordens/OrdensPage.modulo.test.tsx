/**
 * Aviso de Phoebus/Modulo no quadro de Ordens, na coluna do Financeiro.
 *
 * Essas caixas chegam ao Financeiro SEM ter passado pelo Pos-Vendas (o fluxo delas
 * desvia em `os_workflow.PROXIMA_MODULO`), e quem recebe precisa saber por que. Os
 * tres casos sao distintos de proposito: so o aparelho, so o modulo, ou os dois.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { OrdensPage } from './OrdensPage'

const quadro = vi.fn()
vi.mock('../caixas/api', () => ({ caixasApi: { quadro: (...a: unknown[]) => quadro(...a) } }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, ordensApi: { listar: vi.fn().mockResolvedValue({ items: [], total: 0 }) } }
})

function tela() {
  return render(<MemoryRouter><OrdensPage /></MemoryRouter>)
}

function caixaNoFinanceiro(modulo: string | null) {
  return [{
    fase: 10, descricao: 'Financeiro', cor: 'a855f7', total: 1,
    caixas: [{ id: 1049, cliente_nome: 'CONSORCIO SAO BERNARDO', total_os: 3,
               prontos: 3, pendentes: 0, modulo }],
  }]
}

beforeEach(() => { quadro.mockReset() })

describe('aviso de Phoebus/Modulo no Financeiro', () => {
  it('mostra "Phoebus" quando a caixa so tem o aparelho', async () => {
    quadro.mockResolvedValue(caixaNoFinanceiro('phoebus'))
    tela()
    expect(await screen.findByText('Phoebus')).toBeInTheDocument()
  })

  it('mostra "Modulo" quando a caixa so tem o modulo', async () => {
    quadro.mockResolvedValue(caixaNoFinanceiro('modulo'))
    tela()
    expect(await screen.findByText('Módulo')).toBeInTheDocument()
  })

  it('mostra os dois quando a caixa leva aparelho e modulo juntos', async () => {
    // Caso mais comum no Financeiro: 7 das 8 caixas em 18/09/2026.
    quadro.mockResolvedValue(caixaNoFinanceiro('ambos'))
    tela()
    expect(await screen.findByText('Phoebus + Módulo')).toBeInTheDocument()
  })

  it('nao mostra aviso em caixa de aparelho comum', async () => {
    quadro.mockResolvedValue(caixaNoFinanceiro(null))
    tela()
    expect(await screen.findByText('CX 1049')).toBeInTheDocument()
    expect(screen.queryByText(/Phoebus|Módulo/)).toBeNull()
  })

  it('nao mostra aviso fora do Financeiro, mesmo sendo caixa de modulo', async () => {
    // O pedido foi especifico: e o Financeiro que recebe a caixa sem entender o
    // porque. Nas outras colunas o badge so poluiria.
    quadro.mockResolvedValue([{
      fase: 5, descricao: 'Laboratório', cor: 'abc', total: 1,
      caixas: [{ id: 900, cliente_nome: 'ACME', total_os: 1, prontos: 1,
                 pendentes: 0, modulo: 'ambos' }],
    }])
    tela()
    expect(await screen.findByText('CX 900')).toBeInTheDocument()
    expect(screen.queryByText(/Phoebus|Módulo/)).toBeNull()
  })
})
