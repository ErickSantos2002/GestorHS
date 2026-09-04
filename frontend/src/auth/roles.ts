import { type User } from './AuthContext'
import { posLaboratorio } from '../app/ordens/api'

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
  return isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL || user?.funcao === FUNCAO_FINANCEIRO
}

export function podeAnexarNotaFiscal(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_FINANCEIRO
}

/** Avançar a caixa do Financeiro SEM anexar a nota fiscal.
 *
 * Só Administrador, espelhando o guard do backend em app/api/caixas.py. Existe
 * para as caixas do modelo antigo, que não têm nota para anexar e ficariam
 * travadas no Financeiro para sempre. */
export function podeAvancarSemNotaFiscal(user: User | null): boolean {
  return isAdmin(user)
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
// criar e transferir (Expedição dá entrada de módulos novos no estoque).
// ALTERAR é mais amplo — ver podeEditarCadastros abaixo.
// EXCLUIR continua exclusivo do Administrador — por isso os botões de excluir
// seguem usando isAdmin(), não este helper.
// Espelha GESTOR_CADASTRO em backend/app/api/deps.py — mudou lá, mude aqui.
export function podeGerenciarCadastros(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO || user?.funcao === FUNCAO_EXPEDICAO
}

// Alterar cadastro JA EXISTENTE: os gestores acima mais o Comercial Pós-Vendas,
// que precisa corrigir endereço/dados do cliente e marcar aparelho como inativo.
// Criar e transferir continuam em podeGerenciarCadastros; excluir segue só com isAdmin().
// Espelha EDITOR_CADASTRO em backend/app/api/deps.py — mudou lá, mude aqui.
export function podeEditarCadastros(user: User | null): boolean {
  return podeGerenciarCadastros(user) || user?.funcao === FUNCAO_COMERCIAL
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

/** Corrigir o tipo de serviço da OS, durante o laboratório.
 *
 * A Expedição registra o tipo na entrada pelo que vê por fora; quem descobre
 * que o aparelho também precisa de manutenção é o técnico na bancada. Só na
 * fase do Laboratório: depois dela a OS já emitiu certificado e seguiu para
 * cobrança. Espelha o guard de app/api/ordens.py. */
export function podeEditarTipoServico(user: User | null, fase: number | null): boolean {
  return (isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO) && fase === 5
}

/** Registrar a manutenção e gerar o relatório.
 *
 * Laboratório e Administrador, do Laboratório em diante — a mesma janela do
 * certificado de calibração, que permite regerar OS antiga sob demanda.
 * Espelha `na_janela` em app/api/manutencoes.py.
 *
 * Usa `posLaboratorio` (o mesmo helper de `podeGerarOuRegerar`) em vez de uma
 * lista de ids: o Financeiro é o id 10, maior que Preparando Retorno (7) e
 * Finalizada (8), então uma lista "em ordem" o deixava de fora e travava a OS
 * justamente na fase por onde toda OS passa. */
export function podeRegistrarManutencao(user: User | null, fase: number | null): boolean {
  return (isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO) && posLaboratorio(fase)
}

// Espelha require_funcao("Financeiro", "Administrador") em
// backend/app/api/propostas.py (POST /propostas/{id}/faturar) — mudou lá, mude aqui.
export function podeFaturarProposta(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_FINANCEIRO
}

// Espelha require_funcao("Financeiro", "Administrador") em
// backend/app/api/propostas.py (POST /propostas/{id}/desfaturar) — mudou lá, mude
// aqui. Mesma regra de `podeFaturarProposta`: quem marca o faturamento e' quem
// descobre o engano, entao desfaz tambem. Era exclusivo do Admin ate 04/09/2026.
export function podeDesfaturarProposta(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_FINANCEIRO
}

// Espelha require_funcao("Administrador") em backend/app/api/propostas.py
// (POST /propostas/{id}/reativar). Desabilitar é do mesmo grupo que edita
// (`podeGerenciarPropostas`); devolver à circulação é só do Admin.
export function podeReativarProposta(user: User | null): boolean {
  return isAdmin(user)
}

// Espelha require_funcao("Administrador", "Laboratório") em
// backend/app/api/certificados_config.py — mudou la, mude aqui.
// O Laboratorio edita a configuracao e cadastra/altera cilindro: e quem opera a
// calibracao e sabe qual gas esta na bancada.
export function podeEditarConfigCertificado(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO
}

// EXCLUIR cilindro fica so com o Administrador, a pedido do proprio laboratorio: apagar
// e irreversivel e leva junto a rastreabilidade dos certificados emitidos com aquele
// cilindro. Para aposentar um cilindro existe "encerrar vigencia".
// Espelha _excluir em backend/app/api/certificados_config.py.
export function podeExcluirCilindro(user: User | null): boolean {
  return isAdmin(user)
}
