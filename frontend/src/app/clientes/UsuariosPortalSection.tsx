import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { usuariosPortalApi, type UsuarioPortal, type UsuarioPortalPayload } from './api'

const VAZIO: UsuarioPortalPayload = { login: '', nome: null, email: null, senha: '' }

export function UsuariosPortalSection({ clienteId }: { clienteId: number }) {
  const [itens, setItens] = useState<UsuarioPortal[] | null>(null)
  const [erro, setErro] = useState('')
  const [aberto, setAberto] = useState(false)
  const [editandoId, setEditandoId] = useState<number | null>(null)
  const [form, setForm] = useState<UsuarioPortalPayload>(VAZIO)
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [resetandoId, setResetandoId] = useState<number | null>(null)
  const [novaSenha, setNovaSenha] = useState('')

  async function carregar() {
    setErro('')
    try {
      setItens(await usuariosPortalApi.listarPorCliente(clienteId))
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
      setItens([])
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void carregar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clienteId])

  function set<K extends keyof UsuarioPortalPayload>(chave: K, valor: UsuarioPortalPayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }
  function abrirNovo() {
    setEditandoId(null); setForm(VAZIO); setErroForm(''); setAberto(true)
  }
  function abrirEdicao(u: UsuarioPortal) {
    setEditandoId(u.id)
    setForm({ login: u.login, nome: u.nome, email: u.email, senha: '' })
    setErroForm(''); setAberto(true)
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      if (editandoId !== null) await usuariosPortalApi.atualizar(editandoId, { login: form.login, nome: form.nome, email: form.email })
      else await usuariosPortalApi.criar(clienteId, form)
      setAberto(false); await carregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function salvarReset(e: FormEvent) {
    e.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      if (resetandoId !== null) await usuariosPortalApi.redefinirSenha(resetandoId, novaSenha)
      setResetandoId(null); setNovaSenha(''); await carregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao redefinir')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(u: UsuarioPortal) {
    if (!window.confirm(`Excluir o acesso "${u.login}"?`)) return
    try { await usuariosPortalApi.excluir(u.id); await carregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao excluir') }
  }

  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Usuários do portal</h2>
        <Button onClick={abrirNovo}>Novo acesso</Button>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-8"><Spinner className="w-6 h-6" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum acesso ao portal.</p>
      ) : (
        <Table head={<><TH>Login</TH><TH>Nome</TH><TH>E-mail</TH><TH>Status</TH><TH>Ações</TH></>}>
          {itens.map((u) => (
            <tr key={u.id} className="hover:bg-background-elevated transition-colors">
              <TD>{u.login}</TD>
              <TD>{u.nome ?? '—'}</TD>
              <TD>{u.email ?? '—'}</TD>
              <TD>{u.precisa_redefinir_senha ? <Badge tone="warning">Senha temporária</Badge> : <Badge tone="primary">Ativa</Badge>}</TD>
              <TD>
                <div className="flex gap-3">
                  <button onClick={() => abrirEdicao(u)} className="text-xs text-primary hover:underline">Editar</button>
                  <button onClick={() => { setResetandoId(u.id); setNovaSenha(''); setErroForm('') }} className="text-xs text-primary hover:underline">Redefinir senha</button>
                  <button onClick={() => excluir(u)} className="text-xs text-danger hover:underline">Excluir</button>
                </div>
              </TD>
            </tr>
          ))}
        </Table>
      )}

      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editandoId !== null ? 'Editar acesso' : 'Novo acesso'}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-up" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-up" className="space-y-4" onSubmit={salvar}>
            <Input id="up-login" label="Login" value={form.login} onChange={(e) => set('login', e.target.value)} required />
            <Input id="up-nome" label="Nome" value={form.nome ?? ''} onChange={(e) => set('nome', e.target.value || null)} />
            <Input id="up-email" label="E-mail" type="email" value={form.email ?? ''} onChange={(e) => set('email', e.target.value || null)} />
            {editandoId === null && (
              <Input id="up-senha" label="Senha temporária" type="password" value={form.senha} onChange={(e) => set('senha', e.target.value)} required />
            )}
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}

      {resetandoId !== null && (
        <Modal
          open
          onClose={() => setResetandoId(null)}
          title="Redefinir senha"
          footer={
            <>
              <button type="button" onClick={() => setResetandoId(null)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-rs" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Redefinir</button>
            </>
          }
        >
          <form id="form-rs" className="space-y-4" onSubmit={salvarReset}>
            <p className="text-sm text-slate-400">A nova senha é temporária — o cliente define a definitiva no próximo acesso.</p>
            <Input id="rs-senha" label="Nova senha temporária" type="password" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} required />
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </div>
  )
}
