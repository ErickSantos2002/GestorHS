# Elo Phoebus ↔ Módulo — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans. Passos usam checkbox (`- [ ]`).

**Goal:** Registrar, guardar com histórico e exibir (somente leitura) qual módulo está instalado em qual Phoebus, carregado por um script único a partir da planilha.

**Architecture:** Regras de decisão puras em `core/elo_modulos.py` (testáveis sem I/O); tabela `instalacoes_modulo` com instalação aberta = elo atual; leitura exposta no `GET /equipamentos-cliente/{id}`; script de carga lê o `.xlsx` com biblioteca padrão e usa as regras puras; frontend mostra um painel conforme o papel do equipamento.

**Tech Stack:** Backend Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic. Frontend React 19 · TS · Vite 8 · Vitest.

## Global Constraints

- Idioma PT-BR em nomes, mensagens e colunas.
- **ATENÇÃO — colisão de nome:** `equipamentos_cliente` **já tem** uma coluna `modulo` (inteiro legado, **sem relação** com o módulo do Phoebus). O elo novo NÃO usa nem altera essa coluna. Os campos novos na API são `modulo_instalado` e `instalado_em`.
- Elo é **somente leitura** no sistema: nenhum endpoint de escrita, nenhuma tela de edição.
- Script é **aditivo**: só insere/fecha em `instalacoes_modulo`; nunca altera equipamento, cliente ou OS.
- Casamento por **série exata** (`.strip()`); sem normalização agressiva.
- Regras de carga: (1) lado não encontrado → **pendência**; (2) módulo duplicado → **vence a maior "Próxima Calibração"**, perdedores viram pendência; (3) módulo com série vazia no banco → **ignorado**. Linha sem série de módulo na planilha → **ignorada** (não é pendência).
- Sem nova dependência no backend (ler `.xlsx` com `zipfile` + `xml.etree`).
- Backend: `docker exec gestorhs-backend pytest -q`. Frontend: `npm run lint && npx tsc -b --noEmit && npm run build && npm test`.
- Commits Conventional Commits em PT-BR sem acentos, uma linha, sem trailer.

---

### Task 1: Regras puras em `core/elo_modulos.py`

**Files:**
- Create: `backend/app/core/elo_modulos.py`
- Test: `backend/tests/test_elo_modulos.py`

**Interfaces:**
- `parse_data(valor: str | None) -> datetime | None` — `"2027-03-27 04:00:59"` → datetime; vazio/inválido → `None`.
- `escolher_vencedor(linhas: list[dict]) -> dict` — entre linhas com a MESMA série de módulo, devolve a de maior `prox_calib`; quem não tem data válida perde para quem tem; empate → a primeira.
- `resolver_elos(linhas, series_phoebus, series_modulo) -> tuple[list[dict], list[dict]]`
  - `linhas`: `[{"linha": int, "serie_aparelho": str, "serie_modulo": str, "prox_calib": str, "empresa": str}]`
  - `series_*`: `{serie: equipamento_cliente_id}`
  - devolve `(elos, pendencias)`; `elos`: `[{"linha", "phoebus_id", "modulo_id"}]`; `pendencias`: `[{"linha","serie_aparelho","serie_modulo","empresa","motivo"}]`.
  - Motivos: `"aparelho nao encontrado"`, `"modulo nao encontrado"`, `"duplicado (modulo em outro aparelho mais recente)"`.
  - Linha com `serie_modulo` vazia é **ignorada** (não entra em elos nem em pendências).

- [ ] **Step 1: Escrever o teste que falha**

