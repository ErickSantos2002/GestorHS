import { describe, expect, it } from 'vitest'
import { chaveDeAcesso, nomeDoXml } from './notaFiscal'

const CHAVE = '35261112345678000190550010000123451234567890'
const NFE = `<?xml version="1.0"?><nfeProc><NFe><infNFe Id="NFe${CHAVE}" versao="4.00"/></NFe>` +
  `<protNFe><infProt><chNFe>${CHAVE}</chNFe></infProt></protNFe></nfeProc>`

describe('chaveDeAcesso', () => {
  it('le do infNFe', () => expect(chaveDeAcesso(NFE)).toBe(CHAVE))
  it('le so do protocolo', () => expect(chaveDeAcesso(`<x><chNFe>${CHAVE}</chNFe></x>`)).toBe(CHAVE))
  it('sem chave devolve null', () => expect(chaveDeAcesso('<nfse><numero>1</numero></nfse>')).toBeNull())
})

describe('nomeDoXml', () => {
  it('usa a chave', async () => {
    expect(await nomeDoXml(new Blob([NFE]), '123.xml')).toBe(`${CHAVE}.xml`)
  })
  it('cai na reserva sem chave', async () => {
    expect(await nomeDoXml(new Blob(['<nfse/>']), '123.xml')).toBe('123.xml')
  })
})
