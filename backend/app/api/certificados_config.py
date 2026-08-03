"""Configuracao do certificado (linha unica) e cadastro dos padroes (cilindros).

Leitura liberada a qualquer usuario interno — o modal de gerar certificado precisa
dos limites para destacar medicao fora da faixa. Escrita e so do Administrador:
sao os numeros que definem a incerteza de todo certificado emitido.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario, require_funcao
from app.core.certificado_calculo import CASAS_MEDICAO, calcular, formatar_numero
from app.core.certificado_config import DOCUMENTOS_QR, obter_config, parametros_de
from app.models import CertificadoGeral, CertificadoPadrao, Ordem, Usuario
from app.models.database import get_db
from app.schemas.certificado_config import (
    CalculoPreviaIn,
    CalculoPreviaOut,
    CertificadoConfigIn,
    CertificadoConfigOut,
    CertificadoPadraoIn,
    CertificadoPadraoOut,
    CertificadoPadraoUpdate,
)

router = APIRouter(tags=["certificado-config"])

# Espelhado em podeEditarConfigCertificado, frontend/src/auth/roles.ts — mudou aqui, mude la.
_escrita = require_funcao("Administrador")


@router.get("/certificado-config", response_model=CertificadoConfigOut)
def ler_config(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return obter_config(db)


@router.put("/certificado-config", response_model=CertificadoConfigOut)
def gravar_config(dados: CertificadoConfigIn, db: Session = Depends(get_db),
                  _: Usuario = Depends(_escrita)):
    config = obter_config(db)
    alteracoes = dados.model_dump(exclude_unset=True)

    # doc_*_id nao tem ON DELETE e nao ha handler global de IntegrityError: gravar um
    # id apagado entre a tela abrir e o admin salvar estouraria no db.commit() como
    # 500 sem explicacao. Validar antes e o que da um 422 acionavel em vez disso.
    for campo, rotulo in DOCUMENTOS_QR:
        if campo in alteracoes and alteracoes[campo] is not None:
            if db.get(CertificadoGeral, alteracoes[campo]) is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"O documento selecionado para \"{rotulo}\" não existe mais. "
                           f"Recarregue a página e escolha novamente.",
                )

    for chave, valor in alteracoes.items():
        setattr(config, chave, valor)
    db.commit()
    db.refresh(config)
    return config


@router.get("/certificado-padroes", response_model=list[CertificadoPadraoOut])
def listar_padroes(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return (
        db.query(CertificadoPadrao)
        .order_by(CertificadoPadrao.vigencia_inicio.desc(), CertificadoPadrao.id.desc())
        .all()
    )


@router.post("/certificado-padroes", response_model=CertificadoPadraoOut,
             status_code=status.HTTP_201_CREATED)
def criar_padrao(dados: CertificadoPadraoIn, db: Session = Depends(get_db),
                 _: Usuario = Depends(_escrita)):
    obj = CertificadoPadrao(**dados.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _padrao_ou_404(db: Session, padrao_id: int) -> CertificadoPadrao:
    obj = db.query(CertificadoPadrao).filter(CertificadoPadrao.id == padrao_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="padrão não encontrado")
    return obj


@router.patch("/certificado-padroes/{padrao_id}", response_model=CertificadoPadraoOut)
def atualizar_padrao(padrao_id: int, dados: CertificadoPadraoUpdate,
                     db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    obj = _padrao_ou_404(db, padrao_id)
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/certificado-padroes/{padrao_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_padrao(padrao_id: int, db: Session = Depends(get_db),
                   _: Usuario = Depends(_escrita)):
    obj = _padrao_ou_404(db, padrao_id)
    # ordens.padrao_id e FK sem ON DELETE: no Postgres, apagar um cilindro ja usado
    # estoura IntegrityError e vira 500. Alem disso, apagar destruiria a rastreabilidade
    # dos certificados ja emitidos com ele — quem quer aposentar um cilindro encerra a
    # vigencia, nao apaga o registro.
    em_uso = db.query(Ordem).filter(Ordem.padrao_id == padrao_id).count()
    if em_uso:
        raise HTTPException(
            status_code=409,
            detail=f"Este cilindro está em uso por {em_uso} ordem(ns) de serviço e não pode "
                   f"ser excluído. Para aposentá-lo, informe a vigência fim ou marque-o "
                   f"como inativo.",
        )
    db.delete(obj)
    db.commit()


@router.post("/certificado-calculo-previa", response_model=CalculoPreviaOut)
def calculo_previa(dados: CalculoPreviaIn, db: Session = Depends(get_db),
                   _: Usuario = Depends(get_current_usuario)):
    """Prévia dos valores calculados para o modal.

    Existe para que a tela NAO reimplemente a formula em TypeScript: uma formula,
    um lugar. Sem isso, a tela mostra um U e o PDF sai com outro.
    """
    config = obter_config(db)
    parametros = parametros_de(config)
    resultado = calcular(dados.medicoes, parametros)

    minimo = None if config.limite_minimo is None else float(config.limite_minimo)
    maximo = None if config.limite_maximo is None else float(config.limite_maximo)

    def _fora(medida: str | None) -> bool:
        # medicao em branco nao e "fora da faixa" — e ausencia de medicao
        texto = "" if medida is None else str(medida).strip().replace(",", ".")
        if not texto:
            return False
        try:
            numero = float(texto)
        except ValueError:
            return False
        return (minimo is not None and numero < minimo) or (maximo is not None and numero > maximo)

    fora = [_fora(m) for m in dados.medicoes]

    return CalculoPreviaOut(
        # Erros, media e limites com as casas FIXAS do certificado: o painel do modal
        # e o PDF tem de mostrar o mesmo numero. Divergir numa casa decimal e o tipo
        # de coisa que so aparece depois, no documento na mao do cliente.
        erros=[formatar_numero(e, casas=CASAS_MEDICAO, cortar_zeros=False) for e in resultado.erros],
        media=formatar_numero(resultado.media, casas=CASAS_MEDICAO, cortar_zeros=False),
        desvio_padrao=formatar_numero(resultado.desvio_padrao),
        incerteza_combinada=formatar_numero(resultado.incerteza_combinada),
        incerteza_expandida=formatar_numero(resultado.incerteza_expandida),
        fator_k=formatar_numero(resultado.fator_k, casas=2),
        limite_minimo=formatar_numero(minimo, casas=CASAS_MEDICAO, cortar_zeros=False),
        limite_maximo=formatar_numero(maximo, casas=CASAS_MEDICAO, cortar_zeros=False),
        fora_da_faixa=fora,
    )
