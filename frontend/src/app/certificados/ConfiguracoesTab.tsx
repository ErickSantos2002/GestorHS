import { useEffect, useState } from 'react'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { useAuth } from '../../auth/AuthContext'
import { podeEditarConfigCertificado } from '../../auth/roles'
import { hojeISO } from './valoresCertificado'
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

/** Um cilindro esta vigente se esta ativo e hoje cai dentro da vigencia.
 *  Espelha padrao_vigente() em backend/app/core/certificado_config.py. */
function estaVigente(p: CertificadoPadrao): boolean {
  const hoje = hojeISO()
  if (!p.ativo || !p.vigencia_inicio) return false
  return p.vigencia_inicio <= hoje && (p.vigencia_fim === null || p.vigencia_fim >= hoje)
}

export function ConfiguracoesTab() {
  const { user } = useAuth()
  const podeEditar = podeEditarConfigCertificado(user)

  const [config, setConfig] = useState<CertificadoConfig | null>(null)
  const [padroes, setPadroes] = useState<CertificadoPadrao[]>([])
  const [novo, setNovo] = useState({ ...PADRAO_NOVO })
  const [salvando, setSalvando] = useState(false)
  const [aviso, setAviso] = useState('')

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
    try {
      const criado = await certificadosApi.criarPadrao(novo)
      setPadroes((atual) => [criado, ...atual])
      setNovo({ ...PADRAO_NOVO })
    } catch {
      setAviso('Falha ao cadastrar o cilindro.')
    }
  }

  async function excluirPadrao(id: number) {
    try {
      await certificadosApi.excluirPadrao(id)
      setPadroes((atual) => atual.filter((p) => p.id !== id))
    } catch {
      setAviso('Falha ao excluir o cilindro.')
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
                <td>{estaVigente(p)
                  ? <span className="text-emerald-400 text-xs font-medium">Em uso</span>
                  : <span className="text-slate-500 text-xs">—</span>}</td>
                <td className="text-right">
                  {podeEditar && (
                    <button onClick={() => excluirPadrao(p.id)}
                      className="text-xs text-red-400 hover:text-red-300">Excluir</button>
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
            <Button onClick={adicionarPadrao}>Adicionar</Button>
          </div>
        )}
      </div>
    </div>
  )
}
