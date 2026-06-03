import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Table, TH, TD } from '../../components/ui/Table'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { equipamentosClienteApi, STATUS_CALIBRACAO, type EquipamentoCliente, type EquipamentoClientePayload, type Historico, type StatusCalibracao } from './api'
import { equipamentosApi, type Equipamento } from '../cadastros/api'

const VAZIO: EquipamentoClientePayload = {
  cliente: 0, equipamento: 0, modulo: 0, serie: null, patrimonio: null,
  datacompra: null, ult_calibragem: null, prox_calibragem: null, ativo: true, status: 'A',
}

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>
      {children}
    </div>
  )
}

export function EquipamentoClienteDetailPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const editando = id !== undefined
  const podeEditar = isAdmin(user)
  const clienteParam = searchParams.get('cliente')
  const clienteId = clienteParam ? Number(clienteParam) : 0

  const [form, setForm] = useState<EquipamentoClientePayload>({ ...VAZIO, cliente: clienteId })
  const [obj, setObj] = useState<EquipamentoCliente | null>(null)
  const [catalogo, setCatalogo] = useState<Equipamento[]>([])
  const [historico, setHistorico] = useState<Historico[]>([])
  const [carregando, setCarregando] = useState(editando)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    void equipamentosApi.listar().then(setCatalogo).catch(() => setCatalogo([]))
  }, [])

  useEffect(() => {
    if (!editando) return
    let ativo = true
    equipamentosClienteApi
      .obter(Number(id))
      .then((e) => {
        if (!ativo) return
        setObj(e)
        setForm({
          cliente: e.cliente, equipamento: e.equipamento, modulo: e.modulo, serie: e.serie, patrimonio: e.patrimonio,
          datacompra: e.datacompra, ult_calibragem: e.ult_calibragem, prox_calibragem: e.prox_calibragem,
          ativo: e.ativo, status: (e.status as 'A' | 'I' | 'M'),
        })
      })
      .catch((err) => {
        if (ativo) setErro(err instanceof ApiError ? err.message : 'Falha ao carregar')
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    void equipamentosClienteApi.historico(Number(id)).then((h) => { if (ativo) setHistorico(h) }).catch(() => {})
    return () => {
      ativo = false
    }
  }, [id, editando])

  function set<K extends keyof EquipamentoClientePayload>(chave: K, valor: EquipamentoClientePayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErro(''); setEnviando(true)
    try {
      if (editando) {
        const { cliente: _c, ...resto } = form
        void _c
        const atualizado = await equipamentosClienteApi.atualizar(Number(id), resto)
        setObj(atualizado)
      } else {
        const novo = await equipamentosClienteApi.criar(form)
        navigate(`/app/frota/${novo.id}`, { replace: true })
        return
      }
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir() {
    if (!editando) return
    if (!window.confirm('Excluir este aparelho?')) return
    setErro('')
    try {
      await equipamentosClienteApi.excluir(Number(id))
      navigate('/app/frota', { replace: true })
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao excluir')
    }
  }

  if (carregando) {
    return <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
  }

  if (!editando && !clienteId) {
    return (
      <div className="px-4 md:px-6 py-6">
        <p className="text-sm text-slate-400">Abra a partir da frota de um cliente para cadastrar um aparelho.</p>
        <Button variant="secondary" className="mt-3" onClick={() => navigate('/app/frota')}>Ir para a Frota</Button>
      </div>
    )
  }

  const ro = !podeEditar
  const statusCal: StatusCalibracao | null = obj ? obj.status_calibracao : null
  const sc = statusCal ? STATUS_CALIBRACAO[statusCal] : null
  const nomeCliente = obj?.cliente_nome ?? (clienteId ? `#${clienteId}` : '')

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-extrabold text-slate-100">{editando ? (obj?.equipamento_descricao || 'Aparelho') : 'Novo aparelho'}</h1>
          {sc && <Badge tone={sc.tone}>{sc.label}</Badge>}
        </div>
        <div className="flex gap-2">
          {editando && podeEditar && <Button variant="danger" onClick={excluir}>Excluir</Button>}
          <Button variant="secondary" onClick={() => navigate('/app/frota')}>Voltar</Button>
        </div>
      </div>

      <p className="text-sm text-slate-400">Cliente: {nomeCliente}</p>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      <form className="space-y-6" onSubmit={salvar}>
        <Secao titulo="Aparelho">
          <Select id="ec-equipamento" label="Equipamento (catálogo)" value={form.equipamento ? String(form.equipamento) : ''} onChange={(e) => set('equipamento', Number(e.target.value))} disabled={ro} required>
            <option value="">— selecione —</option>
            {catalogo.map((c) => <option key={c.id} value={c.id}>{c.descricao}</option>)}
          </Select>
          <div className="grid grid-cols-2 gap-3">
            <Input id="ec-serie" label="Série" value={form.serie ?? ''} onChange={(e) => set('serie', e.target.value || null)} disabled={ro} />
            <Input id="ec-patrimonio" label="Patrimônio" value={form.patrimonio ?? ''} onChange={(e) => set('patrimonio', e.target.value || null)} disabled={ro} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input id="ec-modulo" label="Módulo" type="number" value={String(form.modulo)} onChange={(e) => set('modulo', Number(e.target.value) || 0)} disabled={ro} />
            <Select id="ec-status" label="Situação" value={form.status} onChange={(e) => set('status', e.target.value as 'A' | 'I' | 'M')} disabled={ro}>
              <option value="A">Ativo</option>
              <option value="I">Inativo</option>
              <option value="M">Manutenção</option>
            </Select>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" checked={form.ativo} onChange={(e) => set('ativo', e.target.checked)} disabled={ro} className="accent-primary" />
            Ativo
          </label>
        </Secao>

        <Secao titulo="Calibração">
          <div className="grid grid-cols-3 gap-3">
            <Input id="ec-datacompra" label="Compra" type="date" value={form.datacompra ?? ''} onChange={(e) => set('datacompra', e.target.value || null)} disabled={ro} />
            <Input id="ec-ult" label="Última calibração" type="date" value={form.ult_calibragem ?? ''} onChange={(e) => set('ult_calibragem', e.target.value || null)} disabled={ro} />
            <Input id="ec-prox" label="Próxima calibração" type="date" value={form.prox_calibragem ?? ''} onChange={(e) => set('prox_calibragem', e.target.value || null)} disabled={ro} />
          </div>
        </Secao>

        {podeEditar && (
          <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-60 transition-all">
            {editando ? 'Salvar alterações' : 'Criar aparelho'}
          </button>
        )}
      </form>

      {editando && obj && (obj.calib_cert || obj.calib_situacao || obj.calib_teste_media) && (
        <Secao titulo="Última calibração (resultado da OS)">
          <div className="grid grid-cols-2 gap-3 text-sm text-slate-300">
            <p>Certificado: <span className="text-slate-100">{obj.calib_cert ?? '—'}</span></p>
            <p>Situação: <span className="text-slate-100">{obj.calib_situacao ?? '—'}</span></p>
            <p>Temperatura: <span className="text-slate-100">{obj.calib_temp ?? '—'}</span></p>
            <p>Pressão: <span className="text-slate-100">{obj.calib_pressao ?? '—'}</span></p>
            <p>Média dos testes: <span className="text-slate-100">{obj.calib_teste_media ?? '—'}</span></p>
          </div>
        </Secao>
      )}

      {editando && (
        <Secao titulo="Histórico de movimentação">
          {historico.length === 0 ? (
            <p className="text-sm text-slate-500">Sem movimentações.</p>
          ) : (
            <Table head={<><TH>Data</TH><TH>Saída</TH><TH>Entrada</TH></>}>
              {historico.map((m) => (
                <tr key={m.id} className="hover:bg-background-elevated transition-colors">
                  <TD>{m.datamov ?? '—'}</TD>
                  <TD>{m.saida ?? '—'}</TD>
                  <TD>{m.entrada ?? '—'}</TD>
                </tr>
              ))}
            </Table>
          )}
        </Secao>
      )}
    </div>
  )
}
