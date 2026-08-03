/** Média das medições de calibração, formatada como no certificado.
 *
 * Variádica para atender as 5 medições do certificado EPS-LAB-002 sem quebrar as
 * chamadas de 3 argumentos que já existiam. Arredonda para até 3 casas decimais e
 * remove os zeros à direita, para acompanhar a precisão digitada.
 * Retorna '' quando alguma medição está vazia ou não é número (usado para só
 * preencher automaticamente enquanto o usuário não editou a média à mão).
 */
export function mediaTestes(...valores: string[]): string {
  if (valores.length === 0) return ''
  if (valores.some((v) => v.trim() === '')) return ''
  const nums = valores.map((v) => Number(v.replace(',', '.')))
  if (nums.some((n) => Number.isNaN(n))) return ''
  const media = (nums.reduce((a, b) => a + b, 0) / nums.length)
    .toFixed(3)
    .replace(/0+$/, '')   // remove zeros à direita (0,180 → 0,18)
    .replace(/\.$/, '')   // e o ponto solto, se sobrar (1,000 → 1)
  return media.replace('.', ',')
}

/** Média das medições PREENCHIDAS, ignorando as vazias.
 *
 * É o que o certificado EPS-LAB-002 precisa: o backend calcula a média sobre as
 * medições que existirem (`statistics.fmean` sobre a lista já filtrada, em
 * `core/certificado_calculo.py`), então a tela tem de fazer o mesmo. Com a regra
 * do `mediaTestes` — vazio se QUALQUER medição estiver em branco — toda OS anterior
 * a este formato, que tem só 3 das 5 medições, teria a média apagada ao abrir o modal.
 * Sem nenhuma medição preenchida devolve '' (não há o que calcular).
 */
export function mediaTestesPreenchidas(...valores: string[]): string {
  const preenchidos = valores.filter((v) => v.trim() !== '')
  if (preenchidos.length === 0) return ''
  return mediaTestes(...preenchidos)
}
