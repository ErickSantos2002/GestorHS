import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { IconButton } from './IconButton'
import { IconTrash } from './icons'

describe('IconButton', () => {
  it('desabilitado nao dispara onClick e fica com o atributo disabled', () => {
    const onClick = vi.fn()
    render(
      <IconButton label="Excluir" tone="excluir" onClick={onClick} disabled>
        <IconTrash className="w-4 h-4" />
      </IconButton>,
    )
    const botao = screen.getByRole('button', { name: /excluir/i })
    expect(botao).toBeDisabled()
    fireEvent.click(botao)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('sem disabled mantem o comportamento normal', () => {
    const onClick = vi.fn()
    render(
      <IconButton label="Excluir" tone="excluir" onClick={onClick}>
        <IconTrash className="w-4 h-4" />
      </IconButton>,
    )
    const botao = screen.getByRole('button', { name: /excluir/i })
    expect(botao).not.toBeDisabled()
    fireEvent.click(botao)
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})
