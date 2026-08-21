import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { CamposCertificado } from '../certificados/CamposCertificado'
import { valoresIniciais, hojeISO, type ValoresCertificado } from '../certificados/valoresCertificado'
import { soDigitos } from '../../lib/documento'
import { ordensApi, type OrdemDetalhe, type OSCertificado, type GerarCertificadoPayload } from './api'

export function GerarCertificadoModal({ os, onClose, onGerado }: {
  os: OrdemDetalhe
  onClose: () => void
  onGerado: (certs: OSCertificado[]) => void
}) {
  const [carregando, setCarregando] = useState(true)
  const [v, setV] = useState<ValoresCertificado>(valoresIniciais())
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  // Manutencao pura nao tem medicao: mostrar o bloco de calibracao pediria
  // dados de um ensaio que nao foi feito. Espelha tipos_para no backend.
  const temCalibracao = os.tipo_servico !== 'M'

  function set(patch: Partial<ValoresCertificado>) {
    setV((atual) => ({ ...atual, ...patch }))
  }

  useEffect(() => {
    let ativo = true
    ordensApi.certificadoCampos(os.id)
      .then((c) => {
        if (!ativo) return
        setV({
          nomecli: c.nomecli ?? '', cnpj: soDigitos(c.cnpj ?? ''), endcli: c.endcli ?? '',
          modelo: c.modelo ?? '', marca: c.marca ?? '', serie: c.serie ?? '',
          patrimonio: c.patrimonio ?? '', datacompra: c.datacompra ?? '',
          cert: c.calib_cert ?? '', situacao: c.calib_situacao ?? '',
          temp: c.calib_temp ?? '', pressao: c.calib_pressao ?? '',
          t1: c.calib_teste1 ?? '', t2: c.calib_teste2 ?? '', t3: c.calib_teste3 ?? '',
          t4: c.calib_teste4 ?? '', t5: c.calib_teste5 ?? '',
          media: c.calib_teste_media ?? '',
          dataCalib: c.data_calibracao ? c.data_calibracao.slice(0, 10) : hojeISO(),
        })
        setCarregando(false)
      })
      .catch(() => { if (ativo) { setErro('Falha ao carregar os campos do certificado'); setCarregando(false) } })
    return () => { ativo = false }
  }, [os.id])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro(''); setEnviando(true)
    const payload: GerarCertificadoPayload = {
      data_calibracao: v.dataCalib || null,
      nomecli: v.nomecli.trim() || null,
      cnpj: v.cnpj.trim() || null,
      endcli: v.endcli.trim() || null,
      modelo: v.modelo.trim() || null,
      marca: v.marca.trim() || null,
      serie: v.serie.trim() || null,
      patrimonio: v.patrimonio.trim() || null,
      datacompra: v.datacompra.trim() || null,
      calib_cert: v.cert.trim() || null,
      calib_temp: v.temp.trim() || null,
      calib_pressao: v.pressao.trim() || null,
      calib_teste1: v.t1.trim() || null,
      calib_teste2: v.t2.trim() || null,
      calib_teste3: v.t3.trim() || null,
      calib_teste4: v.t4.trim() || null,
      calib_teste5: v.t5.trim() || null,
      calib_teste_media: v.media.trim() || null,
      calib_situacao: v.situacao.trim() || null,
    }
    try {
      onGerado(await ordensApi.gerarCertificado(os.id, payload))
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
      size="lg"
      title="Gerar certificado de calibração"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-gerar-cert" disabled={enviando || carregando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Gerar</button>
        </>
      }
    >
      {carregando ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : (
        <form id="form-gerar-cert" className="space-y-5" onSubmit={submeter}>
          <CamposCertificado valores={v} onChange={set} medicoes={5} mostrarCalibracao={temCalibracao} />
          {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
        </form>
      )}
    </Modal>
  )
}
