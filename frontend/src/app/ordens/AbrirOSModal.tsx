import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal } from '../../components/ui/Modal'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { ordensApi, type TipoServico } from './api'

export function AbrirOSModal({ equipamentoClienteId, osAtual, onClose }: {
  equipamentoClienteId: number
  osAtual: number | null
  onClose: () => void
}) {
  const navigate = useNavigate()
  const [tipo, setTipo] = useState<TipoServico>('C')
  const [condicao, setCondicao] = useState('')
  const [acessorios, setAcessorios] = useState('')
  const [erro, setErro] = useState('')
  const [osAtivaId, setOsAtivaId] = useState<number | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setOsAtivaId(null)
    setEnviando(true)
    try {
      const os = await ordensApi.abrir({
        equipamento_cliente: equipamentoClienteId,
        tipo_servico: tipo,
        condicao_chegada: condicao.trim() || null,
        acessorios: acessorios.trim() || null,
      })
      navigate(`/app/ordens/${os.id}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setErro('Este aparelho já possui uma OS ativa.')
        setOsAtivaId(osAtual)
      } else {
        setErro(err instanceof ApiError ? err.message : 'Falha ao abrir OS')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Abrir OS"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-abrir-os" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Abrir</button>
        </>
      }
    >
      <form id="form-abrir-os" className="space-y-4" onSubmit={submeter}>
        <Select id="tipo-servico" label="Tipo de serviço" value={tipo} onChange={(e) => setTipo(e.target.value as TipoServico)}>
          <option value="C">Calibração</option>
          <option value="M">Manutenção</option>
          <option value="A">Ambas</option>
        </Select>
        <div>
          <label htmlFor="condicao" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Condição de chegada</label>
          <textarea id="condicao" value={condicao} onChange={(e) => setCondicao(e.target.value)} rows={2} className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50" />
        </div>
        <div>
          <label htmlFor="acessorios" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Acessórios</label>
          <textarea id="acessorios" value={acessorios} onChange={(e) => setAcessorios(e.target.value)} rows={2} className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50" />
        </div>
        {erro && (
          <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger space-y-2">
            <p>{erro}</p>
            {osAtivaId && (
              <button type="button" onClick={() => navigate(`/app/ordens/${osAtivaId}`)} className="text-xs font-semibold text-primary hover:underline">Ver OS atual</button>
            )}
          </div>
        )}
      </form>
    </Modal>
  )
}
