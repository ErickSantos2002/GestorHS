import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useCrud } from './useCrud'
import { ApiError } from '../../lib/api'

describe('useCrud', () => {
  it('carrega itens no mount', async () => {
    const client = { listar: vi.fn().mockResolvedValue([{ id: 1 }, { id: 2 }]) }
    const { result } = renderHook(() => useCrud(client))
    await waitFor(() => expect(result.current.itens).not.toBeNull())
    expect(result.current.itens).toHaveLength(2)
    expect(result.current.erro).toBe('')
  })

  it('expõe erro quando listar falha', async () => {
    const client = { listar: vi.fn().mockRejectedValue(new ApiError(500, 'boom')) }
    const { result } = renderHook(() => useCrud(client))
    await waitFor(() => expect(result.current.erro).toBe('boom'))
    expect(result.current.itens).toEqual([])
  })

  it('recarregar busca de novo', async () => {
    const client = { listar: vi.fn().mockResolvedValue([{ id: 1 }]) }
    const { result } = renderHook(() => useCrud(client))
    await waitFor(() => expect(result.current.itens).toHaveLength(1))
    client.listar.mockResolvedValue([{ id: 1 }, { id: 2 }])
    await act(async () => {
      await result.current.recarregar()
    })
    expect(result.current.itens).toHaveLength(2)
  })
})
