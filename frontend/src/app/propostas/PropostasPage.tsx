import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { SearchBar } from '../../components/ui/SearchBar'
import { PageContainer } from '../../components/ui/Page'
import { IconButton, IconButtonGroup } from '../../components/ui/IconButton'
import { IconEye, IconDownload, IconClock, IconPencil, IconCopy, IconTrash } from '../../components/ui/icons'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarPropostas } from '../../auth/roles'
import { ApiError } from '../../lib/api'
import { formatData } from '../../lib/utils'
import { formatarDocumento } from '../../lib/documento'
import { propostasApi, type Proposta } from './api'
import { PropostaModal } from './PropostaModal'
import { HistoricoModal } from './HistoricoModal'

const PAGE = 25
const formatarMoeda = (v: number) => v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export function PropostasPage() {
  const { user } = useAuth()
  const podeEscrever = podeGerenciarPropostas(user)
  const [q, setQ] = useState('')
  const [busca, setBusca] = useState('')
  const [page, setPage] = useState(1)
  const [dados, setDados] = useState<{ items: Proposta[]; total: number; total_pages: number } | null>(null)
  const [erro, setErro] = useState('')
  const [recarga, setRecarga] = useState(0)
  const [busyId, setBusyId] = useState<number | null>(null)

  // modal do construtor: undefined = fechado; null = nova; number = editando id
  const [modalId, setModalId] = useState<number | null | undefined>(undefined)
  const [historico, setHistorico] = useState<{ id: number; numero: number } | null>(null)

  useEffect(() => {
    let vivo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDados(null)
    setErro('')
    propostasApi
      .listar({ q: busca || undefined, page, page_size: PAGE })
      .then((r) => { if (vivo) setDados({ items: r.items, total: r.total, total_pages: r.total_pages }) })
      .catch((e) => { if (vivo) { setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setDados({ items: [], total: 0, total_pages: 0 }) } })
    return () => { vivo = false }
  }, [busca, page, recarga])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setPage(1)
    setBusca(q.trim())
  }

  function recarregar() {
    setRecarga((n) => n + 1)
  }

  async function baixarPdf(p: Proposta) {
    setErro('')
    setBusyId(p.id)
    try {
      const blob = await propostasApi.baixarPdf(p.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `proposta-${p.numero}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao baixar PDF')
    } finally {
      setBusyId(null)
    }
  }

  async function visualizarPdf(p: Proposta) {
    const win = window.open('', '_blank')
    setBusyId(p.id)
    setErro('')
    try {
      const blob = await propostasApi.baixarPdf(p.id)
      const url = URL.createObjectURL(blob)
      if (win) win.location.href = url
      else window.open(url, '_blank')
    } catch (e) {
      if (win) win.close()
      setErro(e instanceof ApiError ? e.message : 'Falha ao abrir o PDF')
    } finally {
      setBusyId(null)
    }
  }

  async function duplicar(id: number) {
    setErro('')
    setBusyId(id)
    try {
      const nova = await propostasApi.duplicar(id)
      setModalId(nova.id)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao duplicar')
    } finally {
      setBusyId(null)
    }
  }

  async function excluir(p: Proposta) {
    if (!window.confirm(`Excluir a proposta #${p.numero}? Esta ação não pode ser desfeita.`)) return
    setErro('')
    setBusyId(p.id)
    try {
      await propostasApi.excluir(p.id)
      recarregar()
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao excluir')
    } finally {
      setBusyId(null)
    }
  }

  const inicio = dados && dados.total > 0 ? (page - 1) * PAGE + 1 : 0
  const fim = dados ? Math.min(page * PAGE, dados.total) : 0

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100">Propostas</h1>
          <p className="text-sm text-slate-500 mt-0.5">Propostas técnicas comerciais.</p>
        </div>
        {podeEscrever && (
          <Button onClick={() => setModalId(null)}>Nova proposta</Button>
        )}
      </div>

      <SearchBar
        id="filtro-busca"
        value={q}
        onChange={setQ}
        onSubmit={onBuscar}
        placeholder="Cliente ou número"
      />

      {erro && (
        <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>
      )}

      {dados === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : dados.items.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma proposta.</p>
      ) : (
        <>
          <Table head={
            <>
              <TH>Número</TH>
              <TH>Data</TH>
              <TH>Cliente</TH>
              <TH>CNPJ</TH>
              <TH>Valor</TH>
              <TH>Ações</TH>
            </>
          }>
            {dados.items.map((p) => (
              <tr key={p.id} className="hover:bg-background-elevated transition-colors">
                <TD><span className="font-semibold text-slate-200">#{p.numero}</span></TD>
                <TD>{formatData(p.data)}</TD>
                <TD><span className="truncate max-w-xs block">{p.cliente_nome ?? '—'}</span></TD>
                <TD>{formatarDocumento(p.cliente_documento) || '—'}</TD>
                <TD>R$ {formatarMoeda(p.total)}</TD>
                <TD>
                  <IconButtonGroup>
                    <IconButton label="Visualizar" tone="ver" disabled={busyId === p.id} onClick={() => visualizarPdf(p)}>
                      <IconEye className="w-4 h-4" />
                    </IconButton>
                    <IconButton label="Baixar PDF" tone="neutro" disabled={busyId === p.id} onClick={() => baixarPdf(p)}>
                      <IconDownload className="w-4 h-4" />
                    </IconButton>
                    <IconButton label="Histórico" tone="neutro" onClick={() => setHistorico({ id: p.id, numero: p.numero })}>
                      <IconClock className="w-4 h-4" />
                    </IconButton>
                    {podeEscrever && (
                      <>
                        <IconButton label="Editar" tone="editar" onClick={() => setModalId(p.id)}>
                          <IconPencil className="w-4 h-4" />
                        </IconButton>
                        <IconButton label="Duplicar" tone="neutro" disabled={busyId === p.id} onClick={() => duplicar(p.id)}>
                          <IconCopy className="w-4 h-4" />
                        </IconButton>
                        <IconButton label="Excluir" tone="excluir" disabled={busyId === p.id} onClick={() => excluir(p)}>
                          <IconTrash className="w-4 h-4" />
                        </IconButton>
                      </>
                    )}
                  </IconButtonGroup>
                </TD>
              </tr>
            ))}
          </Table>

          <div className="flex items-center justify-between text-sm text-slate-400">
            <span>{inicio}–{fim} de {dados.total}</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Anterior</Button>
              <Button variant="secondary" disabled={page >= dados.total_pages} onClick={() => setPage((p) => p + 1)}>Próxima</Button>
            </div>
          </div>
        </>
      )}

      {modalId !== undefined && (
        <PropostaModal
          propostaId={modalId}
          onClose={() => setModalId(undefined)}
          onSalvo={() => { setModalId(undefined); recarregar() }}
        />
      )}

      {historico && (
        <HistoricoModal
          propostaId={historico.id}
          propostaNumero={historico.numero}
          onClose={() => setHistorico(null)}
        />
      )}
    </PageContainer>
  )
}
