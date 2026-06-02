import { apiJson, apiFetch, ApiError } from '../../lib/api'

export interface Funcao {
  id: number
  descricao: string
}

export interface UsuarioItem {
  id: number
  nome: string | null
  login: string
  email: string | null
  funcao_id: number | null
  funcao: string | null
  precisa_redefinir_senha: boolean
}

export interface UsuarioCreatePayload {
  nome?: string | null
  login: string
  email?: string | null
  senha: string
  funcao_id?: number | null
}

export interface UsuarioUpdatePayload {
  nome?: string | null
  email?: string | null
  funcao_id?: number | null
  login?: string
}

async function apiVoid(path: string, options: RequestInit = {}): Promise<void> {
  const res = await apiFetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers as Record<string, string>) },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // sem corpo JSON
    }
    throw new ApiError(res.status, detail)
  }
}

export function listarFuncoes(): Promise<Funcao[]> {
  return apiJson<Funcao[]>('/funcoes')
}

export function listarUsuarios(): Promise<UsuarioItem[]> {
  return apiJson<UsuarioItem[]>('/usuarios')
}

export function criarUsuario(payload: UsuarioCreatePayload): Promise<UsuarioItem> {
  return apiJson<UsuarioItem>('/usuarios', { method: 'POST', body: JSON.stringify(payload) })
}

export function atualizarUsuario(id: number, payload: UsuarioUpdatePayload): Promise<UsuarioItem> {
  return apiJson<UsuarioItem>(`/usuarios/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export function excluirUsuario(id: number): Promise<void> {
  return apiVoid(`/usuarios/${id}`, { method: 'DELETE' })
}

export function redefinirSenha(id: number, nova_senha: string): Promise<void> {
  return apiVoid(`/usuarios/${id}/redefinir-senha`, { method: 'POST', body: JSON.stringify({ nova_senha }) })
}

export function trocarMinhaSenha(senha_atual: string, nova_senha: string): Promise<void> {
  return apiVoid('/auth/trocar-senha', { method: 'POST', body: JSON.stringify({ senha_atual, nova_senha }) })
}
