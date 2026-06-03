import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { tiposCalibragemApi, type TipoCalibragem } from '../cadastros/api'
import { ordensApi, type OrdemDetalhe, type AvancarPayload } from './api'

function maisUmAno(): string {
  const d = new Date()
  d.setFullYear(d.getFullYear() + 1)
  return d.toISOString().slice(0, 10)
}

function calcMedia(t1: string, t2: string, t3: string): string {
  const vals = [t1, t2, t3]
  if (vals.some((v) => v.trim() === '')) return ''
  const nums = vals.map((v) => Number(v.replace(',', '.')))
  if (nums.some((n) => Number.isNaN(n))) return ''
  return ((nums[0] + nums[1] + nums[2]) / 3).toFixed(2).replace('.', ',')
}

export function AvancarModal({ os, rotulo, pedeCodRetorno, pedeCalibracao, onClose, onConcluido }: {
  os: OrdemDetalhe
  rotulo: string
  pedeCodRetorno?: boolean
  pedeCalibracao?: boolean
  onClose: () => void
  onConcluido: (os: OrdemDetalhe) => void
}) {
  const [obs, setObs] = useState('')
  const [codRetorno, setCodRetorno] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  const [tipos, setTipos] = useState<TipoCalibragem[]>([])
  const [tipoCal, setTipoCal] = useState('')
  const [cert, setCert] = useState('')
  const [temp, setTemp] = useState('')
  const [pressao, setPressao] = useState('')
  const [t1, setT1] = useState('')
  const [t2, setT2] = useState('')
  const [t3, setT3] = useState('')
  const [media, setMedia] = useState('')
  const [mediaEditada, setMediaEditada] = useState(false)
  const [situacao, setSituacao] = useState('')
  const [pdf, setPdf] = useState('')
  const [prox, setProx] = useState(pedeCalibracao ? maisUmAno() : '')

  useEffect(() => {
    if (!pedeCalibracao) return
    let ativo = true
    void tiposCalibragemApi.listar().then((ts) => { if (ativo) setTipos(ts) }).catch(() => {})
    return () => { ativo = false }
  }, [pedeCalibracao])

  useEffect(() => {
    if (!pedeCalibracao || mediaEditada) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMedia(calcMedia(t1, t2, t3))
  }, [t1, t2, t3, mediaEditada, pedeCalibracao])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (pedeCodRetorno && !codRetorno.trim()) {
      setErro('Código de retorno é obrigatório.')
      return
    }
    const payload: AvancarPayload = {
      obs: obs.trim() || null,
      cod_retorno: pedeCodRetorno ? codRetorno.trim() : null,
    }
    if (pedeCalibracao) {
      payload.tipo_calibragem = tipoCal ? Number(tipoCal) : null
      payload.calib_cert = cert.trim() || null
      payload.calib_temp = temp.trim() || null
      payload.calib_pressao = pressao.trim() || null
      payload.calib_teste1 = t1.trim() || null
      payload.calib_teste2 = t2.trim() || null
      payload.calib_teste3 = t3.trim() || null
      payload.calib_teste_media = media.trim() || null
      payload.calib_situacao = situacao.trim() || null
      payload.pdf_certificado = pdf.trim() || null
      payload.prox_calibragem = prox || null
    }
    setEnviando(true)
    try {
      const atualizada = await ordensApi.avancar(os.id, payload)
      onConcluido(atualizada)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao avançar')
    } finally {
      setEnviando(false)
    }
  }

  const inputClass = 'w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50'

  return (
    <Modal
      open
      onClose={onClose}
      title={rotulo}
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-avancar" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Confirmar</button>
        </>
      }
    >
      <form id="form-avancar" className="space-y-4" onSubmit={submeter}>
        {pedeCodRetorno && (
          <Input id="cod-retorno" label="Código de retorno" value={codRetorno} onChange={(e) => setCodRetorno(e.target.value)} required />
        )}
        {pedeCalibracao && (
          <>
            <Select id="tipo-cal" label="Tipo de calibragem" value={tipoCal} onChange={(e) => setTipoCal(e.target.value)}>
              <option value="">— selecione —</option>
              {tipos.map((t) => <option key={t.id} value={t.id}>{t.descricao}</option>)}
            </Select>
            <div className="grid grid-cols-2 gap-3">
              <Input id="cert" label="Nº do certificado" value={cert} onChange={(e) => setCert(e.target.value)} />
              <Input id="situacao" label="Situação" value={situacao} onChange={(e) => setSituacao(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input id="temp" label="Temperatura" value={temp} onChange={(e) => setTemp(e.target.value)} />
              <Input id="pressao" label="Pressão" value={pressao} onChange={(e) => setPressao(e.target.value)} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Input id="t1" label="Teste 1" value={t1} onChange={(e) => setT1(e.target.value)} />
              <Input id="t2" label="Teste 2" value={t2} onChange={(e) => setT2(e.target.value)} />
              <Input id="t3" label="Teste 3" value={t3} onChange={(e) => setT3(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input id="media" label="Média dos testes" value={media} onChange={(e) => { setMediaEditada(true); setMedia(e.target.value) }} />
              <Input id="prox" label="Próxima calibração" type="date" value={prox} onChange={(e) => setProx(e.target.value)} />
            </div>
            <Input id="pdf" label="PDF do certificado (nome ou URL)" value={pdf} onChange={(e) => setPdf(e.target.value)} />
          </>
        )}
        <div>
          <label htmlFor="obs" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observação</label>
          <textarea id="obs" value={obs} onChange={(e) => setObs(e.target.value)} rows={3} className={inputClass} />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
