import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { CamposCertificado } from '../certificados/CamposCertificado'
import { valoresIniciais, hojeISO, type ValoresCertificado } from '../certificados/valoresCertificado'
import { equipamentosClienteApi, type CertificadoVendaPayload } from './api'

export function CertificadoVendaModal({ aparelhoId, onClose, onGerado }: {
  aparelhoId: number
  onClose: () => void
  onGerado: () => void
}) {
  const [carregando, setCarregando] = useState(true)
  const [v, setV] = useState<ValoresCertificado>(valoresIniciais())
  const [prox, setProx] = useState('')
  const [jaGerado, setJaGerado] = useState(false)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  function set(patch: Partial<ValoresCertificado>) {
    setV((atual) => ({ ...atual, ...patch }))
  }

  useEffect(() => {
    let ativo = true
    equipamentosClienteApi.certificadoVendaCampos(aparelhoId)
      .then((c) => {
        if (!ativo) return
        setV({
          nomecli: c.nomecli, cnpj: c.cnpj, endcli: c.endcli,
          modelo: c.modelo, marca: c.marca, serie: c.serie, patrimonio: c.patrimonio,
          datacompra: c.datacompra ?? '',
          cert: c.calib_cert ?? '', situacao: c.calib_situacao ?? '',
          temp: c.calib_temp ?? '', pressao: c.calib_pressao ?? '',
          t1: c.calib_teste1 ?? '', t2: c.calib_teste2 ?? '', t3: c.calib_teste3 ?? '',
          media: c.calib_teste_media ?? '',
          dataCalib: c.data_calibracao ?? hojeISO(),
        })
        setProx(c.prox_calibragem ?? '')
        setJaGerado(c.ja_gerado)
        setCarregando(false)
      })
      .catch(() => { if (ativo) { setErro('Falha ao carregar os campos do certificado'); setCarregando(false) } })
    return () => { ativo = false }
  }, [aparelhoId])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro(''); setEnviando(true)
    const payload: CertificadoVendaPayload = {
      nomecli: v.nomecli.trim() || null,
      cnpj: v.cnpj.trim() || null,
      endcli: v.endcli.trim() || null,
      serie: v.serie.trim() || null,
      patrimonio: v.patrimonio.trim() || null,
      datacompra: v.datacompra.trim() || null,
      calib_cert: v.cert.trim() || null,
      data_calibracao: v.dataCalib || null,
      prox_calibragem: prox || null,
      calib_temp: v.temp.trim() || null,
      calib_pressao: v.pressao.trim() || null,
      calib_teste1: v.t1.trim() || null,
      calib_teste2: v.t2.trim() || null,
      calib_teste3: v.t3.trim() || null,
      calib_teste_media: v.media.trim() || null,
      calib_situacao: v.situacao.trim() || null,
    }
    try {
      await equipamentosClienteApi.gerarCertificadoVenda(aparelhoId, payload)
      onGerado()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao gerar certificado de venda')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={jaGerado ? 'Regerar certificado de venda' : 'Gerar certificado de venda'}
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-cert-venda" disabled={enviando || carregando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">{jaGerado ? 'Regerar' : 'Gerar'}</button>
        </>
      }
    >
      {carregando ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : (
        <form id="form-cert-venda" className="space-y-5" onSubmit={submeter}>
          <CamposCertificado
            valores={v}
            onChange={set}
            extra={
              <Input
                id="prox-calibragem"
                label="Próxima calibração"
                type="date"
                value={prox}
                onChange={(e) => setProx(e.target.value)}
              />
            }
          />
          {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
        </form>
      )}
    </Modal>
  )
}
