import { useEffect, useState } from 'react'
import { IconButton } from '../../components/ui/IconButton'
import { IconX } from '../../components/ui/icons'
import { formatarDocumento } from '../../lib/documento'
import { clientesApi, type ClienteListItem } from '../clientes/api'

export interface MatrizValor { id: number; nome: string | null }

const inputClass = 'w-full px-3 py-2.5 text-sm rounded-lg border border-border bg-background-elevated text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-colors'

/** Cliente matriz da Empresa (opcional): de onde vem a frota da proposta. */
export function MatrizSelect({ valor, onChange, disabled }: {
  valor: MatrizValor | null
  onChange: (v: MatrizValor | null) => void
  disabled?: boolean
}) {
  const [termo, setTermo] = useState('')
  const [resultados, setResultados] = useState<ClienteListItem[]>([])

  useEffect(() => {
    if (valor || termo.trim().length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResultados([])
      return
    }
    let vivo = true
    clientesApi.listar({ q: termo.trim(), limit: 10 })
      .then((r) => { if (vivo) setResultados(r.items) })
      .catch(() => { if (vivo) setResultados([]) })
    return () => { vivo = false }
  }, [termo, valor])

  return (
    <div className="sm:col-span-2">
      <label htmlFor="matriz-busca" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">
        Cliente matriz (opcional)
      </label>
      {valor ? (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-background-elevated px-3 py-2">
          <span className="truncate text-sm text-slate-200">{valor.nome ?? `Cliente #${valor.id}`}</span>
          {!disabled && (
            <IconButton label="Remover matriz" tone="excluir" onClick={() => onChange(null)}><IconX className="w-4 h-4" /></IconButton>
          )}
        </div>
      ) : (
        <>
          <input id="matriz-busca" value={termo} disabled={disabled} onChange={(e) => setTermo(e.target.value)}
            placeholder="Buscar cliente por nome, CNPJ ou série do aparelho" className={inputClass} />
          {resultados.length > 0 && (
            <ul className="mt-1.5 divide-y divide-border rounded-lg border border-border max-h-48 overflow-y-auto">
              {resultados.map((c) => (
                <li key={c.id}>
                  <button type="button" onClick={() => { onChange({ id: c.id, nome: c.nome }); setTermo('') }}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-background-elevated">
                    <span className="block font-semibold text-slate-200">{c.nome ?? `Cliente #${c.id}`}</span>
                    {(c.cgc || c.cpf) && <span className="block text-xs text-slate-500">{formatarDocumento(c.cgc || c.cpf)}</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
