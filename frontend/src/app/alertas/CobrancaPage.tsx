import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { podeRegistrarContato } from '../../auth/roles'
import { alertasApi, formatData, type AlertaItem } from './api'
import { PageContainer } from '../../components/ui/Page'
import { IconButton, IconButtonGroup } from '../../components/ui/IconButton'
import { IconEye, IconPhone } from '../../components/ui/icons'

const LIMITE = 25

export function CobrancaPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const podeContato = podeRegistrarContato(user)
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [ocultar, setOcultar] = useState(false)
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<AlertaItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    alertasApi
      .listar({ q: busca || undefined, ocultar_recentes: ocultar, offset, limit: LIMITE })
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
  }, [busca, ocultar, offset])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(termo.trim())
  }

  async function contato(item: AlertaItem) {
    setErro('')
    try {
      const r = await alertasApi.registrarContato(item.cliente)
      setItens((prev) => prev?.map((i) => (i.cliente === item.cliente ? { ...i, ult_contato: r.ult_contato } : i)) ?? prev)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao registrar contato')
    }
  }

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <PageContainer>
      <h1 className="text-2xl font-extrabold text-slate-100">Cobrança</h1>

      <div className="flex flex-wrap gap-3 items-end">
        <form onSubmit={onBuscar} className="flex gap-2 items-end flex-1 min-w-60">
          <div className="flex-1"><Input id="busca" label="Buscar cliente" value={termo} onChange={(e) => setTermo(e.target.value)} /></div>
          <Button type="submit" variant="secondary">Buscar</Button>
        </form>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={ocultar} onChange={(e) => { setOffset(0); setOcultar(e.target.checked) }} className="accent-primary" />
          Ocultar contatados (30 dias)
        </label>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum cliente com pendências.</p>
      ) : (
        <>
          <Table head={<><TH>Cliente</TH><TH>Vencidos</TH><TH>Vencendo</TH><TH>Venc. mais antigo</TH><TH>Último contato</TH><TH>Ações</TH></>}>
            {itens.map((i) => (
              <tr key={i.cliente} className="hover:bg-background-elevated transition-colors">
                <TD>{i.cliente_nome ?? `#${i.cliente}`}</TD>
                <TD>{i.vencidos > 0 ? <Badge tone="danger">{String(i.vencidos)}</Badge> : '—'}</TD>
                <TD>{i.vencendo > 0 ? <Badge tone="warning">{String(i.vencendo)}</Badge> : '—'}</TD>
                <TD>{formatData(i.prox_antiga)}</TD>
                <TD>{formatData(i.ult_contato)}</TD>
                <TD>
                  <IconButtonGroup>
                    <IconButton label="Ver equipamentos" tone="ver" onClick={() => navigate(`/app/clientes/${i.cliente}/equipamentos`)}>
                      <IconEye className="w-4 h-4" />
                    </IconButton>
                    {podeContato && (
                      <IconButton label="Registrar contato" tone="ok" onClick={() => contato(i)}>
                        <IconPhone className="w-4 h-4" />
                      </IconButton>
                    )}
                  </IconButtonGroup>
                </TD>
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
    </PageContainer>
  )
}
