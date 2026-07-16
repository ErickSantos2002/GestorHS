import { type User } from './AuthContext'

export const FUNCAO_ADMIN = 'Administrador'

export function isAdmin(user: User | null): boolean {
  return user?.funcao === FUNCAO_ADMIN
}

export const FUNCAO_EXPEDICAO = 'Expedição'

export function podeAbrirOS(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_EXPEDICAO
}

export const FUNCAO_COMERCIAL = 'Comercial Pós-Vendas'

export const FUNCAO_FINANCEIRO = 'Financeiro'

export function podeRegistrarContato(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL
}

export function podeAtenderSolicitacao(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL
}

export function podeAnexarNotaFiscal(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_FINANCEIRO
}

export const FUNCAO_LABORATORIO = 'Laboratório'
export const FUNCAO_QUALIDADE = 'Qualidade'

export function podeGerenciarCertificadosGerais(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO || user?.funcao === FUNCAO_QUALIDADE
}
