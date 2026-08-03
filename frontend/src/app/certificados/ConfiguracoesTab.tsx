import { useEffect, useState } from 'react'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { useAuth } from '../../auth/AuthContext'
import { podeEditarConfigCertificado } from '../../auth/roles'
import { ApiError } from '../../lib/api'
import { hojeISO } from './valoresCertificado'
import { padraoVigente } from './padraoVigente'
import { certificadosApi, type CertificadoConfig, type CertificadoPadrao } from './api'

const secao = 'text-xs font-semibold text-slate-500 uppercase tracking-wide'

/** Campos numericos do calculo. Um array em vez de JSX repetido: sao oito campos
 *  com o mesmo comportamento, e a lista e o que garante que nenhum fique de fora. */
const CAMPOS_NUMERICOS = [
  ['valor_referencia', 'Valor de referência'],
  ['limite_minimo', 'Limite mínimo'],
  ['limite_maximo', 'Limite máximo'],
  ['resolucao_instrumento', 'Resolução do instrumento'],
  ['incerteza_padrao_temp', 'Incerteza do padrão (temperatura)'],
  ['resolucao_pressao', 'Resolução (pressão)'],
  ['incerteza_padrao_pressao', 'Incerteza do padrão (pressão)'],
  ['fator_k', 'Fator k'],
] as const

const PADRAO_NOVO = {
  numero_cilindro: '', numero_certificado: '', concentracao: '', incerteza_concentracao: '',
  unidade: 'µmol/mol', vigencia_inicio: hojeISO(), vigencia_fim: null as string | null, ativo: true,
}

