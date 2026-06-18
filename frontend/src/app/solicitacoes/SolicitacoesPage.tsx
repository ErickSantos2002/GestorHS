import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { podeAtenderSolicitacao } from '../../auth/roles'
import { solicitacoesApi, STATUS_SOLIC, formatData, type SolicitacaoItem } from './api'
import { PageContainer } from '../../components/ui/Page'

const LIMITE = 25

export function SolicitacoesPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const podeAtender = podeAtenderSolicitacao(user)
  const [status, setStatus] = useState('pendente')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<SolicitacaoItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    solicitacoesApi.listar({ status: status || undefined, offset, limit: LIMITE })
      .then((p) => { if (!ativo) return; setItens(p.items); setTotal(p.total) })
      .catch((e) => { if (!ativo) return; setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) })
    return () => { ativo = false }
  }, [status, offset])

  async function atender(item: SolicitacaoItem) {
    setErro('')
    try {
      const atualizada = await solicitacoesApi.atender(item.id)
      setItens((prev) => prev?.map((i) => (i.id === atualizada.id ? atualizada : i)) ?? prev)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao atender')
    }
  }

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <PageContainer>
      <h1 className="text-2xl font-extrabold text-slate-100">Solicitações</h1>
      <div className="w-52">
        <Select id="status" label="Status" value={status} onChange={(e) => { setOffset(0); setStatus(e.target.value) }}>
          <option value="">Todas</option>
          <option value="pendente">Pendentes</option>
          <option value="atendida">Atendidas</option>
        </Select>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma solicitação.</p>
      ) : (
        <>
          <Table head={<><TH>Cliente</TH><TH>Aparelho</TH><TH>Data</TH><TH>Status</TH><TH>Atendido por</TH><TH>Ações</TH></>}>
            {itens.map((s) => {
              const st = STATUS_SOLIC[s.status] ?? STATUS_SOLIC.pendente
              return (
                <tr key={s.id} className="hover:bg-background-elevated transition-colors">
                  <TD>{s.cliente_nome ?? `#${s.cliente}`}</TD>
                  <TD>{s.equipamento_descricao ?? '—'}</TD>
                  <TD>{formatData(s.data_solicitacao)}</TD>
                  <TD><Badge tone={st.tone}>{st.label}</Badge></TD>
                  <TD>{s.atendido_por_nome ?? '—'}</TD>
                  <TD>
                    <div className="flex gap-3">
                      <button onClick={() => navigate(`/app/equipamentos?cliente=${s.cliente}`)} className="text-xs text-primary hover:underline">Ver equipamentos</button>
                      {podeAtender && s.status === 'pendente' && (
                        <button onClick={() => atender(s)} className="text-xs text-primary hover:underline">Marcar como atendida</button>
                      )}
                    </div>
                  </TD>
                </tr>
              )
            })}
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
