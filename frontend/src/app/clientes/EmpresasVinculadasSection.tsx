import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatarDocumento } from '../../lib/documento'
import { empresasApi, type Empresa } from '../empresas/api'

/** Filiais cujo cliente matriz e' este. Sem nenhuma, o bloco nao aparece. */
export function EmpresasVinculadasSection({ clienteId }: { clienteId: number }) {
  const [empresas, setEmpresas] = useState<Empresa[]>([])

  useEffect(() => {
    let vivo = true
    empresasApi.listar({ cliente: clienteId, limit: 100 })
      .then((p) => { if (vivo) setEmpresas(p.items) })
      .catch(() => { if (vivo) setEmpresas([]) })
    return () => { vivo = false }
  }, [clienteId])

  if (empresas.length === 0) return null

  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-100">Empresas vinculadas</h2>
      <ul className="divide-y divide-border">
        {empresas.map((e) => (
          <li key={e.id} className="py-2">
            <Link to="/app/empresas" className="block text-sm font-semibold text-primary hover:underline">{e.nome}</Link>
            <span className="block text-xs text-slate-500">
              {formatarDocumento(e.cgc || e.cpf)}{e.municipio ? ` · ${e.municipio}/${e.estado ?? ''}` : ''}{e.ativo ? '' : ' · inativa'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
