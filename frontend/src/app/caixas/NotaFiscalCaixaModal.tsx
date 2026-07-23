import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { caixasApi } from './api'

interface Props {
  caixaId: number
  onClose: () => void
  onEnviado: () => void
}

// Mirror de ../ordens/NotaFiscalModal.tsx, mas anexando a mesma nota fiscal para
// todas as OS ativas da caixa de uma vez (POST /caixas/{id}/nota-fiscal) — evita
// o retrabalho de anexar aparelho-por-aparelho pela tela da OS.
export function NotaFiscalCaixaModal({ caixaId, onClose, onEnviado }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [numero, setNumero] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (!file) { setErro('Escolha o arquivo da nota fiscal (PDF ou XML).'); return }
    if (!numero.trim()) { setErro('Informe o número da nota fiscal.'); return }
    setEnviando(true)
    try {
      await caixasApi.enviarNotaFiscalCaixa(caixaId, file, numero.trim())
      onEnviado()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao anexar a nota fiscal')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Anexar nota fiscal da caixa"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">
            Cancelar
          </button>
          <button type="submit" form="form-nota-fiscal-caixa" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">
            Anexar
          </button>
        </>
      }
    >
      <form id="form-nota-fiscal-caixa" className="space-y-4" onSubmit={onSubmit}>
        <p className="text-sm text-slate-400">
          A nota fiscal é anexada a todas as OS ativas desta caixa de uma só vez.
        </p>
        <Input id="numero-nf-caixa" label="Número da nota fiscal" value={numero} onChange={(e) => setNumero(e.target.value)} maxLength={50} required />
        <div>
          <label htmlFor="arquivo-nf-caixa" className="block text-sm font-medium text-slate-300 mb-1.5">Arquivo (PDF ou XML)</label>
          <input
            id="arquivo-nf-caixa"
            type="file"
            accept="application/pdf,.pdf,application/xml,text/xml,.xml"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-background-elevated file:text-slate-200 file:text-sm"
          />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
