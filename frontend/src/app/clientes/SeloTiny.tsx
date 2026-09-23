import { cn } from '../../lib/utils'
import { rotuloTiny, type TinyStatus } from '../empresas/api'

interface Props {
  tiny_id: number | null
  tiny_status: TinyStatus
  tiny_erro: string | null
}

/** Status do contato no Tiny, no mesmo visual da coluna da página Empresas.
 *  Cliente só é espelhado quando recebe proposta; sem status, não mostra nada. */
export function SeloTiny({ tiny_id, tiny_status, tiny_erro }: Props) {
  if (!tiny_status) return null
  return (
    <span className="text-xs">
      <span className={cn(tiny_status === 'erro' && 'font-semibold text-danger')} title={tiny_erro ?? undefined}>
        {rotuloTiny({ tiny_status })}
      </span>
      {tiny_id != null && <span className="block text-slate-500">{tiny_id}</span>}
    </span>
  )
}
