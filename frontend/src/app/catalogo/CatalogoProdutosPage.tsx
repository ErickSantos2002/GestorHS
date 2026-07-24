import { useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { IconButton, IconButtonGroup } from '../../components/ui/IconButton'
import { IconPencil, IconTrash } from '../../components/ui/icons'
import { useCrud } from '../cadastros/useCrud'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarPropostas } from '../../auth/roles'
import { PageContainer } from '../../components/ui/Page'
import { produtosApi, type Produto, type ProdutoPayload } from '../propostas/api'

const VAZIO: ProdutoPayload = {
  nome: '', sku: '', unidade: '', preco: 0, ncm: '', ativo: true,
}

export function CatalogoProdutosPage() {
  const { user } = useAuth()
  const { itens, erro, setErro, recarregar } = useCrud<Produto>(produtosApi)
  const [aberto, setAberto] = useState(false)
  const [editandoId, setEditandoId] = useState<number | null>(null)
  const [form, setForm] = useState<ProdutoPayload>(VAZIO)
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (!podeGerenciarPropostas(user)) {
    return (
      <div className="px-4 md:px-6 py-6">
        <p className="text-sm text-slate-400">Acesso restrito.</p>
      </div>
    )
  }

  function set<K extends keyof ProdutoPayload>(chave: K, valor: ProdutoPayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }

  function abrirNovo() {
    setEditandoId(null); setForm(VAZIO); setErroForm(''); setAberto(true)
  }
  function abrirEdicao(p: Produto) {
    setEditandoId(p.id)
    setForm({
      nome: p.nome, sku: p.sku ?? '', unidade: p.unidade ?? '',
      preco: p.preco, ncm: p.ncm ?? '', ativo: p.ativo,
    })
    setErroForm(''); setAberto(true)
  }

  async function salvar(ev: FormEvent) {
    ev.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      if (editandoId !== null) await produtosApi.atualizar(editandoId, form)
      else await produtosApi.criar(form)
      setAberto(false); await recarregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(p: Produto) {
    if (!window.confirm(`Excluir "${p.nome}"?`)) return
    try { await produtosApi.excluir(p.id); await recarregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao excluir') }
  }

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Produtos</h1>
        <Button onClick={abrirNovo}>Novo</Button>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum produto cadastrado.</p>
      ) : (
        <Table head={<><TH>Nome</TH><TH>SKU</TH><TH>Preço</TH><TH>Status</TH><TH>Ações</TH></>}>
          {itens.map((p) => (
            <tr key={p.id} className="hover:bg-background-elevated transition-colors">
              <TD>{p.nome}</TD>
              <TD>{p.sku ?? '—'}</TD>
              <TD>{p.preco.toFixed(2)}</TD>
              <TD><Badge tone={p.ativo ? 'primary' : 'neutral'}>{p.ativo ? 'Ativo' : 'Inativo'}</Badge></TD>
              <TD>
                <IconButtonGroup>
                  <IconButton label="Editar" tone="editar" onClick={() => abrirEdicao(p)}>
                    <IconPencil className="w-4 h-4" />
                  </IconButton>
                  <IconButton label="Excluir" tone="excluir" onClick={() => excluir(p)}>
                    <IconTrash className="w-4 h-4" />
                  </IconButton>
                </IconButtonGroup>
              </TD>
            </tr>
          ))}
        </Table>
      )}
      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editandoId !== null ? 'Editar — Produto' : 'Novo — Produto'}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-produto" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-produto" className="space-y-4" onSubmit={salvar}>
            <Input id="p-nome" label="Nome" value={form.nome} onChange={(ev) => set('nome', ev.target.value)} required />
            <div className="grid grid-cols-2 gap-3">
              <Input id="p-sku" label="SKU" value={form.sku ?? ''} onChange={(ev) => set('sku', ev.target.value)} />
              <Input id="p-unidade" label="Unidade" value={form.unidade ?? ''} onChange={(ev) => set('unidade', ev.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input id="p-preco" label="Preço" type="number" step="0.01" value={String(form.preco ?? 0)} onChange={(ev) => set('preco', Number(ev.target.value))} />
              <Input id="p-ncm" label="NCM" value={form.ncm ?? ''} onChange={(ev) => set('ncm', ev.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={form.ativo ?? true} onChange={(ev) => set('ativo', ev.target.checked)} className="accent-primary" />
              Ativo
            </label>
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </PageContainer>
  )
}
