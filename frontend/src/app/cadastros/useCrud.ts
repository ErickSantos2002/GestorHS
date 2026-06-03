import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../lib/api'

export interface ListClient<T> {
  listar: () => Promise<T[]>
}

export function useCrud<T>(client: ListClient<T>) {
  const [itens, setItens] = useState<T[] | null>(null)
  const [erro, setErro] = useState('')

  const recarregar = useCallback(async () => {
    setErro('')
    try {
      const dados = await client.listar()
      setItens(dados)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
      setItens([])
    }
  }, [client])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void recarregar()
  }, [recarregar])

  return { itens, erro, setErro, recarregar }
}
