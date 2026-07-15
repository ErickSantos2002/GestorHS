/** Média dos 3 testes de calibração, formatada como no certificado.
 *
 * Fonte única — o certificado da OS e o avulso usam a mesma regra. Arredonda para até
 * 3 casas decimais e remove os zeros à direita, para acompanhar a precisão digitada:
 * 0,186/0,183/0,183 → 0,184; 0,18/0,18/0,18 → 0,18; 0,10/0,11/0,12 → 0,11.
 * Retorna '' quando algum teste está vazio ou não é número (usado para só preencher
 * automaticamente enquanto o usuário não editou a média à mão).
 */
export function mediaTestes(t1: string, t2: string, t3: string): string {
  const vals = [t1, t2, t3]
  if (vals.some((v) => v.trim() === '')) return ''
  const nums = vals.map((v) => Number(v.replace(',', '.')))
  if (nums.some((n) => Number.isNaN(n))) return ''
  const media = ((nums[0] + nums[1] + nums[2]) / 3)
    .toFixed(3)
    .replace(/0+$/, '')   // remove zeros à direita (0,180 → 0,18)
    .replace(/\.$/, '')   // e o ponto solto, se sobrar (1,000 → 1)
  return media.replace('.', ',')
}
