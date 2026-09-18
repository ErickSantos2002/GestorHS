/**
 * Badge de Phoebus/Modulo no quadro de Ordens.
 *
 * O badge fala de COMPOSICAO da caixa, nao de desvio de fase: diz o que ela leva
 * dentro, e portanto que o card dela no TaskHS e' feito a mao. Desde 18/09/2026 so a
 * caixa 100% Modulo pula o Pos-Vendas, entao amarrar o badge ao Financeiro esconderia
 * a informacao justamente das caixas de Phoebus, que seguem o fluxo normal.
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

describe('badge de Phoebus/Modulo no quadro', () => {
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
    // 22 caixas na base. Desde 18/09/2026 elas passam pelo Pos-Vendas, nao pulam.
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

  it('mostra o badge fora do Financeiro tambem', async () => {
    // Phoebus+Modulo passa pelo Pos-Vendas como qualquer caixa, e no Laboratorio ou
    // no Pos-Vendas continua sendo util saber o que ela carrega.
    quadro.mockResolvedValue([{
      fase: 5, descricao: 'Laboratório', cor: 'abc', total: 1,
      caixas: [{ id: 900, cliente_nome: 'ACME', total_os: 1, prontos: 1,
                 pendentes: 0, modulo: 'ambos' }],
    }])
    tela()
    expect(await screen.findByText('CX 900')).toBeInTheDocument()
    expect(screen.getByText('Phoebus + Módulo')).toBeInTheDocument()
  })
})
