import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { funcionariosApi, type Funcionario, type FuncionarioPayload } from './api'
import { setoresApi, type Setor } from '../cadastros/api'

const VAZIO: FuncionarioPayload = { nome: '', matricula: null, cargo: null, setor: null, email: null, admissao: null, ativo: true }

export function FuncionariosSection({ clienteId, podeEditar }: { clienteId: number; podeEditar: boolean }) {
  const [itens, setItens] = useState<Funcionario[] | null>(null)
  const [setores, setSetores] = useState<Setor[]>([])
  const [erro, setErro] = useState('')
  const [aberto, setAberto] = useState(false)
  const [editandoId, setEditandoId] = useState<number | null>(null)
  const [form, setForm] = useState<FuncionarioPayload>(VAZIO)
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function carregar() {
    setErro('')
    try {
      setItens(await funcionariosApi.listarPorCliente(clienteId))
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
      setItens([])
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void carregar()
    void setoresApi.listar().then(setSetores).catch(() => setSetores([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clienteId])

  function nomeSetor(id: number | null) {
    return setores.find((s) => s.id === id)?.descricao ?? '—'
  }
  function set<K extends keyof FuncionarioPayload>(chave: K, valor: FuncionarioPayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }
  function abrirNovo() {
    setEditandoId(null); setForm(VAZIO); setErroForm(''); setAberto(true)
  }
  function abrirEdicao(fn: Funcionario) {
    setEditandoId(fn.id)
    setForm({ nome: fn.nome ?? '', matricula: fn.matricula, cargo: fn.cargo, setor: fn.setor, email: fn.email, admissao: fn.admissao, ativo: fn.ativo })
    setErroForm(''); setAberto(true)
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      if (editandoId !== null) await funcionariosApi.atualizar(editandoId, form)
      else await funcionariosApi.criar(clienteId, form)
      setAberto(false); await carregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(fn: Funcionario) {
    if (!window.confirm(`Excluir o funcionário "${fn.nome}"?`)) return
    try { await funcionariosApi.excluir(fn.id); await carregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao excluir') }
  }

  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Funcionários</h2>
        {podeEditar && <Button onClick={abrirNovo}>Novo funcionário</Button>}
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-8"><Spinner className="w-6 h-6" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum funcionário.</p>
      ) : (
        <Table head={<><TH>Nome</TH><TH>Cargo</TH><TH>Setor</TH><TH>E-mail</TH>{podeEditar && <TH>Ações</TH>}</>}>
          {itens.map((fn) => (
            <tr key={fn.id} className="hover:bg-background-elevated transition-colors">
              <TD>{fn.nome ?? '—'}</TD>
              <TD>{fn.cargo ?? '—'}</TD>
              <TD>{nomeSetor(fn.setor)}</TD>
              <TD>{fn.email ?? '—'}</TD>
              {podeEditar && (
                <TD>
                  <div className="flex gap-3">
                    <button onClick={() => abrirEdicao(fn)} className="text-xs text-primary hover:underline">Editar</button>
                    <button onClick={() => excluir(fn)} className="text-xs text-danger hover:underline">Excluir</button>
                  </div>
                </TD>
              )}
            </tr>
          ))}
        </Table>
      )}
      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editandoId !== null ? 'Editar funcionário' : 'Novo funcionário'}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-func" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-func" className="space-y-4" onSubmit={salvar}>
            <Input id="f-nome" label="Nome" value={form.nome} onChange={(e) => set('nome', e.target.value)} required />
            <div className="grid grid-cols-2 gap-3">
              <Input id="f-matricula" label="Matrícula" value={form.matricula ?? ''} onChange={(e) => set('matricula', e.target.value || null)} />
              <Input id="f-cargo" label="Cargo" value={form.cargo ?? ''} onChange={(e) => set('cargo', e.target.value || null)} />
            </div>
            <Select id="f-setor" label="Setor" value={form.setor ? String(form.setor) : ''} onChange={(e) => set('setor', e.target.value ? Number(e.target.value) : null)}>
              <option value="">— sem setor —</option>
              {setores.map((s) => <option key={s.id} value={s.id}>{s.descricao}</option>)}
            </Select>
            <Input id="f-email" label="E-mail" type="email" value={form.email ?? ''} onChange={(e) => set('email', e.target.value || null)} />
            <Input id="f-admissao" label="Admissão" type="date" value={form.admissao ?? ''} onChange={(e) => set('admissao', e.target.value || null)} />
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={form.ativo} onChange={(e) => set('ativo', e.target.checked)} className="accent-primary" />
              Ativo
            </label>
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </div>
  )
}
