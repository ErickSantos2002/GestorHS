import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { caixasApi } from './api'

interface Props {
  caixaId: number
  numeroAtual: number
  onClose: () => void
  onTrocada: () => void
}

/** Corrige o numero da proposta da caixa — erro de digitacao no card do GrowthHS.
 *  Quem confere se a proposta e' do cliente da caixa e atualiza o card do TaskHS e'
 *  o backend; aqui so se colhe o numero. */
export function TrocarPropostaModal({ caixaId, numeroAtual, onClose, onTrocada }: Props) {
  const [numero, setNumero] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    const n = Number(numero.trim())
    if (!numero.trim() || !Number.isInteger(n) || n <= 0) {
      setErro('Informe o número da proposta.')
      return
    }
    if (n === numeroAtual) {
      setErro(`A caixa já está com a proposta #${numeroAtual}.`)
      return
    }
    setEnviando(true)
    try {
      await caixasApi.trocarProposta(caixaId, n)
      onTrocada()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao trocar a proposta')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Trocar proposta da caixa"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">
            Cancelar
          </button>
          <button type="submit" form="form-trocar-proposta" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">
            Trocar
          </button>
        </>
      }
    >
      <form id="form-trocar-proposta" onSubmit={onSubmit} className="space-y-4">
        <p className="text-sm text-slate-300">
          Proposta atual: <span className="font-semibold text-slate-100">#{numeroAtual}</span>
        </p>
        <Input
          id="trocar-proposta-numero"
          label="Número da proposta correta"
          inputMode="numeric"
          autoFocus
          value={numero}
          onChange={(e) => setNumero(e.target.value.replace(/\D/g, ''))}
        />
        <p className="text-xs text-slate-500">
          Só é aceita proposta do mesmo cliente da caixa. O card do TaskHS é atualizado
          junto. Corrija também o número no card do GrowthHS: um novo “Ganho” lá
          regrava o número antigo.
        </p>
        {erro && <p className="text-sm text-danger">{erro}</p>}
      </form>
    </Modal>
  )
}
