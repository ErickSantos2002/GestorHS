import { useEffect, useState } from 'react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { IconSearch } from '../../components/ui/icons'
import { formatarDocumento, soDigitos } from '../../lib/documento'
import { destinatariosApi, type DestinatarioResultado } from '../empresas/api'

const inputClass = 'w-full pl-9 px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-transparent transition-colors'

/** Termo que é um documento completo digitado (só dígitos e pontuação). */
function documentoCompleto(termo: string): string | null {
  if (!/^[\d.\-/\s]+$/.test(termo)) return null
  const d = soDigitos(termo)
  return d.length === 11 || d.length === 14 ? d : null
}

export function DestinatarioBusca({ onEscolher, onCadastrarEmpresa }: {
  onEscolher: (r: DestinatarioResultado) => void
  onCadastrarEmpresa: (documento: string) => void
}) {
  const [termo, setTermo] = useState('')
  const [resultados, setResultados] = useState<DestinatarioResultado[] | null>(null)
  const [buscando, setBuscando] = useState(false)
  const [erro, setErro] = useState(false)

  useEffect(() => {
    const q = termo.trim()
    if (q.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResultados(null)
      setErro(false)
      return
    }
    let vivo = true
    setBuscando(true)
    setErro(false)
    destinatariosApi.buscar(q)
      .then((r) => { if (vivo) setResultados(r) })
      .catch(() => { if (vivo) { setErro(true); setResultados(null) } })
      .finally(() => { if (vivo) setBuscando(false) })
    return () => { vivo = false }
  }, [termo])

  const documento = documentoCompleto(termo)

  return (
    <div className="relative">
      <span className="absolute left-3 top-2.5 text-slate-500 pointer-events-none"><IconSearch className="w-4 h-4" /></span>
      <input value={termo} onChange={(e) => setTermo(e.target.value)} className={inputClass}
        placeholder="Buscar cliente ou empresa por nome, CNPJ ou CPF" />
      {buscando && <p className="mt-1 text-xs text-slate-500">Buscando…</p>}
      {!buscando && erro && <p className="mt-1 text-xs text-danger">Falha ao buscar. Tente de novo.</p>}
      {!buscando && resultados && resultados.length > 0 && (
        <ul className="mt-1.5 divide-y divide-border rounded-lg border border-border overflow-hidden max-h-60 overflow-y-auto">
          {resultados.map((r) => (
            <li key={`${r.tipo}-${r.id}`}>
              <button type="button" onClick={() => onEscolher(r)}
                className="w-full text-left px-3 py-2.5 text-sm hover:bg-background-elevated transition-colors">
                <span className="flex items-center gap-2">
                  <span className="font-semibold text-slate-200">{r.nome ?? `#${r.id}`}</span>
                  <Badge tone={r.tipo === 'cliente' ? 'primary' : 'info'}>
                    {r.tipo === 'cliente' ? 'Cliente' : r.matriz_nome ? `Empresa · matriz ${r.matriz_nome}` : 'Empresa · sem matriz'}
                  </Badge>
                </span>
                <span className="block text-xs text-slate-500">
                  {formatarDocumento(r.documento)}{r.municipio ? ` · ${r.municipio}/${r.estado ?? ''}` : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {!buscando && !erro && resultados && resultados.length === 0 && (
        <div className="mt-1.5 flex flex-wrap items-center gap-3">
          <p className="text-xs text-slate-500">Nenhum cliente ou empresa encontrado.</p>
          {documento && (
            <Button type="button" variant="secondary" onClick={() => onCadastrarEmpresa(documento)}>
              Cadastrar empresa com este documento
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
