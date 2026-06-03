import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { clientesApi, type ClienteListItem } from './api'

const LIMITE = 25

export function ClientesPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<ClienteListItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    clientesApi
      .listar({ q: busca || undefined, offset, limit: LIMITE })
      .then((p) => {
        if (!ativo) return
        setItens(p.items)
        setTotal(p.total)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
        setItens([])
      })
    return () => {
      ativo = false
    }
  }, [busca, offset])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(termo.trim())
  }

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Clientes</h1>
        {isAdmin(user) && <Button onClick={() => navigate('/app/clientes/novo')}>Novo cliente</Button>}
      </div>

      <form onSubmit={onBuscar} className="flex gap-2 max-w-md">
        <Input id="busca" placeholder="Buscar por nome, CNPJ, CPF ou município" value={termo} onChange={(e) => setTermo(e.target.value)} />
        <Button type="submit" variant="secondary">Buscar</Button>
      </form>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum cliente encontrado.</p>
      ) : (
        <>
          <Table head={<><TH>Nome</TH><TH>CNPJ / CPF</TH><TH>Município/UF</TH><TH>Ativo</TH></>}>
            {itens.map((c) => (
              <tr key={c.id} className="hover:bg-background-elevated transition-colors cursor-pointer" onClick={() => navigate(`/app/clientes/${c.id}`)}>
                <TD>{c.nome ?? '—'}</TD>
                <TD>{c.cgc || c.cpf || '—'}</TD>
                <TD>{[c.municipio, c.estado].filter(Boolean).join(' / ') || '—'}</TD>
                <TD><Badge tone={c.ativo ? 'primary' : 'neutral'}>{c.ativo ? 'Ativo' : 'Inativo'}</Badge></TD>
              </tr>
            ))}
          </Table>
          <div className="flex items-center justify-between text-sm text-slate-400">
            <span>{inicio}–{fim} de {total}</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMITE))}>Anterior</Button>
              <Button variant="secondary" disabled={fim >= total} onClick={() => setOffset(offset + LIMITE)}>Próxima</Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
