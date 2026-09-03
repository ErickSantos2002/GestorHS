import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { PageContainer } from '../../components/ui/Page'
import { Table, TH, TD } from '../../components/ui/Table'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Select } from '../../components/ui/Select'
import { Pagination } from '../../components/ui/Pagination'
import { usePaginacaoLocal } from '../../lib/usePaginacaoLocal'
import { ApiError } from '../../lib/api'
import {
  logsIntegracaoApi, podeReenviar, TONE_STATUS,
  type LogIntegracao, type EstadoIntegracoes,
} from './api'

const NOME_INTEGRACAO: Record<string, string> = { growthhs: 'GrowthHS', taskhs: 'TaskHS' }

export function LogsIntegracaoPage() {
  const [itens, setItens] = useState<LogIntegracao[] | null>(null)
  const [estado, setEstado] = useState<EstadoIntegracoes | null>(null)
  const [integracao, setIntegracao] = useState('')
  const [status, setStatus] = useState('')
  const [reenviando, setReenviando] = useState<number | null>(null)
  const [aviso, setAviso] = useState('')
  const [erro, setErro] = useState('')
  const { page, setPage, totalPages, total, pageSize, visiveis } = usePaginacaoLocal(itens, 15)

  const carregar = useCallback(async () => {
    setErro('')
    try {
      const page = await logsIntegracaoApi.listar({ integracao, status })
      setItens(page.items)
      setEstado(page.estado)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
      setItens([])
    }
  }, [integracao, status])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void carregar() }, [carregar])

  async function reenviar(log: LogIntegracao) {
    setReenviando(log.id); setAviso('')
    try {
      const r = await logsIntegracaoApi.reenviar(log.id)
      setAviso(r.ok ? `Reenviado: ${log.external_id ?? log.id}` : `Falhou: ${r.mensagem ?? ''}`)
      await carregar()
    } catch (e) {
      setAviso(e instanceof ApiError ? e.message : 'Falha ao reenviar')
    } finally {
      setReenviando(null)
    }
  }

  function selo(ativo: boolean, nome: string) {
    return <Badge tone={ativo ? 'primary' : 'danger'}>{nome}: {ativo ? 'ativo' : 'desligado'}</Badge>
  }

  return (
    <PageContainer>
      <h1 className="text-2xl font-extrabold text-slate-100">Logs de Integração</h1>

      {estado && (
        <div className="flex gap-2">
          {selo(estado.growthhs_ativo, 'GrowthHS')}
          {selo(estado.taskhs_ativo, 'TaskHS')}
        </div>
      )}

      <div className="flex flex-wrap gap-3 items-end">
        <div className="w-48">
          <Select id="integracao" label="Integração" value={integracao} onChange={(e) => { setPage(1); setIntegracao(e.target.value) }}>
            <option value="">Todas</option>
            <option value="growthhs">GrowthHS</option>
            <option value="taskhs">TaskHS</option>
          </Select>
        </div>
        <div className="w-48">
          <Select id="status" label="Status" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value) }}>
            <option value="">Todos</option>
            <option value="sucesso">Sucesso</option>
            <option value="erro">Erro</option>
            <option value="pulado">Pulado</option>
          </Select>
        </div>
      </div>

      {aviso && <div className="rounded-lg bg-info/10 border border-info/20 px-3 py-2.5 text-sm text-info">{aviso}</div>}
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
      ) : (
        <Table
          head={<>
            <TH>Quando</TH><TH>Integração</TH><TH>Tipo</TH><TH>Referência</TH>
            <TH>Status</TH><TH>Detalhe</TH><TH>Ação</TH>
          </>}
          footer={total > 0 ? <Pagination page={page} totalPages={totalPages} total={total} pageSize={pageSize} onPageChange={setPage} itemLabel="logs" /> : undefined}
        >
          {visiveis.map((log) => (
            <tr key={log.id} className="align-top">
              <TD>{log.criado_em ? new Date(log.criado_em).toLocaleString('pt-BR') : '—'}</TD>
              <TD>{NOME_INTEGRACAO[log.integracao] ?? log.integracao}</TD>
              <TD>{log.tipo}</TD>
              <TD>
                {log.referencia_os
                  ? <Link
                      className="text-primary"
                      to={log.referencia_tipo === 'caixa'
                        ? `/app/caixas/${log.referencia_os}`
                        : `/app/ordens/${log.referencia_os}`}
                    >
                      {log.referencia_tipo === 'caixa' ? `CX ${log.referencia_os}` : `OS #${log.referencia_os}`}
                    </Link>
                  : (log.external_id ?? '—')}
              </TD>
              <TD><Badge tone={TONE_STATUS[log.status]}>{log.status}</Badge></TD>
              <TD>
                <span className="block max-w-md truncate text-slate-400" title={log.resposta ?? log.motivo ?? ''}>
                  {log.motivo ?? log.resposta ?? '—'}
                </span>
              </TD>
              <TD>
                {podeReenviar(log) && (
                  <Button variant="secondary" onClick={() => reenviar(log)} disabled={reenviando === log.id}>
                    {reenviando === log.id ? 'Reenviando…' : 'Reenviar'}
                  </Button>
                )}
              </TD>
            </tr>
          ))}
          {itens.length === 0 && (
            <tr><TD><span className="text-slate-400">Nenhum log encontrado</span></TD></tr>
          )}
        </Table>
      )}
    </PageContainer>
  )
}
