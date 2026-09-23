import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SeloTiny } from './SeloTiny'

describe('SeloTiny', () => {
  it('enviada mostra o rótulo e o id do contato', () => {
    render(<SeloTiny tiny_id={610662219} tiny_status="enviada" tiny_erro={null} />)
    expect(screen.getByText('Enviada')).toBeInTheDocument()
    expect(screen.getByText('610662219')).toBeInTheDocument()
  })

  it('erro traz a mensagem no title', () => {
    render(<SeloTiny tiny_id={null} tiny_status="erro" tiny_erro="Cidade não encontrada" />)
    expect(screen.getByText('Erro')).toHaveAttribute('title', 'Cidade não encontrada')
  })

  it('pendente mostra o rótulo', () => {
    render(<SeloTiny tiny_id={null} tiny_status="pendente" tiny_erro={null} />)
    expect(screen.getByText('Pendente')).toBeInTheDocument()
  })

  it('sem status não renderiza nada', () => {
    const { container } = render(<SeloTiny tiny_id={null} tiny_status={null} tiny_erro={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
