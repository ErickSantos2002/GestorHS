/** Valores do formulario de certificado, compartilhados entre o fluxo da OS e o de venda.
 *
 * Fica em modulo separado do componente porque o Fast Refresh exige que um arquivo de
 * componente exporte apenas componentes (regra react-refresh/only-export-components).
 */
export interface ValoresCertificado {
  nomecli: string
  cnpj: string
  endcli: string
  modelo: string
  marca: string
  serie: string
  patrimonio: string
  datacompra: string
  dataCalib: string
  cert: string
  situacao: string
  temp: string
  pressao: string
  t1: string
  t2: string
  t3: string
  media: string
}

export function hojeISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function valoresIniciais(): ValoresCertificado {
  return {
    nomecli: '', cnpj: '', endcli: '',
    modelo: '', marca: '', serie: '', patrimonio: '', datacompra: '',
    dataCalib: hojeISO(), cert: '', situacao: '',
    temp: '', pressao: '', t1: '', t2: '', t3: '', media: '',
  }
}
