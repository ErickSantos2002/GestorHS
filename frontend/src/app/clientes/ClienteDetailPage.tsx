import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { clientesApi, type ClientePayload } from './api'
import { gruposApi, type Grupo } from '../cadastros/api'
import { FuncionariosSection } from './FuncionariosSection'

const VAZIO: ClientePayload = {
  nome: '', grupo: null, cgc: null, cpf: null, endereco: null, numero: null, complemento: null,
  bairro: null, municipio: null, estado: null, cep: null, contato: null, email: null, telefones: null,
  celular: null, whatsapp: null, whatsapp1: null, whatsapp2: null, insc_mun: null, insc_est: null,
  obs: null, ativo: true,
}

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>
      {children}
    </div>
  )
}

export function ClienteDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const editando = id !== undefined
  const podeEditar = isAdmin(user)

  const [form, setForm] = useState<ClientePayload>(VAZIO)
  const [grupos, setGrupos] = useState<Grupo[]>([])
  const [carregando, setCarregando] = useState(editando)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    void gruposApi.listar().then(setGrupos).catch(() => setGrupos([]))
  }, [])

  useEffect(() => {
    if (!editando) return
    let ativo = true
    clientesApi
      .obter(Number(id))
      .then((c) => {
        if (!ativo) return
        setForm({
          nome: c.nome ?? '', grupo: c.grupo, cgc: c.cgc, cpf: c.cpf, endereco: c.endereco, numero: c.numero,
          complemento: c.complemento, bairro: c.bairro, municipio: c.municipio, estado: c.estado, cep: c.cep,
          contato: c.contato, email: c.email, telefones: c.telefones, celular: c.celular, whatsapp: c.whatsapp,
          whatsapp1: c.whatsapp1, whatsapp2: c.whatsapp2, insc_mun: c.insc_mun, insc_est: c.insc_est, obs: c.obs, ativo: c.ativo,
        })
      })
      .catch((e) => {
        if (ativo) setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [id, editando])

  function set<K extends keyof ClientePayload>(chave: K, valor: ClientePayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }

  async function excluir() {
    if (!editando) return
    if (!window.confirm('Excluir este cliente?')) return
    setErro('')
    try {
      await clientesApi.excluir(Number(id))
      navigate('/app/clientes', { replace: true })
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao excluir')
    }
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErro(''); setEnviando(true)
    try {
      if (editando) {
        await clientesApi.atualizar(Number(id), form)
      } else {
        const novo = await clientesApi.criar(form)
        navigate(`/app/clientes/${novo.id}`, { replace: true })
        return
      }
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  if (carregando) {
    return <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
  }

  const ro = !podeEditar
  const txt = (label: string, chave: keyof ClientePayload) => (
    <Input
      id={`c-${chave}`}
      label={label}
      value={(form[chave] as string | null) ?? ''}
      onChange={(e) => set(chave, (e.target.value || null) as ClientePayload[typeof chave])}
      disabled={ro}
    />
  )

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">{editando ? (form.nome || 'Cliente') : 'Novo cliente'}</h1>
        <div className="flex gap-2">
          {editando && podeEditar && <Button variant="danger" onClick={excluir}>Excluir</Button>}
          {editando && <Button variant="secondary" onClick={() => navigate(`/app/frota?cliente=${id}`)}>Frota</Button>}
          <Button variant="secondary" onClick={() => navigate('/app/clientes')}>Voltar</Button>
        </div>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      <form className="space-y-6" onSubmit={salvar}>
        <Secao titulo="Identificação">
          <Input id="c-nome" label="Nome" value={form.nome} onChange={(e) => set('nome', e.target.value)} required disabled={ro} />
          <div className="grid grid-cols-2 gap-3">
            <Select id="c-grupo" label="Grupo" value={form.grupo ? String(form.grupo) : ''} onChange={(e) => set('grupo', e.target.value ? Number(e.target.value) : null)} disabled={ro}>
              <option value="">— sem grupo —</option>
              {grupos.map((g) => <option key={g.id} value={g.id}>{g.descricao}</option>)}
            </Select>
            <label className="flex items-center gap-2 text-sm text-slate-300 mt-6">
              <input type="checkbox" checked={form.ativo} onChange={(e) => set('ativo', e.target.checked)} disabled={ro} className="accent-primary" />
              Ativo
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">{txt('CNPJ', 'cgc')}{txt('CPF', 'cpf')}</div>
          <div className="grid grid-cols-2 gap-3">{txt('Inscrição municipal', 'insc_mun')}{txt('Inscrição estadual', 'insc_est')}</div>
        </Secao>

        <Secao titulo="Endereço">
          {txt('Logradouro', 'endereco')}
          <div className="grid grid-cols-2 gap-3">
            <Input id="c-numero" label="Número" type="number" value={form.numero != null ? String(form.numero) : ''} onChange={(e) => set('numero', e.target.value ? Number(e.target.value) : null)} disabled={ro} />
            {txt('Complemento', 'complemento')}
          </div>
          <div className="grid grid-cols-2 gap-3">{txt('Bairro', 'bairro')}{txt('CEP', 'cep')}</div>
          <div className="grid grid-cols-2 gap-3">{txt('Município', 'municipio')}{txt('UF', 'estado')}</div>
        </Secao>

        <Secao titulo="Contatos">
          <div className="grid grid-cols-2 gap-3">{txt('Contato', 'contato')}{txt('E-mail', 'email')}</div>
          <div className="grid grid-cols-2 gap-3">{txt('Telefones', 'telefones')}{txt('Celular', 'celular')}</div>
          <div className="grid grid-cols-3 gap-3">{txt('WhatsApp', 'whatsapp')}{txt('WhatsApp 2', 'whatsapp1')}{txt('WhatsApp 3', 'whatsapp2')}</div>
        </Secao>

        <Secao titulo="Observações">
          <textarea
            value={form.obs ?? ''}
            onChange={(e) => set('obs', e.target.value || null)}
            disabled={ro}
            rows={3}
            className="w-full text-sm text-slate-200 bg-background-elevated border border-border rounded-lg px-3 py-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 placeholder-slate-500 leading-relaxed disabled:opacity-60"
          />
        </Secao>

        {podeEditar && (
          <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-60 transition-all">
            {editando ? 'Salvar alterações' : 'Criar cliente'}
          </button>
        )}
      </form>

      {editando && <FuncionariosSection clienteId={Number(id)} podeEditar={podeEditar} />}
    </div>
  )
}
