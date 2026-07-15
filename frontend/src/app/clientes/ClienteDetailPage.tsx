import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { clientesApi, type ClientePayload } from './api'
import { gruposApi, type Grupo } from '../cadastros/api'
import { ClienteFormFields } from './ClienteFormFields'
import { FuncionariosSection } from './FuncionariosSection'
import { UsuariosPortalSection } from './UsuariosPortalSection'
import { PageContainer, DetailGrid, DetailMain, DetailAside } from '../../components/ui/Page'

const VAZIO: ClientePayload = {
  nome: '', grupo: null, cgc: null, cpf: null, endereco: null, numero: null, complemento: null,
  bairro: null, municipio: null, estado: null, cep: null, contato: null, email: null, telefones: null,
  celular: null, whatsapp: null, whatsapp1: null, whatsapp2: null, insc_mun: null, insc_est: null,
  obs: null, ativo: true,
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

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">{editando ? (form.nome || 'Cliente') : 'Novo cliente'}</h1>
        <div className="flex gap-2">
          {editando && podeEditar && <Button variant="danger" onClick={excluir}>Excluir</Button>}
          {editando && <Button variant="secondary" onClick={() => navigate(`/app/equipamentos?cliente=${id}`)}>Equipamentos</Button>}
          <Button variant="secondary" onClick={() => navigate('/app/clientes')}>Voltar</Button>
        </div>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {editando ? (
        <DetailGrid>
          <DetailMain>
            <ClienteFormFields
              form={form}
              set={set}
              grupos={grupos}
              readOnly={!podeEditar}
              podeEditar={podeEditar}
              enviando={enviando}
              labelSubmit={editando ? 'Salvar alterações' : 'Criar cliente'}
              onSubmit={salvar}
            />
          </DetailMain>
          <DetailAside>
            <FuncionariosSection clienteId={Number(id)} podeEditar={podeEditar} />
            {podeEditar && <UsuariosPortalSection clienteId={Number(id)} />}
          </DetailAside>
        </DetailGrid>
      ) : (
        <div className="max-w-3xl">
          <ClienteFormFields
            form={form}
            set={set}
            grupos={grupos}
            readOnly={!podeEditar}
            podeEditar={podeEditar}
            enviando={enviando}
            labelSubmit={editando ? 'Salvar alterações' : 'Criar cliente'}
            onSubmit={salvar}
          />
        </div>
      )}
    </PageContainer>
  )
}
