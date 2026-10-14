import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePorPagina } from './usePorPagina'

beforeEach(() => localStorage.clear())

describe('usePorPagina', () => {
  it('comeca no padrao quando nao ha nada guardado', () => {
    const { result } = renderHook(() => usePorPagina('teste', 15))
    expect(result.current[0]).toBe(15)
  })

  it('guarda a escolha por tabela e a recupera na proxima montagem', () => {
    const { result } = renderHook(() => usePorPagina('teste', 15))
    act(() => result.current[1](50))
    expect(result.current[0]).toBe(50)
    expect(renderHook(() => usePorPagina('teste', 15)).result.current[0]).toBe(50)
    expect(renderHook(() => usePorPagina('outra', 15)).result.current[0]).toBe(15)
  })

  it('ignora valor guardado fora das opcoes', () => {
    localStorage.setItem('gestorhs:porPagina:teste', '7')
    expect(renderHook(() => usePorPagina('teste', 15)).result.current[0]).toBe(15)
  })
})
