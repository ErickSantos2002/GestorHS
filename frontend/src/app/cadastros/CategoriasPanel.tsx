import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { useCrud } from './useCrud'
import { categoriasApi, setoresApi, type Categoria, type Setor } from './api'

export function CategoriasPanel() {
  const { itens, erro, setErro, recarregar } = useCrud<Categoria>(categoriasApi)
  const [setores, setSetores] = useState<Setor[]>([])
  const [aberto, setAberto] = useState(false)
  const [editando, setEditando] = useState<Categoria | null>(null)
  const [descricao, setDescricao] = useState('')
  const [setorId, setSetorId] = useState('')
  const [posicao, setPosicao] = useState('0')
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    void setoresApi.listar().then(setSetores).catch(() => setSetores([]))
  }, [])

  function nomeSetor(id: number | null) {
    return setores.find((s) => s.id === id)?.descricao ?? '—'
  }

  function abrirNovo() {
    setEditando(null); setDescricao(''); setSetorId(''); setPosicao('0'); setErroForm(''); setAberto(true)
  }
  function abrirEdicao(c: Categoria) {
    setEditando(c); setDescricao(c.descricao ?? ''); setSetorId(c.setor ? String(c.setor) : ''); setPosicao(String(c.posicao)); setErroForm(''); setAberto(true)
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      const payload = { descricao, setor: setorId ? Number(setorId) : null, posicao: Number(posicao) || 0 }
      if (editando) await categoriasApi.atualizar(editando.id, payload)
      else await categoriasApi.criar(payload)
      setAberto(false); await recarregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(c: Categoria) {
    if (!window.confirm(`Excluir "${c.descricao}"?`)) return
    try { await categoriasApi.excluir(c.id); await recarregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao excluir') }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Categorias</h2>
        <Button onClick={abrirNovo}>Novo</Button>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum registro.</p>
      ) : (
        <Table head={<><TH>Descrição</TH><TH>Setor</TH><TH>Posição</TH><TH>Ações</TH></>}>
          {itens.map((c) => (
            <tr key={c.id} className="hover:bg-background-elevated transition-colors">
              <TD>{c.descricao ?? '—'}</TD>
              <TD>{nomeSetor(c.setor)}</TD>
              <TD>{c.posicao}</TD>
              <TD>
                <div className="flex gap-3">
                  <button onClick={() => abrirEdicao(c)} className="text-xs text-primary hover:underline">Editar</button>
                  <button onClick={() => excluir(c)} className="text-xs text-danger hover:underline">Excluir</button>
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
          title={editando ? 'Editar — Categoria' : 'Nova — Categoria'}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-categoria" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-categoria" className="space-y-4" onSubmit={salvar}>
            <Input id="c-descricao" label="Descrição" value={descricao} onChange={(e) => setDescricao(e.target.value)} required />
            <Select id="c-setor" label="Setor" value={setorId} onChange={(e) => setSetorId(e.target.value)}>
              <option value="">— sem setor —</option>
              {setores.map((s) => <option key={s.id} value={s.id}>{s.descricao}</option>)}
            </Select>
            <Input id="c-posicao" label="Posição" type="number" value={posicao} onChange={(e) => setPosicao(e.target.value)} />
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </div>
  )
}
