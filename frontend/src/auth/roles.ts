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

export function podeGerenciarPropostas(user: User | null): boolean {
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

// Cadastro de clientes e aparelhos: Administrador, Laboratório e Expedição podem
// criar, alterar e transferir (Expedição dá entrada de módulos novos no estoque).
// EXCLUIR continua exclusivo do Administrador — por isso os botões de excluir
// seguem usando isAdmin(), não este helper.
// Espelha GESTOR_CADASTRO em backend/app/api/deps.py — mudou lá, mude aqui.
export function podeGerenciarCadastros(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO || user?.funcao === FUNCAO_EXPEDICAO
}

// Função responsável por avançar/cancelar a caixa em cada fase — espelha
// exige_funcao_da_fase em backend/app/api/caixas.py (via FASE_FUNCAO), que compara
// usuario.funcao com o funcao_responsavel da fase. Mudou lá, mude aqui.
export const FUNCAO_RESPONSAVEL_POR_FASE: Record<number, string> = {
  4: FUNCAO_EXPEDICAO,
  5: FUNCAO_LABORATORIO,
  6: FUNCAO_COMERCIAL,
  10: FUNCAO_FINANCEIRO,
  7: FUNCAO_EXPEDICAO,
}

// Admin sempre passa — espelha o early-return de exige_funcao_da_fase para Administrador.
export function podeAvancarCaixa(user: User | null, fase: number | null): boolean {
  return isAdmin(user) || (fase != null && user?.funcao === FUNCAO_RESPONSAVEL_POR_FASE[fase])
}

export function podeMarcarSemConserto(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO
}
