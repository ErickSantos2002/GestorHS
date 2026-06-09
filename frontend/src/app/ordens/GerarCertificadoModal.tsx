import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { tiposCalibragemApi, type TipoCalibragem } from '../cadastros/api'
import { ordensApi, type OrdemDetalhe, type OSCertificado, type GerarCertificadoPayload } from './api'

function calcMedia(t1: string, t2: string, t3: string): string {
  const vals = [t1, t2, t3]
  if (vals.some((v) => v.trim() === '')) return ''
  const nums = vals.map((v) => Number(v.replace(',', '.')))
  if (nums.some((n) => Number.isNaN(n))) return ''
  return ((nums[0] + nums[1] + nums[2]) / 3).toFixed(2).replace('.', ',')
}

export function GerarCertificadoModal({ os, onClose, onGerado }: {
  os: OrdemDetalhe
  onClose: () => void
  onGerado: (certs: OSCertificado[]) => void
}) {
  const [tipos, setTipos] = useState<TipoCalibragem[]>([])
  const [tipoCal, setTipoCal] = useState(os.tipo_calibragem ? String(os.tipo_calibragem) : '')
  const [cert, setCert] = useState(os.calib_cert ?? '')
  const [temp, setTemp] = useState(os.calib_temp ?? '')
  const [pressao, setPressao] = useState(os.calib_pressao ?? '')
  const [t1, setT1] = useState(os.calib_teste1 ?? '')
  const [t2, setT2] = useState(os.calib_teste2 ?? '')
  const [t3, setT3] = useState(os.calib_teste3 ?? '')
  const [media, setMedia] = useState(os.calib_teste_media ?? '')
  const [mediaEditada, setMediaEditada] = useState(!!os.calib_teste_media)
  const [situacao, setSituacao] = useState(os.calib_situacao ?? '')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    let ativo = true
    void tiposCalibragemApi.listar().then((ts) => { if (ativo) setTipos(ts) }).catch(() => {})
    return () => { ativo = false }
  }, [])

  useEffect(() => {
    if (mediaEditada) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMedia(calcMedia(t1, t2, t3))
  }, [t1, t2, t3, mediaEditada])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro(''); setEnviando(true)
    const payload: GerarCertificadoPayload = {
      tipo_calibragem: tipoCal ? Number(tipoCal) : null,
      calib_cert: cert.trim() || null,
      calib_temp: temp.trim() || null,
      calib_pressao: pressao.trim() || null,
      calib_teste1: t1.trim() || null,
      calib_teste2: t2.trim() || null,
      calib_teste3: t3.trim() || null,
      calib_teste_media: media.trim() || null,
      calib_situacao: situacao.trim() || null,
    }
    try {
      const certs = await ordensApi.gerarCertificado(os.id, payload)
      onGerado(certs)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao gerar certificado')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Gerar certificado de calibração"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-gerar-cert" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Gerar</button>
        </>
      }
    >
      <form id="form-gerar-cert" className="space-y-4" onSubmit={submeter}>
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
        <Input id="media" label="Média dos testes" value={media} onChange={(e) => { setMediaEditada(true); setMedia(e.target.value) }} />
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
