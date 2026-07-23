import { useEffect, useState, type FormEvent } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Table, TH, TD } from '../../components/ui/Table'
import { useAuth } from '../../auth/AuthContext'
import { podeAbrirOS } from '../../auth/roles'
import { apiJson, ApiError } from '../../lib/api'
import { cn } from '../../lib/utils'
import { caixasApi, formatData, type CaixaDetalhe } from './api'
import { AbrirOSModal } from '../ordens/AbrirOSModal'
import { AvancarCaixaModal } from './AvancarCaixaModal'
import { SemConsertoModal } from './SemConsertoModal'
import { TRANSICOES, faseAtiva } from '../ordens/api'
import { PageContainer, DetailGrid, DetailMain, DetailAside } from '../../components/ui/Page'

// Shape retornado por /equipamentos-cliente?q=...&limit=
interface EquipClientePicker {
  id: number
  cliente_nome: string | null
  equipamento_descricao: string | null
  serie: string | null
  os_atual: number | null
}

interface EquipPickerPage {
  items: EquipClientePicker[]
  total: number
}

export function CaixaDetailPage() {
  const { id } = useParams<{ id: string }>()
  const caixaId = Number(id)
  const { user } = useAuth()
  const podeEscrever = podeAbrirOS(user)

  const [caixa, setCaixa] = useState<CaixaDetalhe | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

  // Obs editável
  const [obs, setObs] = useState('')
  const [salvandoObs, setSalvandoObs] = useState(false)
  const [erroObs, setErroObs] = useState('')

  // Erro de ações sobre OS (remover/etc.)
  const [erroAcao, setErroAcao] = useState('')

  // Avançar caixa
  const [avancarCaixaAberto, setAvancarCaixaAberto] = useState(false)
  const [avancandoCaixa, setAvancandoCaixa] = useState(false)

  // Cancelar caixa
  const [cancelarCaixaAberto, setCancelarCaixaAberto] = useState(false)
  const [motivoCancelar, setMotivoCancelar] = useState('')
  const [erroCancelar, setErroCancelar] = useState('')
  const [cancelandoCaixa, setCancelandoCaixa] = useState(false)

  // Sem conserto (por OS, fase 5)
  const [semConsertoOsId, setSemConsertoOsId] = useState<number | null>(null)

  // Modal: Mover OS para outra caixa
  const [moverOsId, setMoverOsId] = useState<number | null>(null)
  const [caixaDestino, setCaixaDestino] = useState('')
  const [erroMover, setErroMover] = useState('')
  const [movendo, setMovendo] = useState(false)

  // Modal: Picker de equipamento para "Abrir OS"
  const [pickerAberto, setPickerAberto] = useState(false)
  const [pickerQ, setPickerQ] = useState('')
  const [pickerResultados, setPickerResultados] = useState<EquipClientePicker[]>([])
  const [pickerCarregando, setPickerCarregando] = useState(false)
  const [pickerErro, setPickerErro] = useState('')
  const [equipSelecionado, setEquipSelecionado] = useState<EquipClientePicker | null>(null)

  function carregar() {
    setCarregando(true)
    setErro('')
    caixasApi.obter(caixaId)
      .then((c) => {
        setCaixa(c)
        setObs(c.obs ?? '')
        setCarregando(false)
      })
      .catch((e) => {
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar caixa')
        setCarregando(false)
      })
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregar()
  }, [caixaId]) // eslint-disable-line react-hooks/exhaustive-deps

  async function salvarObs(e: FormEvent) {
    e.preventDefault()
    if (!caixa) return
    setSalvandoObs(true)
    setErroObs('')
    try {
      await caixasApi.atualizar(caixaId, { obs: obs.trim() || null })
      carregar()
    } catch (err) {
      setErroObs(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setSalvandoObs(false)
    }
  }

  async function removerOrdem(osId: number) {
    if (!caixa) return
    try {
      await caixasApi.desvincularOrdem(caixaId, osId)
      carregar()
    } catch (err) {
      setErroAcao(err instanceof ApiError ? err.message : 'Falha ao remover OS da caixa')
    }
  }

  async function avancarCaixaDireto() {
    setAvancandoCaixa(true)
    setErroAcao('')
    try {
      await caixasApi.avancar(caixaId, { obs: null, cod_retorno: null })
      carregar()
    } catch (err) {
      setErroAcao(err instanceof ApiError ? err.message : 'Falha ao avançar caixa')
    } finally {
      setAvancandoCaixa(false)
    }
  }

  function clicarAvancarCaixa() {
    if (!caixa || caixa.fase == null) return
    if (TRANSICOES[caixa.fase]?.pedeCodRetorno) {
      setAvancarCaixaAberto(true)
    } else {
      avancarCaixaDireto()
    }
  }

  async function confirmarCancelarCaixa(e: FormEvent) {
    e.preventDefault()
    if (!motivoCancelar.trim()) {
      setErroCancelar('Motivo é obrigatório.')
      return
    }
    setCancelandoCaixa(true)
    setErroCancelar('')
    try {
      await caixasApi.cancelar(caixaId, { motivo: motivoCancelar.trim() })
      setCancelarCaixaAberto(false)
      setMotivoCancelar('')
      carregar()
    } catch (err) {
      setErroCancelar(err instanceof ApiError ? err.message : 'Falha ao cancelar caixa')
    } finally {
      setCancelandoCaixa(false)
    }
  }

  async function confirmarMover(e: FormEvent) {
    e.preventDefault()
    const destino = Number(caixaDestino)
    if (!destino || !moverOsId) return
    setMovendo(true)
    setErroMover('')
    try {
      await caixasApi.vincularOrdem(destino, moverOsId)
      setMoverOsId(null)
      setCaixaDestino('')
      carregar()
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setErroMover('Caixa destino não encontrada.')
      } else {
        // 409 = caixa destino finalizada não aceita vínculos (mensagem vem do backend)
        setErroMover(err instanceof ApiError ? err.message : 'Falha ao mover OS')
      }
    } finally {
      setMovendo(false)
    }
  }

  async function buscarEquipamentos(q: string) {
    setPickerCarregando(true)
    setPickerErro('')
    try {
      const sp = new URLSearchParams({ q, limit: '10' })
      const res = await apiJson<EquipPickerPage>(`/equipamentos-cliente?${sp.toString()}`)
      setPickerResultados(res.items)
    } catch (err) {
      setPickerErro(err instanceof ApiError ? err.message : 'Falha ao buscar equipamentos')
    } finally {
      setPickerCarregando(false)
    }
  }

  function onPickerBuscar(e: FormEvent) {
    e.preventDefault()
    buscarEquipamentos(pickerQ.trim())
  }

  function abrirPicker() {
    setPickerQ('')
    setPickerResultados([])
    setPickerErro('')
    setEquipSelecionado(null)
    setPickerAberto(true)
  }

  if (carregando) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="w-8 h-8" />
      </div>
    )
  }

  if (erro || !caixa) {
    return (
      <div className="px-4 md:px-6 py-6">
        <Link to="/app/caixas" className="text-sm text-slate-400 hover:text-slate-200 flex items-center gap-1 mb-4">
          ← Caixas
        </Link>
        <div className="rounded-lg bg-danger/10 border border-danger/20 px-4 py-3 text-sm text-danger">
          {erro || 'Caixa não encontrada.'}
        </div>
      </div>
    )
  }

  const clientesUnicos = new Set(caixa.ordens.map((o) => o.cliente_nome).filter(Boolean)).size

  // Progresso do laboratório (só faz sentido com a caixa em fase 5) — OS ativas apenas,
  // as terminais/canceladas não contam como pendência.
  const ordensAtivasLab = caixa.fase === 5 ? caixa.ordens.filter((o) => faseAtiva(o.fase)) : []
  const prontosLab = ordensAtivasLab.filter((o) => o.desfecho_lab === 'concluido' || o.desfecho_lab === 'sem_conserto').length
  const pendentesLab = ordensAtivasLab.filter((o) => o.desfecho_lab === 'pendente').length
  const transicaoCaixa = caixa.fase != null ? TRANSICOES[caixa.fase] : undefined

  return (
    <PageContainer>
      {/* Cabeçalho */}
      <div>
        <Link to="/app/caixas" className="text-sm text-slate-400 hover:text-slate-200 flex items-center gap-1 mb-3">
          ← Caixas
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-100">Caixa #{caixa.id}</h1>
            <p className="text-sm text-slate-500 mt-1 flex flex-wrap items-center gap-2">
              <span>
                {formatData(caixa.data)} · {caixa.total_os} OS · {clientesUnicos} cliente{clientesUnicos !== 1 ? 's' : ''}
              </span>
              {caixa.fase === 5 && (
                <span className={cn('text-xs px-2 py-0.5 rounded-full',
                  pendentesLab === 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400')}>
                  {prontosLab}/{ordensAtivasLab.length} prontos
                </span>
              )}
            </p>
          </div>
          {podeEscrever && caixa.fase != null && (
            <div className="flex gap-2 flex-wrap">
              <Button
                onClick={clicarAvancarCaixa}
                disabled={pendentesLab > 0 || avancandoCaixa}
              >
                {avancandoCaixa
                  ? 'Avançando…'
                  : `Avançar caixa${transicaoCaixa ? ` — ${transicaoCaixa.rotulo}` : ''}`}
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  setMotivoCancelar('')
                  setErroCancelar('')
                  setCancelarCaixaAberto(true)
                }}
              >
                Cancelar caixa
              </Button>
            </div>
          )}
        </div>
        {erroAcao && (
          <div className="mt-3 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
            {erroAcao}
          </div>
        )}
      </div>

      <DetailGrid>
        <DetailMain>
          {/* Ações do lote */}
          {podeEscrever && (
            <div className="flex gap-2 flex-wrap">
              <Button onClick={abrirPicker}>Abrir OS</Button>
            </div>
          )}

          {/* Tabela de OS vinculadas */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
              Ordens de serviço ({caixa.ordens.length})
            </h2>
            {caixa.ordens.length === 0 ? (
              <p className="text-sm text-slate-500">Nenhuma OS vinculada.</p>
            ) : (
              <Table head={
                <>
                  <TH>OS</TH>
                  <TH>Cliente</TH>
                  <TH>Equipamento</TH>
                  <TH>Fase</TH>
                  {podeEscrever && <TH>Ações</TH>}
                </>
              }>
                {caixa.ordens.map((o) => (
                  <tr key={o.id} className="hover:bg-background-elevated transition-colors">
                    <TD>
                      <Link to={`/app/ordens/${o.id}`} className="font-semibold text-primary hover:underline">
                        #{o.id}
                      </Link>
                    </TD>
                    <TD>{o.cliente_nome ?? '—'}</TD>
                    <TD>
                      <span>
                        {o.equipamento_descricao ?? '—'}
                        {o.equipamento_serie && (
                          <span className="text-slate-500 ml-1 text-xs">· {o.equipamento_serie}</span>
                        )}
                      </span>
                    </TD>
                    <TD>
                      {o.fase_descricao ? (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full" style={{ background: `#${o.fase_cor}` }} />
                          {o.fase_descricao}
                        </span>
                      ) : '—'}
                    </TD>
                    {podeEscrever && (
                      <TD>
                        <div className="flex gap-2">
                          {caixa.fase === 5 && o.desfecho_lab === 'pendente' && (
                            <Button
                              variant="secondary"
                              onClick={() => setSemConsertoOsId(o.id)}
                            >
                              Sem conserto
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            onClick={() => {
                              setCaixaDestino('')
                              setErroMover('')
                              setMoverOsId(o.id)
                            }}
                          >
                            Mover
                          </Button>
                          <Button
                            variant="danger"
                            onClick={() => removerOrdem(o.id)}
                          >
                            Remover
                          </Button>
                        </div>
                      </TD>
                    )}
                  </tr>
                ))}
              </Table>
            )}
          </section>
        </DetailMain>

        <DetailAside>
          {/* Obs editável */}
          {podeEscrever && (
            <section className="rounded-2xl bg-background-surface border border-border p-5">
              <form onSubmit={salvarObs} className="flex gap-3 items-end">
                <div className="flex-1">
                  <Input
                    id="obs-caixa"
                    label="Descrição / origem"
                    value={obs}
                    onChange={(e) => setObs(e.target.value)}
                    placeholder="Ex.: Lote Cuiabá"
                  />
                </div>
                <Button type="submit" variant="secondary" disabled={salvandoObs}>
                  {salvandoObs ? 'Salvando…' : 'Salvar'}
                </Button>
              </form>
              {erroObs && <p className="mt-2 text-sm text-danger">{erroObs}</p>}
            </section>
          )}

          {!podeEscrever && caixa.obs && (
            <section className="rounded-2xl bg-background-surface border border-border p-5">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Descrição</p>
              <p className="text-sm text-slate-300">{caixa.obs}</p>
            </section>
          )}

          {/* Resumo */}
          <section className="rounded-2xl bg-background-surface border border-border p-5">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Resumo</p>
            <dl className="space-y-1 text-sm text-slate-300">
              <div className="flex justify-between"><dt>Data</dt><dd className="text-slate-100">{formatData(caixa.data)}</dd></div>
              <div className="flex justify-between"><dt>OS</dt><dd className="text-slate-100">{caixa.total_os}</dd></div>
              <div className="flex justify-between"><dt>Clientes</dt><dd className="text-slate-100">{clientesUnicos}</dd></div>
            </dl>
          </section>
        </DetailAside>
      </DetailGrid>

      {/* Modal: Avançar caixa (fases que pedem código de retorno, ex.: fase 7) */}
      {avancarCaixaAberto && transicaoCaixa && (
        <AvancarCaixaModal
          id={caixaId}
          rotulo={transicaoCaixa.rotulo}
          onClose={() => setAvancarCaixaAberto(false)}
          onConcluido={() => {
            setAvancarCaixaAberto(false)
            carregar()
          }}
        />
      )}

      {/* Modal: Cancelar caixa */}
      {cancelarCaixaAberto && (
        <Modal
          open
          onClose={() => setCancelarCaixaAberto(false)}
          title={`Cancelar caixa #${caixa.id}`}
          footer={
            <>
              <Button variant="secondary" onClick={() => setCancelarCaixaAberto(false)}>Voltar</Button>
              <Button variant="danger" type="submit" form="form-cancelar-caixa" disabled={cancelandoCaixa}>
                {cancelandoCaixa ? 'Cancelando…' : 'Cancelar caixa'}
              </Button>
            </>
          }
        >
          <form id="form-cancelar-caixa" onSubmit={confirmarCancelarCaixa} className="space-y-4">
            <div>
              <label htmlFor="motivo-cancelar-caixa" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Motivo</label>
              <textarea
                id="motivo-cancelar-caixa"
                value={motivoCancelar}
                onChange={(e) => setMotivoCancelar(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
            {erroCancelar && <p className="text-sm text-danger">{erroCancelar}</p>}
          </form>
        </Modal>
      )}

      {/* Modal: Sem conserto (por OS, fase 5) */}
      {semConsertoOsId !== null && (
        <SemConsertoModal
          osId={semConsertoOsId}
          onClose={() => setSemConsertoOsId(null)}
          onConcluido={() => {
            setSemConsertoOsId(null)
            carregar()
          }}
        />
      )}

      {/* Modal: Mover OS para outra caixa */}
      {moverOsId !== null && (
        <Modal
          open
          onClose={() => setMoverOsId(null)}
          title={`Mover OS #${moverOsId} para outra caixa`}
          footer={
            <>
              <Button variant="secondary" onClick={() => setMoverOsId(null)}>Cancelar</Button>
              <Button type="submit" form="form-mover-os" disabled={movendo || !caixaDestino}>
                {movendo ? 'Movendo…' : 'Mover'}
              </Button>
            </>
          }
        >
          <form id="form-mover-os" onSubmit={confirmarMover} className="space-y-4">
            <Input
              id="caixa-destino"
              label="Número da caixa destino"
              type="number"
              min={1}
              value={caixaDestino}
              onChange={(e) => setCaixaDestino(e.target.value)}
              placeholder="Ex.: 7"
              required
            />
            {erroMover && (
              <p className="text-sm text-danger">{erroMover}</p>
            )}
          </form>
        </Modal>
      )}

      {/* Modal: Picker de equipamento para "Abrir OS" */}
      {pickerAberto && !equipSelecionado && (
        <Modal
          open
          onClose={() => setPickerAberto(false)}
          title="Selecionar aparelho"
        >
          <div className="space-y-4">
            <form onSubmit={onPickerBuscar} className="flex gap-2 items-end">
              <div className="flex-1">
                <Input
                  id="picker-q"
                  label="Buscar aparelho"
                  value={pickerQ}
                  onChange={(e) => setPickerQ(e.target.value)}
                  placeholder="Série, cliente, modelo…"
                />
              </div>
              <Button type="submit" variant="secondary" disabled={pickerCarregando}>
                {pickerCarregando ? <Spinner className="w-4 h-4" /> : 'Buscar'}
              </Button>
            </form>
            {pickerErro && <p className="text-sm text-danger">{pickerErro}</p>}
            {pickerResultados.length > 0 && (
              <ul className="divide-y divide-border rounded-lg border border-border overflow-hidden">
                {pickerResultados.map((eq) => (
                  <li key={eq.id}>
                    <button
                      type="button"
                      className="w-full text-left px-4 py-3 text-sm hover:bg-background-elevated transition-colors"
                      onClick={() => setEquipSelecionado(eq)}
                    >
                      <span className="font-semibold text-slate-200">
                        {eq.equipamento_descricao ?? 'Equipamento desconhecido'}
                      </span>
                      {eq.serie && <span className="text-slate-400 ml-2">· {eq.serie}</span>}
                      {eq.cliente_nome && (
                        <span className="block text-xs text-slate-500 mt-0.5">{eq.cliente_nome}</span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {pickerResultados.length === 0 && !pickerCarregando && pickerQ && !pickerErro && (
              <p className="text-sm text-slate-500">Nenhum aparelho encontrado.</p>
            )}
          </div>
        </Modal>
      )}

      {/* AbrirOSModal: após selecionar equipamento no picker */}
      {equipSelecionado && (
        <AbrirOSModal
          equipamentoClienteId={equipSelecionado.id}
          osAtual={equipSelecionado.os_atual}
          onClose={() => {
            setEquipSelecionado(null)
            setPickerAberto(false)
          }}
          caixa={caixaId}
          onAberta={() => {
            setEquipSelecionado(null)
            setPickerAberto(false)
            carregar()
          }}
        />
      )}
    </PageContainer>
  )
}
