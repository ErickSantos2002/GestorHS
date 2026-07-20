import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarCadastros } from '../../auth/roles'
import { equipamentosClienteApi, STATUS_CALIBRACAO, type FrotaItem } from '../frota/api'

export function ClienteEquipamentosTab() {
  const { id } = useParams()
  const clienteId = Number(id)
  const navigate = useNavigate()
  const { user } = useAuth()
  const [itens, setItens] = useState<FrotaItem[] | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    equipamentosClienteApi
      .listar({ cliente: clienteId })
      .then((p) => { if (ativo) setItens(p.items) })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
        setItens([])
      })
    return () => { ativo = false }
  }, [clienteId])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Equipamentos do cliente</h2>
        {podeGerenciarCadastros(user) && <Button onClick={() => navigate('novo')}>Novo aparelho</Button>}
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum aparelho cadastrado para este cliente.</p>
      ) : (
        <Table head={<><TH>Aparelho</TH><TH>Série / Patrimônio</TH><TH>Próx. calibração</TH><TH>Status</TH></>}>
          {itens.map((e) => {
            const s = STATUS_CALIBRACAO[e.status_calibracao]
            return (
              <tr key={e.id} className="hover:bg-background-elevated transition-colors cursor-pointer" onClick={() => navigate(String(e.id))}>
                <TD>{e.equipamento_descricao ?? '—'}</TD>
                <TD>{e.serie || e.patrimonio || '—'}</TD>
                <TD>{e.prox_calibragem ?? '—'}</TD>
                <TD><Badge tone={s.tone}>{s.label}</Badge></TD>
              </tr>
            )
          })}
        </Table>
      )}
    </div>
  )
}
