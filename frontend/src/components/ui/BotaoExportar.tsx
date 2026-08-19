import { useState } from 'react'
import { Button } from './Button'
import { Spinner } from './Spinner'
import { IconDownload } from './icons'
import { apiFetch } from '../../lib/api'
import { baixarPlanilha } from '../../lib/download'
import { hojeISO } from '../../lib/datas'

type Valor = string | number | boolean | null | undefined

interface Props {
  /** Rota da exportação, ex.: `/equipamentos-cliente/exportar` */
  caminho: string
  /** Filtros que estão na tela AGORA. Vazio, nulo e indefinido não entram na query. */
  params: Record<string, Valor>
  /** Base do nome do arquivo; a data entra aqui. */
  nome: string
  desabilitado?: boolean
}

function montarQuery(params: Record<string, Valor>): string {
  const sp = new URLSearchParams()
  for (const [chave, valor] of Object.entries(params)) {
    if (valor === undefined || valor === null || valor === '') continue
    sp.set(chave, String(valor))
  }
  const query = sp.toString()
  return query ? `?${query}` : ''
}

export function BotaoExportar({ caminho, params, nome, desabilitado }: Props) {
  const [gerando, setGerando] = useState(false)
  const [erro, setErro] = useState('')

  async function exportar() {
    setErro('')
    setGerando(true)
    try {
      const hoje = hojeISO()
      await baixarPlanilha(`${nome}-${hoje}.xlsx`, async () => {
        const res = await apiFetch(`${caminho}${montarQuery(params)}`)
        if (!res.ok) {
          let detalhe = 'Falha ao gerar a planilha'
          try {
            const corpo = (await res.json()) as { detail?: string }
            if (corpo.detail) detalhe = corpo.detail
          } catch {
            // sem corpo JSON
          }
          throw new Error(detalhe)
        }
        return res.blob()
      })
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Falha ao gerar a planilha')
    } finally {
      setGerando(false)
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant="secondary" onClick={exportar} disabled={gerando || desabilitado}>
        {gerando ? <Spinner className="w-4 h-4" /> : <IconDownload className="w-4 h-4" />}
        {gerando ? 'Gerando planilha…' : 'Exportar Excel'}
      </Button>
      {erro && <span className="text-xs text-danger max-w-xs text-right">{erro}</span>}
    </div>
  )
}
