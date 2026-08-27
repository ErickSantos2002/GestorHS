import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { SearchBar } from '../../components/ui/SearchBar'
import { Pagination } from '../../components/ui/Pagination'
import { PageContainer } from '../../components/ui/Page'
import { IconButton, IconButtonGroup } from '../../components/ui/IconButton'
import { IconEye, IconDownload, IconClock, IconPencil, IconCopy, IconBan, IconRestore, IconCheck, IconX } from '../../components/ui/icons'
import { Badge } from '../../components/ui/Badge'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarPropostas, podeFaturarProposta, podeDesfaturarProposta, podeReativarProposta } from '../../auth/roles'
import { ApiError } from '../../lib/api'
import { formatData } from '../../lib/utils'
import { formatarDocumento } from '../../lib/documento'
import { formatarMoeda } from '../../lib/moeda'
import { propostasApi, type Proposta } from './api'
import { PropostaModal } from './PropostaModal'
import { HistoricoModal } from './HistoricoModal'
import { VisualizarPropostaModal } from './VisualizarPropostaModal'
import { OverrideDetalheModal } from './OverrideDetalhe'
import { temOverride } from './clienteOverride'

const PAGE = 25

export function PropostasPage() {
  const { user } = useAuth()
  const podeEscrever = podeGerenciarPropostas(user)
  const [q, setQ] = useState('')
  const [busca, setBusca] = useState('')
  const [incluirDesabilitadas, setIncluirDesabilitadas] = useState(false)
  const [page, setPage] = useState(1)
  const [dados, setDados] = useState<{ items: Proposta[]; total: number; total_pages: number } | null>(null)
  const [erro, setErro] = useState('')
  const [recarga, setRecarga] = useState(0)
  const [busyId, setBusyId] = useState<number | null>(null)

  // modal do construtor: undefined = fechado; null = nova; number = editando id
  const [modalId, setModalId] = useState<number | null | undefined>(undefined)
  const [historico, setHistorico] = useState<{ id: number; numero: number } | null>(null)
  const [visualizar, setVisualizar] = useState<{ id: number; numero: number } | null>(null)
  const [overrideDe, setOverrideDe] = useState<Proposta | null>(null)
  // id da proposta-modelo p/ duplicar (abre a modal como nova, sem salvar até confirmar)
  const [duplicarDeId, setDuplicarDeId] = useState<number | null>(null)

  useEffect(() => {
    let vivo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDados(null)
    setErro('')
    propostasApi
      .listar({ q: busca || undefined, page, page_size: PAGE, incluir_desabilitadas: incluirDesabilitadas || undefined })
      .then((r) => { if (vivo) setDados({ items: r.items, total: r.total, total_pages: r.total_pages }) })
      .catch((e) => { if (vivo) { setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setDados({ items: [], total: 0, total_pages: 0 }) } })
    return () => { vivo = false }
  }, [busca, page, recarga, incluirDesabilitadas])

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

  // Abre a modal como proposta NOVA pré-preenchida com os dados da original
  // (vendedor/assinatura = quem duplica, data de hoje). Só cria ao confirmar —
  // cancelar não deixa rastro, ao contrário da criação imediata de antes.
  function duplicar(id: number) {
    setDuplicarDeId(id)
  }

  // Não existe excluir proposta: ela sai de circulação e continua inteira no banco,
  // com itens, versões e o vínculo com a caixa. Só Admin traz de volta.
  async function desabilitar(p: Proposta) {
    const aviso = `Desabilitar a proposta #${p.numero}? Ela sai da lista mas continua `
      + 'no sistema, e um Administrador pode reativá-la.'
    if (!window.confirm(aviso)) return
    setErro('')
    setBusyId(p.id)
    try {
      await propostasApi.desabilitar(p.id)
      recarregar()
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao desabilitar')
    } finally {
      setBusyId(null)
    }
  }

  async function reativar(p: Proposta) {
    setErro('')
    setBusyId(p.id)
    try {
      await propostasApi.reativar(p.id)
      recarregar()
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao reativar')
    } finally {
      setBusyId(null)
    }
  }

  async function faturar(p: Proposta) {
    setErro('')
    setBusyId(p.id)
    try {
      await propostasApi.faturar(p.id)
      recarregar()
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao marcar como faturada')
    } finally {
      setBusyId(null)
    }
  }

  async function desfaturar(p: Proposta) {
    setErro('')
    setBusyId(p.id)
    try {
      await propostasApi.desfaturar(p.id)
      recarregar()
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao desfazer faturamento')
    } finally {
      setBusyId(null)
    }
  }


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

      <label className="flex items-center gap-2 text-sm text-slate-400 select-none w-fit">
        <input
          type="checkbox"
          checked={incluirDesabilitadas}
          onChange={(e) => { setPage(1); setIncluirDesabilitadas(e.target.checked) }}
          className="rounded border-border"
        />
        Mostrar desabilitadas
      </label>

      {erro && (
        <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>
      )}

      {dados === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : dados.items.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma proposta.</p>
      ) : (
        <>
          <Table
            head={
              <>
                <TH>Número</TH>
                <TH>Data</TH>
                <TH>Cliente</TH>
                <TH>CNPJ</TH>
                <TH>Valor</TH>
                <TH>Ações</TH>
              </>
            }
            footer={
              <Pagination
                page={page}
                totalPages={dados.total_pages}
                total={dados.total}
                pageSize={PAGE}
                onPageChange={setPage}
                itemLabel="propostas"
              />
            }
          >
            {dados.items.map((p) => (
              <tr key={p.id} className="hover:bg-background-elevated transition-colors">
                <TD>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-200">#{p.numero}</span>
                    {p.faturada && <Badge tone="primary">Faturada</Badge>}
                    {p.is_deleted && <Badge tone="danger">Desabilitada</Badge>}
                  </div>
                </TD>
                <TD>{formatData(p.data)}</TD>
                <TD>
                  <span className="truncate max-w-xs block">{p.cliente_nome ?? '—'}</span>
                  {temOverride(p.cliente_override) && (
                    <button
                      type="button"
                      onClick={() => setOverrideDe(p)}
                      title="Ver o que foi editado só nesta proposta"
                      className="mt-1 inline-flex items-center gap-1 rounded-full bg-warning/10 px-2 py-0.5 text-xs font-semibold text-warning hover:bg-warning/20 transition-colors"
                    >
                      <IconPencil className="w-3 h-3" />
                      Dados editados
                    </button>
                  )}
                </TD>
                <TD>{formatarDocumento(p.cliente_documento) || '—'}</TD>
                <TD>R$ {formatarMoeda(p.total)}</TD>
                <TD>
                  <IconButtonGroup>
                    <IconButton label="Visualizar" tone="ver" onClick={() => setVisualizar({ id: p.id, numero: p.numero })}>
                      <IconEye className="w-4 h-4" />
                    </IconButton>
                    <IconButton label="Baixar PDF" tone="baixar" disabled={busyId === p.id} onClick={() => baixarPdf(p)}>
                      <IconDownload className="w-4 h-4" />
                    </IconButton>
                    <IconButton label="Histórico" tone="historico" onClick={() => setHistorico({ id: p.id, numero: p.numero })}>
                      <IconClock className="w-4 h-4" />
                    </IconButton>
                    {!p.is_deleted && !p.faturada && podeFaturarProposta(user) && (
                      <IconButton label="Marcar como Faturada" tone="ok" disabled={busyId === p.id} onClick={() => faturar(p)}>
                        <IconCheck className="w-4 h-4" />
                      </IconButton>
                    )}
                    {!p.is_deleted && p.faturada && podeDesfaturarProposta(user) && (
                      <IconButton label="Desfazer faturamento" tone="neutro" disabled={busyId === p.id} onClick={() => desfaturar(p)}>
                        <IconX className="w-4 h-4" />
                      </IconButton>
                    )}
                    {/* Desabilitada só lê: o backend recusa editar/duplicar/faturar com 409. */}
                    {podeEscrever && !p.is_deleted && (
                      <>
                        <IconButton label="Editar" tone="editar" onClick={() => setModalId(p.id)}>
                          <IconPencil className="w-4 h-4" />
                        </IconButton>
                        <IconButton label="Duplicar" tone="duplicar" onClick={() => duplicar(p.id)}>
                          <IconCopy className="w-4 h-4" />
                        </IconButton>
                        <IconButton label="Desabilitar" tone="excluir" disabled={busyId === p.id} onClick={() => desabilitar(p)}>
                          <IconBan className="w-4 h-4" />
                        </IconButton>
                      </>
                    )}
                    {p.is_deleted && podeReativarProposta(user) && (
                      <IconButton label="Reativar" tone="ok" disabled={busyId === p.id} onClick={() => reativar(p)}>
                        <IconRestore className="w-4 h-4" />
                      </IconButton>
                    )}
                  </IconButtonGroup>
                </TD>
              </tr>
            ))}
          </Table>
        </>
      )}

      {modalId !== undefined && (
        <PropostaModal
          propostaId={modalId}
          onClose={() => setModalId(undefined)}
          onSalvo={() => { setModalId(undefined); recarregar() }}
        />
      )}

      {duplicarDeId !== null && (
        <PropostaModal
          propostaId={null}
          duplicarDe={duplicarDeId}
          onClose={() => setDuplicarDeId(null)}
          onSalvo={() => { setDuplicarDeId(null); recarregar() }}
        />
      )}

      {historico && (
        <HistoricoModal
          propostaId={historico.id}
          propostaNumero={historico.numero}
          onClose={() => setHistorico(null)}
        />
      )}

      {overrideDe && (
        <OverrideDetalheModal
          propostaNumero={overrideDe.numero}
          clienteId={overrideDe.cliente}
          override={overrideDe.cliente_override}
          onClose={() => setOverrideDe(null)}
        />
      )}

      {visualizar && (
        <VisualizarPropostaModal
          propostaId={visualizar.id}
          propostaNumero={visualizar.numero}
          onClose={() => setVisualizar(null)}
        />
      )}
    </PageContainer>
  )
}
