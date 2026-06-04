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

export function podeRegistrarContato(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL
}

export function podeAtenderSolicitacao(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL
}
