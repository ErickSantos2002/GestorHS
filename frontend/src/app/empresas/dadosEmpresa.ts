// Dados cadastrais de um destinatario (Cliente ou Empresa) como aparecem no
// formulario compartilhado. Fonte unica dos campos, rotulos e obrigatorios —
// usada pela pagina Empresas e pelo modal da proposta.

import { soDigitos } from '../../lib/documento'
import type { Cliente } from '../clientes/api'
import type { Empresa } from './api'

export const CAMPOS_DADOS = [
  'nome', 'documento', 'cep', 'endereco', 'numero', 'complemento', 'bairro',
  'municipio', 'estado', 'telefone', 'email',
] as const
export type CampoDados = (typeof CAMPOS_DADOS)[number]
export type DadosEmpresa = Record<CampoDados, string>

export const ROTULOS_DADOS: Record<CampoDados, string> = {
  nome: 'Razão social / Nome',
  documento: 'CNPJ / CPF',
  cep: 'CEP',
  endereco: 'Endereço',
  numero: 'Número',
  complemento: 'Complemento',
  bairro: 'Bairro',
  municipio: 'Município',
  estado: 'Estado (UF)',
  telefone: 'Telefone',
  email: 'E-mail',
}

export const UFS = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG',
  'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
]

/** Obrigatorios na proposta. "Aos cuidados de" tambem e', mas mora na proposta. */
export const OBRIGATORIOS_PROPOSTA: readonly CampoDados[] = [
  'nome', 'documento', 'cep', 'endereco', 'municipio', 'estado', 'telefone', 'email',
]

const SO_DIGITOS = new Set<CampoDados>(['documento', 'cep'])

export function dadosVazios(documento = ''): DadosEmpresa {
  const d = Object.fromEntries(CAMPOS_DADOS.map((c) => [c, ''])) as DadosEmpresa
  d.documento = documento
  return d
}

interface Opcoes {
  /** Traz e-mail e telefone do cadastro. Na proposta eles abrem VAZIOS de
   *  proposito: vindo prontos, ninguem conferia e a proposta saia com o contato
   *  velho (pedido do comercial, commit 706fc68). */
  comContato?: boolean
}

const txt = (v: string | number | null | undefined) => (v == null ? '' : String(v))

export function sugestoesDeCliente(c: Cliente): { email: string; telefone: string } {
  return { email: txt(c.email), telefone: txt(c.telefones || c.celular || c.whatsapp) }
}

export function sugestoesDeEmpresa(e: Empresa): { email: string; telefone: string } {
  return { email: txt(e.email), telefone: txt(e.telefone) }
}

export function dadosDeCliente(c: Cliente, opcoes: Opcoes = {}): DadosEmpresa {
  const s = sugestoesDeCliente(c)
  return {
    nome: txt(c.nome), documento: soDigitos(c.cgc || c.cpf), cep: soDigitos(c.cep),
    endereco: txt(c.endereco), numero: txt(c.numero), complemento: txt(c.complemento),
    bairro: txt(c.bairro), municipio: txt(c.municipio), estado: txt(c.estado),
    email: opcoes.comContato ? s.email : '', telefone: opcoes.comContato ? s.telefone : '',
  }
}

export function dadosDeEmpresa(e: Empresa, opcoes: Opcoes = {}): DadosEmpresa {
  const s = sugestoesDeEmpresa(e)
  return {
    nome: e.nome, documento: soDigitos(e.cgc || e.cpf), cep: soDigitos(e.cep),
    endereco: txt(e.endereco), numero: txt(e.numero), complemento: txt(e.complemento),
    bairro: txt(e.bairro), municipio: txt(e.municipio), estado: txt(e.estado),
    email: opcoes.comContato ? s.email : '', telefone: opcoes.comContato ? s.telefone : '',
  }
}

export function camposFaltando(d: DadosEmpresa, obrigatorios: readonly CampoDados[]): CampoDados[] {
  return obrigatorios.filter((c) => (SO_DIGITOS.has(c) ? !soDigitos(d[c]) : d[c].trim() === ''))
}
