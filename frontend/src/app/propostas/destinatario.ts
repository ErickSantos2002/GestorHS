// Destinatario da proposta: um Cliente (matriz, dono da frota), uma Empresa
// (filial, frota da matriz) ou uma Empresa ainda nao cadastrada, que nasce no
// servidor junto com a proposta.

import { soDigitos } from '../../lib/documento'
import type { Cliente } from '../clientes/api'
import type { Empresa } from '../empresas/api'
import type { DadosEmpresa } from '../empresas/dadosEmpresa'
import type { MatrizValor } from '../empresas/MatrizSelect'
import type { DestinatarioIn } from './api'

export type Selecao =
  | { tipo: 'cliente'; cliente: Cliente }
  | { tipo: 'empresa'; empresa: Empresa }
  | { tipo: 'nova_empresa'; matriz: MatrizValor | null }

/** De qual cliente sai a frota (aparelhos) da proposta. */
export function clienteDaFrota(s: Selecao | null): number | null {
  if (!s) return null
  if (s.tipo === 'cliente') return s.cliente.id
  if (s.tipo === 'empresa') return s.empresa.cliente
  return s.matriz?.id ?? null
}

export function descreverSelecao(s: Selecao): string {
  if (s.tipo === 'cliente') return 'Cliente'
  const matriz = s.tipo === 'empresa' ? s.empresa.matriz_nome : s.matriz?.nome
  const temMatriz = s.tipo === 'empresa' ? s.empresa.cliente != null : s.matriz != null
  const rotulo = s.tipo === 'empresa' ? 'Empresa' : 'Nova empresa'
  return `${rotulo} · ${temMatriz ? `matriz ${matriz ?? ''}`.trim() : 'sem matriz'}`
}

const nulo = (v: string) => (v.trim() === '' ? null : v.trim())

export function montarDestinatario(s: Selecao, d: DadosEmpresa): DestinatarioIn {
  return {
    tipo: s.tipo,
    id: s.tipo === 'cliente' ? s.cliente.id : s.tipo === 'empresa' ? s.empresa.id : null,
    // A matriz e' editavel tanto na empresa nova quanto na ja cadastrada; o
    // Cliente e' a propria matriz, entao nao tem campo.
    matriz: s.tipo === 'cliente' ? null : s.tipo === 'empresa' ? s.empresa.cliente : (s.matriz?.id ?? null),
    // Documento de cadastro existente nao muda pela proposta (o servidor ignora).
    documento: s.tipo === 'nova_empresa' ? soDigitos(d.documento) : null,
    nome: d.nome.trim(),
    cep: nulo(soDigitos(d.cep)),
    endereco: nulo(d.endereco),
    numero: nulo(d.numero),
    complemento: nulo(d.complemento),
    bairro: nulo(d.bairro),
    municipio: nulo(d.municipio),
    estado: nulo(d.estado),
    email: d.email.trim(),
    telefone: d.telefone.trim(),
  }
}
