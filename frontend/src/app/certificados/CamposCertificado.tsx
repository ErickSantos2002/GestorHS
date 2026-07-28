import { useEffect, useState, type ReactNode } from 'react'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { mediaTestes } from '../../lib/calibragem'
import { formatarDocumento, soDigitos } from '../../lib/documento'
import type { ValoresCertificado } from './valoresCertificado'

const secao = 'text-xs font-semibold text-slate-500 uppercase tracking-wide'

/** Formulario de certificado compartilhado entre o fluxo da OS e o de venda.
 *  `extra` entra no fim da secao Calibracao (a venda usa para "Proxima calibracao"). */
export function CamposCertificado({ valores, onChange, extra }: {
  valores: ValoresCertificado
  onChange: (patch: Partial<ValoresCertificado>) => void
  extra?: ReactNode
}) {
  const [mediaEditada, setMediaEditada] = useState(false)

  useEffect(() => {
    if (mediaEditada) return
    onChange({ media: mediaTestes(valores.t1, valores.t2, valores.t3) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valores.t1, valores.t2, valores.t3, mediaEditada])

  return (
    <>
      <div className="space-y-3">
        <p className={secao}>Cliente</p>
        <Input id="nomecli" label="Nome" value={valores.nomecli} onChange={(e) => onChange({ nomecli: e.target.value })} />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="cnpj" label="CNPJ/CPF" value={formatarDocumento(valores.cnpj)} onChange={(e) => onChange({ cnpj: soDigitos(e.target.value) })} />
          <Input id="endcli" label="Endereço" value={valores.endcli} onChange={(e) => onChange({ endcli: e.target.value })} />
        </div>
      </div>

      <div className="space-y-3">
        <p className={secao}>Aparelho</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="modelo" label="Modelo" value={valores.modelo} onChange={(e) => onChange({ modelo: e.target.value })} />
          <Input id="marca" label="Marca" value={valores.marca} onChange={(e) => onChange({ marca: e.target.value })} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input id="serie" label="Série" value={valores.serie} onChange={(e) => onChange({ serie: e.target.value })} />
          <Input id="patrimonio" label="Patrimônio" value={valores.patrimonio} onChange={(e) => onChange({ patrimonio: e.target.value })} />
          <Input id="datacompra" label="Data de compra" value={valores.datacompra} onChange={(e) => onChange({ datacompra: e.target.value })} />
        </div>
      </div>

      <div className="space-y-3">
        <p className={secao}>Calibração</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="data-calib" label="Data de calibração" type="date" value={valores.dataCalib} onChange={(e) => onChange({ dataCalib: e.target.value })} />
          <Input id="cert" label="Nº do certificado" value={valores.cert} onChange={(e) => onChange({ cert: e.target.value })} />
        </div>
        <Select id="situacao" label="Situação" value={valores.situacao} onChange={(e) => onChange({ situacao: e.target.value })}>
          <option value="">— selecione —</option>
          <option value="Aparelho subsequente">Aparelho subsequente</option>
          <option value="Aparelho inicial">Aparelho inicial</option>
        </Select>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="temp" label="Temperatura" value={valores.temp} onChange={(e) => onChange({ temp: e.target.value })} />
          <Input id="pressao" label="Pressão" value={valores.pressao} onChange={(e) => onChange({ pressao: e.target.value })} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input id="t1" label="Teste 1" value={valores.t1} onChange={(e) => onChange({ t1: e.target.value })} />
          <Input id="t2" label="Teste 2" value={valores.t2} onChange={(e) => onChange({ t2: e.target.value })} />
          <Input id="t3" label="Teste 3" value={valores.t3} onChange={(e) => onChange({ t3: e.target.value })} />
        </div>
        <Input id="media" label="Média dos testes" value={valores.media} onChange={(e) => { setMediaEditada(true); onChange({ media: e.target.value }) }} />
        {extra}
      </div>
    </>
  )
}
