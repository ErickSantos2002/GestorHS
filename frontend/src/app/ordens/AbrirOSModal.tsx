import { useState, useEffect, type FormEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal } from '../../components/ui/Modal'
import { Select } from '../../components/ui/Select'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import {
  IconOrdens,
  IconCalendar,
  IconWrench,
  IconCaixas,
  IconTag,
  IconBattery,
  IconSearch,
  IconPlus,
  IconNote,
  IconX,
  IconAlertCircle,
} from '../../components/ui/icons'
import { ApiError } from '../../lib/api'
import { ordensApi, CHECKLIST_ACESSORIOS, CONDICOES_CHEGADA, type TipoServico } from './api'
import { caixasApi, type CaixaListItem } from '../caixas/api'

function hojeISO(): string {
  const d = new Date()
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10)
}

// Rótulo de seção com ícone sutil
function SectionLabel({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
      <span className="text-slate-500">{icon}</span>
      {children}
    </div>
  )
}

// Rótulo de campo com ícone
function FieldLabel({ htmlFor, icon, children }: { htmlFor?: string; icon: ReactNode; children: ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">
      <span className="text-slate-500">{icon}</span>
      {children}
    </label>
  )
}

export function AbrirOSModal({ equipamentoClienteId, osAtual, onClose, caixa, onAberta }: {
  equipamentoClienteId: number
  osAtual: number | null
  onClose: () => void
  caixa?: number
  onAberta?: (osId: number) => void
}) {
  const navigate = useNavigate()
  const [dataChegada, setDataChegada] = useState(hojeISO())
  const [tipo, setTipo] = useState<TipoServico>('C')
  const [condicao, setCondicao] = useState('')
  const [checklist, setChecklist] = useState<number[]>([])
  const [pilhas, setPilhas] = useState('0')
  const [bocais, setBocais] = useState('0')
  const [obs, setObs] = useState('')
  const [erro, setErro] = useState('')
  const [osAtivaId, setOsAtivaId] = useState<number | null>(null)
  const [enviando, setEnviando] = useState(false)

  const caixaTravada = caixa != null
  const [caixaId, setCaixaId] = useState<number | null>(caixa ?? null)
  const [caixaQ, setCaixaQ] = useState('')
  const [caixaResultados, setCaixaResultados] = useState<CaixaListItem[]>([])
  const [criandoCaixa, setCriandoCaixa] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (caixaTravada || !caixaQ.trim()) { setCaixaResultados([]); return }
    let vivo = true
    caixasApi.listar({ q: caixaQ.trim(), limit: 8 })
      .then((r) => { if (vivo) setCaixaResultados(r.items) })
      .catch(() => { if (vivo) setCaixaResultados([]) })
    return () => { vivo = false }
  }, [caixaQ, caixaTravada])

  function toggleChecklist(id: number) {
    setChecklist((cur) => cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id])
  }

  async function criarCaixa() {
    setCriandoCaixa(true)
    setErro('')
    try {
      const nova = await caixasApi.criar({ obs: caixaQ.trim() || null })
      setCaixaId(nova.id)
      setCaixaResultados([])
      setCaixaQ('')
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao criar caixa')
    } finally {
      setCriandoCaixa(false)
    }
  }

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setOsAtivaId(null)
    setEnviando(true)
    try {
      const os = await ordensApi.abrir({
        equipamento_cliente: equipamentoClienteId,
        tipo_servico: tipo,
        data_chegada: dataChegada || null,
        caixa: caixaId,
        condicao_chegada: condicao || null,
        checklist: checklist.length ? checklist : null,
        pilhas: Number(pilhas) || 0,
        bocais: Number(bocais) || 0,
        observacoes: obs.trim() || null,
      })
      if (onAberta) onAberta(os.id)
      else navigate(`/app/ordens/${os.id}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setErro('Este aparelho já possui uma OS ativa.')
        setOsAtivaId(osAtual)
      } else {
        setErro(err instanceof ApiError ? err.message : 'Falha ao abrir OS')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Abrir OS"
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="form-abrir-os" disabled={enviando}>
            {enviando ? 'Abrindo…' : 'Abrir OS'}
          </Button>
        </>
      }
    >
      {/* Wrapper com largura própria — não afeta outros modais */}
      <div className="sm:w-120">
        {/* Cabeçalho do corpo */}
        <div className="flex items-center gap-3 mb-5">
          <div className="grid place-items-center w-10 h-10 rounded-xl bg-primary/15 text-primary shrink-0">
            <IconOrdens className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-200 leading-tight">Recebimento do equipamento</p>
            <p className="text-xs text-slate-500 mt-0.5">Registre os dados de entrada da OS.</p>
          </div>
        </div>

        <form id="form-abrir-os" className="space-y-6 max-h-[65vh] overflow-y-auto pr-1" onSubmit={submeter}>
          {/* Seção: Recebimento */}
          <section className="space-y-4">
            <SectionLabel icon={<IconCaixas className="w-3.5 h-3.5" />}>Recebimento</SectionLabel>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel htmlFor="data-chegada" icon={<IconCalendar className="w-3.5 h-3.5" />}>Data de chegada</FieldLabel>
                <Input id="data-chegada" type="date" value={dataChegada} onChange={(e) => setDataChegada(e.target.value)} />
              </div>
              <div>
                <FieldLabel htmlFor="tipo-servico" icon={<IconWrench className="w-3.5 h-3.5" />}>Tipo de serviço</FieldLabel>
                <Select id="tipo-servico" value={tipo} onChange={(e) => setTipo(e.target.value as TipoServico)}>
                  <option value="C">Calibração</option>
                  <option value="M">Manutenção</option>
                  <option value="A">Ambas</option>
                </Select>
              </div>
            </div>

            {/* Caixa */}
            <div>
              <FieldLabel htmlFor="caixa-q" icon={<IconCaixas className="w-3.5 h-3.5" />}>
                Caixa {caixaTravada ? '' : '(opcional)'}
              </FieldLabel>
              {caixaTravada ? (
                <div className="inline-flex items-center gap-2 rounded-full bg-primary/15 text-primary border border-primary/40 px-3 py-1.5 text-sm font-semibold">
                  <IconCaixas className="w-4 h-4" />
                  Caixa #{caixa}
                </div>
              ) : caixaId ? (
                <div className="flex items-center justify-between rounded-lg border border-border bg-background-elevated px-3 py-2.5 text-sm">
                  <span className="inline-flex items-center gap-2 font-semibold text-slate-200">
                    <IconCaixas className="w-4 h-4 text-primary" />
                    Caixa #{caixaId}
                  </span>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-danger transition-colors"
                    onClick={() => setCaixaId(null)}
                  >
                    <IconX className="w-3.5 h-3.5" /> remover
                  </button>
                </div>
              ) : (
                <div>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
                      <IconSearch className="w-4 h-4" />
                    </span>
                    <input
                      id="caixa-q"
                      value={caixaQ}
                      onChange={(e) => setCaixaQ(e.target.value)}
                      placeholder="Buscar por nº/descrição"
                      className="w-full pl-9 pr-3 py-2.5 text-sm rounded-lg border border-border bg-background-elevated text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-colors"
                    />
                  </div>
                  {caixaResultados.length > 0 && (
                    <ul className="mt-1.5 divide-y divide-border rounded-lg border border-border overflow-hidden">
                      {caixaResultados.map((c) => (
                        <li key={c.id}>
                          <button
                            type="button"
                            className="w-full flex items-center gap-2.5 text-left px-3 py-2.5 text-sm hover:bg-background-elevated transition-colors"
                            onClick={() => { setCaixaId(c.id); setCaixaResultados([]); setCaixaQ('') }}
                          >
                            <IconCaixas className="w-4 h-4 text-slate-500 shrink-0" />
                            <span className="min-w-0">
                              <span className="font-semibold text-slate-200">#{c.id}</span>
                              {c.obs && <span className="block text-xs text-slate-500 truncate">{c.obs}</span>}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  {caixaQ.trim() && (
                    <button
                      type="button"
                      onClick={criarCaixa}
                      disabled={criandoCaixa}
                      className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:text-primary-600 disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 rounded"
                    >
                      <IconPlus className="w-3.5 h-3.5" />
                      {criandoCaixa ? 'Criando…' : `Criar caixa "${caixaQ.trim()}"`}
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Condição de chegada */}
            <div>
              <FieldLabel htmlFor="condicao" icon={<IconTag className="w-3.5 h-3.5" />}>Condição de chegada</FieldLabel>
              <Select id="condicao" value={condicao} onChange={(e) => setCondicao(e.target.value)}>
                <option value="">—</option>
                {CONDICOES_CHEGADA.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </div>
          </section>

          {/* Seção: Acessórios */}
          <section className="space-y-4 border-t border-border pt-5">
            <SectionLabel icon={<IconTag className="w-3.5 h-3.5" />}>Acessórios</SectionLabel>

            <div>
              <FieldLabel icon={<IconTag className="w-3.5 h-3.5" />}>Checklist</FieldLabel>
              <div className="flex flex-wrap gap-2">
                {CHECKLIST_ACESSORIOS.map((item) => {
                  const ativo = checklist.includes(item.id)
                  return (
                    <button
                      key={item.id}
                      type="button"
                      aria-pressed={ativo}
                      onClick={() => toggleChecklist(item.id)}
                      className={
                        'rounded-full px-3 py-1.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 ' +
                        (ativo
                          ? 'bg-primary/15 text-primary border border-primary/40'
                          : 'border border-border text-slate-400 hover:bg-background-elevated hover:text-slate-200')
                      }
                    >
                      {item.label}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel htmlFor="pilhas" icon={<IconBattery className="w-3.5 h-3.5" />}>Pilhas</FieldLabel>
                <Input id="pilhas" type="number" min={0} value={pilhas} onChange={(e) => setPilhas(e.target.value)} />
              </div>
              <div>
                <FieldLabel htmlFor="bocais" icon={<IconWrench className="w-3.5 h-3.5" />}>Bocais</FieldLabel>
                <Input id="bocais" type="number" min={0} value={bocais} onChange={(e) => setBocais(e.target.value)} />
              </div>
            </div>
          </section>

          {/* Seção: Observações */}
          <section className="space-y-2 border-t border-border pt-5">
            <SectionLabel icon={<IconNote className="w-3.5 h-3.5" />}>Observações</SectionLabel>
            <textarea
              id="obs"
              value={obs}
              onChange={(e) => setObs(e.target.value)}
              rows={3}
              placeholder="Anote detalhes do recebimento (opcional)"
              className="w-full px-3 py-2.5 text-sm rounded-lg border border-border bg-background-elevated text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-colors resize-none"
            />
          </section>

          {erro && (
            <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger space-y-2">
              <p className="flex items-start gap-2">
                <IconAlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{erro}</span>
              </p>
              {osAtivaId && (
                <button
                  type="button"
                  onClick={() => navigate(`/app/ordens/${osAtivaId}`)}
                  className="ml-6 text-xs font-semibold text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-primary/50 rounded"
                >
                  Ver OS atual
                </button>
              )}
            </div>
          )}
        </form>
      </div>
    </Modal>
  )
}
