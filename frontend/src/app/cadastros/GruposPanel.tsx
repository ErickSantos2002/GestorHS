import { useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { IconButton, IconButtonGroup } from '../../components/ui/IconButton'
import { IconPencil, IconTrash } from '../../components/ui/icons'
import { useCrud } from './useCrud'
import { gruposApi, type Grupo } from './api'

export function GruposPanel() {
  const { itens, erro, setErro, recarregar } = useCrud<Grupo>(gruposApi)
  const [aberto, setAberto] = useState(false)
  const [editando, setEditando] = useState<Grupo | null>(null)
  const [descricao, setDescricao] = useState('')
  const [texto, setTexto] = useState('')
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)

  function abrirNovo() {
    setEditando(null); setDescricao(''); setTexto(''); setErroForm(''); setAberto(true)
  }
  function abrirEdicao(g: Grupo) {
    setEditando(g); setDescricao(g.descricao); setTexto(g.texto ?? ''); setErroForm(''); setAberto(true)
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      const payload = { descricao, texto: texto.trim() || null }
      if (editando) await gruposApi.atualizar(editando.id, payload)
      else await gruposApi.criar(payload)
      setAberto(false); await recarregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(g: Grupo) {
    if (!window.confirm(`Excluir "${g.descricao}"?`)) return
    try { await gruposApi.excluir(g.id); await recarregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao excluir') }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Grupos</h2>
        <Button onClick={abrirNovo}>Novo</Button>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum registro.</p>
      ) : (
        <Table head={<><TH>Descrição</TH><TH>Observação</TH><TH>Ações</TH></>}>
          {itens.map((g) => (
            <tr key={g.id} className="hover:bg-background-elevated transition-colors">
              <TD>{g.descricao}</TD>
              <TD>{g.texto ?? '—'}</TD>
              <TD>
                <IconButtonGroup>
                  <IconButton label="Editar" tone="editar" onClick={() => abrirEdicao(g)}>
                    <IconPencil className="w-4 h-4" />
                  </IconButton>
                  <IconButton label="Excluir" tone="excluir" onClick={() => excluir(g)}>
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
          title={editando ? 'Editar — Grupo' : 'Novo — Grupo'}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-grupo" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-grupo" className="space-y-4" onSubmit={salvar}>
            <Input id="g-descricao" label="Descrição" value={descricao} onChange={(e) => setDescricao(e.target.value)} required />
            <div>
              <label htmlFor="g-texto" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observação</label>
              <textarea id="g-texto" value={texto} onChange={(e) => setTexto(e.target.value)} className="w-full text-sm text-slate-200 bg-background-elevated border border-border rounded-lg px-3 py-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 placeholder-slate-500 leading-relaxed" rows={3} />
            </div>
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </div>
  )
}
