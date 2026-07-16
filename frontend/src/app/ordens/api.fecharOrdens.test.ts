import { describe, it, expect, vi } from 'vitest'
import { podeFecharOS, fecharOrdens } from './api'
import { ApiError } from '../../lib/api'

describe('podeFecharOS', () => {
  it('só a fase que pede código de retorno (Preparando Retorno) é fechável', () => {
    expect(podeFecharOS(7)).toBe(true)   // Preparando Retorno
    expect(podeFecharOS(5)).toBe(false)  // Laboratório
    expect(podeFecharOS(8)).toBe(false)  // Finalizada
    expect(podeFecharOS(null)).toBe(false)
  })
})

describe('fecharOrdens', () => {
  it('chama avancar uma vez por id com o mesmo código e conta sucessos', async () => {
    const avancar = vi.fn().mockResolvedValue({})
    const r = await fecharOrdens([10, 11, 12], 'BR123', 'lote', avancar)
    expect(avancar).toHaveBeenCalledTimes(3)
    expect(avancar).toHaveBeenCalledWith(10, { cod_retorno: 'BR123', obs: 'lote' })
    expect(r.sucessos).toEqual([10, 11, 12])
    expect(r.falhas).toEqual([])
  })

  it('falha parcial não interrompe as demais e é reportada', async () => {
    const avancar = vi.fn()
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new ApiError(403, 'Acesso negado para sua função nesta fase'))
      .mockResolvedValueOnce({})
    const r = await fecharOrdens([1, 2, 3], 'BR9', null, avancar)
    expect(avancar).toHaveBeenCalledTimes(3)
    expect(r.sucessos).toEqual([1, 3])
    expect(r.falhas).toEqual([{ id: 2, motivo: 'Acesso negado para sua função nesta fase' }])
  })
})
