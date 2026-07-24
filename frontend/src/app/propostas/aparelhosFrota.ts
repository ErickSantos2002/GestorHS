// Texto auxiliar da seção "Aparelhos" da proposta — quanto falta (ou já
// passou) para a próxima calibração de um item da frota do cliente.
import { formatData } from '../../lib/utils'

// Limite (em dias) abaixo do qual mostramos "faltam/há N dias" em vez de meses
// — evita "faltam ~0 meses", que não dá noção nenhuma.
const LIMITE_DIAS_MOSTRA_MESES = 60

/** Descreve, em texto curto, quanto falta (ou já passou) para `prox` — a
 *  próxima calibração de um aparelho da frota. `hoje` é injetável para o
 *  cálculo ser determinístico em teste (não usar `new Date()` direto aqui). */
export function descreverVencimento(prox: string | null, hoje: Date = new Date()): string {
  if (!prox) return 'Sem data de calibração'
  const normalizado = /^\d{4}-\d{2}-\d{2}$/.test(prox) ? `${prox}T00:00:00` : prox
  const data = new Date(normalizado)
  if (isNaN(data.getTime())) return 'Sem data de calibração'

  const dataTexto = formatData(prox)
  const diffDias = Math.round((data.getTime() - hoje.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDias < 0) {
    const diasAtraso = Math.abs(diffDias)
    if (diasAtraso < LIMITE_DIAS_MOSTRA_MESES) return `Venceu em ${dataTexto}`
    const meses = Math.max(1, Math.round(diasAtraso / 30))
    return `Venceu em ${dataTexto} · vencido há ~${meses} ${meses === 1 ? 'mês' : 'meses'}`
  }
  if (diffDias < LIMITE_DIAS_MOSTRA_MESES) {
    return `Vence em ${dataTexto} · faltam ${diffDias} ${diffDias === 1 ? 'dia' : 'dias'}`
  }
  const meses = Math.round(diffDias / 30)
  return `Vence em ${dataTexto} · faltam ~${meses} meses`
}
