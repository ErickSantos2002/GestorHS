import { describe, it, expect } from 'vitest'
import { isAdmin } from './roles'
import { type User } from './AuthContext'

const admin: User = { id: 1, nome: null, login: 'a', email: null, funcao_id: 1, funcao: 'Administrador' }
const comum: User = { id: 2, nome: null, login: 'b', email: null, funcao_id: 2, funcao: 'Expedição' }

describe('isAdmin', () => {
  it('true para Administrador', () => expect(isAdmin(admin)).toBe(true))
  it('false para outra função', () => expect(isAdmin(comum)).toBe(false))
  it('false para null', () => expect(isAdmin(null)).toBe(false))
})