```python
# backend/tests/test_elo_modulos.py
from app.core.elo_modulos import parse_data, escolher_vencedor, resolver_elos


def _l(n, ap, mod, prox="2027-01-01 00:00:00", emp="ACME"):
    return {"linha": n, "serie_aparelho": ap, "serie_modulo": mod, "prox_calib": prox, "empresa": emp}


def test_parse_data():
    assert parse_data("2027-03-27 04:00:59").year == 2027
    assert parse_data("") is None
    assert parse_data(None) is None
    assert parse_data("nao é data") is None


def test_escolher_vencedor_maior_prox_calibracao():
    """Caso real F000876: a perdedora tem data de 2000 (lixo)."""
    a = _l(42, "WATFR01-00364", "F000876", "2026-09-28 11:01:40")
    b = _l(43, "WATFR01-00488", "F000876", "2000-11-24 07:46:30")
    assert escolher_vencedor([a, b]) is a
    assert escolher_vencedor([b, a]) is a


def test_escolher_vencedor_sem_data_perde():
    com = _l(1, "AP1", "M1", "2027-01-01 00:00:00")
    sem = _l(2, "AP2", "M1", "")
    assert escolher_vencedor([sem, com]) is com


def test_resolver_elos_casa_os_dois_lados():
    linhas = [_l(2, "AP1", "M1")]
    elos, pend = resolver_elos(linhas, {"AP1": 10}, {"M1": 20})
    assert elos == [{"linha": 2, "phoebus_id": 10, "modulo_id": 20}]
    assert pend == []


def test_resolver_elos_pendencia_quando_lado_nao_existe():
    linhas = [_l(2, "AP_X", "M1"), _l(3, "AP1", "M_X")]
    elos, pend = resolver_elos(linhas, {"AP1": 10}, {"M1": 20})
    assert elos == []
    motivos = sorted(p["motivo"] for p in pend)
    assert motivos == ["aparelho nao encontrado", "modulo nao encontrado"]


def test_resolver_elos_linha_sem_modulo_e_ignorada():
    """91 aparelhos da planilha nao tem modulo — nao e erro, nao vira pendencia."""
    elos, pend = resolver_elos([_l(2, "AP1", "")], {"AP1": 10}, {})
    assert elos == [] and pend == []


def test_resolver_elos_duplicado_vence_o_mais_recente():
    linhas = [
        _l(42, "AP1", "M1", "2026-09-28 11:01:40"),
        _l(43, "AP2", "M1", "2000-11-24 07:46:30"),
    ]
    elos, pend = resolver_elos(linhas, {"AP1": 10, "AP2": 11}, {"M1": 20})
    assert elos == [{"linha": 42, "phoebus_id": 10, "modulo_id": 20}]
    assert len(pend) == 1 and pend[0]["linha"] == 43
    assert "duplicado" in pend[0]["motivo"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_elo_modulos.py`
Expected: FAIL — módulo `app.core.elo_modulos` não existe.

- [ ] **Step 3: Implementar**

