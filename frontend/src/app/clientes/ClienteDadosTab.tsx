import { useEffect, useState, type FormEvent } from 'react'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin, podeGerenciarCadastros } from '../../auth/roles'
import { clientesApi, type Cliente, type ClientePayload } from './api'
import { gruposApi, type Grupo } from '../cadastros/api'
import { ClienteFormFields } from './ClienteFormFields'
import { FuncionariosSection } from './FuncionariosSection'
import { UsuariosPortalSection } from './UsuariosPortalSection'
import { DetailGrid, DetailMain, DetailAside } from '../../components/ui/Page'
import { useCliente } from './ClienteLayout'

export function ClienteDadosTab() {
  const { cliente, recarregar } = useCliente()
  const { user } = useAuth()
  const podeEditar = podeGerenciarCadastros(user)
  const [grupos, setGrupos] = useState<Grupo[]>([])
  const [form, setForm] = useState<ClientePayload>(() => paraForm(cliente))
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => { void gruposApi.listar().then(setGrupos).catch(() => setGrupos([])) }, [])
  // re-seed se o cliente recarregar
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { setForm(paraForm(cliente)) }, [cliente])

  function set<K extends keyof ClientePayload>(chave: K, valor: ClientePayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }
  async function salvar(e: FormEvent) {
    e.preventDefault(); setErro(''); setEnviando(true)
    try { await clientesApi.atualizar(cliente.id, form); recarregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao salvar') }
    finally { setEnviando(false) }
  }

  return (
    <>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      <DetailGrid>
        <DetailMain>
          <ClienteFormFields form={form} set={set} grupos={grupos} readOnly={!podeEditar}
            podeEditar={podeEditar} enviando={enviando} labelSubmit="Salvar alterações" onSubmit={salvar} />
        </DetailMain>
        <DetailAside>
          <FuncionariosSection clienteId={cliente.id} podeEditar={podeEditar} />
          {/* Usuarios do portal criam CREDENCIAL de acesso do cliente — continua so Admin,
              mesmo com o Laboratorio podendo editar o cadastro. */}
          {isAdmin(user) && <UsuariosPortalSection clienteId={cliente.id} />}
        </DetailAside>
      </DetailGrid>
    </>
  )
}

function paraForm(c: Cliente): ClientePayload {
  return {
    nome: c.nome ?? '', grupo: c.grupo, cgc: c.cgc, cpf: c.cpf, endereco: c.endereco, numero: c.numero,
    complemento: c.complemento, bairro: c.bairro, municipio: c.municipio, estado: c.estado, cep: c.cep,
    contato: c.contato, email: c.email, telefones: c.telefones, celular: c.celular, whatsapp: c.whatsapp,
    whatsapp1: c.whatsapp1, whatsapp2: c.whatsapp2, insc_mun: c.insc_mun, insc_est: c.insc_est, obs: c.obs, ativo: c.ativo,
  }
}
