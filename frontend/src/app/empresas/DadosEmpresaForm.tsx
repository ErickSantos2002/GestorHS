import { useState, type ReactNode } from 'react'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { IconSearch } from '../../components/ui/icons'
import { formatarDocumento, mascararCEP, soDigitos } from '../../lib/documento'
import { cn } from '../../lib/utils'
import { camposFaltando, ROTULOS_DADOS, UFS, type CampoDados, type DadosEmpresa } from './dadosEmpresa'
import { aplicarResultadoCep, aplicarResultadoCnpj, buscaApi, mensagemErroBusca } from './buscaEndereco'

function ComLupa({ aoBuscar, carregando, desabilitado, rotulo, children }: {
  aoBuscar: () => void
  /** Spinner nesta lupa especifica — so a que de fato esta buscando. */
  carregando: boolean
  /** Vale para as duas lupas enquanto qualquer busca estiver em andamento: uma
   *  segunda busca dispararia com os dados ja desatualizados pela primeira. */
  desabilitado: boolean
  rotulo: string
  children: ReactNode
}) {
  return (
    <div className="flex items-end gap-2">
      <div className="flex-1 min-w-0">{children}</div>
      <button
        type="button" onClick={aoBuscar} disabled={desabilitado} aria-label={rotulo} title={rotulo}
        className="mb-0.5 shrink-0 rounded-lg border border-border bg-background-elevated p-2.5 text-slate-400 hover:text-primary hover:border-primary/40 disabled:opacity-50 transition-colors"
      >
        {carregando ? <Spinner className="w-4 h-4" /> : <IconSearch className="w-4 h-4" />}
      </button>
    </div>
  )
}

export interface DadosEmpresaFormProps {
  dados: DadosEmpresa
  onChange: (dados: DadosEmpresa) => void
  documentoTravado?: boolean
  somenteLeitura?: boolean
  sugestoes?: { email?: string; telefone?: string }
  obrigatorios?: readonly CampoDados[]
  destacarFaltando?: boolean
  idPrefixo?: string
  children?: ReactNode
}

export function DadosEmpresaForm({
  dados, onChange, documentoTravado, somenteLeitura, sugestoes, obrigatorios = [],
  destacarFaltando, idPrefixo = 'de', children,
}: DadosEmpresaFormProps) {
  const [buscando, setBuscando] = useState<'cep' | 'cnpj' | null>(null)
  const [erroBusca, setErroBusca] = useState('')
  const [resultado, setResultado] = useState<{ origem: 'CEP' | 'CNPJ'; campos: string[]; situacao?: string } | null>(null)
  const [anterior, setAnterior] = useState<DadosEmpresa | null>(null)

  const faltando = destacarFaltando ? camposFaltando(dados, obrigatorios) : []
  const id = (c: CampoDados) => `${idPrefixo}-${c}`
  const rotulo = (c: CampoDados) => (obrigatorios.includes(c) ? `${ROTULOS_DADOS[c]} *` : ROTULOS_DADOS[c])
  const classe = (c: CampoDados, extra?: string) => cn(extra, faltando.includes(c) && 'border-danger')
  const definir = (c: CampoDados, v: string) => onChange({ ...dados, [c]: v })

  async function buscar(tipo: 'cep' | 'cnpj') {
    if (buscando) return
    setErroBusca('')
    setBuscando(tipo)
    const antes = dados
    try {
      if (tipo === 'cnpj') {
        const r = await buscaApi.cnpj(soDigitos(dados.documento))
        const { dados: novos, preenchidos } = aplicarResultadoCnpj(dados, r)
        onChange(novos)
        setResultado({ origem: 'CNPJ', campos: preenchidos.map((c) => ROTULOS_DADOS[c]), situacao: r.situacao || undefined })
      } else {
        const { dados: novos, preenchidos } = aplicarResultadoCep(dados, await buscaApi.cep(soDigitos(dados.cep)))
        onChange(novos)
        setResultado({ origem: 'CEP', campos: preenchidos.map((c) => ROTULOS_DADOS[c]) })
      }
      setAnterior(antes)
    } catch (e) {
      setResultado(null)
      setErroBusca(mensagemErroBusca(e, tipo === 'cnpj' ? 'CNPJ' : 'CEP'))
    } finally {
      setBuscando(null)
    }
  }

  function desfazer() {
    if (anterior) onChange(anterior)
    setAnterior(null)
    setResultado(null)
  }

  function campoTexto(c: CampoDados, extra?: string) {
    return (
      <Input id={id(c)} label={rotulo(c)} value={dados[c]} disabled={somenteLeitura}
        onChange={(e) => definir(c, e.target.value)} className={classe(c, extra)} />
    )
  }

  function campoContato(c: 'email' | 'telefone') {
    const sugestao = sugestoes?.[c]
    return (
      <div>
        {campoTexto(c)}
        {!somenteLeitura && sugestao && sugestao !== dados[c] && (
          <button type="button" onClick={() => definir(c, sugestao)} className="mt-1 text-xs font-semibold text-primary hover:underline">
            Usar do cadastro: {sugestao}
          </button>
        )}
      </div>
    )
  }

  const documento = (
    <Input id={id('documento')} label={rotulo('documento')} value={formatarDocumento(dados.documento)}
      readOnly={documentoTravado} disabled={somenteLeitura}
      onChange={(e) => definir('documento', soDigitos(e.target.value))}
      className={classe('documento', documentoTravado ? 'opacity-70' : undefined)} />
  )
  const cep = (
    <Input id={id('cep')} label={rotulo('cep')} value={mascararCEP(dados.cep)} disabled={somenteLeitura}
      onChange={(e) => definir('cep', soDigitos(e.target.value))} className={classe('cep')} />
  )

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">{campoTexto('nome')}</div>
        {somenteLeitura ? documento : (
          <ComLupa aoBuscar={() => buscar('cnpj')} carregando={buscando === 'cnpj'} desabilitado={buscando !== null} rotulo="Buscar dados pelo CNPJ">
            {documento}
          </ComLupa>
        )}
        {somenteLeitura ? cep : (
          <ComLupa aoBuscar={() => buscar('cep')} carregando={buscando === 'cep'} desabilitado={buscando !== null} rotulo="Buscar endereço pelo CEP">
            {cep}
          </ComLupa>
        )}
        <div className="sm:col-span-2">{campoTexto('endereco')}</div>
        {campoTexto('numero')}
        {campoTexto('complemento')}
        {campoTexto('bairro')}
        {campoTexto('municipio')}
        <Select id={id('estado')} label={rotulo('estado')} value={dados.estado} disabled={somenteLeitura}
          onChange={(e) => definir('estado', e.target.value)} className={classe('estado')}>
          <option value="">—</option>
          {UFS.map((uf) => <option key={uf} value={uf}>{uf}</option>)}
        </Select>
        {campoContato('telefone')}
        <div className="sm:col-span-2">{campoContato('email')}</div>
        {children}
      </div>
      {erroBusca && <p className="text-xs font-medium text-danger">{erroBusca}</p>}
      {resultado && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span className="text-slate-400">Preenchido pelo {resultado.origem}: {resultado.campos.join(', ')}.</span>
          {resultado.situacao && (
            <span className={resultado.situacao === 'ATIVA' ? 'text-slate-500' : 'font-semibold text-warning'}>
              Situação na Receita: {resultado.situacao}
            </span>
          )}
          <button type="button" onClick={desfazer} className="font-semibold text-primary hover:underline">Desfazer</button>
        </div>
      )}
    </div>
  )
}
