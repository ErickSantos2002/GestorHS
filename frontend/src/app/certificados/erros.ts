import { ApiError } from '../../lib/api'

/** Mostra o que o backend disse, e não um genérico.
 *
 *  O 409 de cilindro em uso explica o que fazer ("encerre a vigência"), e o 422 diz
 *  qual campo recusou — engolir isso deixa o admin sem saída, tendo que pedir para
 *  alguém ler o log para descobrir o que ele digitou de errado. Foi exatamente o que
 *  aconteceu em 03/08/2026 com "Falha ao cadastrar o cilindro.". Compartilhado entre
 *  as abas de certificados porque o mesmo problema apareceu nas duas.
 */
export function mensagemDeErro(err: unknown, generica: string): string {
  return err instanceof ApiError && err.message ? err.message : generica
}
