import { useEffect, useState } from 'react'
import { Select } from '../../components/ui/Select'
import { equipamentosApi } from '../cadastros/api'

interface Opcao { id: number; descricao: string | null }

/** Select de modelo do catálogo (`equipamentos`). Usado na frota ("Modelo") e na
 * lista de clientes ("Tem aparelho"). Falha ao carregar o catálogo não quebra a
 * página: o filtro só fica com "Todos". */
export function FiltroModelo({ id, label, valor, onChange }: {
  id: string
  label: string
  valor: number | undefined
  onChange: (equipamento: number | undefined) => void
}) {
  const [opcoes, setOpcoes] = useState<Opcao[]>([])

  useEffect(() => {
    let vivo = true
    equipamentosApi
      .listar()
      .then((lista) => {
        if (!vivo) return
        setOpcoes(
          [...lista].sort((a, b) => (a.descricao ?? '').localeCompare(b.descricao ?? '', 'pt-BR')),
        )
      })
      .catch(() => { /* sem catálogo, sem filtro */ })
    return () => { vivo = false }
  }, [])

  return (
    <Select
      id={id}
      label={label}
      value={valor === undefined ? '' : String(valor)}
      onChange={(e) => onChange(e.target.value === '' ? undefined : Number(e.target.value))}
    >
      <option value="">Todos</option>
      {opcoes.map((o) => (
        <option key={o.id} value={o.id}>{o.descricao ?? `#${o.id}`}</option>
      ))}
    </Select>
  )
}
