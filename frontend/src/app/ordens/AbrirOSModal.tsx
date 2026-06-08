import { useState, useEffect, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal } from '../../components/ui/Modal'
import { Select } from '../../components/ui/Select'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { ApiError } from '../../lib/api'
import { ordensApi, CHECKLIST_ACESSORIOS, CONDICOES_CHEGADA, type TipoServico } from './api'
import { caixasApi, type CaixaListItem } from '../caixas/api'

function hojeISO(): string {
  const d = new Date()
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10)
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
          <Button type="submit" form="form-abrir-os" disabled={enviando}>Abrir</Button>
        </>
      }
    >
      <div className="overflow-y-auto max-h-[60vh]">
        <form id="form-abrir-os" className="space-y-4" onSubmit={submeter}>
          <div className="grid grid-cols-2 gap-3">
            <Input id="data-chegada" label="Data de chegada" type="date" value={dataChegada} onChange={(e) => setDataChegada(e.target.value)} />
            <Select id="tipo-servico" label="Tipo de serviço" value={tipo} onChange={(e) => setTipo(e.target.value as TipoServico)}>
              <option value="C">Calibração</option>
              <option value="M">Manutenção</option>
              <option value="A">Ambas</option>
            </Select>
          </div>

          {caixaTravada ? (
            <p className="text-sm text-slate-400">Caixa: <span className="font-semibold text-slate-200">#{caixa}</span></p>
          ) : caixaId ? (
            <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm">
              <span className="text-slate-200">Caixa #{caixaId}</span>
              <button type="button" className="text-xs text-danger hover:underline" onClick={() => setCaixaId(null)}>remover</button>
            </div>
          ) : (
            <div>
              <Input id="caixa-q" label="Caixa (opcional)" value={caixaQ} onChange={(e) => setCaixaQ(e.target.value)} placeholder="Buscar por nº/descrição" />
              {caixaResultados.length > 0 && (
                <ul className="mt-1 divide-y divide-border rounded-lg border border-border overflow-hidden">
                  {caixaResultados.map((c) => (
                    <li key={c.id}>
                      <button type="button" className="w-full text-left px-3 py-2 text-sm hover:bg-background-elevated" onClick={() => { setCaixaId(c.id); setCaixaResultados([]); setCaixaQ('') }}>
                        <span className="font-semibold text-slate-200">#{c.id}</span>
                        {c.obs && <span className="text-slate-500"> · {c.obs}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {caixaQ.trim() && (
                <button type="button" onClick={criarCaixa} disabled={criandoCaixa} className="mt-1 text-xs font-semibold text-primary hover:underline disabled:opacity-50">
                  + Criar caixa "{caixaQ.trim()}"
                </button>
              )}
            </div>
          )}

          <Select id="condicao" label="Condição de chegada" value={condicao} onChange={(e) => setCondicao(e.target.value)}>
            <option value="">—</option>
            {CONDICOES_CHEGADA.map((c) => <option key={c} value={c}>{c}</option>)}
          </Select>

          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Checklist de acessórios</label>
            <div className="grid grid-cols-2 gap-1.5">
              {CHECKLIST_ACESSORIOS.map((item) => (
                <label key={item.id} className="flex items-center gap-2 text-sm text-slate-300">
                  <input type="checkbox" checked={checklist.includes(item.id)} onChange={() => toggleChecklist(item.id)} />
                  {item.label}
                </label>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Input id="pilhas" label="Pilhas" type="number" min={0} value={pilhas} onChange={(e) => setPilhas(e.target.value)} />
            <Input id="bocais" label="Bocais" type="number" min={0} value={bocais} onChange={(e) => setBocais(e.target.value)} />
          </div>

          <div>
            <label htmlFor="obs" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observações</label>
            <textarea id="obs" value={obs} onChange={(e) => setObs(e.target.value)} rows={3} className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50" />
          </div>

          {erro && (
            <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger space-y-2">
              <p>{erro}</p>
              {osAtivaId && (
                <button type="button" onClick={() => navigate(`/app/ordens/${osAtivaId}`)} className="text-xs font-semibold text-primary hover:underline">Ver OS atual</button>
              )}
            </div>
          )}
        </form>
      </div>
    </Modal>
  )
}
