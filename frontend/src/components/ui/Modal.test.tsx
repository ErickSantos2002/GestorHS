import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Modal } from './Modal'

describe('Modal', () => {
  it('por padrao, clique no fundo fecha', () => {
    const onClose = vi.fn()
    render(<Modal open onClose={onClose} title="Teste"><p>conteudo</p></Modal>)

    fireEvent.click(screen.getByTestId('modal-backdrop'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('com closeOnBackdrop=false, clique no fundo nao fecha mas o X fecha', () => {
    const onClose = vi.fn()
    render(<Modal open onClose={onClose} title="Teste" closeOnBackdrop={false}><p>conteudo</p></Modal>)

    fireEvent.click(screen.getByTestId('modal-backdrop'))
    expect(onClose).not.toHaveBeenCalled()

    fireEvent.click(screen.getByLabelText('Fechar'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('clique dentro do conteudo nunca fecha', () => {
    const onClose = vi.fn()
    render(<Modal open onClose={onClose} title="Teste"><p>conteudo</p></Modal>)

    fireEvent.click(screen.getByText('conteudo'))
    expect(onClose).not.toHaveBeenCalled()
  })
})