```python
# backend/app/core/elo_modulos.py
"""Regras puras da carga do elo Phoebus<->Modulo (sem I/O, sem banco).

NAO confundir com `equipamentos_cliente.modulo`, uma coluna inteira legada sem
relacao com o modulo de calibracao do Phoebus.
"""
from datetime import datetime

_FORMATOS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def parse_data(valor):
    if not valor:
        return None
    texto = str(valor).strip()
    for fmt in _FORMATOS:
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None


def escolher_vencedor(linhas):
    """Entre linhas com a MESMA serie de modulo, vence a de maior 'Proxima Calibracao'.

    Um modulo so pode estar em um aparelho; a linha com calibracao mais recente e onde
    ele esta de fato (a outra e o aparelho onde ele estava). Sem data valida perde.
    """
    melhor = linhas[0]
    melhor_data = parse_data(melhor.get("prox_calib"))
    for atual in linhas[1:]:
        data = parse_data(atual.get("prox_calib"))
        if data is not None and (melhor_data is None or data > melhor_data):
            melhor, melhor_data = atual, data
    return melhor


def resolver_elos(linhas, series_phoebus, series_modulo):
    """Aplica as 3 regras de carga. Devolve (elos, pendencias)."""
    elos, pendencias = [], []

    def pendencia(l, motivo):
        pendencias.append({
            "linha": l.get("linha"), "serie_aparelho": l.get("serie_aparelho"),
            "serie_modulo": l.get("serie_modulo"), "empresa": l.get("empresa"),
            "motivo": motivo,
        })

    # agrupa por serie de modulo para resolver duplicados
    por_modulo = {}
    for l in linhas:
        serie_mod = (l.get("serie_modulo") or "").strip()
        if not serie_mod:
            continue                      # aparelho sem modulo na planilha: ignora
        por_modulo.setdefault(serie_mod, []).append(l)

    for serie_mod, grupo in por_modulo.items():
        vencedora = escolher_vencedor(grupo) if len(grupo) > 1 else grupo[0]
        for l in grupo:
            if l is not vencedora:
                pendencia(l, "duplicado (modulo em outro aparelho mais recente)")
        serie_ap = (vencedora.get("serie_aparelho") or "").strip()
        phoebus_id = series_phoebus.get(serie_ap)
        modulo_id = series_modulo.get(serie_mod)
        if phoebus_id is None:
            pendencia(vencedora, "aparelho nao encontrado")
            continue
        if modulo_id is None:
            pendencia(vencedora, "modulo nao encontrado")
            continue
        elos.append({"linha": vencedora.get("linha"), "phoebus_id": phoebus_id, "modulo_id": modulo_id})

    elos.sort(key=lambda e: e["linha"])
    pendencias.sort(key=lambda p: p["linha"])
    return elos, pendencias
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_elo_modulos.py`
Expected: PASS (7 testes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/elo_modulos.py backend/tests/test_elo_modulos.py
git commit -m "feat(frota): regras puras da carga do elo phoebus-modulo"
```

---

### Task 2: Modelo `InstalacaoModulo`, migração 0016 e leitura na API

**Files:**
- Create: `backend/app/models/instalacao_modulo.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0016_instalacao_modulo.py`
- Modify: `backend/app/schemas/frota.py`
- Modify: `backend/app/api/equipamentos_cliente.py`
- Test: `backend/tests/test_elo_instalacao.py`

**Interfaces:**
- Modelo `InstalacaoModulo` (tabela `instalacoes_modulo`): `id`, `modulo` (FK `equipamentos_cliente.id`), `phoebus` (FK `equipamentos_cliente.id`), `entrou_em` (Date), `saiu_em` (Date, nulo = **aberta**), `origem` (String 100).
  - `__table_args__` com **dois índices únicos parciais** (`saiu_em IS NULL`): um em `modulo`, outro em `phoebus`. Declarar com `postgresql_where` **e** `sqlite_where` para que a restrição também valha nos testes (SQLite).
- Schemas novos em `frota.py`: `EloModuloOut {id, serie, entrou_em, origem}` e `EloPhoebusOut {id, serie, cliente_nome, entrou_em, origem}`.
- `EquipamentoClienteOut` ganha `modulo_instalado: EloModuloOut | None` e `instalado_em: EloPhoebusOut | None`.
- `GET /equipamentos-cliente/{id}` preenche os dois consultando a instalação **aberta** (padrão já usado em `ordens.py::_anotar_modelos_faltantes`: setar atributo no objeto ORM antes de retornar).

- [ ] **Step 1: Modelo + registro**

```python
# backend/app/models/instalacao_modulo.py
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Index, text

from app.models.database import Base


class InstalacaoModulo(Base):
    """Qual modulo de calibracao esta instalado em qual Phoebus, ao longo do tempo.

    `saiu_em` nulo = instalacao ABERTA = elo atual. Os dois lados apontam para
    `equipamentos_cliente` (Phoebus e Modulo sao ambos linhas dessa tabela).
    ATENCAO: nada a ver com a coluna legada `equipamentos_cliente.modulo` (inteiro).
    """
    __tablename__ = "instalacoes_modulo"

    id = Column(Integer, primary_key=True, index=True)
    modulo = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=False)
    phoebus = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=False)
    entrou_em = Column(Date, nullable=True)
    saiu_em = Column(Date, nullable=True)
    origem = Column(String(100), nullable=True)

    __table_args__ = (
        Index("uq_instalacao_modulo_aberta", "modulo", unique=True,
              postgresql_where=text("saiu_em IS NULL"), sqlite_where=text("saiu_em IS NULL")),
        Index("uq_instalacao_phoebus_aberta", "phoebus", unique=True,
              postgresql_where=text("saiu_em IS NULL"), sqlite_where=text("saiu_em IS NULL")),
    )
