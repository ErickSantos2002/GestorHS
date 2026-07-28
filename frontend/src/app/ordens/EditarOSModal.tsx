import { useState, type FormEvent, type ReactNode } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Select } from '../../components/ui/Select'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import {
  IconOrdens,
  IconCalendar,
  IconWrench,
  IconTag,
  IconBattery,
  IconNote,
  IconAlertCircle,
} from '../../components/ui/icons'
import { ApiError } from '../../lib/api'
import { ordensApi, CHECKLIST_ACESSORIOS, CONDICOES_CHEGADA, type TipoServico, type OrdemDetalhe } from './api'

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

export function EditarOSModal({ os, onClose, onSalvo }: {
  os: OrdemDetalhe
  onClose: () => void
  onSalvo: () => void
}) {
  const [dataChegada, setDataChegada] = useState(os.data_chegada ? os.data_chegada.slice(0, 10) : '')
  const [tipo, setTipo] = useState<TipoServico>((os.tipo_servico as TipoServico) || 'C')
  const [condicao, setCondicao] = useState(os.condicao_chegada ?? '')
  const [checklist, setChecklist] = useState<number[]>(os.checklist_ids ?? [])
  const [pilhas, setPilhas] = useState(String(os.pilhas ?? 0))
  const [bocais, setBocais] = useState(String(os.bocais ?? 0))
  const [obs, setObs] = useState(os.obs ?? '')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  function toggleChecklist(id: number) {
    setChecklist((cur) => cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id])
  }

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      await ordensApi.editar(os.id, {
        tipo_servico: tipo,
        condicao_chegada: condicao || null,
        checklist: checklist.length ? checklist : null,
        pilhas: Number(pilhas) || 0,
        bocais: Number(bocais) || 0,
        observacoes: obs.trim() || null,
        data_chegada: dataChegada || null,
      })
      onSalvo()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar edição')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Editar OS"
      size="xl"
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="form-editar-os" disabled={enviando}>
            {enviando ? 'Salvando…' : 'Salvar'}
          </Button>
        </>
      }
    >
      <div>
        {/* Cabeçalho do corpo */}
        <div className="flex items-center gap-3 mb-5">
          <div className="grid place-items-center w-10 h-10 rounded-xl bg-primary/15 text-primary shrink-0">
            <IconOrdens className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-200 leading-tight">Recebimento do equipamento</p>
            <p className="text-xs text-slate-500 mt-0.5">Ajuste os dados de entrada da OS #{os.id}.</p>
          </div>
        </div>

        <form id="form-editar-os" className="space-y-6" onSubmit={submeter}>
          {/* Seção: Recebimento */}
          <section className="space-y-4">
            <SectionLabel icon={<IconTag className="w-3.5 h-3.5" />}>Recebimento</SectionLabel>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel htmlFor="editar-data-chegada" icon={<IconCalendar className="w-3.5 h-3.5" />}>Data de chegada</FieldLabel>
                <Input id="editar-data-chegada" type="date" value={dataChegada} onChange={(e) => setDataChegada(e.target.value)} />
              </div>
              <div>
                <FieldLabel htmlFor="editar-tipo-servico" icon={<IconWrench className="w-3.5 h-3.5" />}>Tipo de serviço</FieldLabel>
                <Select id="editar-tipo-servico" value={tipo} onChange={(e) => setTipo(e.target.value as TipoServico)}>
                  <option value="C">Calibração</option>
                  <option value="M">Manutenção</option>
                  <option value="A">Ambas</option>
                </Select>
              </div>
            </div>

            {/* Condição de chegada */}
            <div>
              <FieldLabel htmlFor="editar-condicao" icon={<IconTag className="w-3.5 h-3.5" />}>Condição de chegada</FieldLabel>
              <Select id="editar-condicao" value={condicao} onChange={(e) => setCondicao(e.target.value)}>
                <option value="">—</option>
                {CONDICOES_CHEGADA.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </div>
          </section>

          {/* Seção: Acessórios */}
          <section className="space-y-4 border-t border-border pt-5">
            <SectionLabel icon={<IconTag className="w-3.5 h-3.5" />}>Acessórios que vieram com o aparelho</SectionLabel>

            <div>
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
                <FieldLabel htmlFor="editar-pilhas" icon={<IconBattery className="w-3.5 h-3.5" />}>Pilhas</FieldLabel>
                <Input id="editar-pilhas" type="number" min={0} value={pilhas} onChange={(e) => setPilhas(e.target.value)} />
              </div>
              <div>
                <FieldLabel htmlFor="editar-bocais" icon={<IconWrench className="w-3.5 h-3.5" />}>Bocais</FieldLabel>
                <Input id="editar-bocais" type="number" min={0} value={bocais} onChange={(e) => setBocais(e.target.value)} />
              </div>
            </div>
          </section>

          {/* Seção: Observações */}
          <section className="space-y-2 border-t border-border pt-5">
            <FieldLabel htmlFor="editar-obs" icon={<IconNote className="w-3.5 h-3.5" />}>Observações</FieldLabel>
            <textarea
              id="editar-obs"
              value={obs}
              onChange={(e) => setObs(e.target.value)}
              rows={3}
              placeholder="Anote detalhes do recebimento (opcional)"
              className="w-full px-3 py-2.5 text-sm rounded-lg border border-border bg-background-elevated text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-colors resize-none"
            />
          </section>

          {erro && (
            <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
              <p className="flex items-start gap-2">
                <IconAlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{erro}</span>
              </p>
            </div>
          )}
        </form>
      </div>
    </Modal>
  )
}
