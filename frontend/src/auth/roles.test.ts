import { describe, it, expect } from 'vitest'
import { isAdmin, podeAbrirOS, podeRegistrarContato } from './roles'
import { type User } from './AuthContext'

const admin: User = { id: 1, nome: null, login: 'a', email: null, funcao_id: 1, funcao: 'Administrador' }
const comum: User = { id: 2, nome: null, login: 'b', email: null, funcao_id: 2, funcao: 'Expedição' }

describe('isAdmin', () => {
  it('true para Administrador', () => expect(isAdmin(admin)).toBe(true))
  it('false para outra função', () => expect(isAdmin(comum)).toBe(false))
  it('false para null', () => expect(isAdmin(null)).toBe(false))
})

function u(funcao: string | null): User {
  return { id: 1, nome: 'x', login: 'x', funcao } as User
}

describe('auth/roles — podeAbrirOS', () => {
  it('admin pode', () => expect(podeAbrirOS(u('Administrador'))).toBe(true))
  it('Expedição pode', () => expect(podeAbrirOS(u('Expedição'))).toBe(true))
  it('Laboratório não pode', () => expect(podeAbrirOS(u('Laboratório'))).toBe(false))
  it('null não pode', () => expect(podeAbrirOS(null)).toBe(false))
})

describe('auth/roles — podeRegistrarContato', () => {
  it('podeRegistrarContato: admin e Comercial sim, outros não', () => {
    expect(podeRegistrarContato(u('Administrador'))).toBe(true)
    expect(podeRegistrarContato(u('Comercial Pós-Vendas'))).toBe(true)
    expect(podeRegistrarContato(u('Laboratório'))).toBe(false)
    expect(podeRegistrarContato(null)).toBe(false)
  })
})
