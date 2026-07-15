import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { clientesApi, type ClientePayload } from './api'
import { gruposApi, type Grupo } from '../cadastros/api'
import { ClienteFormFields } from './ClienteFormFields'
import { PageContainer } from '../../components/ui/Page'

const VAZIO: ClientePayload = {
  nome: '', grupo: null, cgc: null, cpf: null, endereco: null, numero: null, complemento: null,
  bairro: null, municipio: null, estado: null, cep: null, contato: null, email: null, telefones: null,
  celular: null, whatsapp: null, whatsapp1: null, whatsapp2: null, insc_mun: null, insc_est: null,
  obs: null, ativo: true,
}

export function ClienteDetailPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const podeEditar = isAdmin(user)

  const [form, setForm] = useState<ClientePayload>(VAZIO)
  const [grupos, setGrupos] = useState<Grupo[]>([])
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    void gruposApi.listar().then(setGrupos).catch(() => setGrupos([]))
  }, [])

  function set<K extends keyof ClientePayload>(chave: K, valor: ClientePayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErro(''); setEnviando(true)
    try {
      const novo = await clientesApi.criar(form)
      navigate(`/app/clientes/${novo.id}`, { replace: true })
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Novo cliente</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => navigate('/app/clientes')}>Voltar</Button>
        </div>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      <div className="max-w-3xl">
        <ClienteFormFields
          form={form}
          set={set}
          grupos={grupos}
          readOnly={!podeEditar}
          podeEditar={podeEditar}
          enviando={enviando}
          labelSubmit="Criar cliente"
          onSubmit={salvar}
        />
      </div>
    </PageContainer>
  )
}
