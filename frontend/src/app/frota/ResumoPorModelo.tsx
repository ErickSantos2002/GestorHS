import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Spinner } from '../../components/ui/Spinner'
import { IconChevronDown } from '../../components/ui/icons'
import { ApiError } from '../../lib/api'
import { cn } from '../../lib/utils'
import { equipamentosClienteApi, type ResumoModelo } from './api'

/** "Quantos aparelhos de cada modelo temos, e em quantos clientes?" — só ativos,
 * sem o estoque da HS (mesmo critério do filtro "Tem aparelho" de Clientes).
 * Nasce fechado e só busca ao abrir, para não pesar a tela de Equipamentos. */
export function ResumoPorModelo() {
  const [aberto, setAberto] = useState(false)
  const [linhas, setLinhas] = useState<ResumoModelo[] | null>(null)
  const [erro, setErro] = useState('')

  function alternar() {
    const abrir = !aberto
    setAberto(abrir)
    if (abrir && linhas === null) {
      setErro('')
      equipamentosClienteApi
        .resumoPorModelo()
        .then(setLinhas)
        .catch((e) => {
          setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
          setLinhas([])
        })
    }
  }

  return (
    <section className="rounded-xl border border-border bg-background-card">
      <button
        type="button"
        onClick={alternar}
        aria-expanded={aberto}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-slate-200"
      >
        Aparelhos por modelo
        <IconChevronDown className={cn('w-4 h-4 text-slate-500 transition-transform', aberto && 'rotate-180')} />
      </button>
      {aberto && (
        <div className="px-4 pb-4">
          {erro && <p className="text-sm text-danger mb-2">{erro}</p>}
          {linhas === null ? (
            <div className="flex justify-center py-6"><Spinner className="w-6 h-6" /></div>
          ) : linhas.length === 0 ? (
            !erro && <p className="text-sm text-slate-500">Nenhum aparelho ativo.</p>
          ) : (
            <Table head={<><TH>Modelo</TH><TH>Aparelhos</TH><TH>Clientes</TH><TH>Ver</TH></>}>
              {linhas.map((l) => (
                <tr key={l.equipamento}>
                  <TD>{l.descricao ?? `#${l.equipamento}`}</TD>
                  <TD>{l.aparelhos}</TD>
                  <TD>{l.clientes}</TD>
                  <TD>
                    <div className="flex gap-3 text-xs font-semibold">
                      <Link className="text-primary hover:underline" to={`/app/equipamentos?equipamento=${l.equipamento}`}>Ver aparelhos</Link>
                      <Link className="text-primary hover:underline" to={`/app/clientes?equipamento=${l.equipamento}`}>Ver clientes</Link>
                    </div>
                  </TD>
                </tr>
              ))}
            </Table>
          )}
        </div>
      )}
    </section>
  )
}
