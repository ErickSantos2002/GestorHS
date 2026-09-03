from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status as http_status, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import (Usuario, Ordem, Cliente, Fase, LogOS, EquipamentoCliente, Caixa,
                        OSCertificado, Manutencao)
from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import agora, registrar_log, exige_funcao_da_fase, concluir_laboratorio
from app.core import os_workflow as wf
from app.core import recebimento as rec
from app.core.garantia import garantias as _calc_garantias
from app.core.certificado_gerar import tipos_para, tipos_sem_modelo
from app.api.caixas import sincronizar_principal
from app.api.exportar_common import carregar_ate_o_teto, resposta_xlsx
from app.core.exportacoes import COLUNAS_ORDENS, linha_ordem
from app.api.espelhamento import agendar_espelhamento_caixa
from app.core.taskhs import TIPO_SERVICO_LABEL
from app.schemas.ordens import (
    OrdemListOut, OrdemPage, QuadroColuna, OrdemOut, LogOut, OrdemAbrirIn, OrdemEditarIn,
    AvancarIn, CancelarIn, DesfechoLabIn, ObservacoesIn, TipoServicoIn,
)

router = APIRouter(prefix="/ordens", tags=["ordens"])

LIMITE_FINALIZADAS_QUADRO = 300


def _query_ordens(db: Session, fase: int | None = None, cliente: int | None = None,
                  tipo: str | None = None, q: str | None = None,
                  chegada_de: date | None = None, chegada_ate: date | None = None):
    """Filtros da lista de OS. Usado por listar() e por exportar() — ter um lugar
    so' impede que a planilha ignore um filtro novo em silencio."""
    query = db.query(Ordem)
    if fase is not None:
        query = query.filter(Ordem.fase == fase)
    if cliente is not None:
        query = query.filter(Ordem.cliente == cliente)
    if tipo:
        query = query.filter(Ordem.tipo_servico == tipo)
    # Faixa de data de chegada, INCLUSIVA nas duas pontas. `data_chegada` e um
    # DateTime: uma data digitada no recebimento fica em 00:00 UTC, mas a que o
    # sistema preenche sozinho carrega a hora. Por isso o fim da faixa e "< dia
    # seguinte" em vez de "<= o dia" — senao uma OS chegada as 14h do ultimo dia
    # ficaria de fora do proprio filtro que a inclui.
    if chegada_de is not None:
        query = query.filter(Ordem.data_chegada >= datetime.combine(chegada_de, datetime.min.time(), tzinfo=timezone.utc))
    if chegada_ate is not None:
        limite = datetime.combine(chegada_ate, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)
        query = query.filter(Ordem.data_chegada < limite)
    if q:
        if q.strip().isdigit():
            query = query.filter(Ordem.id == int(q.strip()))
        else:
            termo = f"%{q}%"
            query = query.join(Cliente, Ordem.cliente == Cliente.id).filter(
                or_(Ordem.etiqueta.ilike(termo), Cliente.nome.ilike(termo))
            )
    return query.order_by(Ordem.id.desc())


