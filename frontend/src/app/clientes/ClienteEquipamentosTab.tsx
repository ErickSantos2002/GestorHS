import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { PaginationOffset } from '../../components/ui/Pagination'
import { ApiError } from '../../lib/api'
import { cn } from '../../lib/utils'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarCadastros } from '../../auth/roles'
import { equipamentosClienteApi, STATUS_CALIBRACAO, type FrotaItem } from '../frota/api'

// Mesmo tamanho de pagina da FrotaPage, que lista da mesma API.
const LIMITE = 25

export function ClienteEquipamentosTab() {
  const { id } = useParams()
  const clienteId = Number(id)
  const navigate = useNavigate()
  const { user } = useAuth()
  const [itens, setItens] = useState<FrotaItem[] | null>(null)
  const [erro, setErro] = useState('')
  // A lista NAO cabia numa requisicao so: o endpoint devolve 25 por padrao e a
  // aba pedia sem limite, entao cliente com mais que isso perdia os aparelhos
  // do fim em silencio — parecia que o aparelho nao estava cadastrado.
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)

  // Trocar de cliente volta para a primeira pagina: manter o offset deixaria a
  // tela vazia num cliente com menos aparelhos que o anterior.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOffset(0)
  }, [clienteId])

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    equipamentosClienteApi
      .listar({ cliente: clienteId, offset, limit: LIMITE })
      .then((p) => {
        if (!ativo) return
        setItens(p.items)
        setTotal(p.total)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
        setItens([])
        setTotal(0)
      })
    return () => { ativo = false }
  }, [clienteId, offset])

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
        <Table
          head={<><TH>Aparelho</TH><TH>Série / Patrimônio</TH><TH>Próx. calibração</TH><TH>Status</TH></>}
          footer={<PaginationOffset offset={offset} limit={LIMITE} total={total} onOffsetChange={setOffset} itemLabel="aparelhos" />}
        >
          {itens.map((e) => {
            const s = STATUS_CALIBRACAO[e.status_calibracao]
            return (
              <tr
                key={e.id}
                className={cn('hover:bg-background-elevated transition-colors cursor-pointer', !e.ativo && 'opacity-60')}
                onClick={() => navigate(String(e.id))}
              >
                <TD>
                  <span className="inline-flex items-center gap-2">
                    {e.equipamento_descricao ?? '—'}
                    {!e.ativo && <Badge tone="neutral">Inativo</Badge>}
                  </span>
                </TD>
                <TD>{e.serie || e.patrimonio || '—'}</TD>
                <TD>{e.prox_calibragem ?? '—'}</TD>
                <TD><Badge tone={e.ativo ? s.tone : 'neutral'}>{s.label}</Badge></TD>
              </tr>
            )
          })}
        </Table>
      )}
    </div>
  )
}
