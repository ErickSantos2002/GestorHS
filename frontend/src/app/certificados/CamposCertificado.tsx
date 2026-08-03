import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { mediaTestesPreenchidas } from '../../lib/calibragem'
import { formatarDocumento, soDigitos } from '../../lib/documento'
import { certificadosApi, type CalculoPrevia, type CertificadoPadrao } from './api'
import { padraoVigente } from './padraoVigente'
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
  /** Quantas medicoes renderizar. A OS usa 5 (certificado EPS-LAB-002); venda e
   *  avulso ficam em 3, porque os schemas deles so tem calib_teste1..3 — oferecer
   *  cinco campos la seria aceitar digitacao e descartar em silencio. */
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

  const [previaBruta, setPrevia] = useState<CalculoPrevia | null>(null)
  // A previa so faz sentido com 5 medicoes preenchidas (calculo do EPS-LAB-002); deriva do
  // estado em vez de zerar via setState sincrono no corpo do efeito (react-hooks/set-state-in-effect).
  const mostrarPrevia = medicoes === 5 && !valoresMedicoes.every((m) => m.trim() === '')
  const previa = mostrarPrevia ? previaBruta : null

  useEffect(() => {
    if (!mostrarPrevia) return
    const timer = setTimeout(() => {
      certificadosApi.calculoPrevia(valoresMedicoes)
        .then(setPrevia)
        // a previa e informativa: falhar nela nao pode travar a geracao do certificado
        .catch(() => setPrevia(null))
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveMedicoes, medicoes])

  // Cilindro que sera gravado nesta geracao. So no modo de 5 medicoes: e o unico
  // fluxo que grava padrao_id. A lista vem inteira e a resolucao roda aqui porque a
  // data de calibracao e editavel no proprio formulario.
  const [padroes, setPadroes] = useState<CertificadoPadrao[] | null>(null)
  useEffect(() => {
    if (medicoes !== 5) return
    let ativo = true
    certificadosApi.padroes()
      .then((lista) => { if (ativo) setPadroes(lista) })
      // informativo: falhar aqui nao pode travar a geracao do certificado
      .catch(() => { if (ativo) setPadroes(null) })
    return () => { ativo = false }
  }, [medicoes])
  const padrao = padroes ? padraoVigente(padroes, valores.dataCalib) : null

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
        {medicoes === 5 && padroes !== null && (
          // Rastreabilidade (seção 8 do EPS-LAB-002): o operador precisa ver o cilindro
          // que sairá no documento. NAO bloqueia a geração — mesmo princípio do aviso de
          // medição fora da faixa: um certificado que precisa sair, sai.
          <p className="text-xs text-slate-400">
            {padrao ? (
              <>
                Cilindro que será gravado: <strong className="text-slate-200">{padrao.numero_cilindro}</strong>
                {' '}· certificado {padrao.numero_certificado ?? '—'}
                {' '}· {padrao.concentracao ?? '—'} {padrao.unidade ?? ''}
              </>
            ) : (
              <span className="text-amber-400">
                Nenhum cilindro cadastrado cobre esta data — a seção de padrões sairá em branco.
              </span>
            )}
          </p>
        )}
        {previa && (
          <div className="rounded-lg border border-slate-700 bg-background-elevated p-3 space-y-2">
            <p className={secao}>Cálculo (somente leitura)</p>
            {previa.fora_da_faixa.some(Boolean) && (
              <p className="text-xs text-red-400">
                Medição fora da faixa {previa.limite_minimo} – {previa.limite_maximo}. Confira antes de gerar.
              </p>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs text-slate-400">
              {previa.erros.map((erro, i) => (
                <span key={i}>Erro {i + 1}: <strong className="text-slate-200">{erro || '—'}</strong></span>
              ))}
            </div>
            <p className="text-xs text-slate-400">
              Incerteza expandida (U): <strong className="text-slate-200">{previa.incerteza_expandida}</strong>
              {' '}· k = {previa.fator_k} (95% de confiança)
            </p>
          </div>
        )}
        {extra}
      </div>
    </>
  )
}
