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

// Espelha require_funcao("Laboratório", "Administrador") em
// backend/app/api/certificados_venda.py — mudou lá, mude aqui.
export function podeGerarCertificadoVenda(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO
}

// Cadastro de clientes e aparelhos: Administrador e Laboratório podem criar,
// alterar e transferir. EXCLUIR continua exclusivo do Administrador — por isso
// os botões de excluir seguem usando isAdmin(), não este helper.
export function podeGerenciarCadastros(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO
}
