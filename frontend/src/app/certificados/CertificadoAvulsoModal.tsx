import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { mediaTestes } from '../../lib/calibragem'
import { certificadosApi, type ModeloItem, type AvulsoPayload } from './api'

function hojeISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function CertificadoAvulsoModal({ onClose, onGerado }: {
  onClose: () => void
  onGerado: () => void
}) {
  const [carregando, setCarregando] = useState(true)
  const [modelos, setModelos] = useState<ModeloItem[]>([])
  const [template, setTemplate] = useState('')

  const [nomecli, setNomecli] = useState('')
  const [cnpj, setCnpj] = useState('')
  const [endcli, setEndcli] = useState('')
  const [serie, setSerie] = useState('')
  const [datacompra, setDatacompra] = useState('')
  const [os, setOs] = useState('XXXX')
  const [dataRecebimento, setDataRecebimento] = useState(hojeISO())
  const [dataCalib, setDataCalib] = useState('')
  const [cert, setCert] = useState('')
  const [situacao, setSituacao] = useState('')
  const [temp, setTemp] = useState('')
  const [pressao, setPressao] = useState('')
  const [t1, setT1] = useState('')
  const [t2, setT2] = useState('')
  const [t3, setT3] = useState('')
  const [media, setMedia] = useState('')
  const [mediaEditada, setMediaEditada] = useState(false)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    let ativo = true
    certificadosApi.listarModelos()
      .then((r) => { if (ativo) setModelos(r.items) })
      .catch(() => { if (ativo) setErro('Falha ao carregar os modelos de certificado') })
      .finally(() => { if (ativo) setCarregando(false) })
    return () => { ativo = false }
  }, [])

  useEffect(() => {
    if (mediaEditada) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMedia(mediaTestes(t1, t2, t3))
  }, [t1, t2, t3, mediaEditada])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (!template) return
    setErro(''); setEnviando(true)
    const [equipamentoStr, tipo] = template.split(':')
    const payload: AvulsoPayload = {
      equipamento: Number(equipamentoStr),
      tipo: tipo as 'C' | 'M',
      nomecli: nomecli.trim() || null,
      cnpj: cnpj.trim() || null,
      endcli: endcli.trim() || null,
      serie: serie.trim() || null,
      datacompra: datacompra.trim() || null,
      os: os.trim() || null,
      data_recebimento: dataRecebimento || null,
      calib_cert: cert.trim() || null,
      data_calibracao: dataCalib || null,
      calib_temp: temp.trim() || null,
      calib_pressao: pressao.trim() || null,
      calib_teste1: t1.trim() || null,
      calib_teste2: t2.trim() || null,
      calib_teste3: t3.trim() || null,
      calib_teste_media: media.trim() || null,
      calib_situacao: situacao.trim() || null,
    }
    try {
      await certificadosApi.gerarAvulso(payload)
      onGerado()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao gerar certificado')
    } finally {
      setEnviando(false)
    }
  }

  const secao = 'text-xs font-semibold text-slate-500 uppercase tracking-wide'

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Gerar certificado em branco"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-gerar-cert-avulso" disabled={enviando || carregando || !template} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Gerar</button>
        </>
      }
    >
      {carregando ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : (
        <form id="form-gerar-cert-avulso" className="space-y-5" onSubmit={submeter}>
          <div className="space-y-3">
            <p className={secao}>Modelo de certificado</p>
            <Select id="template" label="Modelo do aparelho" value={template} onChange={(e) => setTemplate(e.target.value)}>
              <option value="">— selecione —</option>
              {modelos.flatMap((m) => [
                m.tem_calibracao && (
                  <option key={`${m.equipamento}:C`} value={`${m.equipamento}:C`}>{`${m.equipamento_descricao ?? `#${m.equipamento}`} — Calibração`}</option>
                ),
                m.tem_manutencao && (
                  <option key={`${m.equipamento}:M`} value={`${m.equipamento}:M`}>{`${m.equipamento_descricao ?? `#${m.equipamento}`} — Manutenção`}</option>
                ),
              ].filter(Boolean))}
            </Select>
          </div>

          <div className="space-y-3">
            <p className={secao}>Cliente</p>
            <Input id="nomecli" label="Nome" value={nomecli} onChange={(e) => setNomecli(e.target.value)} />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input id="cnpj" label="CNPJ/CPF" value={cnpj} onChange={(e) => setCnpj(e.target.value)} />
              <Input id="endcli" label="Endereço" value={endcli} onChange={(e) => setEndcli(e.target.value)} />
            </div>
          </div>

          <div className="space-y-3">
            <p className={secao}>Ordem de serviço</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input id="os" label="Número da OS" value={os} onChange={(e) => setOs(e.target.value)} />
              <Input id="data-recebimento" label="Data de recebimento" type="date" value={dataRecebimento} onChange={(e) => setDataRecebimento(e.target.value)} />
            </div>
          </div>

          <div className="space-y-3">
            <p className={secao}>Aparelho</p>
            {/* Modelo e marca NAO sao digitados: vem do cadastro do aparelho do modelo
                escolhido acima — nos modelos atuais eles ja estao escritos no proprio HTML. */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input id="serie" label="Série" value={serie} onChange={(e) => setSerie(e.target.value)} />
              {/* type="date": o backend recebe `Optional[date]` — texto livre viraria 422. */}
              <Input id="datacompra" label="Data de compra" type="date" value={datacompra} onChange={(e) => setDatacompra(e.target.value)} />
            </div>
          </div>

          <div className="space-y-3">
            <p className={secao}>Calibração</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input id="data-calib" label="Data de calibração" type="date" value={dataCalib} onChange={(e) => setDataCalib(e.target.value)} />
              <Input id="cert" label="Nº do certificado" value={cert} onChange={(e) => setCert(e.target.value)} />
            </div>
            <Select id="situacao" label="Situação" value={situacao} onChange={(e) => setSituacao(e.target.value)}>
              <option value="">— selecione —</option>
              <option value="Aparelho subsequente">Aparelho subsequente</option>
              <option value="Aparelho inicial">Aparelho inicial</option>
            </Select>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input id="temp" label="Temperatura" value={temp} onChange={(e) => setTemp(e.target.value)} />
              <Input id="pressao" label="Pressão" value={pressao} onChange={(e) => setPressao(e.target.value)} />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Input id="t1" label="Teste 1" value={t1} onChange={(e) => setT1(e.target.value)} />
              <Input id="t2" label="Teste 2" value={t2} onChange={(e) => setT2(e.target.value)} />
              <Input id="t3" label="Teste 3" value={t3} onChange={(e) => setT3(e.target.value)} />
            </div>
            <Input id="media" label="Média dos testes" value={media} onChange={(e) => { setMediaEditada(true); setMedia(e.target.value) }} />
          </div>

          {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
        </form>
      )}
    </Modal>
  )
}
