import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Toggle } from './Toggle'

describe('Toggle', () => {
  it('dispara onChange com o valor invertido', async () => {
    const onChange = vi.fn()
    render(<Toggle checked={false} onChange={onChange} label="Ativo" />)
    await userEvent.click(screen.getByRole('switch'))
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('desabilitado nao dispara onChange', async () => {
    const onChange = vi.fn()
    render(<Toggle checked={false} onChange={onChange} label="Ativo" disabled />)
    const sw = screen.getByRole('switch')
    expect(sw).toBeDisabled()
    await userEvent.click(sw)
    expect(onChange).not.toHaveBeenCalled()
  })

  it('sem a prop disabled continua habilitado (default das telas que ja usam)', () => {
    render(<Toggle checked onChange={() => {}} label="Ativo" />)
    expect(screen.getByRole('switch')).not.toBeDisabled()
  })
})