@router.get("", response_model=OrdemPage)
def listar(
    fase: int | None = None,
    cliente: int | None = None,
    tipo: str | None = None,
    q: str | None = None,
    chegada_de: date | None = None,
    chegada_ate: date | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = _query_ordens(db, fase=fase, cliente=cliente, tipo=tipo, q=q,
                          chegada_de=chegada_de, chegada_ate=chegada_ate)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return OrdemPage(items=[OrdemListOut.model_validate(o) for o in items], total=total)


@router.get("/quadro", response_model=list[QuadroColuna])
def quadro(cliente: int | None = None, db: Session = Depends(get_db),
           _: Usuario = Depends(get_current_usuario)):
    fases_ids = list(wf.ATIVAS) + [wf.FASE_FINALIZADA]
    fases = {f.id: f for f in db.query(Fase).filter(Fase.id.in_(fases_ids)).all()}
    colunas: list[QuadroColuna] = []
    for fid in fases_ids:
        query = db.query(Ordem).filter(Ordem.fase == fid)
        if cliente is not None:
            query = query.filter(Ordem.cliente == cliente)
        total = query.count()
        ordenadas = query.order_by(Ordem.id.desc())
        if fid == wf.FASE_FINALIZADA:
            ordenadas = ordenadas.limit(LIMITE_FINALIZADAS_QUADRO)
        ordens = ordenadas.all()
        f = fases.get(fid)
        colunas.append(QuadroColuna(
            fase=fid,
            descricao=f.descricao if f else "",
            cor=f.cor if f else "000000",
            total=total,
            ordens=[OrdemListOut.model_validate(o) for o in ordens],
        ))
    return colunas


@router.get("/exportar", response_class=Response)
def exportar(
    fase: int | None = None,
    cliente: int | None = None,
    tipo: str | None = None,
    q: str | None = None,
    chegada_de: date | None = None,
    chegada_ate: date | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    itens = carregar_ate_o_teto(_query_ordens(db, fase=fase, cliente=cliente, tipo=tipo, q=q,
                                              chegada_de=chegada_de, chegada_ate=chegada_ate))

    # O rodape existe para identificar a exportacao parcial — mostrar o id cru do
    # filtro nao diz nada pra quem abre o arquivo por e-mail; resolve nome/descricao
    # so' quando o filtro correspondente veio preenchido.
    cliente_nome = cliente
    if cliente is not None:
        nome = db.query(Cliente.nome).filter(Cliente.id == cliente).scalar()
        cliente_nome = nome if nome is not None else cliente
    fase_descricao = fase
    if fase is not None:
        descricao = db.query(Fase.descricao).filter(Fase.id == fase).scalar()
        fase_descricao = descricao if descricao is not None else fase

    return resposta_xlsx(
        "ordens", "Ordens de servico", COLUNAS_ORDENS,
        [linha_ordem(o) for o in itens],
        {"Fase": fase_descricao, "Cliente": cliente_nome, "Tipo": tipo, "Busca": q,
         "Chegada de": chegada_de.strftime("%d/%m/%Y") if chegada_de else None,
         "Chegada ate": chegada_ate.strftime("%d/%m/%Y") if chegada_ate else None},
    )


def _anotar_modelos_faltantes(db: Session, ordem) -> None:
    """Anota na OS quais tipos de certificado o aparelho não tem modelo cadastrado.

    A tela usa isso para avisar ANTES de o usuário tentar gerar. Precisa ser aplicado em
    TODA resposta `OrdemOut` — se ficar só no `obter`, o default `[]` do schema faz o
    aviso sumir (e o botão "Gerar" reaparecer) depois de avançar/cancelar a OS.
    """
    ordem.certificado_modelos_faltantes = tipos_sem_modelo(db, ordem, tipos_para(ordem))


def _ultima_manutencao(db: Session, equipamento_cliente_id: int) -> date | None:
    """Data da última manutenção do aparelho, base da garantia de manutenção.

    Vale a partir da CONCLUSÃO DO LABORATÓRIO — o mesmo momento em que a
    calibração é espelhada no aparelho. Exigir a fase Finalizada deixava a
    garantia de manutenção praticamente invisível: das 40 OS de manutenção do
    banco, uma só tinha chegado lá (03/09/2026).

    `desfecho_lab == concluido` é o que separa manutenção FEITA de OS que saíram
    do laboratório sem serviço (`liberado`/`sem_conserto`) — essas não geram
    garantia, nem as canceladas.

    A data é a do registro de manutenção (`manutencoes.data_manutencao`, a data
    real do serviço, que pode ser anterior à conclusão da OS); OS abertas antes
    desse registro existir caem na data da própria OS.
    """
    linhas = (
        db.query(Manutencao.data_manutencao, Ordem.data_calibracao)
        .select_from(Ordem)
        .outerjoin(Manutencao, Manutencao.os == Ordem.id)
        .filter(
            Ordem.equipamento_cliente == equipamento_cliente_id,
            Ordem.tipo_servico.in_(("M", "A")),
            Ordem.desfecho_lab == wf.DESFECHO_CONCLUIDO,
            Ordem.fase != wf.FASE_CANCELADA,
        )
        .all()
    )
    datas = [
        m if m is not None else (d.date() if d is not None else None)
        for m, d in linhas
    ]
    datas = [d for d in datas if d is not None]
    return max(datas) if datas else None


@router.get("/{ordem_id}", response_model=OrdemOut)
def obter(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    eqc = obj.equipamento_rel
    if eqc is not None:
        obj.garantias = _calc_garantias(
            datacompra=eqc.datacompra,
            ult_calibragem=eqc.ult_calibragem,
            ult_manutencao=_ultima_manutencao(db, eqc.id),
            hoje=date.today(),
        )
    else:
        obj.garantias = None
    _anotar_modelos_faltantes(db, obj)
    return obj


@router.get("/{ordem_id}/logs", response_model=list[LogOut])
def logs(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(Ordem).filter(Ordem.id == ordem_id).first() is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return db.query(LogOS).filter(LogOS.os == ordem_id).order_by(LogOS.id).all()


@router.post("", response_model=OrdemOut, status_code=http_status.HTTP_201_CREATED)
def abrir(dados: OrdemAbrirIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db),
          usuario: Usuario = Depends(require_funcao("Expedição", "Administrador"))):
    ec = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == dados.equipamento_cliente).first()
    if ec is None:
        raise HTTPException(status_code=404, detail="equipamento do cliente não encontrado")
    ativa = (
        db.query(Ordem)
        .filter(Ordem.equipamento_cliente == ec.id, Ordem.fase.in_(wf.ATIVAS))
        .first()
    )
    if ativa is not None:
        raise HTTPException(status_code=409, detail="aparelho já possui OS ativa")
    if dados.caixa is None:
        # Sem caixa informada, ela nasce AQUI, dentro da mesma transacao da OS.
        # Duas razoes: o numero da caixa e' o id, entao so o banco sabe qual e' o
        # proximo — criar antes, por outra tela, era adivinhar; e uma caixa criada
        # num passo separado sobrevive a desistencia no meio do cadastro, virando
        # caixa vazia. Aqui, se a abertura falhar, a transacao desfaz as duas.
        cx = Caixa(data=date.today())
        db.add(cx)
        db.flush()
    else:
        cx = db.query(Caixa).filter(Caixa.id == dados.caixa).first()
        if cx is None:
            raise HTTPException(status_code=404, detail="caixa não encontrada")
    if dados.condicao_chegada is not None and dados.condicao_chegada not in rec.CONDICOES_CHEGADA:
        raise HTTPException(status_code=400, detail="condição de chegada inválida")
    try:
        checklist_csv = rec.checklist_ids_para_csv(dados.checklist)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if dados.data_chegada is not None:
        data_chegada = datetime(
            dados.data_chegada.year, dados.data_chegada.month, dados.data_chegada.day,
            tzinfo=timezone.utc,
        )
    else:
        data_chegada = agora()
    fase_inicial = cx.fase if cx.fase is not None else wf.FASE_RECEBIDO
    ordem = Ordem(
        cliente=ec.cliente,
        equipamento_cliente=ec.id,
        fase=fase_inicial,
        tipo_servico=dados.tipo_servico,
        condicao_chegada=dados.condicao_chegada,
        checklist=checklist_csv,
        pilhas=dados.pilhas or 0,
        sopradores=dados.bocais or 0,
        obs=dados.observacoes,
        data_chegada=data_chegada,
        recebido=True,
        situacao="E",
        caixa=cx.id,
    )
    db.add(ordem)
    db.flush()
    ec.os_atual = ordem.id
    cx.fase = fase_inicial
    sincronizar_principal(db, cx)
    registrar_log(db, ordem, usuario, "OS aberta — Recebido")
    db.commit()
    db.refresh(ordem)
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx)
    _anotar_modelos_faltantes(db, ordem)
    return ordem


@router.put("/{ordem_id}/editar", response_model=OrdemOut)
def editar(ordem_id: int, dados: OrdemEditarIn, db: Session = Depends(get_db),
           usuario: Usuario = Depends(require_funcao("Administrador"))):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    campos = dados.model_dump(exclude_unset=True)
    if "condicao_chegada" in campos and campos["condicao_chegada"] is not None \
            and campos["condicao_chegada"] not in rec.CONDICOES_CHEGADA:
        raise HTTPException(status_code=400, detail="condição de chegada inválida")
    if "checklist" in campos:
        try:
            ordem.checklist = rec.checklist_ids_para_csv(campos["checklist"])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if "data_chegada" in campos and campos["data_chegada"] is not None:
        d = campos["data_chegada"]
        ordem.data_chegada = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    if "tipo_servico" in campos:
        ordem.tipo_servico = campos["tipo_servico"]
    if "condicao_chegada" in campos:
        ordem.condicao_chegada = campos["condicao_chegada"]
    if "pilhas" in campos:
        ordem.pilhas = campos["pilhas"]
    if "bocais" in campos:
        ordem.sopradores = campos["bocais"]
    if "garantia" in campos and campos["garantia"] is not None:
        ordem.garantia = campos["garantia"]
    if "observacoes" in campos:
        ordem.obs = campos["observacoes"]
    alterados = ", ".join(sorted(campos.keys()))
    registrar_log(db, ordem, usuario, f"OS editada (admin): {alterados}")
    db.commit()
    db.refresh(ordem)
    _anotar_modelos_faltantes(db, ordem)
    return ordem


@router.patch("/{ordem_id}/observacoes", response_model=OrdemOut)
def editar_observacoes(ordem_id: int, dados: ObservacoesIn, db: Session = Depends(get_db),
                       usuario: Usuario = Depends(get_current_usuario)):
    """Anotacao livre da OS: sem dono de fase e sem funcao exigida.

    Endpoint proprio de proposito — o `/editar` mexe em tipo de servico, checklist,
    datas e garantia, e exige Administrador; abri-lo daria muito mais que isto.
    """
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    texto = (dados.observacoes or "").strip() or None
    ordem.obs = texto
    registrar_log(db, ordem, usuario,
                  "Observações editadas" if texto else "Observações apagadas")
    db.commit()
    db.refresh(ordem)
    _anotar_modelos_faltantes(db, ordem)
    return ordem


@router.patch("/{ordem_id}/tipo-servico", response_model=OrdemOut)
def editar_tipo_servico(ordem_id: int, dados: TipoServicoIn, background_tasks: BackgroundTasks,
                        db: Session = Depends(get_db),
                        usuario: Usuario = Depends(require_funcao("Laboratório", "Administrador"))):
    """Corrige o tipo de servico DURANTE o laboratorio.

    A Expedicao registra o tipo na entrada pelo que da para ver por fora; quem
    descobre que o aparelho tambem precisa de manutencao e' o tecnico na bancada.

    Endpoint proprio, e nao uma abertura do `/editar`: aquele e' de Administrador
    e mexe tambem em checklist, datas e garantia. So na fase do laboratorio —
    depois dela a OS ja emitiu certificado e seguiu para cobranca, e trocar o
    tipo mudaria o que foi cobrado e o que foi emitido. Fora dessa janela o
    Administrador continua com o `/editar`.
    """
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    if ordem.fase != wf.FASE_LABORATORIO:
        raise HTTPException(status_code=409,
                            detail="o tipo de serviço só pode ser corrigido enquanto a OS está no Laboratório")
    anterior = ordem.tipo_servico
    if dados.tipo_servico == anterior:
        return ordem
    ordem.tipo_servico = dados.tipo_servico
    registrar_log(db, ordem, usuario,
                  f"Tipo de serviço alterado: {TIPO_SERVICO_LABEL.get(anterior, anterior or '—')}"
                  f" -> {TIPO_SERVICO_LABEL[dados.tipo_servico]}")
    db.commit()
    db.refresh(ordem)
    # O card do TaskHS mostra o tipo no cabecalho — sem reespelhar, ele ficaria
    # com o valor antigo ate o proximo avanco de fase. Reespelha a CAIXA, nunca a
    # OS: quem vira card no board e' a caixa, e um card por OS deixaria a mesma
    # caixa com dois cards.
    cx = db.query(Caixa).filter(Caixa.id == ordem.caixa).first() if ordem.caixa else None
    if cx is not None:
        agendar_espelhamento_caixa(db, background_tasks, cx)
    _anotar_modelos_faltantes(db, ordem)
    return ordem


@router.post("/{ordem_id}/avancar", response_model=OrdemOut)
def avancar(ordem_id: int, dados: AvancarIn, background_tasks: BackgroundTasks,
            db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    raise HTTPException(status_code=409, detail="a OS anda pela caixa; use /caixas/{id}/avancar")


@router.post("/{ordem_id}/desfecho-lab", response_model=OrdemOut)
def marcar_desfecho_lab(ordem_id: int, dados: DesfechoLabIn, db: Session = Depends(get_db),
                        usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    if ordem.fase != wf.FASE_LABORATORIO:
        raise HTTPException(status_code=409, detail="desfecho só no laboratório")
    exige_funcao_da_fase(db, usuario, ordem.fase)
    if dados.desfecho == wf.DESFECHO_CONCLUIDO:
        # Os documentos que o TIPO DE SERVICO pede — nao "qualquer certificado".
        # Antes bastava um: uma OS de Calibracao com o certificado gerado, trocada
        # para "Ambas" na propria fase do laboratorio, concluia sem o relatorio de
        # manutencao, porque o certificado antigo satisfazia a trava.
        emitidos = {c.tipo for c in db.query(OSCertificado).filter(OSCertificado.os == ordem.id).all()}
        faltam = [t for t in tipos_para(ordem) if t not in emitidos]
        if faltam:
            nomes = " e ".join(TIPO_SERVICO_LABEL.get(t, t) for t in faltam)
            raise HTTPException(status_code=409,
                                detail=f"gere o certificado de {nomes} antes de concluir")
        concluir_laboratorio(db, ordem)
        texto = "Laboratório concluído (aparelho)"
    elif dados.desfecho == wf.DESFECHO_SEM_CONSERTO:
        if not (dados.obs and dados.obs.strip()):
            raise HTTPException(status_code=400, detail="justificativa obrigatória para sem conserto")
        ordem.desfecho_lab = wf.DESFECHO_SEM_CONSERTO
        ordem.desfecho_lab_obs = dados.obs.strip()
        texto = f"Sem conserto: {ordem.desfecho_lab_obs}"
    else:  # liberado — sai do laboratorio sem certificado; justificativa opcional
        ordem.desfecho_lab = wf.DESFECHO_LIBERADO
        ordem.desfecho_lab_obs = (dados.obs or "").strip() or None
        texto = f"Liberado do laboratorio sem certificado: {ordem.desfecho_lab_obs or '(sem motivo)'}"
    registrar_log(db, ordem, usuario, texto)
    db.commit()
    db.refresh(ordem)
    return ordem


@router.post("/{ordem_id}/cancelar", response_model=OrdemOut)
def cancelar(ordem_id: int, dados: CancelarIn, background_tasks: BackgroundTasks,
             db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    raise HTTPException(status_code=409, detail="a OS anda pela caixa; use /caixas/{id}/avancar")
