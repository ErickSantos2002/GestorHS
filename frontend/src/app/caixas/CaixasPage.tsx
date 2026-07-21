import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { SearchBar } from '../../components/ui/SearchBar'
import { Toggle } from '../../components/ui/Toggle'
import { useAuth } from '../../auth/AuthContext'
import { podeAbrirOS } from '../../auth/roles'
import { ApiError } from '../../lib/api'
import { caixasApi, formatData, type CaixaListItem } from './api'
import { PageContainer } from '../../components/ui/Page'

const PAGE = 25

export function CaixasPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const podeEscrever = podeAbrirOS(user)
  const [q, setQ] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [incluirConcluidas, setIncluirConcluidas] = useState(false)
  const [dados, setDados] = useState<{ items: CaixaListItem[]; total: number } | null>(null)
  const [erro, setErro] = useState('')
  const [novaAberta, setNovaAberta] = useState(false)
  const [novaObs, setNovaObs] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [erroModal, setErroModal] = useState('')

  useEffect(() => {
    let vivo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDados(null)
    setErro('')
    caixasApi
      .listar({ q: busca || undefined, incluir_concluidas: incluirConcluidas, offset, limit: PAGE })
      .then((r) => { if (vivo) setDados(r) })
      .catch((e) => { if (vivo) { setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setDados({ items: [], total: 0 }) } })
    return () => { vivo = false }
  }, [busca, offset, incluirConcluidas])

  async function criar(e: FormEvent) {
    e.preventDefault()
    setSalvando(true)
    setErroModal('')
    try {
      const c = await caixasApi.criar({ obs: novaObs.trim() || null })
      navigate(`/app/caixas/${c.id}`)
    } catch (err) {
      setErroModal(err instanceof ApiError ? err.message : 'Falha ao criar caixa')
    } finally {
      setSalvando(false)
    }
  }

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(q.trim())
  }

  const inicio = dados && dados.total > 0 ? offset + 1 : 0
  const fim = dados ? Math.min(offset + PAGE, dados.total) : 0

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100">Caixas</h1>
          <p className="text-sm text-slate-500 mt-0.5">Agrupamento físico de ordens de serviço.</p>
        </div>
        {podeEscrever && (
          <Button
            onClick={() => { setNovaObs(''); setErroModal(''); setNovaAberta(true) }}
          >
            Nova caixa
          </Button>
        )}
      </div>

      <SearchBar
        id="filtro-busca"
        value={q}
        onChange={setQ}
        onSubmit={onBuscar}
        placeholder="Nº ou descrição"
        abaixo={
          <label className="flex items-center gap-2 text-sm text-slate-400 select-none cursor-pointer">
            <Toggle checked={incluirConcluidas} onChange={(v) => { setOffset(0); setIncluirConcluidas(v) }} label="Mostrar concluídas" />
            <span>Mostrar concluídas</span>
          </label>
        }
      />

      {erro && (
        <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>
      )}

      {dados === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : dados.items.length === 0 && !erro ? (
        <p className="text-sm text-slate-500">Nenhuma caixa.</p>
      ) : dados.items.length > 0 ? (
        <>
          <Table head={
            <>
              <TH>Caixa</TH>
              <TH>Data</TH>
              <TH>OS</TH>
              <TH>Clientes</TH>
              <TH>Descrição</TH>
            </>
          }>
            {dados.items.map((c) => (
              <tr
                key={c.id}
                className="hover:bg-background-elevated transition-colors cursor-pointer"
                onClick={() => navigate(`/app/caixas/${c.id}`)}
              >
                <TD><span className="font-semibold text-slate-200">#{c.id}</span></TD>
                <TD>{formatData(c.data)}</TD>
                <TD>{c.total_os}</TD>
                <TD>
                  {c.clientes.length === 0
                    ? '—'
                    : c.clientes.length === 1
                      ? c.clientes[0]
                      : `${c.clientes.length} clientes`}
                </TD>
                <TD>
                  <span className="truncate max-w-xs block">{c.obs ?? '—'}</span>
                </TD>
              </tr>
            ))}
          </Table>

          <div className="flex items-center justify-between text-sm text-slate-400">
            <span>{inicio}–{fim} de {dados.total}</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Anterior</Button>
              <Button variant="secondary" disabled={fim >= dados.total} onClick={() => setOffset(offset + PAGE)}>Próxima</Button>
            </div>
          </div>
        </>
      ) : null}

      {novaAberta && (
        <Modal
          open
          onClose={() => setNovaAberta(false)}
          title="Nova caixa"
          footer={
            <>
              <Button variant="secondary" type="button" onClick={() => setNovaAberta(false)}>
                Cancelar
              </Button>
              <Button type="submit" form="form-nova-caixa" disabled={salvando}>
                Criar
              </Button>
            </>
          }
        >
          <form id="form-nova-caixa" onSubmit={criar} className="space-y-4">
            <Input
              id="obs"
              label="Descrição / origem (opcional)"
              value={novaObs}
              onChange={(e) => setNovaObs(e.target.value)}
              placeholder="Ex.: Lote Cuiabá"
            />
            {erroModal && <p className="text-sm text-danger">{erroModal}</p>}
          </form>
        </Modal>
      )}
    </PageContainer>
  )
}
