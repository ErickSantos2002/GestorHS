import { useEffect, useState } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { fasesApi, funcoesApi, type Fase, type Funcao } from './api'

export function FasesPanel() {
  const [fases, setFases] = useState<Fase[] | null>(null)
  const [funcoes, setFuncoes] = useState<Funcao[]>([])
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    Promise.all([fasesApi.listar(), funcoesApi.listar()])
      .then(([fs, fns]) => {
        if (!ativo) return
        setFases(fs)
        setFuncoes(fns)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
        setFases([])
      })
    return () => {
      ativo = false
    }
  }, [])

  async function mudar(fase: Fase, valor: string) {
    setErro('')
    const funcao_responsavel = valor ? Number(valor) : null
    try {
      const atualizada = await fasesApi.atualizar(fase.id, { funcao_responsavel })
      setFases((prev) => prev?.map((f) => (f.id === atualizada.id ? atualizada : f)) ?? prev)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao salvar')
    }
  }

  if (fases === null) return <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold text-slate-100">Fases — responsável por fase</h2>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      <Table head={<><TH>Fase</TH><TH>Responsável</TH></>}>
        {fases.map((f) => (
          <tr key={f.id} className="hover:bg-background-elevated transition-colors">
            <TD>
              <span className="inline-flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: `#${f.cor}` }} />
                {f.descricao}
              </span>
            </TD>
            <TD>
              <Select id={`fase-${f.id}`} value={f.funcao_responsavel ?? ''} onChange={(e) => mudar(f, e.target.value)}>
                <option value="">— sem responsável —</option>
                {funcoes.map((fn) => <option key={fn.id} value={fn.id}>{fn.descricao}</option>)}
              </Select>
            </TD>
          </tr>
        ))}
      </Table>
    </div>
  )
}
