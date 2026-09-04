import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let mockUser: { funcao: string } | null = { funcao: 'Administrador' }
vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}))

const { obter, logs, certificados, editar, editarObservacoes } = vi.hoisted(() => ({
  obter: vi.fn(), logs: vi.fn(), certificados: vi.fn(), editar: vi.fn(), editarObservacoes: vi.fn(),
}))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return {
    ...real,
    ordensApi: { ...real.ordensApi, obter, logs, certificados, editar, editarObservacoes },
    fotosApi: { ...real.fotosApi, listar: vi.fn().mockResolvedValue([]) },
  }
})

import { OrdemDetailPage } from './OrdemDetailPage'

function baseOs(over: Record<string, unknown> = {}) {
  return {
    id: 500, cliente: 1, cliente_nome: 'ACME', equipamento_cliente: 1,
    equipamento_descricao: 'IBLOW10D', equipamento_serie: 'SN-1', fase: 4,
    fase_descricao: 'Recebido', fase_cor: 'abc123', tipo_servico: 'C',
    data_chegada: null, prox_calibragem: null, situacao: 'A', caixa: null,
    condicao_chegada: null, acessorios: null, aceite: false, recebido: true,
    etiqueta: null, cod_retorno: null, obs: null, data_calibracao: null,
    data_retorno: null, data_aceite: null, tipo_calibragem: null,
    calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null,
    calib_teste2: null, calib_teste3: null, calib_teste_media: null,
    calib_situacao: null, pdf_certificado: null, nota_fiscal: null,
    nota_fiscal_numero: null, notas_fiscais: [], certificado_modelos_faltantes: [], pilhas: 0,
    bocais: 0, checklist_ids: [], acessorios_presentes: [], garantias: null,
    desfecho_lab: null, desfecho_lab_obs: null,
    ...over,
  }
}

function tela() {
  return render(
    <MemoryRouter initialEntries={['/app/ordens/500']}>
      <Routes><Route path="/app/ordens/:id" element={<OrdemDetailPage />} /></Routes>
    </MemoryRouter>,
  )
}

describe('OrdemDetailPage — Observações', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Administrador' }
    obter.mockReset(); logs.mockReset(); certificados.mockReset()
    editar.mockReset(); editarObservacoes.mockReset()
    logs.mockResolvedValue([])
    certificados.mockResolvedValue([])
  })

  it('mostra a secao Observacoes mesmo quando a OS nao tem observacao', async () => {
    obter.mockResolvedValue(baseOs({ obs: null }))
    tela()
    expect(await screen.findByRole('heading', { name: 'Observações' })).toBeInTheDocument()
  })

  it('a secao Observacoes fica entre Recebimento e Fotos', async () => {
    obter.mockResolvedValue(baseOs({ obs: null }))
    tela()
    await screen.findByRole('heading', { name: 'Observações' })
    const recebimento = screen.getByRole('heading', { name: 'Recebimento' })
    const observacoes = screen.getByRole('heading', { name: 'Observações' })
    const fotos = screen.getByRole('heading', { name: 'Fotos' })
    // DOCUMENT_POSITION_FOLLOWING = 4: o segundo elemento vem DEPOIS do primeiro
    expect(recebimento.compareDocumentPosition(observacoes) & 4).toBeTruthy()
    expect(observacoes.compareDocumentPosition(fotos) & 4).toBeTruthy()
  })

  it('o botao Salvar nasce desabilitado e habilita quando o texto muda', async () => {
    obter.mockResolvedValue(baseOs({ obs: null }))
    tela()
    const campo = await screen.findByLabelText('Observações')
    const botao = screen.getByRole('button', { name: /salvar observações/i })
    expect(botao).toBeDisabled()
    await userEvent.type(campo, 'veio sem tampa')
    expect(botao).not.toBeDisabled()
  })

  it('salvar manda o texto digitado para a API', async () => {
    obter.mockResolvedValue(baseOs({ obs: null }))
    editarObservacoes.mockResolvedValue(baseOs({ obs: 'veio sem tampa' }))
    tela()
    const campo = await screen.findByLabelText('Observações')
    await userEvent.type(campo, 'veio sem tampa')
    await userEvent.click(screen.getByRole('button', { name: /salvar observações/i }))
    expect(editarObservacoes).toHaveBeenCalledWith(expect.any(Number), 'veio sem tampa')
  })

  it('o botao volta a desabilitar depois de um salvamento sem efeito (so espaco a mais)', async () => {
    // Regressao do achado 1: se o usuario so acrescenta espaco ao final de uma
    // observacao ja salva, o servidor normaliza (trim) e devolve o MESMO valor
    // que ja estava em os.obs. Sem sincronizar obsTexto a partir da resposta,
    // o botao ficaria aceso para sempre (o efeito de sync so dispara quando
    // os.obs muda, e aqui ele nao muda).
    obter.mockResolvedValue(baseOs({ obs: 'nota' }))
    editarObservacoes.mockResolvedValue(baseOs({ obs: 'nota' }))
    tela()
    const campo = await screen.findByDisplayValue('nota')
    const botao = screen.getByRole('button', { name: /salvar observações/i })
    expect(botao).toBeDisabled()
    await userEvent.type(campo, ' ')
    expect(botao).not.toBeDisabled()
    await userEvent.click(botao)
    expect(await screen.findByDisplayValue('nota')).toBeInTheDocument()
    expect(botao).toBeDisabled()
  })

  it('o textarea fica desabilitado enquanto o salvamento esta em andamento', async () => {
    // Regressao do achado 2: se o campo continuar editavel durante o PATCH,
    // o setOs(atualizado) ao final sobrescreve o textarea e descarta o que
    // a pessoa tiver digitado nesse meio-tempo.
    obter.mockResolvedValue(baseOs({ obs: null }))
    let liberar: (v: ReturnType<typeof baseOs>) => void = () => {}
    editarObservacoes.mockImplementation(() => new Promise((resolve) => { liberar = resolve }))
    tela()
    const campo = await screen.findByLabelText('Observações')
    const botao = screen.getByRole('button', { name: /salvar observações/i })
    await userEvent.type(campo, 'em andamento')
    expect(campo).not.toBeDisabled()
    await userEvent.click(botao)
    expect(campo).toBeDisabled()
    liberar(baseOs({ obs: 'em andamento' }))
    await screen.findByDisplayValue('em andamento')
    expect(campo).not.toBeDisabled()
  })

  it('a observacao aparece uma unica vez na pagina', async () => {
    obter.mockResolvedValue(baseOs({ obs: 'anotacao existente' }))
    tela()
    // O <textarea> controlado as vezes reflete o valor inicial no textContent
    // (comportamento legitimo do React/JSDOM ao montar com valor ja sincronizado)
    // e as vezes so na propriedade .value — os dois sao corretos e nao indicam
    // duplicacao. Por isso esperamos o campo sincronizar via findByDisplayValue
    // e, na checagem de duplicidade, ignoramos o proprio textarea: o que nao
    // pode existir e um SEGUNDO elemento (o antigo bloco dt/dd) com o mesmo texto.
    await screen.findByDisplayValue('anotacao existente')
    const fora = screen.queryAllByText('anotacao existente').filter((el) => el.tagName !== 'TEXTAREA')
    expect(fora).toHaveLength(0)
  })
})
