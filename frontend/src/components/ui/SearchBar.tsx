import { type FormEvent, type ReactNode } from 'react'
import { Input } from './Input'
import { Button } from './Button'

interface SearchBarProps {
  value: string
  onChange: (valor: string) => void
  onSubmit: (e: FormEvent) => void
  placeholder?: string
  id?: string
  /** Filtros exibidos na mesma linha da busca, antes do campo (ex.: um select). */
  antes?: ReactNode
  /** Filtros e alternadores exibidos abaixo da busca, alinhados à esquerda. */
  abaixo?: ReactNode
}

/**
 * Barra de busca padrão: campo ocupando toda a largura + botão "Buscar" ao final,
 * e uma linha opcional abaixo (à esquerda) para selects/toggles.
 */
export function SearchBar({ value, onChange, onSubmit, placeholder, id = 'busca', antes, abaixo }: SearchBarProps) {
  return (
    <div className="space-y-3">
      <form onSubmit={onSubmit} className="flex items-end gap-2">
        {antes}
        <div className="flex-1">
          <Input
            id={id}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
          />
        </div>
        <Button type="submit" variant="secondary" className="shrink-0 py-2.5">Buscar</Button>
      </form>
      {abaixo && <div className="flex flex-wrap items-end gap-4">{abaixo}</div>}
    </div>
  )
}