```

Em `backend/app/models/__init__.py`: `from app.models.instalacao_modulo import InstalacaoModulo` e incluir `"InstalacaoModulo"` em `__all__`.

- [ ] **Step 2: Migração 0016**

```python
# backend/alembic/versions/0016_instalacao_modulo.py
"""elo phoebus<->modulo: instalacoes com historico

Revision ID: 0016_instalacao_modulo
Revises: 0015_certificado_geral
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_instalacao_modulo"
down_revision = "0015_certificado_geral"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "instalacoes_modulo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("modulo", sa.Integer(), sa.ForeignKey("equipamentos_cliente.id"), nullable=False),
        sa.Column("phoebus", sa.Integer(), sa.ForeignKey("equipamentos_cliente.id"), nullable=False),
        sa.Column("entrou_em", sa.Date(), nullable=True),
        sa.Column("saiu_em", sa.Date(), nullable=True),
        sa.Column("origem", sa.String(100), nullable=True),
    )
    op.create_index("uq_instalacao_modulo_aberta", "instalacoes_modulo", ["modulo"],
                    unique=True, postgresql_where=sa.text("saiu_em IS NULL"))
    op.create_index("uq_instalacao_phoebus_aberta", "instalacoes_modulo", ["phoebus"],
                    unique=True, postgresql_where=sa.text("saiu_em IS NULL"))


def downgrade():
    op.drop_index("uq_instalacao_phoebus_aberta", table_name="instalacoes_modulo")
    op.drop_index("uq_instalacao_modulo_aberta", table_name="instalacoes_modulo")
    op.drop_table("instalacoes_modulo")
```

- [ ] **Step 3: Escrever o teste (falha)**

```python
# backend/tests/test_elo_instalacao.py
import pytest
from datetime import date


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _equip(db_session, os_base, serie):
    """Cria um equipamento_cliente extra (serve como Phoebus ou Modulo)."""
    from app.models import EquipamentoCliente
    ec = EquipamentoCliente(cliente=os_base["cliente"], equipamento=os_base["equipamento"], serie=serie)
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _instalar(db_session, modulo_id, phoebus_id, saiu_em=None):
    from app.models import InstalacaoModulo
    i = InstalacaoModulo(modulo=modulo_id, phoebus=phoebus_id, entrou_em=date(2026, 7, 18),
                         saiu_em=saiu_em, origem="teste")
    db_session.add(i); db_session.commit()
    return i


def test_phoebus_mostra_modulo_instalado(client, usuario_comum, os_base, db_session):
    pho = _equip(db_session, os_base, "WATFR01-00257")
    mod = _equip(db_session, os_base, "F004230")
    _instalar(db_session, mod.id, pho.id)
    h = _headers(client, "comum@hs.com", "senha123")
    body = client.get(f"/equipamentos-cliente/{pho.id}", headers=h).json()
    assert body["modulo_instalado"]["id"] == mod.id
    assert body["modulo_instalado"]["serie"] == "F004230"
    assert body["instalado_em"] is None


def test_modulo_mostra_onde_esta_instalado(client, usuario_comum, os_base, db_session):
    pho = _equip(db_session, os_base, "WATFR01-00257")
    mod = _equip(db_session, os_base, "F004230")
    _instalar(db_session, mod.id, pho.id)
    h = _headers(client, "comum@hs.com", "senha123")
    body = client.get(f"/equipamentos-cliente/{mod.id}", headers=h).json()
    assert body["instalado_em"]["id"] == pho.id
    assert body["instalado_em"]["serie"] == "WATFR01-00257"
    assert body["modulo_instalado"] is None


def test_instalacao_fechada_nao_aparece(client, usuario_comum, os_base, db_session):
    """Historico nao vaza como elo atual."""
    pho = _equip(db_session, os_base, "AP-1")
    mod = _equip(db_session, os_base, "MOD-1")
    _instalar(db_session, mod.id, pho.id, saiu_em=date(2026, 7, 18))
    h = _headers(client, "comum@hs.com", "senha123")
    assert client.get(f"/equipamentos-cliente/{pho.id}", headers=h).json()["modulo_instalado"] is None
    assert client.get(f"/equipamentos-cliente/{mod.id}", headers=h).json()["instalado_em"] is None


def test_nao_permite_duas_instalacoes_abertas_do_mesmo_modulo(db_session, os_base):
    from sqlalchemy.exc import IntegrityError
    pho1 = _equip(db_session, os_base, "AP-1"); pho2 = _equip(db_session, os_base, "AP-2")
    mod = _equip(db_session, os_base, "MOD-1")
    _instalar(db_session, mod.id, pho1.id)
    with pytest.raises(IntegrityError):
        _instalar(db_session, mod.id, pho2.id)
    db_session.rollback()


def test_nao_permite_dois_modulos_abertos_no_mesmo_phoebus(db_session, os_base):
    from sqlalchemy.exc import IntegrityError
    pho = _equip(db_session, os_base, "AP-1")
    m1 = _equip(db_session, os_base, "MOD-1"); m2 = _equip(db_session, os_base, "MOD-2")
    _instalar(db_session, m1.id, pho.id)
    with pytest.raises(IntegrityError):
        _instalar(db_session, m2.id, pho.id)
    db_session.rollback()
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_elo_instalacao.py`
Expected: FAIL — `InstalacaoModulo` / campos novos não existem.

- [ ] **Step 5: Schemas + endpoint**

Em `backend/app/schemas/frota.py`, antes de `EquipamentoClienteOut`:

```python
class EloModuloOut(BaseModel):
    id: int
    serie: Optional[str] = None
    entrou_em: Optional[date] = None
    origem: Optional[str] = None
    model_config = {"from_attributes": True}


class EloPhoebusOut(BaseModel):
    id: int
    serie: Optional[str] = None
    cliente_nome: Optional[str] = None
    entrou_em: Optional[date] = None
    origem: Optional[str] = None
    model_config = {"from_attributes": True}
```

E em `EquipamentoClienteOut` acrescentar:
```python
    modulo_instalado: Optional[EloModuloOut] = None
    instalado_em: Optional[EloPhoebusOut] = None
```

Em `backend/app/api/equipamentos_cliente.py`, no `obter`:

```python
def _anotar_elo(db: Session, obj) -> None:
    """Preenche o elo conforme o PAPEL do equipamento, sem precisar saber ids de catalogo:
    se ha instalacao aberta com phoebus=obj -> ele e um Phoebus e tem modulo instalado;
    se ha instalacao aberta com modulo=obj -> ele e um modulo e esta dentro de um Phoebus."""
    from app.models import InstalacaoModulo
    obj.modulo_instalado = None
    obj.instalado_em = None

    inst = db.query(InstalacaoModulo).filter(
        InstalacaoModulo.phoebus == obj.id, InstalacaoModulo.saiu_em.is_(None)
    ).first()
    if inst is not None:
        mod = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == inst.modulo).first()
        if mod is not None:
            obj.modulo_instalado = {"id": mod.id, "serie": mod.serie,
                                    "entrou_em": inst.entrou_em, "origem": inst.origem}

    inst = db.query(InstalacaoModulo).filter(
        InstalacaoModulo.modulo == obj.id, InstalacaoModulo.saiu_em.is_(None)
    ).first()
    if inst is not None:
        pho = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == inst.phoebus).first()
        if pho is not None:
            obj.instalado_em = {"id": pho.id, "serie": pho.serie,
                                "cliente_nome": pho.cliente_nome if hasattr(pho, "cliente_nome") else None,
                                "entrou_em": inst.entrou_em, "origem": inst.origem}
```
e chamar `_anotar_elo(db, obj)` no `obter` antes do `return obj`.

(Se `cliente_nome` não for um atributo direto do modelo, obter o nome via a relação de cliente como já é feito na listagem da frota — verificar no arquivo.)

- [ ] **Step 6: Rodar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_elo_instalacao.py`
Expected: PASS (5 testes).

- [ ] **Step 7: Suíte completa + commit**

Run: `docker exec gestorhs-backend pytest -q` (tudo verde)

```bash
git add backend/app/models/instalacao_modulo.py backend/app/models/__init__.py backend/alembic/versions/0016_instalacao_modulo.py backend/app/schemas/frota.py backend/app/api/equipamentos_cliente.py backend/tests/test_elo_instalacao.py
git commit -m "feat(frota): tabela de instalacoes e elo phoebus-modulo na API"
```

---

### Task 3: Script de carga `importar_elo_modulos`

**Files:**
- Create: `backend/app/scripts/importar_elo_modulos.py`
- Test: `backend/tests/test_importar_elo_modulos.py`

**Interfaces:**
- `ler_planilha(caminho) -> list[dict]` — lê o `.xlsx` com `zipfile` + `xml.etree` (sem dependência nova) e devolve `[{"linha","serie_aparelho","serie_modulo","prox_calib","empresa"}]`. Localiza as colunas **pelo cabeçalho** ("Número de Série", "Número de Série do Módulo", "Próxima Calibração", "Nome da Empresa") — não por posição fixa.
- `aplicar(db, elos, origem, dry_run) -> dict` — para cada elo: se já existe instalação aberta idêntica (mesmo módulo **e** mesmo phoebus) não faz nada (idempotente); senão **fecha** (`saiu_em = hoje`) as instalações abertas daquele módulo e daquele phoebus e **abre** a nova. Devolve contagens `{criados, fechados, inalterados}`.
- `main()` — CLI: `python -m app.scripts.importar_elo_modulos <arquivo.xlsx> [--origem TEXTO] [--phoebus-id 36] [--modulo-id 47] [--dry-run] [--pendencias CAMINHO.csv]`.
- Consumes: `resolver_elos` (Task 1), `InstalacaoModulo` (Task 2), `EquipamentoCliente`.

- [ ] **Step 1: Escrever o teste (falha)**

```python
# backend/tests/test_importar_elo_modulos.py
from datetime import date


def _equip(db_session, os_base, serie, equipamento=None):
    from app.models import EquipamentoCliente
    ec = EquipamentoCliente(cliente=os_base["cliente"],
                            equipamento=equipamento or os_base["equipamento"], serie=serie)
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def test_aplicar_cria_instalacao(db_session, os_base):
    from app.scripts.importar_elo_modulos import aplicar
    from app.models import InstalacaoModulo
    pho = _equip(db_session, os_base, "AP-1"); mod = _equip(db_session, os_base, "MOD-1")
    r = aplicar(db_session, [{"linha": 2, "phoebus_id": pho.id, "modulo_id": mod.id}],
                origem="teste", dry_run=False)
    assert r["criados"] == 1
    inst = db_session.query(InstalacaoModulo).one()
    assert inst.modulo == mod.id and inst.phoebus == pho.id and inst.saiu_em is None


def test_aplicar_e_idempotente(db_session, os_base):
    """Rodar duas vezes a mesma planilha nao duplica nem fecha/reabre à toa."""
    from app.scripts.importar_elo_modulos import aplicar
    from app.models import InstalacaoModulo
    pho = _equip(db_session, os_base, "AP-1"); mod = _equip(db_session, os_base, "MOD-1")
    elos = [{"linha": 2, "phoebus_id": pho.id, "modulo_id": mod.id}]
    aplicar(db_session, elos, origem="t1", dry_run=False)
    r = aplicar(db_session, elos, origem="t2", dry_run=False)
    assert r["criados"] == 0 and r["inalterados"] == 1
    assert db_session.query(InstalacaoModulo).count() == 1


def test_aplicar_fecha_a_anterior_quando_o_modulo_muda_de_aparelho(db_session, os_base):
    from app.scripts.importar_elo_modulos import aplicar
    from app.models import InstalacaoModulo
    pho1 = _equip(db_session, os_base, "AP-1"); pho2 = _equip(db_session, os_base, "AP-2")
    mod = _equip(db_session, os_base, "MOD-1")
    aplicar(db_session, [{"linha": 2, "phoebus_id": pho1.id, "modulo_id": mod.id}], origem="t1", dry_run=False)
    r = aplicar(db_session, [{"linha": 3, "phoebus_id": pho2.id, "modulo_id": mod.id}], origem="t2", dry_run=False)
    assert r["criados"] == 1 and r["fechados"] == 1
    abertas = db_session.query(InstalacaoModulo).filter(InstalacaoModulo.saiu_em.is_(None)).all()
    assert len(abertas) == 1 and abertas[0].phoebus == pho2.id
    fechadas = db_session.query(InstalacaoModulo).filter(InstalacaoModulo.saiu_em.isnot(None)).all()
    assert len(fechadas) == 1 and fechadas[0].phoebus == pho1.id


def test_aplicar_dry_run_nao_grava(db_session, os_base):
    from app.scripts.importar_elo_modulos import aplicar
    from app.models import InstalacaoModulo
    pho = _equip(db_session, os_base, "AP-1"); mod = _equip(db_session, os_base, "MOD-1")
    r = aplicar(db_session, [{"linha": 2, "phoebus_id": pho.id, "modulo_id": mod.id}],
                origem="teste", dry_run=True)
    assert r["criados"] == 1                       # conta o que faria
    assert db_session.query(InstalacaoModulo).count() == 0   # mas nao gravou


def test_ler_planilha_acha_colunas_pelo_cabecalho(tmp_path):
    """Le um .xlsx minimo gerado na hora (sem dependencia externa)."""
    from app.scripts.importar_elo_modulos import ler_planilha
    caminho = tmp_path / "mini.xlsx"
    _escrever_xlsx_minimo(caminho)
    linhas = ler_planilha(str(caminho))
    assert len(linhas) == 1
    assert linhas[0]["serie_aparelho"] == "WATFR01-00257"
    assert linhas[0]["serie_modulo"] == "F004230"
    assert linhas[0]["empresa"] == "ACME"


def _escrever_xlsx_minimo(caminho):
    """xlsx valido minimo com 1 cabecalho + 1 linha, usando inlineStr (sem sharedStrings)."""
    import zipfile
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
    wb = ('<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
          '<sheets><sheet name="devices" sheetId="1" r:id="rId1" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets></workbook>')

    def c(ref, txt):
        return f'<c r="{ref}" t="inlineStr"><is><t>{txt}</t></is></c>'

    sheet = ('<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
             '<row r="1">' + c("A1", "Número de Série") + c("B1", "Número de Série do Módulo")
             + c("C1", "Próxima Calibração") + c("D1", "Nome da Empresa") + '</row>'
             '<row r="2">' + c("A2", "WATFR01-00257") + c("B2", "F004230")
             + c("C2", "2027-04-25 04:01:05") + c("D2", "ACME") + '</row>'
             '</sheetData></worksheet>')
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_importar_elo_modulos.py`
Expected: FAIL — módulo do script não existe.

- [ ] **Step 3: Implementar o script**

Pontos obrigatórios:
- `ler_planilha`: abre o `.xlsx` com `zipfile`; lê `xl/sharedStrings.xml` (se houver) e a **primeira** `xl/worksheets/sheet*.xml`; suporta `t="s"` (shared) e `t="inlineStr"`; mapeia as colunas **pelo texto do cabeçalho** (aceitando variação de acento/caixa) e devolve os dicts com `linha` = número da linha na planilha.
- `main`: monta `series_phoebus`/`series_modulo` consultando `EquipamentoCliente.serie` filtrando por `--phoebus-id` (default 36) e `--modulo-id` (default 47), **ignorando série vazia** (regra 3); chama `resolver_elos`; chama `aplicar`; escreve o CSV de pendências (default `docs/pendencias-elo-<data>.csv`) com colunas `linha,serie_aparelho,serie_modulo,empresa,motivo`; imprime resumo (lidas, ignoradas sem módulo, elos criados/fechados/inalterados, pendências por motivo).
- `aplicar`: idempotente (mesmo par já aberto → `inalterados`); ao mudar, fecha as abertas do módulo **e** do phoebus com `saiu_em = date.today()` antes de abrir a nova (evita violar os índices únicos); em `dry_run`, calcula e **não** grava (nem commit).

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_importar_elo_modulos.py`
Expected: PASS (5 testes).

- [ ] **Step 5: Suíte completa + commit**

Run: `docker exec gestorhs-backend pytest -q`

```bash
git add backend/app/scripts/importar_elo_modulos.py backend/tests/test_importar_elo_modulos.py
git commit -m "feat(frota): script de carga do elo phoebus-modulo a partir da planilha"
```

---

### Task 4: Frontend — painel do elo na ficha do equipamento

**Files:**
- Modify: `frontend/src/app/frota/api.ts`
- Modify: `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`
- Test: `frontend/src/app/frota/elo.test.tsx`

**Interfaces:**
- Em `api.ts`, adicionar aos tipos:
```ts
export interface EloModulo { id: number; serie: string | null; entrou_em: string | null; origem: string | null }
export interface EloPhoebus { id: number; serie: string | null; cliente_nome: string | null; entrou_em: string | null; origem: string | null }
```
e em `EquipamentoCliente`: `modulo_instalado: EloModulo | null` e `instalado_em: EloPhoebus | null`.
- Na tela: renderizar **somente leitura**, no `DetailAside`, a seção que tiver dado.

- [ ] **Step 1: Escrever o teste (falha)**

Teste de componente com `MemoryRouter`, mockando `equipamentosClienteApi.obter` (e os demais `historico/ordens/certificados/transferencias` resolvendo vazio), no padrão de `EquipamentoClienteDetailPage.embutido.test.tsx`:
1. Com `modulo_instalado: { id: 9, serie: 'F004230', … }` → aparece "Módulo instalado" e a série `F004230`; **não** aparece "Instalado em".
2. Com `instalado_em: { id: 5, serie: 'WATFR01-00257', cliente_nome: 'ACME', … }` → aparece "Instalado em", a série e o cliente.
3. Com os dois `null` **e** o equipamento sendo um módulo → aparece "No estoque".
   (Como a tela não sabe o catálogo, o critério é: mostrar "No estoque" quando `instalado_em` é `null` e `modulo_instalado` é `null` **e** a descrição do equipamento contém "Módulo" — decidir no código um critério simples e testável; se preferir, mostrar apenas quando `instalado_em === null` num equipamento cuja descrição casa com módulo.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/app/frota/elo.test.tsx`
Expected: FAIL — seções não existem.

- [ ] **Step 3: Implementar o painel**

Em `EquipamentoClienteDetailPage.tsx`, dentro do `DetailAside` (perto de "Última calibração"), acrescentar:

```tsx
{obj?.modulo_instalado && (
  <Secao titulo="Módulo instalado">
    <p className="text-sm text-slate-300">
      <Link to={`/app/equipamentos/${obj.modulo_instalado.id}`} className="text-primary hover:underline">
        {obj.modulo_instalado.serie || `#${obj.modulo_instalado.id}`}
      </Link>
    </p>
    {obj.modulo_instalado.origem && (
      <p className="text-xs text-slate-500">Registrado em {formatData(obj.modulo_instalado.entrou_em)} · {obj.modulo_instalado.origem}</p>
    )}
  </Secao>
)}

{obj?.instalado_em && (
  <Secao titulo="Instalado em">
    <p className="text-sm text-slate-300">
      <Link to={`/app/equipamentos/${obj.instalado_em.id}`} className="text-primary hover:underline">
        {obj.instalado_em.serie || `#${obj.instalado_em.id}`}
      </Link>
      {obj.instalado_em.cliente_nome && <span className="text-slate-500"> · {obj.instalado_em.cliente_nome}</span>}
    </p>
    {obj.instalado_em.origem && (
      <p className="text-xs text-slate-500">Registrado em {formatData(obj.instalado_em.entrou_em)} · {obj.instalado_em.origem}</p>
    )}
  </Secao>
)}
```
Mais a seção "No estoque" conforme o critério definido no Step 1. **Sem botões** — é informativo.

- [ ] **Step 4: Rodar e ver passar + verificar**

Run: `cd frontend && npx vitest run src/app/frota/elo.test.tsx && npm run lint && npx tsc -b --noEmit`
Expected: PASS, lint/tipos limpos.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/frota/api.ts frontend/src/app/frota/EquipamentoClienteDetailPage.tsx frontend/src/app/frota/elo.test.tsx
git commit -m "feat(frota): mostra o elo phoebus-modulo na ficha do equipamento"
```

---

### Task 5: Changelog + verificação completa

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Bump v1.19.0**

Primeira entrada de `CHANGELOG`:
```ts
{
  versao: '1.19.0',
  data: '18/07/2026',
  itens: [
    { tipo: 'novidade', texto: 'A ficha de um aparelho agora mostra o elo entre o Phoebus e o módulo de calibração: abrindo um Phoebus você vê qual módulo está instalado nele, e abrindo um módulo vê em qual aparelho (e cliente) ele está — ou que está no estoque. A informação vem de uma carga feita a partir da lista de dispositivos e mostra de quando é aquele retrato.' },
  ],
},
```

- [ ] **Step 2: Verificação completa**

Run backend: `docker exec gestorhs-backend pytest -q`
Run frontend: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build && npm test`
Expected: tudo verde.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.19.0 — elo phoebus-modulo na ficha do equipamento"
```

---

## Self-Review (feita)

- **Cobertura da spec:** regras de carga puras (T1), tabela+histórico+índices únicos (T2), leitura por papel na API (T2), script com xlsx sem dependência + pendências + dry-run + idempotência (T3), painéis somente leitura (T4), changelog (T5). ✔
- **Sem placeholders:** todo passo tem código concreto e comando com resultado esperado; os pontos que dependem do arquivo real (nome de `cliente_nome`, critério de "No estoque") estão marcados para verificar no código, com o caminho indicado. ✔
- **Consistência de tipos:** `resolver_elos` (T1) devolve exatamente o que `aplicar` (T3) consome; `EloModuloOut`/`EloPhoebusOut` (T2) batem com `EloModulo`/`EloPhoebus` (T4); migração 0016 encadeia em 0015. ✔
- **Armadilha sinalizada:** a coluna legada `equipamentos_cliente.modulo` **não** é o elo — está nas Global Constraints e no docstring do modelo. ✔
- **Não-destrutivo:** o script só mexe em `instalacoes_modulo`. ✔
