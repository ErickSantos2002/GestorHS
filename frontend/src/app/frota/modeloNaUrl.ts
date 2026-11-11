// Estado do filtro de modelo na URL (?equipamento=), compartilhado por Frota e Clientes.

/** Lê `?equipamento=` da URL: número válido ou undefined. */
export function lerEquipamento(sp: URLSearchParams): number | undefined {
  const v = Number(sp.get('equipamento'))
  return Number.isInteger(v) && v > 0 ? v : undefined
}

/** Devolve uma cópia de `sp` com `equipamento` gravado (ou removido). */
export function comEquipamento(sp: URLSearchParams, equipamento: number | undefined): URLSearchParams {
  const novo = new URLSearchParams(sp)
  if (equipamento === undefined) novo.delete('equipamento')
  else novo.set('equipamento', String(equipamento))
  return novo
}
