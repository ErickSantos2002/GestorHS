/** Datas no formato do <input type="date"> (AAAA-MM-DD), sempre no fuso LOCAL.
 *
 *  NAO usar `new Date().toISOString().slice(0, 10)` para isso: o toISOString
 *  converte para UTC, entao a noite no Brasil (UTC-3) ele devolve o dia
 *  SEGUINTE — uma OS aberta as 22h nasceria com a data de amanha.
 */

/** Data local de `d` como AAAA-MM-DD. */
export function dataISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Hoje, no fuso local. */
export function hojeISO(): string {
  return dataISO(new Date())
}

/** Hoje + `anos`. 29/02 vira 01/03 no ano seguinte (normalizacao do Date). */
export function daquiAAnos(anos: number): string {
  const d = new Date()
  d.setFullYear(d.getFullYear() + anos)
  return dataISO(d)
}
