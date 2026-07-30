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
import { type CrudClient } from './api'

interface SimpleItem {
  id: number
  descricao: string
}

type SimpleClient<T> = CrudClient<T, { descricao: string }, { descricao?: string }>

export function CadastroSimples<T extends SimpleItem>({ titulo, rotuloNovo = 'Novo', client }: { titulo: string; rotuloNovo?: string; client: SimpleClient<T> }) {
  const { itens, erro, setErro, recarregar } = useCrud<T>(client)
  const [aberto, setAberto] = useState(false)
  const [editando, setEditando] = useState<T | null>(null)
  const [descricao, setDescricao] = useState('')
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)

  function abrirNovo() {
    setEditando(null)
    setDescricao('')
    setErroForm('')
    setAberto(true)
  }

  function abrirEdicao(it: T) {
    setEditando(it)
    setDescricao(it.descricao)
    setErroForm('')
    setAberto(true)
  }

  async function salvar(e: FormEvent) {
    e.preventDefault()
    setErroForm('')
    setEnviando(true)
    try {
      if (editando) await client.atualizar(editando.id, { descricao })
      else await client.criar({ descricao })
      setAberto(false)
      await recarregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(it: T) {
    if (!window.confirm(`Excluir "${it.descricao}"?`)) return
    try {
      await client.excluir(it.id)
      await recarregar()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao excluir')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>
        <Button onClick={abrirNovo}>{rotuloNovo}</Button>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum registro.</p>
      ) : (
        <Table head={<><TH>Descrição</TH><TH>Ações</TH></>}>
          {itens.map((it) => (
            <tr key={it.id} className="hover:bg-background-elevated transition-colors">
              <TD>{it.descricao}</TD>
              <TD>
                <IconButtonGroup>
                  <IconButton label="Editar" tone="editar" onClick={() => abrirEdicao(it)}>
                    <IconPencil className="w-4 h-4" />
                  </IconButton>
                  <IconButton label="Excluir" tone="excluir" onClick={() => excluir(it)}>
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
          title={editando ? `Editar — ${titulo}` : `Novo — ${titulo}`}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-simples" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-simples" className="space-y-4" onSubmit={salvar}>
            <Input id="descricao" label="Descrição" value={descricao} onChange={(e) => setDescricao(e.target.value)} required />
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </div>
  )
}
