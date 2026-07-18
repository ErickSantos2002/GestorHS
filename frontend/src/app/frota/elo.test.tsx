import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))
const { obter } = vi.hoisted(() => ({ obter: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, equipamentosClienteApi: {
    obter,
    historico: () => Promise.resolve([]), ordens: () => Promise.resolve([]),
    certificados: () => Promise.resolve([]), transferencias: () => Promise.resolve([]),
  } }
})
vi.mock('../cadastros/api', () => ({ equipamentosApi: { listar: () => Promise.resolve([]) } }))

import { EquipamentoClienteDetailPage } from './EquipamentoClienteDetailPage'

const BASE = {
  id: 9, cliente: 5, cliente_nome: 'ACME', equipamento: 1, equipamento_descricao: 'Bafômetro X',
  modulo: 0, serie: 'SN', patrimonio: null, datacompra: null, ult_calibragem: null, prox_calibragem: null,
  ativo: true, status: 'A', status_calibracao: 'em_dia' as const, os_atual: null,
  calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null, calib_teste2: null, calib_teste3: null, calib_teste_media: null, calib_situacao: null,
  modulo_instalado: null, instalado_em: null, em_estoque: false,
}

function tela() {
  return render(
    <MemoryRouter initialEntries={['/app/equipamentos/9']}>
      <Routes>
        <Route path="/app/equipamentos/:id" element={<EquipamentoClienteDetailPage />} />
        <Route path="/app/equipamentos/:otherId" element={<div>ficha do outro</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('elo Phoebus-Módulo na ficha do equipamento', () => {
  beforeEach(() => {
    obter.mockReset()
  })

  it('mostra "Módulo instalado" quando o aparelho é um Phoebus com módulo instalado', async () => {
    obter.mockResolvedValue({
      ...BASE,
      modulo_instalado: { id: 9, serie: 'F004230', entrou_em: '2026-01-10', origem: 'instalacao' },
    })
    tela()
    expect(await screen.findByText('Módulo instalado')).toBeInTheDocument()
    expect(screen.getByText('F004230')).toBeInTheDocument()
    expect(screen.queryByText('Instalado em')).not.toBeInTheDocument()
    expect(screen.queryByText('No estoque')).not.toBeInTheDocument()
  })

  it('mostra "Instalado em" com série e cliente quando o aparelho é um módulo instalado num Phoebus', async () => {
    obter.mockResolvedValue({
      ...BASE,
      instalado_em: { id: 5, serie: 'WATFR01-00257', cliente_nome: 'Filial Norte', entrou_em: '2026-02-01', origem: 'instalacao' },
    })
    tela()
    expect(await screen.findByText('Instalado em')).toBeInTheDocument()
    expect(screen.getByText('WATFR01-00257')).toBeInTheDocument()
    expect(screen.getByText(/Filial Norte/)).toBeInTheDocument()
    expect(screen.queryByText('Módulo instalado')).not.toBeInTheDocument()
  })

  it('mostra "No estoque" quando o aparelho é um módulo sem instalação em aberto', async () => {
    obter.mockResolvedValue({
      ...BASE,
      modulo_instalado: null,
      instalado_em: null,
      em_estoque: true,
    })
    tela()
    expect(await screen.findByText('No estoque')).toBeInTheDocument()
    expect(screen.queryByText('Módulo instalado')).not.toBeInTheDocument()
    expect(screen.queryByText('Instalado em')).not.toBeInTheDocument()
  })

  it('não mostra nenhuma seção do elo quando não aplicável (não é módulo nem tem módulo instalado)', async () => {
    obter.mockResolvedValue({ ...BASE })
    tela()
    expect(await screen.findByText('Bafômetro X')).toBeInTheDocument()
    expect(screen.queryByText('Módulo instalado')).not.toBeInTheDocument()
    expect(screen.queryByText('Instalado em')).not.toBeInTheDocument()
    expect(screen.queryByText('No estoque')).not.toBeInTheDocument()
  })
})
