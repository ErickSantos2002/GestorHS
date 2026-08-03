import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { mediaTestesPreenchidas } from '../../lib/calibragem'
import { formatarDocumento, soDigitos } from '../../lib/documento'
import { PainelCalculoCertificado } from './PainelCalculoCertificado'
import { useCalculoCertificado } from './useCalculoCertificado'
import type { ValoresCertificado } from './valoresCertificado'

const secao = 'text-xs font-semibold text-slate-500 uppercase tracking-wide'

const CHAVES_5 = ['t1', 't2', 't3', 't4', 't5'] as const
const CHAVES_3 = ['t1', 't2', 't3'] as const

/** Formulario de certificado compartilhado entre o fluxo da OS e o de venda.
 *  `extra` entra no fim da secao Calibracao (a venda usa para "Proxima calibracao"). */
export function CamposCertificado({ valores, onChange, extra, medicoes = 3 }: {
  valores: ValoresCertificado
  onChange: (patch: Partial<ValoresCertificado>) => void
  extra?: ReactNode
  /** Quantas medicoes renderizar. OS e venda passam 5 (certificado EPS-LAB-002); o
   *  padrao de 3 e para o aparelho cujo modelo de certificado ainda so tem tres
   *  celulas de medicao no template (nao migrado pro EPS-LAB-002). O avulso tem
   *  formulario proprio e nao usa este componente. */
  medicoes?: 3 | 5
}) {
  const chaves = medicoes === 5 ? CHAVES_5 : CHAVES_3
  const [mediaEditada, setMediaEditada] = useState(false)

  const valoresMedicoes = chaves.map((c) => valores[c])
  const chaveMedicoes = valoresMedicoes.join('|')

  // Media que ja veio gravada do backend e as medicoes com que ela chegou. Enquanto
  // as medicoes nao mudarem, a media preenchida NAO pode ser recalculada: o efeito
  // roda na montagem e sobrescreveria em silencio o valor gravado na OS.
  const mediaInicial = useRef(valores.media.trim())
  const medicoesIniciais = useRef(chaveMedicoes)

  useEffect(() => {
    if (mediaEditada) return
    if (mediaInicial.current !== '' && chaveMedicoes === medicoesIniciais.current) return
    // Media sobre as medicoes PREENCHIDAS — mesma regra do backend. Exigir as cinco
    // apagaria a media de toda OS anterior a este formato, que tem so tres.
    onChange({ media: mediaTestesPreenchidas(...valoresMedicoes) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveMedicoes, mediaEditada])

  // Previa do calculo (EPS-LAB-002) e cilindro vigente — so fazem sentido no modo de
  // 5 medicoes, o unico fluxo que grava o bloco calculado e o padrao_id.
  const { previa, padroes, padrao } = useCalculoCertificado(valoresMedicoes, valores.dataCalib, medicoes === 5)

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
        <div className={medicoes === 5 ? 'grid grid-cols-2 sm:grid-cols-5 gap-3' : 'grid grid-cols-1 sm:grid-cols-3 gap-3'}>
          {chaves.map((chave, i) => {
            const fora = previa?.fora_da_faixa[i] ?? false
            return (
              <Input key={chave} id={chave} label={`Teste ${i + 1}`} value={valores[chave]}
                className={fora ? 'border-red-500 focus:border-red-500' : undefined}
                // chave computada a partir de uma uniao de literais: o TS infere
                // { [x: string]: string } e nao casa com Partial<ValoresCertificado>
                onChange={(e) => onChange({ [chave]: e.target.value } as Partial<ValoresCertificado>)} />
            )
          })}
        </div>
        <Input id="media" label="Média dos testes" value={valores.media} onChange={(e) => { setMediaEditada(true); onChange({ media: e.target.value }) }} />
        <PainelCalculoCertificado previa={previa} padroes={padroes} padrao={padrao} />
        {extra}
      </div>
    </>
  )
}