export function ConfiguracoesTab() {
  const { user } = useAuth()
  const podeEditar = podeEditarConfigCertificado(user)

  const [config, setConfig] = useState<CertificadoConfig | null>(null)
  const [padroes, setPadroes] = useState<CertificadoPadrao[]>([])
  const [novo, setNovo] = useState({ ...PADRAO_NOVO })
  const [salvando, setSalvando] = useState(false)
  const [adicionando, setAdicionando] = useState(false)
  const [excluindoId, setExcluindoId] = useState<number | null>(null)
  const [encerrandoId, setEncerrandoId] = useState<number | null>(null)
  const [aviso, setAviso] = useState('')

  // O vigente sai da LISTA, nao de cada linha isolada: entre os cilindros que cobrem
  // hoje, o backend escolhe um so — o de vigencia_inicio mais recente. Avaliar linha a
  // linha marcava "Em uso" nos dois no fluxo esperado (cadastrar o novo, deixar o
  // antigo em aberto), justamente quando a tela precisa ser inequivoca.
  const idVigente = padraoVigente(padroes, hojeISO())?.id ?? null

  useEffect(() => {
    certificadosApi.config().then(setConfig).catch(() => setAviso('Falha ao carregar a configuração.'))
    certificadosApi.padroes().then(setPadroes).catch(() => setPadroes([]))
  }, [])

  function alterar(patch: Partial<CertificadoConfig>) {
    setConfig((atual) => (atual ? { ...atual, ...patch } : atual))
  }

  async function salvar() {
    if (!config) return
    setSalvando(true)
    setAviso('')
    try {
      setConfig(await certificadosApi.salvarConfig(config))
      setAviso('Configuração salva.')
    } catch {
      setAviso('Falha ao salvar a configuração.')
    } finally {
      setSalvando(false)
    }
  }

  async function adicionarPadrao() {
    if (!novo.numero_cilindro.trim()) return
    setAdicionando(true)
    setAviso('')
    try {
      const criado = await certificadosApi.criarPadrao(novo)
      setPadroes((atual) => [criado, ...atual])
      setNovo({ ...PADRAO_NOVO })
      setAviso('Cilindro cadastrado.')
    } catch {
      setAviso('Falha ao cadastrar o cilindro.')
    } finally {
      setAdicionando(false)
    }
  }

  /** Aposenta o cilindro sem apagá-lo: a rastreabilidade dos certificados já emitidos
   *  depende do registro continuar existindo. Encerra HOJE — as calibrações feitas
   *  hoje ainda saem com este cilindro. */
  async function encerrarVigencia(id: number) {
    setEncerrandoId(id)
    setAviso('')
    try {
      const atualizado = await certificadosApi.atualizarPadrao(id, { vigencia_fim: hojeISO() })
      setPadroes((atual) => atual.map((p) => (p.id === id ? atualizado : p)))
      setAviso('Vigência encerrada.')
    } catch {
      setAviso('Falha ao encerrar a vigência do cilindro.')
    } finally {
      setEncerrandoId(null)
    }
  }

  async function excluirPadrao(id: number) {
    setExcluindoId(id)
    setAviso('')
    try {
      await certificadosApi.excluirPadrao(id)
      setPadroes((atual) => atual.filter((p) => p.id !== id))
      setAviso('Cilindro excluído.')
    } catch (err) {
      // O 409 de cilindro em uso explica o que fazer ("encerre a vigência"); engolir a
      // mensagem do backend deixaria o admin sem saída.
      setAviso(err instanceof ApiError ? err.message : 'Falha ao excluir o cilindro.')
    } finally {
      setExcluindoId(null)
    }
  }

  if (!config) return <p className="text-sm text-slate-500">Carregando…</p>

  return (
    <div className="space-y-8">
      {!podeEditar && (
        <p className="text-xs text-amber-400">
          Somente o Administrador pode alterar estes valores — eles definem a incerteza de todo certificado emitido.
        </p>
      )}
      {aviso && <p className="text-xs text-slate-400">{aviso}</p>}

      <div className="space-y-3">
        <p className={secao}>Parâmetros do cálculo</p>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          {CAMPOS_NUMERICOS.map(([chave, rotulo]) => (
            <Input key={chave} id={chave} label={rotulo} disabled={!podeEditar}
              value={config[chave] ?? ''}
              onChange={(e) => alterar({ [chave]: e.target.value || null } as Partial<CertificadoConfig>)} />
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <p className={secao}>Laboratório</p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input id="tecnico_nome" label="Técnico responsável" disabled={!podeEditar}
            value={config.tecnico_nome ?? ''}
            onChange={(e) => alterar({ tecnico_nome: e.target.value })} />
          <Input id="tecnico_cargo" label="Cargo do técnico" disabled={!podeEditar}
            value={config.tecnico_cargo ?? ''}
            onChange={(e) => alterar({ tecnico_cargo: e.target.value })} />
          <Input id="margem_temperatura" label="Margem de temperatura" disabled={!podeEditar}
            value={config.margem_temperatura ?? ''}
            onChange={(e) => alterar({ margem_temperatura: e.target.value })} />
        </div>
        <label htmlFor="equipamentos_auxiliares" className="block text-xs text-slate-400">
          Equipamentos auxiliares
        </label>
        <textarea id="equipamentos_auxiliares" rows={3} disabled={!podeEditar}
          className="w-full rounded-lg bg-background-elevated border border-slate-700 p-2 text-sm text-slate-200"
          value={config.equipamentos_auxiliares ?? ''}
          onChange={(e) => alterar({ equipamentos_auxiliares: e.target.value })} />
        {podeEditar && (
          <Button onClick={salvar} disabled={salvando}>{salvando ? 'Salvando…' : 'Salvar'}</Button>
        )}
      </div>

      <div className="space-y-3">
        <p className={secao}>Padrões (cilindros de gás)</p>
        <table className="w-full text-sm text-slate-300">
          <thead className="text-xs text-slate-500 uppercase">
            <tr>
              <th className="text-left py-1">Cilindro</th>
              <th className="text-left py-1">Certificado</th>
              <th className="text-left py-1">Concentração</th>
              <th className="text-left py-1">Vigência</th>
              <th className="text-left py-1">Situação</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {padroes.map((p) => (
              <tr key={p.id} className="border-t border-slate-800">
                <td className="py-1.5">{p.numero_cilindro}</td>
                <td>{p.numero_certificado ?? '—'}</td>
                <td>{p.concentracao ?? '—'} {p.unidade ?? ''}</td>
                <td>{p.vigencia_inicio ?? '—'} → {p.vigencia_fim ?? 'vigente'}</td>
                <td>{p.id === idVigente
                  ? <span className="text-emerald-400 text-xs font-medium">Em uso</span>
                  : <span className="text-slate-500 text-xs">—</span>}</td>
                <td className="text-right space-x-3">
                  {podeEditar && p.vigencia_fim === null && (
                    <button onClick={() => encerrarVigencia(p.id)} disabled={encerrandoId === p.id}
                      className="text-xs text-amber-400 hover:text-amber-300 disabled:opacity-60 disabled:cursor-not-allowed">
                      {encerrandoId === p.id ? 'Encerrando…' : 'Encerrar vigência'}
                    </button>
                  )}
                  {podeEditar && (
                    <button onClick={() => excluirPadrao(p.id)} disabled={excluindoId === p.id}
                      className="text-xs text-red-400 hover:text-red-300 disabled:opacity-60 disabled:cursor-not-allowed">
                      {excluindoId === p.id ? 'Excluindo…' : 'Excluir'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {padroes.length === 0 && (
              <tr><td colSpan={6} className="py-3 text-slate-500">Nenhum cilindro cadastrado.</td></tr>
            )}
          </tbody>
        </table>

        {podeEditar && (
          <div className="grid grid-cols-1 sm:grid-cols-6 gap-3 items-end">
            <Input id="novo_cilindro" label="Cilindro" value={novo.numero_cilindro}
              onChange={(e) => setNovo({ ...novo, numero_cilindro: e.target.value })} />
            <Input id="novo_certificado" label="Certificado" value={novo.numero_certificado}
              onChange={(e) => setNovo({ ...novo, numero_certificado: e.target.value })} />
            <Input id="nova_concentracao" label="Concentração" value={novo.concentracao}
              onChange={(e) => setNovo({ ...novo, concentracao: e.target.value })} />
            <Input id="nova_incerteza" label="± Incerteza" value={novo.incerteza_concentracao}
              onChange={(e) => setNovo({ ...novo, incerteza_concentracao: e.target.value })} />
            <Input id="nova_vigencia" label="Vigência a partir de" type="date" value={novo.vigencia_inicio}
              onChange={(e) => setNovo({ ...novo, vigencia_inicio: e.target.value })} />
            <Button onClick={adicionarPadrao} disabled={adicionando}>{adicionando ? 'Adicionando…' : 'Adicionar'}</Button>
          </div>
        )}
      </div>
    </div>
  )
}
