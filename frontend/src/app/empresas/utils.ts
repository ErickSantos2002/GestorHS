import { soDigitos } from '../../lib/documento'
import { type EmpresaPayload } from './api'
import { type DadosEmpresa } from './dadosEmpresa'
import { type MatrizValor } from './MatrizSelect'

const nulo = (v: string) => (v.trim() === '' ? null : v.trim())

export function montarPayloadEmpresa(dados: DadosEmpresa, matriz: MatrizValor | null, inscEst: string): EmpresaPayload {
  return {
    documento: soDigitos(dados.documento), cliente: matriz?.id ?? null, nome: dados.nome.trim(),
    cep: nulo(soDigitos(dados.cep)), endereco: nulo(dados.endereco), numero: nulo(dados.numero),
    complemento: nulo(dados.complemento), bairro: nulo(dados.bairro), municipio: nulo(dados.municipio),
    estado: nulo(dados.estado), email: nulo(dados.email), telefone: nulo(dados.telefone), insc_est: nulo(inscEst),
  }
}
