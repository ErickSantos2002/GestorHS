# Relatório de Manutenção — plano de implementação

> **Para quem executa:** SUB-SKILL OBRIGATÓRIA: use `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para implementar tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** permitir que o Laboratório registre a manutenção feita na bancada e gere o Relatório de Manutenção (FORM-LAB-010 REV 02) em PDF, pelo mesmo motor que já gera o certificado de calibração.

**Arquitetura:** três tabelas novas (`manutencoes`, `manutencao_servicos`, `manutencao_itens`), um núcleo puro que compõe os textos do documento, quatro tokens novos no motor de certificado e um modelo HTML único (sem aparelho) para o tipo `M`. A tela da OS passa a ter duas seções de certificado em vez de uma, e o catálogo de serviços ganha aba própria em Certificados.

**Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · pytest — React 19 · TypeScript · Vite · Tailwind v4 · Vitest.

**Spec:** [docs/superpowers/specs/2026-08-21-relatorio-manutencao-design.md](../specs/2026-08-21-relatorio-manutencao-design.md)

## Restrições globais

- Idioma do domínio é **PT-BR**: modelos, rotas, variáveis e mensagens em português.
- Mensagens de commit em **português sem acentos** (ASCII), uma linha, sem corpo e sem trailer de co-autor. Tipos: `feat`, `fix`, `docs`, `refactor`. Escopo desta entrega: `manut`.
- Lógica de negócio pura vai em `backend/app/core/` (sem I/O, testável isolada); I/O em `app/api/`.
- Toda regra de função vive nos **dois lados**: `backend/app/api/deps.py` e `frontend/src/auth/roles.ts`.
- Router novo precisa de `include_router` em `backend/app/main.py`.
- Testes de backend usam SQLite in-memory (`tests/conftest.py`). Fixtures que este plano usa: `client`, `client_admin`, `client_lab`, `usuario_lab`, `usuario_admin`, `usuario_financeiro`, `fases_seed`, `os_base`, `db_session`, `upload_tmp`.
- **Nesta máquina 4 testes de backend já falham** (`PermissionError` em `/data`, em `test_certificados_gerais.py` e `test_publico_certificado_geral.py`). Esse é o baseline verde — não são regressão.
- Verificação de frontend antes de commitar: `npm run lint && npx tsc -b --noEmit && npm test`.
- **Não fazer commit/push além dos commits previstos aqui.** Deploy e `alembic upgrade` são do Erick.
- `DATABASE_URL` em `backend/.env` aponta para **produção**. Nenhuma tarefa deste plano roda `alembic upgrade`.

---

## Estrutura de arquivos

**Backend — criar:**
| Arquivo | Responsabilidade |
|---|---|
| `alembic/versions/0027_manutencao.py` | as três tabelas |
| `app/models/manutencao.py` | `Manutencao`, `ManutencaoServico`, `ManutencaoItem` |
| `app/core/manutencao.py` | puro: compõe "Tipo do Problema" e o resumo |
| `app/schemas/manutencao.py` | schemas Pydantic |
| `app/api/manutencoes.py` | CRUD da manutenção da OS + campos |
| `app/api/manutencao_servicos.py` | CRUD do catálogo |
| `tests/test_manutencao_core.py` | núcleo puro |
| `tests/test_manutencao_api.py` | manutenção da OS |
| `tests/test_manutencao_servicos.py` | catálogo |
| `tests/test_certificado_manutencao.py` | `tipos_para`, fallback do modelo, geração |
| `tests/test_certificado_modelo_generico.py` | rotas do modelo sem aparelho |

**Backend — modificar:**
| Arquivo | O quê |
|---|---|
| `app/models/__init__.py` | exportar os três modelos |
| `app/models/certificado_modelo.py` | `equipamento` passa a `nullable=True` |
| `app/core/certificado_gerar.py` | 4 tokens novos, `tipos_para`, fallback do modelo |
| `app/api/certificados_os.py` | recusar geração sem manutenção registrada |
| `app/api/certificados_modelo.py` | rotas do modelo genérico (sem aparelho) |
| `app/main.py` | dois `include_router` |

**Frontend — criar:**
| Arquivo | Responsabilidade |
|---|---|
| `src/app/ordens/ManutencaoModal.tsx` | modal de registro |
| `src/app/certificados/ServicosManutencaoTab.tsx` | aba do catálogo |
| `src/app/ordens/manutencao.ts` | tipos + chamadas da API |
| `src/app/ordens/manutencao.test.ts` | composição do resumo no cliente |
| `src/app/ordens/ManutencaoModal.test.tsx` | modal |
| `src/app/ordens/OrdemDetailPage.secoes.test.tsx` | as duas seções |

**Frontend — modificar:**
| Arquivo | O quê |
|---|---|
| `src/auth/roles.ts` + `roles.test.ts` | `podeRegistrarManutencao` |
| `src/app/ordens/OrdemDetailPage.tsx` | duas seções no lugar de uma |
| `src/app/ordens/GerarCertificadoModal.tsx` | esconder calibração em OS de manutenção |
| `src/app/certificados/ModelosTab.tsx` | entrada do modelo genérico |
| `src/app/certificados/CertificadosPage.tsx` | aba nova |
| `src/app/changelog/data.ts` | v1.43.0 |

---

## Task 1: Núcleo puro da composição dos textos

**Arquivos:**
- Criar: `backend/app/core/manutencao.py`
- Testar: `backend/tests/test_manutencao_core.py`

**Interfaces:**
- Consome: nada.
- Produz: `compor_problema(descricoes: list[str]) -> str` e `compor_resumo(frases: list[str]) -> str`.

- [ ] **Passo 1: escrever o teste que falha**

`backend/tests/test_manutencao_core.py`:

```python
"""Composicao dos textos do Relatorio de Manutencao (FORM-LAB-010).

Os exemplos vem dos relatorios reais em docs/certificado-manutencao/.
"""
import pytest

from app.core.manutencao import compor_problema, compor_resumo


def test_um_servico_termina_em_ponto():
    assert compor_problema(["Troca da placa mãe"]) == "Troca da placa mãe."


def test_dois_servicos_ligados_por_e():
    assert compor_problema(["Troca de Pilha interna", "Troca do Bluetooth Mercury"]) == \
        "Troca de Pilha interna e Troca do Bluetooth Mercury."


def test_tres_servicos_usam_virgula_e_e_no_ultimo():
    assert compor_problema(["A", "B", "C"]) == "A, B e C."


def test_sem_servico_devolve_vazio():
    assert compor_problema([]) == ""


def test_ponto_final_ja_existente_nao_duplica():
    assert compor_problema(["Troca da placa mãe."]) == "Troca da placa mãe."


def test_espacos_em_branco_sao_ignorados():
    assert compor_problema(["  Troca da placa mãe  ", "", "   "]) == "Troca da placa mãe."


def test_resumo_junta_as_frases_na_ordem():
    assert compor_resumo(["Primeira frase.", "Segunda frase."]) == "Primeira frase. Segunda frase."


def test_resumo_garante_ponto_entre_as_frases():
    assert compor_resumo(["Primeira frase", "Segunda frase"]) == "Primeira frase. Segunda frase."


def test_resumo_sem_frases_devolve_vazio():
    assert compor_resumo([]) == ""


@pytest.mark.parametrize("frases", [[""], ["   "], ["", "  "]])
def test_resumo_ignora_frases_vazias(frases):
    assert compor_resumo(frases) == ""
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_manutencao_core.py -q -p no:warnings`
Esperado: erro de coleta — `ModuleNotFoundError: No module named 'app.core.manutencao'`.

- [ ] **Passo 3: implementar**

`backend/app/core/manutencao.py`:

```python
"""Composicao dos textos do Relatorio de Manutencao.

Puro, sem I/O. Duas saidas alimentam o documento:
- "Tipo do Problema": os servicos escolhidos, em lista portuguesa;
- "Resumo do Servico": as frases padrao desses servicos, emendadas.

O resultado e' GRAVADO na manutencao, nunca recomposto na hora de imprimir —
senao editar o catalogo amanha reescreveria relatorio ja emitido, e relatorio
emitido e' documento.
"""


def _limpar(itens: list[str]) -> list[str]:
    return [i.strip() for i in itens if i and i.strip()]


def _sem_ponto_final(texto: str) -> str:
    return texto[:-1] if texto.endswith(".") else texto


def compor_problema(descricoes: list[str]) -> str:
    """Lista portuguesa dos servicos, terminada em ponto.

    Um -> "A."   Dois -> "A e B."   Tres ou mais -> "A, B e C."
    """
    itens = [_sem_ponto_final(d) for d in _limpar(descricoes)]
    if not itens:
        return ""
    if len(itens) == 1:
        corpo = itens[0]
    else:
        corpo = f"{', '.join(itens[:-1])} e {itens[-1]}"
    return f"{corpo}."


def compor_resumo(frases: list[str]) -> str:
    """Emenda as frases padrao, garantindo ponto final entre elas."""
    itens = _limpar(frases)
    if not itens:
        return ""
    return " ".join(f"{_sem_ponto_final(f)}." for f in itens)
```

- [ ] **Passo 4: rodar e confirmar que passa**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_manutencao_core.py -q -p no:warnings`
Esperado: `11 passed`.

- [ ] **Passo 5: commitar**

```bash
git add backend/app/core/manutencao.py backend/tests/test_manutencao_core.py
git commit -m "feat(manut): composicao dos textos do relatorio de manutencao"
```

---

## Task 2: Migração e modelos

**Arquivos:**
- Criar: `backend/alembic/versions/0027_manutencao.py`, `backend/app/models/manutencao.py`
- Modificar: `backend/app/models/__init__.py`
- Testar: `backend/tests/test_manutencao_modelos.py`

**Interfaces:**
- Consome: nada.
- Produz: `Manutencao` (campos `id, os, numero, data_manutencao, resumo, criado_por, criado_em, atualizado_em`, relação `itens`), `ManutencaoServico` (`id, descricao, resumo_padrao, ativo`), `ManutencaoItem` (`id, manutencao, servico, ordem`, relação `servico_rel`).

- [ ] **Passo 1: escrever o teste que falha**

`backend/tests/test_manutencao_modelos.py`:

```python
"""As tabelas de manutencao. O conftest cria o schema pelo metadata, entao um
modelo que nao esteja em app.models nao existiria aqui."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Manutencao, ManutencaoServico, ManutencaoItem


def _os(db, os_base, fase=5):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico="M", situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o


def test_grava_manutencao_com_itens(db_session, os_base, fases_seed):
    from datetime import date
    o = _os(db_session, os_base)
    servico = ManutencaoServico(descricao="Troca da placa mãe", resumo_padrao="Placa substituída.")
    db_session.add(servico); db_session.flush()
    m = Manutencao(os=o.id, numero="HF00715", data_manutencao=date(2026, 8, 21),
                   resumo="Placa substituída.", criado_por="Tecnico")
    db_session.add(m); db_session.flush()
    db_session.add(ManutencaoItem(manutencao=m.id, servico=servico.id, ordem=0))
    db_session.commit(); db_session.refresh(m)

    assert m.numero == "HF00715"
    assert len(m.itens) == 1
    assert m.itens[0].servico_rel.descricao == "Troca da placa mãe"


def test_uma_manutencao_por_os(db_session, os_base, fases_seed):
    """Espelha a unicidade (os, tipo) de os_certificados: um relatorio por OS."""
    from datetime import date
    o = _os(db_session, os_base)
    db_session.add(Manutencao(os=o.id, numero="A", data_manutencao=date(2026, 8, 21)))
    db_session.commit()
    db_session.add(Manutencao(os=o.id, numero="B", data_manutencao=date(2026, 8, 21)))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_servico_com_descricao_repetida_e_recusado(db_session):
    db_session.add(ManutencaoServico(descricao="Troca da bateria", resumo_padrao="x"))
    db_session.commit()
    db_session.add(ManutencaoServico(descricao="Troca da bateria", resumo_padrao="y"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_servico_nasce_ativo(db_session):
    s = ManutencaoServico(descricao="Troca do bocal", resumo_padrao="x")
    db_session.add(s); db_session.commit(); db_session.refresh(s)
    assert s.ativo is True


def test_mesmo_servico_duas_vezes_na_mesma_manutencao_e_recusado(db_session, os_base, fases_seed):
    from datetime import date
    o = _os(db_session, os_base)
    s = ManutencaoServico(descricao="Troca do botão", resumo_padrao="x")
    db_session.add(s); db_session.flush()
    m = Manutencao(os=o.id, numero="A", data_manutencao=date(2026, 8, 21))
    db_session.add(m); db_session.flush()
    db_session.add(ManutencaoItem(manutencao=m.id, servico=s.id, ordem=0))
    db_session.commit()
    db_session.add(ManutencaoItem(manutencao=m.id, servico=s.id, ordem=1))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_manutencao_modelos.py -q -p no:warnings`
Esperado: erro de coleta — `ImportError: cannot import name 'Manutencao' from 'app.models'`.

- [ ] **Passo 3: criar os modelos**

`backend/app/models/manutencao.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import (Column, Integer, String, Text, Date, DateTime, Boolean,
                        ForeignKey, UniqueConstraint)
from sqlalchemy.orm import relationship

from app.models.database import Base


class ManutencaoServico(Base):
    """Catalogo FECHADO de servicos. O tecnico escolhe daqui, nao digita.

    Aposentar um servico e' desativar, nunca apagar: apagar faria relatorio
    antigo perder o registro do que foi feito.
    """
    __tablename__ = "manutencao_servicos"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(200), nullable=False, unique=True)   # vai para "Tipo do Problema"
    resumo_padrao = Column(Text, nullable=False, default="")       # frase que compoe o "Resumo do Servico"
    ativo = Column(Boolean, nullable=False, default=True)


class Manutencao(Base):
    """Uma por OS — espelha a unicidade (os, tipo) de os_certificados.

    Dentro dela cabem varios servicos: um mesmo relatorio cobre, por exemplo,
    troca de pilha interna E troca do Bluetooth.
    """
    __tablename__ = "manutencoes"
    __table_args__ = (UniqueConstraint("os", name="uq_manutencoes_os"),)

    id = Column(Integer, primary_key=True, index=True)
    os = Column(Integer, ForeignKey("ordens.id", ondelete="CASCADE"), nullable=False, index=True)
    numero = Column(String(50), nullable=True)          # digitado; serie propria do laboratorio
    data_manutencao = Column(Date, nullable=True)
    resumo = Column(Text, nullable=True)                # texto FINAL, nao a receita
    criado_por = Column(String(255), nullable=True)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    itens = relationship("ManutencaoItem", cascade="all, delete-orphan",
                         order_by="ManutencaoItem.ordem", lazy="selectin")


class ManutencaoItem(Base):
    __tablename__ = "manutencao_itens"
    __table_args__ = (UniqueConstraint("manutencao", "servico", name="uq_manutencao_itens_servico"),)

    id = Column(Integer, primary_key=True, index=True)
    manutencao = Column(Integer, ForeignKey("manutencoes.id", ondelete="CASCADE"), nullable=False, index=True)
    servico = Column(Integer, ForeignKey("manutencao_servicos.id"), nullable=False)
    ordem = Column(Integer, nullable=False, default=0)   # posicao escolhida; define a ordem no texto

    servico_rel = relationship("ManutencaoServico", lazy="joined")
```

- [ ] **Passo 4: exportar em `app/models/__init__.py`**

Acrescentar ao arquivo, seguindo o padrão das linhas vizinhas:

```python
from app.models.manutencao import Manutencao, ManutencaoServico, ManutencaoItem  # noqa: F401
```

Se o arquivo tiver `__all__`, acrescentar `"Manutencao"`, `"ManutencaoServico"` e `"ManutencaoItem"` à lista.

- [ ] **Passo 5: rodar e confirmar que passa**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_manutencao_modelos.py -q -p no:warnings`
Esperado: `5 passed`.

- [ ] **Passo 6: escrever a migração**

`backend/alembic/versions/0027_manutencao.py`:

```python
"""manutencao: registro do servico feito na bancada e o catalogo de servicos"""
import sqlalchemy as sa
from alembic import op

revision = "0027_manutencao"
down_revision = "0026_nota_fiscal_xml"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manutencao_servicos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("descricao", sa.String(200), nullable=False, unique=True),
        sa.Column("resumo_padrao", sa.Text(), nullable=False, server_default=""),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_table(
        "manutencoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("os", sa.Integer(), sa.ForeignKey("ordens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero", sa.String(50), nullable=True),
        sa.Column("data_manutencao", sa.Date(), nullable=True),
        sa.Column("resumo", sa.Text(), nullable=True),
        sa.Column("criado_por", sa.String(255), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_manutencoes_os", "manutencoes", ["os"])
    op.create_unique_constraint("uq_manutencoes_os", "manutencoes", ["os"])
    op.create_table(
        "manutencao_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manutencao", sa.Integer(), sa.ForeignKey("manutencoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("servico", sa.Integer(), sa.ForeignKey("manutencao_servicos.id"), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_manutencao_itens_manutencao", "manutencao_itens", ["manutencao"])
    op.create_unique_constraint("uq_manutencao_itens_servico", "manutencao_itens", ["manutencao", "servico"])


def downgrade() -> None:
    op.drop_table("manutencao_itens")
    op.drop_table("manutencoes")
    op.drop_table("manutencao_servicos")
```

- [ ] **Passo 7: conferir a migração sem aplicar**

`DATABASE_URL` aponta para **produção** — não rodar `upgrade`. Conferir só que a cadeia está íntegra:

Rodar: `cd backend && source .venv/bin/activate && alembic heads`
Esperado: `0027_manutencao (head)` — uma única head.

- [ ] **Passo 8: commitar**

```bash
git add backend/alembic/versions/0027_manutencao.py backend/app/models/manutencao.py backend/app/models/__init__.py backend/tests/test_manutencao_modelos.py
git commit -m "feat(manut): tabelas de manutencao, itens e catalogo de servicos"
```

---

## Task 3: API do catálogo de serviços

**Arquivos:**
- Criar: `backend/app/api/manutencao_servicos.py`, `backend/tests/test_manutencao_servicos.py`
- Modificar: `backend/app/schemas/manutencao.py` (criar), `backend/app/main.py`

**Interfaces:**
- Consome: `ManutencaoServico` (Task 2).
- Produz: rotas `GET/POST /manutencao-servicos`, `PUT/DELETE /manutencao-servicos/{id}`; schemas `ServicoOut`, `ServicoIn`.

- [ ] **Passo 1: escrever o teste que falha**

`backend/tests/test_manutencao_servicos.py`:

```python
"""Catalogo de servicos de manutencao.

Laboratorio e Administrador cadastram e editam; excluir e' so do Administrador
— mesma decisao dos cilindros de gas (03/08/2026): quem opera nao deve apagar
sem querer.
"""


def test_laboratorio_cadastra_servico(client_lab):
    r = client_lab.post("/manutencao-servicos",
                        json={"descricao": "Troca da placa mãe", "resumo_padrao": "Placa substituída."})
    assert r.status_code == 201
    assert r.json()["descricao"] == "Troca da placa mãe"
    assert r.json()["ativo"] is True


def test_listar_devolve_os_cadastrados(client_lab):
    client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."})
    client_lab.post("/manutencao-servicos", json={"descricao": "B", "resumo_padrao": "b."})
    r = client_lab.get("/manutencao-servicos")
    assert r.status_code == 200
    assert [x["descricao"] for x in r.json()] == ["A", "B"]


def test_descricao_repetida_vira_409(client_lab):
    client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."})
    r = client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "outro."})
    assert r.status_code == 409


def test_laboratorio_edita_servico(client_lab):
    sid = client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."}).json()["id"]
    r = client_lab.put(f"/manutencao-servicos/{sid}", json={"resumo_padrao": "novo texto.", "ativo": False})
    assert r.status_code == 200
    assert r.json()["resumo_padrao"] == "novo texto."
    assert r.json()["ativo"] is False


def test_laboratorio_nao_exclui(client_lab):
    sid = client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."}).json()["id"]
    assert client_lab.delete(f"/manutencao-servicos/{sid}").status_code == 403


def test_admin_exclui(client_admin):
    sid = client_admin.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."}).json()["id"]
    assert client_admin.delete(f"/manutencao-servicos/{sid}").status_code == 204


def test_outra_funcao_nao_cadastra(client, usuario_financeiro, fases_seed):
    tok = client.post("/auth/login", json={"email": "fin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."}, headers=h)
    assert r.status_code == 403


def test_exige_autenticacao(client):
    assert client.get("/manutencao-servicos").status_code == 401
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_manutencao_servicos.py -q -p no:warnings`
Esperado: falhas com `404` (rota não existe) em vez dos status esperados.

- [ ] **Passo 3: criar os schemas**

`backend/app/schemas/manutencao.py`:

```python
from datetime import date as date_type
from typing import Optional

from pydantic import BaseModel


class ServicoIn(BaseModel):
    descricao: str
    resumo_padrao: str = ""
    ativo: bool = True


class ServicoUpdate(BaseModel):
    descricao: Optional[str] = None
    resumo_padrao: Optional[str] = None
    ativo: Optional[bool] = None


class ServicoOut(BaseModel):
    id: int
    descricao: str
    resumo_padrao: str
    ativo: bool
    model_config = {"from_attributes": True}


class ManutencaoItemOut(BaseModel):
    servico: int
    descricao: str
    resumo_padrao: str


class ManutencaoIn(BaseModel):
    numero: Optional[str] = None
    data_manutencao: Optional[date_type] = None
    resumo: Optional[str] = None
    servicos: list[int] = []          # ids do catalogo, NA ORDEM escolhida


class ManutencaoOut(BaseModel):
    id: int
    os: int
    numero: Optional[str] = None
    data_manutencao: Optional[date_type] = None
    resumo: Optional[str] = None
    servicos: list[ManutencaoItemOut] = []
    model_config = {"from_attributes": True}
```

- [ ] **Passo 4: criar o router**

`backend/app/api/manutencao_servicos.py`:

```python
"""Catalogo de servicos de manutencao.

Lista FECHADA: o relatorio so aceita servico daqui. Padroniza a escrita do
documento e deixa o dado pronto para responder "qual defeito mais aparece".

Escrita com Laboratorio e Administrador — se so o Administrador cadastrasse, o
tecnico ficaria travado ao encontrar um defeito novo. Excluir segue so com o
Administrador, como nos cilindros de gas.
"""
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, require_funcao
from app.models import ManutencaoServico, Usuario
from app.models.database import get_db
from app.schemas.manutencao import ServicoIn, ServicoOut, ServicoUpdate

router = APIRouter(prefix="/manutencao-servicos", tags=["manutencao"])

_escrita = require_funcao(ADMIN, "Laboratório")
_excluir = require_funcao(ADMIN)


def _ou_404(db: Session, servico_id: int) -> ManutencaoServico:
    s = db.query(ManutencaoServico).filter(ManutencaoServico.id == servico_id).first()
    if s is None:
        raise HTTPException(404, "serviço não encontrado")
    return s


@router.get("", response_model=list[ServicoOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN, "Laboratório", "Expedição", "Financeiro", "Comercial Pós-Vendas", "Qualidade"))):
    return db.query(ManutencaoServico).order_by(ManutencaoServico.descricao).all()


@router.post("", response_model=ServicoOut, status_code=http_status.HTTP_201_CREATED)
def criar(dados: ServicoIn, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    s = ManutencaoServico(descricao=dados.descricao.strip(),
                          resumo_padrao=dados.resumo_padrao.strip(), ativo=dados.ativo)
    db.add(s)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "já existe um serviço com essa descrição")
    db.refresh(s)
    return s


@router.put("/{servico_id}", response_model=ServicoOut)
def atualizar(servico_id: int, dados: ServicoUpdate, db: Session = Depends(get_db),
              _: Usuario = Depends(_escrita)):
    s = _ou_404(db, servico_id)
    campos = dados.model_dump(exclude_unset=True)
    for chave, valor in campos.items():
        setattr(s, chave, valor.strip() if isinstance(valor, str) else valor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "já existe um serviço com essa descrição")
    db.refresh(s)
    return s


@router.delete("/{servico_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def excluir(servico_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_excluir)):
    s = _ou_404(db, servico_id)
    db.delete(s)
    try:
        db.commit()
    except IntegrityError:
        # Servico ja usado em relatorio emitido: desativar em vez de apagar,
        # senao o relatorio perde o registro do que foi feito.
        db.rollback()
        raise HTTPException(409, "este serviço já foi usado em um relatório — desative em vez de excluir")
```

- [ ] **Passo 5: registrar o router**

Em `backend/app/main.py`, acrescentar `manutencao_servicos` à linha de import dos routers e, junto dos demais `include_router`:

```python
app.include_router(manutencao_servicos.router)
```

- [ ] **Passo 6: rodar e confirmar que passa**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_manutencao_servicos.py -q -p no:warnings`
Esperado: `8 passed`.

- [ ] **Passo 7: commitar**

```bash
git add backend/app/api/manutencao_servicos.py backend/app/schemas/manutencao.py backend/app/main.py backend/tests/test_manutencao_servicos.py
git commit -m "feat(manut): catalogo de servicos com escrita do laboratorio"
```

---

## Task 4: API da manutenção da OS

**Arquivos:**
- Criar: `backend/app/api/manutencoes.py`, `backend/tests/test_manutencao_api.py`
- Modificar: `backend/app/main.py`

**Interfaces:**
- Consome: `Manutencao`, `ManutencaoItem`, `ManutencaoServico` (Task 2); `compor_problema`, `compor_resumo` (Task 1); schemas `ManutencaoIn`, `ManutencaoOut` (Task 3).
- Produz: `GET /ordens/{id}/manutencao`, `PUT /ordens/{id}/manutencao`; helper `manutencao_da_os(db, ordem_id) -> Manutencao | None` usado na Task 6.

- [ ] **Passo 1: escrever o teste que falha**

`backend/tests/test_manutencao_api.py`:

```python
"""Manutencao da OS: uma por OS, registrada pelo Laboratorio na janela 5-8."""
import pytest


def _os(db, os_base, fase=5, tipo="M"):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico=tipo, situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o.id


def _servico(client, descricao, resumo):
    return client.post("/manutencao-servicos",
                       json={"descricao": descricao, "resumo_padrao": resumo}).json()["id"]


def test_registrar_manutencao(client_lab, os_base, fases_seed, db_session):
    oid = _os(db_session, os_base)
    s1 = _servico(client_lab, "Troca de Pilha interna", "Pilha da placa mãe substituída.")
    s2 = _servico(client_lab, "Troca do Bluetooth Mercury", "Módulo Bluetooth trocado.")
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={
        "numero": "HF00715", "data_manutencao": "2026-08-21",
        "resumo": "Pilha da placa mãe substituída. Módulo Bluetooth trocado.",
        "servicos": [s1, s2],
    })
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["numero"] == "HF00715"
    assert [x["descricao"] for x in corpo["servicos"]] == \
        ["Troca de Pilha interna", "Troca do Bluetooth Mercury"]


def test_registrar_de_novo_atualiza_e_nao_duplica(client_lab, os_base, fases_seed, db_session):
    from app.models import Manutencao
    oid = _os(db_session, os_base)
    s1 = _servico(client_lab, "A", "a.")
    s2 = _servico(client_lab, "B", "b.")
    client_lab.put(f"/ordens/{oid}/manutencao", json={"numero": "1", "servicos": [s1]})
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={"numero": "2", "servicos": [s2]})
    assert r.status_code == 200
    assert r.json()["numero"] == "2"
    assert [x["descricao"] for x in r.json()["servicos"]] == ["B"]
    db_session.expire_all()
    assert db_session.query(Manutencao).filter(Manutencao.os == oid).count() == 1


def test_ordem_dos_servicos_e_preservada(client_lab, os_base, fases_seed, db_session):
    """A ordem escolhida define a ordem no texto do documento."""
    oid = _os(db_session, os_base)
    a = _servico(client_lab, "A", "a.")
    b = _servico(client_lab, "B", "b.")
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={"servicos": [b, a]})
    assert [x["descricao"] for x in r.json()["servicos"]] == ["B", "A"]


def test_servico_inexistente_vira_422(client_lab, os_base, fases_seed, db_session):
    oid = _os(db_session, os_base)
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={"servicos": [99999]})
    assert r.status_code == 422


def test_ler_manutencao(client_lab, os_base, fases_seed, db_session):
    oid = _os(db_session, os_base)
    s1 = _servico(client_lab, "A", "a.")
    client_lab.put(f"/ordens/{oid}/manutencao", json={"numero": "HF1", "servicos": [s1]})
    r = client_lab.get(f"/ordens/{oid}/manutencao")
    assert r.status_code == 200
    assert r.json()["numero"] == "HF1"


def test_ler_sem_manutencao_vira_404(client_lab, os_base, fases_seed, db_session):
    oid = _os(db_session, os_base)
    assert client_lab.get(f"/ordens/{oid}/manutencao").status_code == 404


@pytest.mark.parametrize("fase", [4, 9])
def test_fora_da_janela_recusa(client_lab, os_base, fases_seed, db_session, fase):
    """Antes do laboratorio nao ha o que registrar; cancelada nao se mexe."""
    oid = _os(db_session, os_base, fase=fase)
    r = client_lab.put(f"/ordens/{oid}/manutencao", json={"numero": "1"})
    assert r.status_code == 409


@pytest.mark.parametrize("fase", [5, 6, 7, 8])
def test_dentro_da_janela_aceita(client_lab, os_base, fases_seed, db_session, fase):
    oid = _os(db_session, os_base, fase=fase)
    assert client_lab.put(f"/ordens/{oid}/manutencao", json={"numero": "1"}).status_code == 200


def test_outra_funcao_nao_registra(client, usuario_financeiro, os_base, fases_seed, db_session):
    oid = _os(db_session, os_base)
    tok = client.post("/auth/login", json={"email": "fin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    assert client.put(f"/ordens/{oid}/manutencao", json={"numero": "1"}, headers=h).status_code == 403


def test_os_inexistente_404(client_lab):
    assert client_lab.put("/ordens/999999/manutencao", json={"numero": "1"}).status_code == 404
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_manutencao_api.py -q -p no:warnings`
Esperado: falhas com `404` (rota não existe).

- [ ] **Passo 3: implementar o router**

`backend/app/api/manutencoes.py`:

```python
"""Registro da manutencao feita na bancada.

Uma por OS (unicidade em `manutencoes.os`), com N servicos do catalogo dentro.
Janela 5-8, a mesma do certificado de calibracao, que permite regerar OS antiga
sob demanda — antes do laboratorio nao ha o que registrar.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, require_funcao
from app.models import Manutencao, ManutencaoItem, ManutencaoServico, Ordem, Usuario
from app.models.database import get_db
from app.schemas.manutencao import ManutencaoIn, ManutencaoItemOut, ManutencaoOut

router = APIRouter(tags=["manutencao"])

_escrita = require_funcao(ADMIN, "Laboratório")

# Do Laboratorio ate Finalizada. Cancelada (9) e Recebido (4) ficam de fora.
FASES_PERMITIDAS = (5, 6, 7, 8)


def _os_ou_404(db: Session, ordem_id: int) -> Ordem:
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None:
        raise HTTPException(404, "OS não encontrada")
    return o


def manutencao_da_os(db: Session, ordem_id: int) -> Manutencao | None:
    """Usado tambem pela geracao do certificado (certificados_os)."""
    return db.query(Manutencao).filter(Manutencao.os == ordem_id).first()


def _saida(m: Manutencao) -> ManutencaoOut:
    return ManutencaoOut(
        id=m.id, os=m.os, numero=m.numero, data_manutencao=m.data_manutencao, resumo=m.resumo,
        servicos=[ManutencaoItemOut(servico=i.servico, descricao=i.servico_rel.descricao,
                                    resumo_padrao=i.servico_rel.resumo_padrao)
                  for i in m.itens],
    )


@router.get("/ordens/{ordem_id}/manutencao", response_model=ManutencaoOut)
def obter(ordem_id: int, db: Session = Depends(get_db),
          _: Usuario = Depends(require_funcao(ADMIN, "Laboratório", "Expedição", "Financeiro", "Comercial Pós-Vendas", "Qualidade"))):
    _os_ou_404(db, ordem_id)
    m = manutencao_da_os(db, ordem_id)
    if m is None:
        raise HTTPException(404, "esta OS não tem manutenção registrada")
    return _saida(m)


@router.put("/ordens/{ordem_id}/manutencao", response_model=ManutencaoOut)
def registrar(ordem_id: int, dados: ManutencaoIn, db: Session = Depends(get_db),
              usuario: Usuario = Depends(_escrita)):
    ordem = _os_ou_404(db, ordem_id)
    if ordem.fase not in FASES_PERMITIDAS:
        raise HTTPException(409, "a manutenção só pode ser registrada do Laboratório em diante")

    servicos = []
    for sid in dados.servicos:
        s = db.query(ManutencaoServico).filter(ManutencaoServico.id == sid).first()
        if s is None:
            raise HTTPException(422, f"serviço {sid} não existe no catálogo")
        servicos.append(s)

    m = manutencao_da_os(db, ordem_id)
    if m is None:
        m = Manutencao(os=ordem_id, criado_por=usuario.nome)
        db.add(m)
    m.numero = dados.numero
    m.data_manutencao = dados.data_manutencao
    m.resumo = dados.resumo
    m.atualizado_em = datetime.now(timezone.utc)
    db.flush()

    # Substitui a lista inteira: e' o jeito de refletir remocao e reordenacao
    # sem precisar diferenciar item a item.
    m.itens.clear()
    db.flush()
    for posicao, s in enumerate(servicos):
        db.add(ManutencaoItem(manutencao=m.id, servico=s.id, ordem=posicao))
    db.commit()
    db.refresh(m)
    return _saida(m)
```

- [ ] **Passo 4: registrar o router**

Em `backend/app/main.py`, acrescentar `manutencoes` ao import e:

```python
app.include_router(manutencoes.router)
```

- [ ] **Passo 5: rodar e confirmar que passa**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_manutencao_api.py -q -p no:warnings`
Esperado: `14 passed`.

- [ ] **Passo 6: commitar**

```bash
git add backend/app/api/manutencoes.py backend/app/main.py backend/tests/test_manutencao_api.py
git commit -m "feat(manut): registro da manutencao por os"
```

---

## Task 5: Tokens, `tipos_para` e o modelo genérico

**Arquivos:**
- Modificar: `backend/app/core/certificado_gerar.py`, `backend/app/models/certificado_modelo.py`
- Criar: `backend/tests/test_certificado_manutencao.py`

**Interfaces:**
- Consome: `compor_problema`, `compor_resumo` (Task 1); `manutencao_da_os` (Task 4).
- Produz: tokens `manutnumero`, `manutdata`, `manutproblema`, `manutresumo` no contexto; `tipos_para` com a nova regra; `modelo_para(db, equipamento_id, tipo)`.

- [ ] **Passo 1: escrever o teste que falha**

`backend/tests/test_certificado_manutencao.py`:

```python
"""Certificado de manutencao: quais tipos a OS pede e de onde vem o modelo."""
from datetime import date

import pytest

from app.core.certificado_gerar import tipos_para, modelo_para


class _OrdemFake:
    def __init__(self, tipo_servico):
        self.tipo_servico = tipo_servico


@pytest.mark.parametrize("tipo,esperado", [
    ("C", ["C"]),
    ("M", ["M"]),
    ("A", ["C", "M"]),
    (None, ["C"]),
])
def test_tipos_para_respeita_o_tipo_de_servico(tipo, esperado):
    """Manutencao pura NAO deve pedir certificado de calibracao: o tecnico
    emitiria um documento de calibracao que nao realizou."""
    assert tipos_para(_OrdemFake(tipo)) == esperado


def _equipamento(db, descricao="Bafômetro X"):
    from app.models import Equipamento
    e = Equipamento(descricao=descricao)
    db.add(e); db.commit(); db.refresh(e)
    return e


def test_modelo_de_manutencao_cai_no_generico(db_session):
    """Um modelo unico serve todos os aparelhos: os relatorios so diferem em
    marca, modelo e serie, que sao dados."""
    from app.models import CertificadoModelo
    eq = _equipamento(db_session)
    db_session.add(CertificadoModelo(equipamento=None, tipo="M", texto="<p>generico</p>"))
    db_session.commit()
    modelo = modelo_para(db_session, eq.id, "M")
    assert modelo is not None and modelo.texto == "<p>generico</p>"


def test_modelo_especifico_de_manutencao_ganha_do_generico(db_session):
    from app.models import CertificadoModelo
    eq = _equipamento(db_session)
    db_session.add(CertificadoModelo(equipamento=None, tipo="M", texto="<p>generico</p>"))
    db_session.add(CertificadoModelo(equipamento=eq.id, tipo="M", texto="<p>proprio</p>"))
    db_session.commit()
    assert modelo_para(db_session, eq.id, "M").texto == "<p>proprio</p>"


def test_calibracao_NAO_cai_no_generico(db_session):
    """Existe um modelo tipo C com equipamento nulo — o "legado" mantido em
    julho. Se o fallback valesse para C, todo aparelho sem modelo passaria a
    gerar certificado com aquele modelo de teste, sem ninguem perceber."""
    from app.models import CertificadoModelo
    eq = _equipamento(db_session)
    db_session.add(CertificadoModelo(equipamento=None, tipo="C", texto="<p>legado</p>"))
    db_session.commit()
    assert modelo_para(db_session, eq.id, "C") is None
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_certificado_manutencao.py -q -p no:warnings`
Esperado: `ImportError: cannot import name 'modelo_para'` e falhas em `tipos_para` para `"M"`.

- [ ] **Passo 3: soltar o `equipamento` do modelo**

Em `backend/app/models/certificado_modelo.py`, trocar a linha do campo por:

```python
    # Nulo = modelo GENERICO. Hoje so o tipo M usa esse caminho (ver modelo_para
    # em core/certificado_gerar.py); existe tambem um registro legado tipo C.
    equipamento = Column(Integer, ForeignKey("equipamentos.id"), nullable=True)
```

- [ ] **Passo 4: implementar `modelo_para` e o novo `tipos_para`**

Em `backend/app/core/certificado_gerar.py`, substituir a função `tipos_para` por:

```python
def tipos_para(ordem) -> list[str]:
    """Documentos que a OS pede, conforme o tipo de servico.

    C -> so calibracao · M -> so manutencao · A -> os dois · vazio -> calibracao.
    OS antigas tem tipo_servico nulo e seguem no comportamento de sempre.
    """
    if ordem.tipo_servico == "M":
        return ["M"]
    if ordem.tipo_servico == "A":
        return ["C", "M"]
    return ["C"]


def modelo_para(db: Session, equipamento_id, tipo: str):
    """Modelo do aparelho; para MANUTENCAO, cai no generico quando nao houver.

    O generico e' o registro com `equipamento` nulo. O fallback vale SO para o
    tipo M de proposito: existe um registro tipo C com equipamento nulo — o
    modelo "legado" mantido em julho — e um fallback amplo faria todo aparelho
    sem modelo de calibracao gerar certificado com aquele modelo de teste, em
    silencio.
    """
    especifico = db.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento == equipamento_id, CertificadoModelo.tipo == tipo
    ).first()
    if especifico is not None or tipo != "M":
        return especifico
    return db.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento.is_(None), CertificadoModelo.tipo == "M"
    ).first()
```

- [ ] **Passo 5: usar `modelo_para` onde o modelo é buscado**

Em `backend/app/core/certificado_gerar.py`, dentro de `tipos_sem_modelo` e de `gerar_certificados`, trocar cada consulta direta

```python
        modelo = db.query(CertificadoModelo).filter(
            CertificadoModelo.equipamento == ec.equipamento, CertificadoModelo.tipo == tipo
        ).first()
```

por

```python
        modelo = modelo_para(db, ec.equipamento, tipo)
```

- [ ] **Passo 6: rodar e confirmar que passa**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_certificado_manutencao.py -q -p no:warnings`
Esperado: `7 passed`.

- [ ] **Passo 7: acrescentar os quatro tokens**

Em `backend/app/core/certificado_gerar.py`, acrescentar à lista `CAMPOS`, junto dos demais:

```python
    ("manutnumero", "Numero do relatorio de manutencao — digitado pelo laboratorio."),
    ("manutdata", "Data da manutencao."),
    ("manutproblema", "Servicos executados, ja compostos em lista portuguesa."),
    ("manutresumo", "Resumo do servico, ja composto e revisado."),
```

E, no fim de `montar_contexto` — antes do `return` —, preencher a partir da manutenção da OS:

```python
    # Campos do Relatorio de Manutencao. Ficam vazios quando a OS nao tem
    # manutencao registrada; a geracao do tipo M e' recusada antes disso
    # (ver certificados_os.gerar), entao vazio aqui so acontece no tipo C.
    from app.api.manutencoes import manutencao_da_os
    manut = manutencao_da_os(db, ordem.id)
    ctx["manutnumero"] = (manut.numero or "") if manut else ""
    ctx["manutdata"] = _fmt(manut.data_manutencao) if manut and manut.data_manutencao else ""
    ctx["manutproblema"] = compor_problema(
        [i.servico_rel.descricao for i in manut.itens]) if manut else ""
    ctx["manutresumo"] = (manut.resumo or "") if manut else ""
```

Acrescentar no topo do arquivo:

```python
from app.core.manutencao import compor_problema
```

> `_fmt` é o helper de data do próprio arquivo (linha 76). Não criar outro.

- [ ] **Passo 8: rodar a suíte de certificado inteira**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/ -k "certificado" -q -p no:warnings`
Esperado: tudo passando, exceto as 4 falhas de baseline (`test_certificados_gerais.py` e `test_publico_certificado_geral.py`, `PermissionError` em `/data`).

- [ ] **Passo 9: commitar**

```bash
git add backend/app/core/certificado_gerar.py backend/app/models/certificado_modelo.py backend/tests/test_certificado_manutencao.py
git commit -m "feat(manut): tokens do relatorio, tipos por servico e modelo generico"
```

---

## Task 6: Recusar geração sem manutenção registrada

**Arquivos:**
- Modificar: `backend/app/api/certificados_os.py`
- Testar: `backend/tests/test_certificado_manutencao.py` (acrescentar)

**Interfaces:**
- Consome: `manutencao_da_os` (Task 4), `tipos_para` (Task 5).
- Produz: nada novo.

- [ ] **Passo 1: escrever o teste que falha**

Acrescentar ao fim de `backend/tests/test_certificado_manutencao.py`:

```python
def _os_manutencao(db, os_base, fase=5):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico="M", situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o.id


def test_gerar_sem_manutencao_registrada_recusa(client_lab, os_base, fases_seed, db_session, upload_tmp):
    """Documento em branco nao deve sair: sem numero, data e servico o
    relatorio nao tem conteudo."""
    from app.models import CertificadoModelo
    db_session.add(CertificadoModelo(equipamento=None, tipo="M", texto="<p>[manutnumero]</p>"))
    db_session.commit()
    oid = _os_manutencao(db_session, os_base)
    r = client_lab.post(f"/ordens/{oid}/gerar-certificado")
    assert r.status_code == 409
    assert "manutenção" in r.json()["detail"].lower()


def test_gerar_com_manutencao_registrada_produz_o_tipo_M(client_lab, os_base, fases_seed, db_session, upload_tmp):
    from app.models import CertificadoModelo, OSCertificado
    db_session.add(CertificadoModelo(equipamento=None, tipo="M", texto="<p>[manutnumero]</p>"))
    db_session.commit()
    oid = _os_manutencao(db_session, os_base)
    sid = client_lab.post("/manutencao-servicos",
                          json={"descricao": "Troca da placa mãe", "resumo_padrao": "Placa trocada."}).json()["id"]
    client_lab.put(f"/ordens/{oid}/manutencao", json={
        "numero": "HF00715", "data_manutencao": "2026-08-21",
        "resumo": "Placa trocada.", "servicos": [sid]})

    r = client_lab.post(f"/ordens/{oid}/gerar-certificado")
    assert r.status_code == 200
    db_session.expire_all()
    tipos = [c.tipo for c in db_session.query(OSCertificado).filter(OSCertificado.os == oid).all()]
    assert tipos == ["M"], "OS de manutencao pura nao emite certificado de calibracao"
    gerado = db_session.query(OSCertificado).filter(OSCertificado.os == oid).first()
    assert "HF00715" in gerado.html
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_certificado_manutencao.py -q -p no:warnings -k "gerar"`
Esperado: o primeiro falha (gera 200 em vez de 409).

- [ ] **Passo 3: implementar a recusa**

Em `backend/app/api/certificados_os.py`, dentro de `gerar`, logo **depois** do bloco que recusa por falta de modelo (`if faltando:`), acrescentar:

```python
    # Relatorio de manutencao sem manutencao registrada sairia em branco.
    # Mesma forma da recusa por falta de modelo: 409 com o caminho da solucao.
    if "M" in tipos_para(ordem):
        from app.api.manutencoes import manutencao_da_os
        manut = manutencao_da_os(db, ordem.id)
        if manut is None or not manut.itens:
            raise HTTPException(
                status_code=409,
                detail="Registre a manutenção (número, data e ao menos um serviço) "
                       "antes de gerar o relatório de manutenção.",
            )
```

- [ ] **Passo 4: rodar e confirmar que passa**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_certificado_manutencao.py -q -p no:warnings`
Esperado: `9 passed`.

- [ ] **Passo 5: rodar a suíte de backend inteira**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest -q -p no:warnings`
Esperado: só as 4 falhas de baseline. Qualquer outra é regressão — corrigir antes de commitar.

- [ ] **Passo 6: commitar**

```bash
git add backend/app/api/certificados_os.py backend/tests/test_certificado_manutencao.py
git commit -m "fix(manut): recusa gerar relatorio sem manutencao registrada"
```

---

## Task 7: Modelo genérico na API e na tela de Modelos

**Arquivos:**
- Modificar: `backend/app/api/certificados_modelo.py`, `frontend/src/app/certificados/ModelosTab.tsx`
- Testar: `backend/tests/test_certificado_modelo_generico.py` (criar)

**Interfaces:**
- Consome: `modelo_para` e o `equipamento` nulo da Task 5.
- Produz: `PUT /certificados-modelo/generico?tipo=M` e `GET /certificados-modelo/generico?tipo=M`.

Sem esta tarefa o modelo de manutenção só entraria por `INSERT` na mão, e a
Qualidade nunca conseguiria editá-lo pela tela — que é o motivo de o modelo
morar no banco.

- [ ] **Passo 1: escrever o teste que falha**

`backend/tests/test_certificado_modelo_generico.py`:

```python
"""Modelo GENERICO (sem aparelho). Hoje so o tipo M usa esse caminho."""


def test_admin_grava_o_modelo_generico_de_manutencao(client_admin):
    r = client_admin.put("/certificados-modelo/generico?tipo=M",
                         json={"texto": "<p>[manutnumero]</p>", "descricao": "Relatório FORM-LAB-010"})
    assert r.status_code == 200
    assert r.json()["texto"] == "<p>[manutnumero]</p>"


def test_ler_o_modelo_generico(client_admin):
    client_admin.put("/certificados-modelo/generico?tipo=M", json={"texto": "<p>x</p>"})
    r = client_admin.get("/certificados-modelo/generico?tipo=M")
    assert r.status_code == 200
    assert r.json()["texto"] == "<p>x</p>"


def test_gravar_de_novo_atualiza_e_nao_duplica(client_admin, db_session):
    from app.models import CertificadoModelo
    client_admin.put("/certificados-modelo/generico?tipo=M", json={"texto": "<p>a</p>"})
    client_admin.put("/certificados-modelo/generico?tipo=M", json={"texto": "<p>b</p>"})
    db_session.expire_all()
    modelos = db_session.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento.is_(None), CertificadoModelo.tipo == "M").all()
    assert len(modelos) == 1 and modelos[0].texto == "<p>b</p>"


def test_generico_de_calibracao_e_recusado(client_admin):
    """O registro legado tipo C existe e nao pode virar padrao de calibracao —
    a rota nem aceita criar generico de C."""
    r = client_admin.put("/certificados-modelo/generico?tipo=C", json={"texto": "<p>x</p>"})
    assert r.status_code == 422


def test_ler_generico_inexistente_404(client_admin):
    assert client_admin.get("/certificados-modelo/generico?tipo=M").status_code == 404
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_certificado_modelo_generico.py -q -p no:warnings`
Esperado: `404` em todas — a rota não existe.

- [ ] **Passo 3: implementar as rotas**

Em `backend/app/api/certificados_modelo.py`, **antes** de `@router.get("/certificados-modelo/{equipamento_id}")` (senão `"generico"` seria capturado como id):

```python
@router.get("/certificados-modelo/generico", response_model=CertificadoModeloOut)
def obter_modelo_generico(tipo: Literal["M"] = "M", db: Session = Depends(get_db),
                          _: Usuario = Depends(get_current_usuario)):
    """Modelo sem aparelho. So o tipo M — ver `modelo_para` em certificado_gerar."""
    modelo = db.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento.is_(None), CertificadoModelo.tipo == tipo
    ).first()
    if modelo is None:
        raise HTTPException(404, "modelo genérico não cadastrado")
    return modelo


@router.put("/certificados-modelo/generico", response_model=CertificadoModeloOut)
def salvar_modelo_generico(dados: CertificadoModeloIn, tipo: Literal["M"] = "M",
                           db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    """Cria ou atualiza o modelo sem aparelho.

    Restrito ao tipo M de proposito: existe um registro tipo C com equipamento
    nulo — o modelo "legado" de julho — e permitir gravar generico de C daria a
    ele status de padrao para todo aparelho sem modelo proprio.
    """
    modelo = db.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento.is_(None), CertificadoModelo.tipo == tipo
    ).first()
    if modelo is None:
        modelo = CertificadoModelo(equipamento=None, tipo=tipo)
        db.add(modelo)
    if dados.texto is not None:
        modelo.texto = dados.texto
    if dados.descricao is not None:
        modelo.descricao = dados.descricao
    db.commit()
    db.refresh(modelo)
    return modelo
```

`Literal["M"]` faz o FastAPI recusar `tipo=C` com **422** sozinho — é o que o teste espera.

Conferir que `Literal` está importado no topo do arquivo (já está, por causa de `salvar_modelo`).

- [ ] **Passo 4: rodar e confirmar que passa**

Rodar: `cd backend && source .venv/bin/activate && python -m pytest tests/test_certificado_modelo_generico.py -q -p no:warnings`
Esperado: `5 passed`.

- [ ] **Passo 5: expor na tela de Modelos**

Em `frontend/src/app/certificados/ModelosTab.tsx`, acrescentar uma entrada fixa no topo da lista, antes dos modelos por aparelho:

```tsx
      {/* O relatório de manutenção é um só para todos os aparelhos: os
          relatórios só diferem em marca, modelo e série, que são dados. */}
      <div className="rounded-lg border border-border px-3 py-2.5 flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-200">Relatório de Manutenção</p>
          <p className="text-xs text-slate-500">Modelo único, usado por todos os aparelhos</p>
        </div>
        <Button variant="secondary" onClick={() => abrirGenerico()}>Editar código-fonte</Button>
      </div>
```

`abrirGenerico()` reaproveita o mesmo editor de código-fonte já usado pelos modelos por aparelho, trocando as chamadas por `GET`/`PUT /certificados-modelo/generico?tipo=M`.

- [ ] **Passo 6: verificar o frontend**

Rodar: `cd frontend && npx tsc -b --noEmit && npx vitest run src/app/certificados/`
Esperado: verde.

- [ ] **Passo 7: commitar**

```bash
git add backend/app/api/certificados_modelo.py backend/tests/test_certificado_modelo_generico.py frontend/src/app/certificados/ModelosTab.tsx
git commit -m "feat(manut): modelo generico de manutencao pela api e pela tela"
```

---

## Task 8: Regra de função e cliente de API no frontend

**Arquivos:**
- Criar: `frontend/src/app/ordens/manutencao.ts`, `frontend/src/app/ordens/manutencao.test.ts`
- Modificar: `frontend/src/auth/roles.ts`, `frontend/src/auth/roles.test.ts`

**Interfaces:**
- Consome: rotas das Tasks 3 e 4.
- Produz: `podeRegistrarManutencao(user, fase)`; `manutencaoApi` (`obter`, `salvar`, `listarServicos`, `criarServico`, `atualizarServico`, `excluirServico`); `comporResumo(frases: string[]): string`; tipos `ServicoManutencao`, `Manutencao`.

- [ ] **Passo 1: escrever o teste que falha**

`frontend/src/app/ordens/manutencao.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { comporResumo } from './manutencao'

// Espelha compor_resumo do backend (app/core/manutencao.py): o modal precisa
// mostrar o resumo composto ANTES de salvar, sem ida ao servidor.
describe('comporResumo', () => {
  it('junta as frases na ordem, com ponto entre elas', () => {
    expect(comporResumo(['Primeira frase', 'Segunda frase'])).toBe('Primeira frase. Segunda frase.')
  })

  it('nao duplica o ponto que ja existe', () => {
    expect(comporResumo(['Primeira frase.', 'Segunda frase.'])).toBe('Primeira frase. Segunda frase.')
  })

  it('ignora frases vazias', () => {
    expect(comporResumo(['', '  ', 'Única.'])).toBe('Única.')
  })

  it('sem frases devolve vazio', () => {
    expect(comporResumo([])).toBe('')
  })
})
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd frontend && npx vitest run src/app/ordens/manutencao.test.ts`
Esperado: falha de resolução — `Failed to resolve import "./manutencao"`.

- [ ] **Passo 3: implementar o módulo**

`frontend/src/app/ordens/manutencao.ts`:

```ts
import { apiJson } from '../../lib/api'

export interface ServicoManutencao {
  id: number
  descricao: string
  resumo_padrao: string
  ativo: boolean
}

export interface ManutencaoServicoItem {
  servico: number
  descricao: string
  resumo_padrao: string
}

export interface Manutencao {
  id: number
  os: number
  numero: string | null
  data_manutencao: string | null
  resumo: string | null
  servicos: ManutencaoServicoItem[]
}

export interface ManutencaoPayload {
  numero: string | null
  data_manutencao: string | null
  resumo: string | null
  servicos: number[]
}

/** Espelha compor_resumo do backend, para o modal mostrar o texto antes de salvar. */
export function comporResumo(frases: string[]): string {
  const limpas = frases.map((f) => f.trim()).filter((f) => f !== '')
  if (limpas.length === 0) return ''
  return limpas.map((f) => (f.endsWith('.') ? f : `${f}.`)).join(' ')
}

export const manutencaoApi = {
  obter: (osId: number): Promise<Manutencao> =>
    apiJson<Manutencao>(`/ordens/${osId}/manutencao`),
  salvar: (osId: number, payload: ManutencaoPayload): Promise<Manutencao> =>
    apiJson<Manutencao>(`/ordens/${osId}/manutencao`, { method: 'PUT', body: JSON.stringify(payload) }),
  listarServicos: (): Promise<ServicoManutencao[]> =>
    apiJson<ServicoManutencao[]>('/manutencao-servicos'),
  criarServico: (dados: { descricao: string; resumo_padrao: string }): Promise<ServicoManutencao> =>
    apiJson<ServicoManutencao>('/manutencao-servicos', { method: 'POST', body: JSON.stringify(dados) }),
  atualizarServico: (id: number, dados: Partial<ServicoManutencao>): Promise<ServicoManutencao> =>
    apiJson<ServicoManutencao>(`/manutencao-servicos/${id}`, { method: 'PUT', body: JSON.stringify(dados) }),
  excluirServico: (id: number): Promise<void> =>
    apiJson<void>(`/manutencao-servicos/${id}`, { method: 'DELETE' }),
}
```

- [ ] **Passo 4: acrescentar a regra de função**

Em `frontend/src/auth/roles.ts`, logo depois de `podeEditarTipoServico`:

```ts
/** Registrar a manutenção e gerar o relatório.
 *
 * Laboratório e Administrador, do Laboratório em diante (fases 5–8) — a mesma
 * janela do certificado de calibração, que permite regerar OS antiga sob
 * demanda. Espelha FASES_PERMITIDAS em app/api/manutencoes.py. */
export function podeRegistrarManutencao(user: User | null, fase: number | null): boolean {
  return (isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO)
    && fase != null && [5, 6, 7, 8].includes(fase)
}
```

- [ ] **Passo 5: testar a regra**

Acrescentar ao fim de `frontend/src/auth/roles.test.ts` (e incluir `podeRegistrarManutencao` no import do topo):

```ts
describe('auth/roles — podeRegistrarManutencao', () => {
  it('laboratório registra nas fases 5 a 8', () => {
    for (const fase of [5, 6, 7, 8]) {
      expect(podeRegistrarManutencao({ funcao: 'Laboratório' } as never, fase)).toBe(true)
    }
  })

  it('admin também registra', () => {
    expect(podeRegistrarManutencao({ funcao: 'Administrador' } as never, 5)).toBe(true)
  })

  it('fora da janela não registra', () => {
    for (const fase of [4, 9]) {
      expect(podeRegistrarManutencao({ funcao: 'Laboratório' } as never, fase)).toBe(false)
    }
    expect(podeRegistrarManutencao({ funcao: 'Laboratório' } as never, null)).toBe(false)
  })

  it('outra função não registra', () => {
    expect(podeRegistrarManutencao({ funcao: 'Financeiro' } as never, 5)).toBe(false)
    expect(podeRegistrarManutencao(null, 5)).toBe(false)
  })
})
```

- [ ] **Passo 6: rodar e confirmar que passa**

Rodar: `cd frontend && npx vitest run src/app/ordens/manutencao.test.ts src/auth/roles.test.ts && npx tsc -b --noEmit`
Esperado: tudo verde e `tsc` sem saída.

- [ ] **Passo 7: commitar**

```bash
git add frontend/src/app/ordens/manutencao.ts frontend/src/app/ordens/manutencao.test.ts frontend/src/auth/roles.ts frontend/src/auth/roles.test.ts
git commit -m "feat(manut): cliente de api e regra de funcao da manutencao"
```

---

## Task 9: Modal de registro da manutenção

**Arquivos:**
- Criar: `frontend/src/app/ordens/ManutencaoModal.tsx`, `frontend/src/app/ordens/ManutencaoModal.test.tsx`

**Interfaces:**
- Consome: `manutencaoApi`, `comporResumo`, tipos (Task 7).
- Produz: `<ManutencaoModal osId={number} onClose={() => void} onSalvo={(m: Manutencao) => void} />`.

- [ ] **Passo 1: escrever o teste que falha**

`frontend/src/app/ordens/ManutencaoModal.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { obter, salvar, listarServicos } = vi.hoisted(() => ({
  obter: vi.fn(), salvar: vi.fn(), listarServicos: vi.fn(),
}))
vi.mock('./manutencao', async (orig) => {
  const real = await orig<typeof import('./manutencao')>()
  return { ...real, manutencaoApi: { ...real.manutencaoApi, obter, salvar, listarServicos } }
})

import { ManutencaoModal } from './ManutencaoModal'

const SERVICOS = [
  { id: 1, descricao: 'Troca da placa mãe', resumo_padrao: 'Placa substituída.', ativo: true },
  { id: 2, descricao: 'Troca da bateria', resumo_padrao: 'Bateria trocada.', ativo: true },
  { id: 3, descricao: 'Serviço aposentado', resumo_padrao: 'x.', ativo: false },
]

describe('ManutencaoModal', () => {
  beforeEach(() => {
    obter.mockReset(); salvar.mockReset(); listarServicos.mockReset()
    listarServicos.mockResolvedValue(SERVICOS)
    obter.mockRejectedValue(new Error('404'))   // OS ainda sem manutenção
    salvar.mockResolvedValue({ id: 1, os: 7, numero: 'HF1', data_manutencao: null, resumo: '', servicos: [] })
  })

  it('serviço inativo não aparece para escolher', async () => {
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    expect(await screen.findByLabelText('Troca da placa mãe')).toBeInTheDocument()
    expect(screen.queryByLabelText('Serviço aposentado')).not.toBeInTheDocument()
  })

  it('escolher serviços compõe o resumo automaticamente', async () => {
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    await userEvent.click(await screen.findByLabelText('Troca da placa mãe'))
    await userEvent.click(screen.getByLabelText('Troca da bateria'))

    const resumo = screen.getByLabelText('Resumo do serviço') as HTMLTextAreaElement
    await waitFor(() => expect(resumo.value).toBe('Placa substituída. Bateria trocada.'))
  })

  it('depois de editar o resumo, mudar os serviços nao sobrescreve o texto', async () => {
    // Sem essa regra, acrescentar um servico no fim apagaria um texto trabalhado.
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    await userEvent.click(await screen.findByLabelText('Troca da placa mãe'))
    const resumo = screen.getByLabelText('Resumo do serviço') as HTMLTextAreaElement
    await waitFor(() => expect(resumo.value).toBe('Placa substituída.'))

    fireEvent.change(resumo, { target: { value: 'Texto escrito à mão.' } })
    await userEvent.click(screen.getByLabelText('Troca da bateria'))

    expect(resumo.value).toBe('Texto escrito à mão.')
    expect(screen.getByText(/não acompanha mais os serviços/i)).toBeInTheDocument()
  })

  it('salvar envia número, data, serviços na ordem e resumo', async () => {
    const onSalvo = vi.fn()
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={onSalvo} />)
    await userEvent.click(await screen.findByLabelText('Troca da bateria'))
    await userEvent.click(screen.getByLabelText('Troca da placa mãe'))
    fireEvent.change(screen.getByLabelText('Número do relatório'), { target: { value: 'HF00715' } })
    fireEvent.change(screen.getByLabelText('Data da manutenção'), { target: { value: '2026-08-21' } })

    await userEvent.click(screen.getByText('Salvar manutenção'))

    await waitFor(() => expect(salvar).toHaveBeenCalled())
    expect(salvar.mock.calls[0][1]).toEqual({
      numero: 'HF00715',
      data_manutencao: '2026-08-21',
      resumo: 'Bateria trocada. Placa substituída.',
      servicos: [2, 1],
    })
    expect(onSalvo).toHaveBeenCalled()
  })

  it('sem serviço escolhido nao deixa salvar', async () => {
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    await screen.findByLabelText('Troca da placa mãe')
    await userEvent.click(screen.getByText('Salvar manutenção'))
    expect(await screen.findByText(/escolha ao menos um serviço/i)).toBeInTheDocument()
    expect(salvar).not.toHaveBeenCalled()
  })
})
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd frontend && npx vitest run src/app/ordens/ManutencaoModal.test.tsx`
Esperado: `Failed to resolve import "./ManutencaoModal"`.

- [ ] **Passo 3: implementar o modal**

`frontend/src/app/ordens/ManutencaoModal.tsx`:

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { comporResumo, manutencaoApi, type Manutencao, type ServicoManutencao } from './manutencao'

export function ManutencaoModal({ osId, onClose, onSalvo }: {
  osId: number
  onClose: () => void
  onSalvo: (m: Manutencao) => void
}) {
  const [servicos, setServicos] = useState<ServicoManutencao[] | null>(null)
  const [escolhidos, setEscolhidos] = useState<number[]>([])
  const [numero, setNumero] = useState('')
  const [data, setData] = useState('')
  const [resumo, setResumo] = useState('')
  // Guarda a ultima composicao automatica. Enquanto o texto for igual a ela, o
  // resumo acompanha a escolha de servicos; assim que o tecnico edita, para de
  // acompanhar — senao acrescentar um servico apagaria o texto dele.
  const [composicao, setComposicao] = useState('')
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    let vivo = true
    void manutencaoApi.listarServicos()
      .then((lista) => { if (vivo) setServicos(lista.filter((s) => s.ativo)) })
      .catch(() => { if (vivo) setServicos([]) })
    // Manutencao ja registrada: 404 aqui e' o caso normal da primeira vez.
    void manutencaoApi.obter(osId)
      .then((m) => {
        if (!vivo) return
        setNumero(m.numero ?? '')
        setData(m.data_manutencao ?? '')
        setResumo(m.resumo ?? '')
        setComposicao(m.resumo ?? '')
        setEscolhidos(m.servicos.map((s) => s.servico))
      })
      .catch(() => { /* sem manutencao ainda */ })
    return () => { vivo = false }
  }, [osId])

  function alternar(servico: ServicoManutencao) {
    const novos = escolhidos.includes(servico.id)
      ? escolhidos.filter((x) => x !== servico.id)
      : [...escolhidos, servico.id]
    setEscolhidos(novos)
    const frases = novos.map((id) => (servicos ?? []).find((s) => s.id === id)?.resumo_padrao ?? '')
    const nova = comporResumo(frases)
    if (resumo === composicao) {
      setResumo(nova)
    }
    setComposicao(nova)
  }

  const resumoDesacoplado = resumo !== composicao && resumo.trim() !== ''

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (escolhidos.length === 0) { setErro('Escolha ao menos um serviço.'); return }
    setErro('')
    setSalvando(true)
    try {
      const m = await manutencaoApi.salvar(osId, {
        numero: numero.trim() || null,
        data_manutencao: data || null,
        resumo: resumo.trim() || null,
        servicos: escolhidos,
      })
      onSalvo(m)
      onClose()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar a manutenção')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Registrar manutenção"
      size="2xl"
      closeOnBackdrop={false}
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose} disabled={salvando}>Cancelar</Button>
          <Button type="submit" form="form-manutencao" disabled={salvando}>
            {salvando ? 'Salvando…' : 'Salvar manutenção'}
          </Button>
        </>
      }
    >
      <form id="form-manutencao" className="space-y-4" onSubmit={submeter}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Input id="manut-numero" label="Número do relatório" value={numero}
                 onChange={(e) => setNumero(e.target.value)} maxLength={50} />
          <Input id="manut-data" label="Data da manutenção" type="date" value={data}
                 onChange={(e) => setData(e.target.value)} />
        </div>

        <div className="space-y-1.5">
          <span className="block text-xs font-semibold text-slate-500 uppercase tracking-wide">Serviços executados</span>
          {servicos === null ? (
            <Spinner className="w-5 h-5" />
          ) : servicos.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum serviço cadastrado — cadastre em Certificados › Serviços de manutenção.</p>
          ) : (
            <div className="space-y-1">
              {servicos.map((s) => (
                <label key={s.id} className="flex items-center gap-2 text-sm text-slate-200">
                  <input type="checkbox" aria-label={s.descricao}
                         checked={escolhidos.includes(s.id)} onChange={() => alternar(s)} />
                  {s.descricao}
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-1">
          <label htmlFor="manut-resumo" className="block text-xs font-semibold text-slate-500 uppercase tracking-wide">
            Resumo do serviço
          </label>
          <textarea id="manut-resumo" rows={6} value={resumo}
                    onChange={(e) => setResumo(e.target.value)}
                    className="w-full rounded-lg bg-background border border-border px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary/40" />
          {resumoDesacoplado && (
            <p className="text-xs text-slate-500">
              Você editou este texto — ele não acompanha mais os serviços escolhidos.
            </p>
          )}
        </div>

        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
```

- [ ] **Passo 4: rodar e confirmar que passa**

Rodar: `cd frontend && npx vitest run src/app/ordens/ManutencaoModal.test.tsx`
Esperado: `5 passed`.

- [ ] **Passo 5: commitar**

```bash
git add frontend/src/app/ordens/ManutencaoModal.tsx frontend/src/app/ordens/ManutencaoModal.test.tsx
git commit -m "feat(manut): modal de registro com resumo composto"
```

---

## Task 10: Modal de geração adapta ao tipo de serviço

**Arquivos:**
- Modificar: `frontend/src/app/ordens/GerarCertificadoModal.tsx`
- Criar: `frontend/src/app/ordens/GerarCertificadoModal.manutencao.test.tsx`

**Interfaces:**
- Consome: `ordensApi.certificadoCampos` (já existe).
- Produz: nada para tarefas seguintes.

O modal já traz TODOS os campos compartilhados (cliente, CNPJ, endereço, marca,
modelo, série, patrimônio, data de venda) preenchidos do cadastro e editáveis,
gravando em `cert_overrides` ao gerar — é o "modal com todos os valores" que a
spec pede. Falta só ele parar de mostrar o bloco de calibração numa OS de
manutenção pura, onde não há medição nenhuma.

- [ ] **Passo 1: escrever o teste que falha**

`frontend/src/app/ordens/GerarCertificadoModal.manutencao.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

const { certificadoCampos, gerarCertificado } = vi.hoisted(() => ({
  certificadoCampos: vi.fn(), gerarCertificado: vi.fn(),
}))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, ordensApi: { ...real.ordensApi, certificadoCampos, gerarCertificado } }
})

import { GerarCertificadoModal } from './GerarCertificadoModal'

const CAMPOS = {
  nomecli: 'ACME', cnpj: '36312056000552', endcli: 'Rua X, 10',
  modelo: 'iBlow10', marca: 'Sentech', serie: 'SN-1', patrimonio: '', datacompra: '2024-01-10',
  calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null,
  calib_teste2: null, calib_teste3: null, calib_teste4: null, calib_teste5: null,
  calib_teste_media: null, calib_situacao: null, data_calibracao: null,
}

function os(tipo: string) {
  return { id: 7, tipo_servico: tipo, equipamento_descricao: 'iBlow10' } as never
}

describe('GerarCertificadoModal — por tipo de serviço', () => {
  beforeEach(() => {
    certificadoCampos.mockReset(); gerarCertificado.mockReset()
    certificadoCampos.mockResolvedValue(CAMPOS)
  })

  it('OS de manutenção mostra os dados do cliente e do aparelho, editáveis', async () => {
    render(<GerarCertificadoModal os={os('M')} onClose={vi.fn()} onGerado={vi.fn()} />)
    const nome = (await screen.findByLabelText(/raz[ãa]o social|cliente/i)) as HTMLInputElement
    expect(nome.value).toBe('ACME')
    expect(nome).not.toBeDisabled()
  })

  it('OS de manutenção NÃO mostra o bloco de calibração', async () => {
    render(<GerarCertificadoModal os={os('M')} onClose={vi.fn()} onGerado={vi.fn()} />)
    await screen.findByLabelText(/raz[ãa]o social|cliente/i)
    expect(screen.queryByLabelText(/teste 1/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/incerteza|situação da calibra/i)).not.toBeInTheDocument()
  })

  it('OS de calibração continua mostrando o bloco de calibração', async () => {
    render(<GerarCertificadoModal os={os('C')} onClose={vi.fn()} onGerado={vi.fn()} />)
    expect(await screen.findByLabelText(/teste 1/i)).toBeInTheDocument()
  })

  it('OS "Ambas" mostra o bloco de calibração', async () => {
    render(<GerarCertificadoModal os={os('A')} onClose={vi.fn()} onGerado={vi.fn()} />)
    expect(await screen.findByLabelText(/teste 1/i)).toBeInTheDocument()
  })
})
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd frontend && npx vitest run src/app/ordens/GerarCertificadoModal.manutencao.test.tsx`
Esperado: o segundo teste falha — o bloco de calibração aparece.

> Se os rótulos do modal forem diferentes dos usados nas expressões regulares
> acima, ajustar o teste ao que a tela realmente rotula — não renomear os
> campos da tela para caber no teste.

- [ ] **Passo 3: implementar**

Em `frontend/src/app/ordens/GerarCertificadoModal.tsx`, acrescentar o derivado logo após os estados:

```tsx
  // Manutenção pura não tem medição: mostrar o bloco de calibração pediria
  // dados de um ensaio que não foi feito. Espelha tipos_para no backend.
  const temCalibracao = os.tipo_servico !== 'M'
```

Envolver o bloco de campos de calibração (`cert`, `situacao`, `temp`, `pressao`, `t1`–`t5`, `media`, `dataCalib`) com:

```tsx
  {temCalibracao && (
    <>
      {/* …bloco de calibração existente, sem alterações… */}
    </>
  )}
```

O bloco de cliente e aparelho fica **fora** da condição: vale para os dois documentos.

- [ ] **Passo 4: rodar e confirmar que passa**

Rodar: `cd frontend && npx vitest run src/app/ordens/`
Esperado: verde, inclusive os testes que já existiam do modal.

- [ ] **Passo 5: commitar**

```bash
git add frontend/src/app/ordens/GerarCertificadoModal.tsx frontend/src/app/ordens/GerarCertificadoModal.manutencao.test.tsx
git commit -m "feat(manut): modal de geracao esconde calibracao em os de manutencao"
```

---

## Task 11: Duas seções de certificado na tela da OS

**Arquivos:**
- Modificar: `frontend/src/app/ordens/OrdemDetailPage.tsx:513-556`
- Criar: `frontend/src/app/ordens/OrdemDetailPage.secoes.test.tsx`

**Interfaces:**
- Consome: `podeRegistrarManutencao` (Task 7), `ManutencaoModal` (Task 8).
- Produz: nada para tarefas seguintes.

- [ ] **Passo 1: escrever o teste que falha**

`frontend/src/app/ordens/OrdemDetailPage.secoes.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let mockUser: { funcao: string } | null = { funcao: 'Laboratório' }
vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

const { obter, logs, certificados } = vi.hoisted(() => ({
  obter: vi.fn(), logs: vi.fn(), certificados: vi.fn(),
}))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return {
    ...real,
    ordensApi: { ...real.ordensApi, obter, logs, certificados },
    fotosApi: { ...real.fotosApi, listar: vi.fn().mockResolvedValue([]) },
  }
})
vi.mock('./manutencao', async (orig) => {
  const real = await orig<typeof import('./manutencao')>()
  return {
    ...real,
    manutencaoApi: {
      ...real.manutencaoApi,
      obter: vi.fn().mockRejectedValue(new Error('404')),
      listarServicos: vi.fn().mockResolvedValue([]),
    },
  }
})

import { OrdemDetailPage } from './OrdemDetailPage'

function baseOs(over: Record<string, unknown> = {}) {
  return {
    id: 500, cliente: 1, cliente_nome: 'ACME', equipamento_cliente: 1,
    equipamento_descricao: 'IBLOW10D', equipamento_serie: 'SN-1', fase: 5,
    fase_descricao: 'Laboratório', fase_cor: 'abc123', tipo_servico: 'C',
    data_chegada: null, prox_calibragem: null, situacao: 'A', caixa: null,
    condicao_chegada: null, acessorios: null, aceite: false, recebido: true,
    etiqueta: null, cod_retorno: null, obs: null, data_calibracao: null,
    data_retorno: null, data_aceite: null, tipo_calibragem: null,
    calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null,
    calib_teste2: null, calib_teste3: null, calib_teste_media: null,
    calib_situacao: null, pdf_certificado: null, nota_fiscal: null,
    nota_fiscal_xml: null, nota_fiscal_numero: null,
    certificado_modelos_faltantes: [], pilhas: 0, bocais: 0, checklist_ids: [],
    acessorios_presentes: [], garantias: null, desfecho_lab: null, desfecho_lab_obs: null,
    ...over,
  }
}

function tela() {
  return render(
    <MemoryRouter initialEntries={['/app/ordens/500']}>
      <Routes><Route path="/app/ordens/:id" element={<OrdemDetailPage />} /></Routes>
    </MemoryRouter>,
  )
}

// As duas seções deixam explícito qual documento está sendo feito e onde.
describe('OrdemDetailPage — seções de certificado', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Laboratório' }
    obter.mockReset(); logs.mockReset(); certificados.mockReset()
    logs.mockResolvedValue([]); certificados.mockResolvedValue([])
  })

  it('OS de calibração mostra só a seção de calibração', async () => {
    obter.mockResolvedValue(baseOs({ tipo_servico: 'C' }))
    tela()
    expect(await screen.findByText('Certificado de calibração')).toBeInTheDocument()
    expect(screen.queryByText('Certificado de manutenção')).not.toBeInTheDocument()
  })

  it('OS de manutenção mostra só a seção de manutenção', async () => {
    obter.mockResolvedValue(baseOs({ tipo_servico: 'M' }))
    tela()
    expect(await screen.findByText('Certificado de manutenção')).toBeInTheDocument()
    expect(screen.queryByText('Certificado de calibração')).not.toBeInTheDocument()
  })

  it('OS "Ambas" mostra as duas', async () => {
    obter.mockResolvedValue(baseOs({ tipo_servico: 'A' }))
    tela()
    expect(await screen.findByText('Certificado de calibração')).toBeInTheDocument()
    expect(screen.getByText('Certificado de manutenção')).toBeInTheDocument()
  })

  it('OS antiga sem tipo de serviço mostra a de calibração', async () => {
    obter.mockResolvedValue(baseOs({ tipo_servico: null }))
    tela()
    expect(await screen.findByText('Certificado de calibração')).toBeInTheDocument()
    expect(screen.queryByText('Certificado de manutenção')).not.toBeInTheDocument()
  })
})
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd frontend && npx vitest run src/app/ordens/OrdemDetailPage.secoes.test.tsx`
Esperado: falha — a tela ainda tem uma seção chamada "Certificados".

- [ ] **Passo 3: dividir a seção**

Em `frontend/src/app/ordens/OrdemDetailPage.tsx`, acrescentar aos imports:

```tsx
import { podeRegistrarManutencao } from '../../auth/roles'   // juntar ao import existente de roles
import { ManutencaoModal } from './ManutencaoModal'
```

Acrescentar ao estado do componente:

```tsx
  const [manutencaoAberta, setManutencaoAberta] = useState(false)
```

Acrescentar aos derivados, ao lado de `podeGerarOuRegerar`:

```tsx
  // Quais seções aparecem — espelha tipos_para no backend.
  const tiposDaOS = os.tipo_servico === 'M' ? ['M'] : os.tipo_servico === 'A' ? ['C', 'M'] : ['C']
  const certDe = (tipo: string) => certs.find((c) => c.tipo === tipo)
```

Substituir o bloco inteiro da seção "Certificados gerados" (de `{/* Certificados gerados */}` até o `</Secao>` correspondente) por:

```tsx
      {/* Uma seção por documento: deixa explícito qual está sendo feito e onde. */}
      {tiposDaOS.includes('C') && (
        <Secao
          icon={<IconCertificado className="w-4 h-4" />}
          titulo="Certificado de calibração"
          acao={podeGerarOuRegerar && !semModelo && (
            <Button variant={certDe('C') ? 'secondary' : 'primary'} onClick={() => setAcao('gerar')}>
              {certDe('C') ? 'Regerar certificado' : 'Gerar certificado'}
            </Button>
          )}
        >
          {/* O aviso ACOMPANHA a lista, nunca a substitui: o documento já emitido
              não pode sumir da tela por falta de modelo de outro tipo. */}
          {semModelo && (
            <div className="rounded-lg bg-warning/10 border border-warning/20 px-3 py-2.5 space-y-1.5">
              <p className="text-sm text-warning">
                Este aparelho não tem modelo de certificado de {modelosFaltantesLabel} cadastrado — por isso não é
                possível gerar o certificado.
              </p>
              <Link to="/app/certificados" className="inline-block text-xs font-semibold text-primary hover:underline">
                Cadastrar modelo de certificado
              </Link>
            </div>
          )}
          {os.desfecho_lab === 'liberado' && (
            <p className="text-sm text-slate-400">Liberado sem certificado{os.desfecho_lab_obs ? ` — ${os.desfecho_lab_obs}` : ''}.</p>
          )}
          {certDe('C') ? (
            <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
              <span className="text-sm text-slate-200">
                Gerado <span className="text-xs text-slate-500 ml-1">{formatData(certDe('C')!.data_geracao)}</span>
              </span>
              <button type="button" onClick={() => void onBaixarPdf('C')} className="text-xs font-semibold text-primary hover:underline">Baixar PDF</button>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Nenhum certificado de calibração gerado.</p>
          )}
        </Secao>
      )}

      {tiposDaOS.includes('M') && (
        <Secao
          icon={<IconCertificado className="w-4 h-4" />}
          titulo="Certificado de manutenção"
          acao={podeRegistrarManutencao(user, os.fase) && (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setManutencaoAberta(true)}>Registrar manutenção</Button>
              {!semModelo && (
                <Button variant={certDe('M') ? 'secondary' : 'primary'} onClick={() => setAcao('gerar')}>
                  {certDe('M') ? 'Regerar relatório' : 'Gerar relatório'}
                </Button>
              )}
            </div>
          )}
        >
          {certDe('M') ? (
            <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
              <span className="text-sm text-slate-200">
                Gerado <span className="text-xs text-slate-500 ml-1">{formatData(certDe('M')!.data_geracao)}</span>
              </span>
              <button type="button" onClick={() => void onBaixarPdf('M')} className="text-xs font-semibold text-primary hover:underline">Baixar PDF</button>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              Nenhum relatório de manutenção gerado. Registre a manutenção antes de gerar.
            </p>
          )}
        </Secao>
      )}
```

E, junto dos outros modais no fim do componente:

```tsx
      {manutencaoAberta && (
        <ManutencaoModal
          osId={osId}
          onClose={() => setManutencaoAberta(false)}
          onSalvo={() => { void ordensApi.obter(osId).then(setOs) }}
        />
      )}
```

> Recarregar a OS é `void ordensApi.obter(osId).then(setOs)` — o mesmo padrão já usado em três pontos da página. Não existe uma função `carregar()`.

- [ ] **Passo 4: rodar e confirmar que passa**

Rodar: `cd frontend && npx vitest run src/app/ordens/`
Esperado: tudo verde, inclusive os testes que já existiam da página.

- [ ] **Passo 5: verificação completa do frontend**

Rodar: `cd frontend && npm run lint && npx tsc -b --noEmit && npm test`
Esperado: sem erros; todos os testes passando.

- [ ] **Passo 6: commitar**

```bash
git add frontend/src/app/ordens/OrdemDetailPage.tsx frontend/src/app/ordens/OrdemDetailPage.secoes.test.tsx
git commit -m "feat(manut): separa as secoes de certificado de calibracao e manutencao"
```

---

## Task 12: Aba do catálogo em Certificados

**Arquivos:**
- Criar: `frontend/src/app/certificados/ServicosManutencaoTab.tsx`, `frontend/src/app/certificados/ServicosManutencaoTab.test.tsx`
- Modificar: `frontend/src/app/certificados/CertificadosPage.tsx`

**Interfaces:**
- Consome: `manutencaoApi` (Task 7), `podeEditarConfigCertificado` e `podeExcluirCilindro` de `roles.ts` — **não** criar regra nova: cadastrar serviço tem exatamente o mesmo público que editar a configuração de certificado, e excluir tem o mesmo público de excluir cilindro.
- Produz: `<ServicosManutencaoTab />`.

- [ ] **Passo 1: escrever o teste que falha**

`frontend/src/app/certificados/ServicosManutencaoTab.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

let mockUser: { funcao: string } | null = { funcao: 'Laboratório' }
vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

const { listarServicos, criarServico, atualizarServico, excluirServico } = vi.hoisted(() => ({
  listarServicos: vi.fn(), criarServico: vi.fn(), atualizarServico: vi.fn(), excluirServico: vi.fn(),
}))
vi.mock('../ordens/manutencao', async (orig) => {
  const real = await orig<typeof import('../ordens/manutencao')>()
  return {
    ...real,
    manutencaoApi: { ...real.manutencaoApi, listarServicos, criarServico, atualizarServico, excluirServico },
  }
})

import { ServicosManutencaoTab } from './ServicosManutencaoTab'

describe('ServicosManutencaoTab', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Laboratório' }
    listarServicos.mockReset(); criarServico.mockReset(); atualizarServico.mockReset(); excluirServico.mockReset()
    listarServicos.mockResolvedValue([
      { id: 1, descricao: 'Troca da placa mãe', resumo_padrao: 'Placa substituída.', ativo: true },
      { id: 2, descricao: 'Serviço antigo', resumo_padrao: 'x.', ativo: false },
    ])
  })

  it('lista os serviços, mostrando os inativos como tal', async () => {
    render(<ServicosManutencaoTab />)
    expect(await screen.findByText('Troca da placa mãe')).toBeInTheDocument()
    expect(screen.getByText('Serviço antigo')).toBeInTheDocument()
    expect(screen.getByText('Inativo')).toBeInTheDocument()
  })

  it('laboratório cadastra um serviço novo', async () => {
    criarServico.mockResolvedValue({ id: 3, descricao: 'Troca do bocal', resumo_padrao: 'Bocal trocado.', ativo: true })
    render(<ServicosManutencaoTab />)
    await userEvent.click(await screen.findByText('Novo serviço'))
    fireEvent.change(screen.getByLabelText('Descrição'), { target: { value: 'Troca do bocal' } })
    fireEvent.change(screen.getByLabelText('Resumo padrão'), { target: { value: 'Bocal trocado.' } })
    await userEvent.click(screen.getByText('Salvar'))

    await waitFor(() => expect(criarServico).toHaveBeenCalledWith({
      descricao: 'Troca do bocal', resumo_padrao: 'Bocal trocado.',
    }))
  })

  it('laboratório não vê o botão de excluir', async () => {
    render(<ServicosManutencaoTab />)
    await screen.findByText('Troca da placa mãe')
    expect(screen.queryByLabelText('Excluir')).not.toBeInTheDocument()
  })

  it('administrador vê o botão de excluir', async () => {
    mockUser = { funcao: 'Administrador' }
    render(<ServicosManutencaoTab />)
    await screen.findByText('Troca da placa mãe')
    expect(screen.getAllByLabelText('Excluir').length).toBeGreaterThan(0)
  })
})
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `cd frontend && npx vitest run src/app/certificados/ServicosManutencaoTab.test.tsx`
Esperado: `Failed to resolve import "./ServicosManutencaoTab"`.

- [ ] **Passo 3: implementar a aba**

`frontend/src/app/certificados/ServicosManutencaoTab.tsx`:

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { IconButton, IconButtonGroup } from '../../components/ui/IconButton'
import { IconPencil, IconTrash } from '../../components/ui/icons'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { podeEditarConfigCertificado, podeExcluirCilindro } from '../../auth/roles'
import { manutencaoApi, type ServicoManutencao } from '../ordens/manutencao'

/** Catálogo fechado dos serviços que o Relatório de Manutenção aceita.
 *
 * Fica aqui, e não em Cadastros: aquela página inteira é fechada para
 * Administrador, e o Laboratório precisa cadastrar serviço. Mesmo público da
 * aba Configurações — por isso reaproveita `podeEditarConfigCertificado`. */
export function ServicosManutencaoTab() {
  const { user } = useAuth()
  const podeEditar = podeEditarConfigCertificado(user)
  const podeExcluir = podeExcluirCilindro(user)

  const [itens, setItens] = useState<ServicoManutencao[] | null>(null)
  const [erro, setErro] = useState('')
  const [aberto, setAberto] = useState(false)
  const [editando, setEditando] = useState<ServicoManutencao | null>(null)
  const [descricao, setDescricao] = useState('')
  const [resumoPadrao, setResumoPadrao] = useState('')
  const [ativo, setAtivo] = useState(true)
  const [erroForm, setErroForm] = useState('')
  const [salvando, setSalvando] = useState(false)

  function carregar() {
    setErro('')
    void manutencaoApi.listarServicos()
      .then(setItens)
      .catch((e) => { setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) })
  }

  useEffect(carregar, [])

  function abrirNovo() {
    setEditando(null); setDescricao(''); setResumoPadrao(''); setAtivo(true)
    setErroForm(''); setAberto(true)
  }

  function abrirEdicao(s: ServicoManutencao) {
    setEditando(s); setDescricao(s.descricao); setResumoPadrao(s.resumo_padrao); setAtivo(s.ativo)
    setErroForm(''); setAberto(true)
  }

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (!descricao.trim()) { setErroForm('Informe a descrição.'); return }
    setErroForm(''); setSalvando(true)
    try {
      if (editando) {
        await manutencaoApi.atualizarServico(editando.id, {
          descricao: descricao.trim(), resumo_padrao: resumoPadrao.trim(), ativo,
        })
      } else {
        await manutencaoApi.criarServico({ descricao: descricao.trim(), resumo_padrao: resumoPadrao.trim() })
      }
      setAberto(false)
      carregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar o serviço')
    } finally {
      setSalvando(false)
    }
  }

  async function excluir(s: ServicoManutencao) {
    if (!window.confirm(`Excluir o serviço "${s.descricao}"?\n\nSe ele já foi usado em algum relatório, desative em vez de excluir.`)) return
    try {
      await manutencaoApi.excluirServico(s.id)
      carregar()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao excluir')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">Serviços de manutenção</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            O relatório de manutenção só aceita serviços desta lista. O resumo padrão é a frase que entra no "Resumo do Serviço".
          </p>
        </div>
        {podeEditar && <Button onClick={abrirNovo}>Novo serviço</Button>}
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum serviço cadastrado ainda.</p>
      ) : (
        <Table head={<><TH>Serviço</TH><TH>Resumo padrão</TH><TH>Situação</TH><TH> </TH></>}>
          {itens.map((s) => (
            <tr key={s.id} className="hover:bg-background-elevated transition-colors">
              <TD>{s.descricao}</TD>
              <TD><span className="text-slate-400">{s.resumo_padrao || '—'}</span></TD>
              <TD>{s.ativo ? <Badge tone="primary">Ativo</Badge> : <Badge tone="neutral">Inativo</Badge>}</TD>
              <TD>
                <IconButtonGroup>
                  {podeEditar && (
                    <IconButton label="Editar" tone="neutro" onClick={() => abrirEdicao(s)}>
                      <IconPencil className="w-4 h-4" />
                    </IconButton>
                  )}
                  {podeExcluir && (
                    <IconButton label="Excluir" tone="perigo" onClick={() => void excluir(s)}>
                      <IconTrash className="w-4 h-4" />
                    </IconButton>
                  )}
                </IconButtonGroup>
              </TD>
            </tr>
          ))}
        </Table>
      )}

      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editando ? 'Editar serviço' : 'Novo serviço'}
          footer={
            <>
              <Button variant="secondary" type="button" onClick={() => setAberto(false)} disabled={salvando}>Cancelar</Button>
              <Button type="submit" form="form-servico-manut" disabled={salvando}>Salvar</Button>
            </>
          }
        >
          <form id="form-servico-manut" className="space-y-4" onSubmit={submeter}>
            <Input id="serv-descricao" label="Descrição" value={descricao}
                   onChange={(e) => setDescricao(e.target.value)} maxLength={200} />
            <div className="space-y-1">
              <label htmlFor="serv-resumo" className="block text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Resumo padrão
              </label>
              <textarea id="serv-resumo" rows={4} value={resumoPadrao}
                        onChange={(e) => setResumoPadrao(e.target.value)}
                        className="w-full rounded-lg bg-background border border-border px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary/40" />
            </div>
            {editando && (
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
                Ativo
              </label>
            )}
            {erroForm && <p className="text-sm text-danger">{erroForm}</p>}
          </form>
        </Modal>
      )}
    </div>
  )
}
```

- [ ] **Passo 4: registrar a aba**

Em `frontend/src/app/certificados/CertificadosPage.tsx`:

```tsx
import { ServicosManutencaoTab } from './ServicosManutencaoTab'
```

Acrescentar `'Serviços de manutenção'` ao fim do array `ABAS` e, junto das demais linhas de aba:

```tsx
        {aba === 'Serviços de manutenção' && <ServicosManutencaoTab />}
```

- [ ] **Passo 5: rodar e confirmar que passa**

Rodar: `cd frontend && npx vitest run src/app/certificados/ && npx tsc -b --noEmit`
Esperado: tudo verde.

- [ ] **Passo 6: commitar**

```bash
git add frontend/src/app/certificados/ServicosManutencaoTab.tsx frontend/src/app/certificados/ServicosManutencaoTab.test.tsx frontend/src/app/certificados/CertificadosPage.tsx
git commit -m "feat(manut): aba do catalogo de servicos em certificados"
```

---

## Task 13: Imagens e modelo HTML do relatório

**Arquivos:**
- Criar: `docs/certificado-manutencao/modelo-relatorio-manutencao.html` (a fonte versionada do modelo)

**Interfaces:**
- Consome: os tokens da Task 5.
- Produz: o HTML que será colado no sistema.

Esta tarefa produz um artefato para o Erick aplicar; nenhuma migração ou script escreve no banco de produção.

- [ ] **Passo 1: extrair as imagens do docx**

```bash
cd /tmp && rm -rf docx-manut && mkdir docx-manut && cd docx-manut && \
unzip -q "/home/ericks/github/GestorHS/docs/certificado-manutencao/FORM-LAB-010 RELATÓRIO DE MANUTENÇÃO - C4 - REV 02.docx" && \
ls -la word/media/
```

Esperado: `image1.jpeg` e `image2.jpeg` (~170×170, os dois selos ISO), `image3.png` (332×94, assinatura FIEMS/SENAI) e `image4.png` (2639×764, timbre do cabeçalho).

- [ ] **Passo 2: enviar as quatro imagens pelo sistema**

Pela tela: **Certificados › Imagens › enviar**, uma a uma. Anotar a URL devolvida por cada uma (formato `https://gestorhsapi.healthsafetytech.com/certificado-imagens/arquivo/<nome>`).

Não embutir as imagens no HTML como base64: o acervo existe justamente para isso, e um HTML com quatro imagens embutidas fica grande demais para editar na tela de Modelos.

- [ ] **Passo 3: escrever o modelo**

Criar `docs/certificado-manutencao/modelo-relatorio-manutencao.html` partindo do modelo de calibração do **Iblow10 PRO** (Certificados › Modelos › Código-fonte), que já traz cabeçalho, rodapé e o CSS de impressão em duas colunas que o Playwright renderiza bem.

Trocar, no que veio da calibração:

| No modelo de calibração | No de manutenção |
|---|---|
| código do documento | `FORM-LAB-010` |
| revisão | `Revisão: 02` |
| classificação | `Classificação: C4` |
| título | `Relatório de Manutenção` |
| corpo inteiro (seções 1–9) | as seções abaixo |

Estrutura do corpo, com os tokens:

```
RELATÓRIO DE MANUTENÇÃO
Nº [manutnumero]

Dados do Cliente
Cliente: [nomecli]
CNPJ: [cnpj]
Endereço: [endcli]

Dados do Equipamento
Equipamento: Bafômetro          Marca: [marca]
N° Série: [serie]               Modelo: [modelo]
Ordem Serviço: [os]             Data de venda: [datacompra]

Identificação da Manutenção
Data da Manutenção: [manutdata]
Local de Manutenção: Health & Safety
Endereço: Rua Viscondessa do Livramento, Nº 54. 3º andar - Sala G. Bairro: Derby. CEP: 52010-065. Recife-PE

Tipo do Problema: [manutproblema]
Resumo do Serviço: [manutresumo]

Comentários
Aparelho em Manutenção: cobertura das peças substituídas, caso ocorra, garantia de mão de obra de 90 dias.

<imagem da assinatura>
FIEMS / SENAI - Metrologia
```

⚠️ O texto de Comentários é o do **REV 02** (um parágrafo). Os dois parágrafos que aparecem nos PDFs são do formulário antigo e **não** entram.

- [ ] **Passo 4: cadastrar o modelo no sistema**

Em **Certificados › Modelos**, usar a entrada "Relatório de Manutenção" criada na Task 7 e colar o HTML no editor de código-fonte. É a mesma rota `PUT /certificados-modelo/generico?tipo=M`.

- [ ] **Passo 5: conferir o PDF**

Gerar o relatório numa OS de manutenção de teste e conferir:
- cabeçalho com `FORM-LAB-010`, `Revisão: 02`, `Classificação: C4` e `Título: Relatório de Manutenção`
- os quatro campos novos preenchidos
- "Tipo do Problema" com a lista composta corretamente (testar com dois serviços)
- o timbre, os dois selos ISO e a assinatura aparecendo
- **contagem de páginas** — o formulário é de 1 página; um resumo longo pode empurrar para 2, e o cabeçalho traz "Páginas: X de Y"

- [ ] **Passo 6: commitar o modelo**

```bash
git add docs/certificado-manutencao/modelo-relatorio-manutencao.html
git commit -m "docs(manut): modelo html do relatorio de manutencao"
```

---

## Task 14: Changelog e verificação final

**Arquivos:**
- Modificar: `frontend/src/app/changelog/data.ts`

- [ ] **Passo 1: rodar as duas suítes inteiras**

```bash
cd backend && source .venv/bin/activate && python -m pytest -q -p no:warnings
cd ../frontend && npm run lint && npx tsc -b --noEmit && npm test
```

Esperado: backend só com as 4 falhas de baseline; frontend inteiramente verde.

- [ ] **Passo 2: acrescentar a entrada do changelog**

No topo do array `CHANGELOG` em `frontend/src/app/changelog/data.ts`:

```ts
  {
    versao: '1.43.0',
    data: '21/08/2026',
    itens: [
      { tipo: 'novidade', texto: 'O Relatório de Manutenção agora sai do sistema. O Laboratório registra o que foi feito na bancada — número, data e os serviços executados — e gera o relatório em PDF, com o mesmo formulário padrão FORM-LAB-010 que era preenchido à mão.' },
      { tipo: 'novidade', texto: 'Os serviços saem de uma lista cadastrada em Certificados › Serviços de manutenção, e cada um traz um resumo padrão. Ao escolher os serviços, o resumo do relatório já vem escrito — o técnico só ajusta o que for específico daquele aparelho.' },
      { tipo: 'melhoria', texto: 'Na tela da OS, a seção "Certificados" virou duas: "Certificado de calibração" e "Certificado de manutenção". Aparece só a que o tipo de serviço da OS pedir, e uma OS de manutenção pura deixa de pedir certificado de calibração.' },
    ],
  },
```

- [ ] **Passo 3: conferir o changelog**

Rodar: `cd frontend && npx vitest run src/app/changelog && npx tsc -b --noEmit`
Esperado: verde.

- [ ] **Passo 4: commitar**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.43.0 — relatorio de manutencao"
```

---

## Depois do plano

Fica para o Erick, fora do escopo das tarefas:

1. **`alembic upgrade head`** em produção (migração `0027`) — antes do deploy do backend. As três tabelas nascem vazias e nada existente muda, então rodar antes é seguro.
2. **Cadastrar os serviços iniciais** em Certificados › Serviços de manutenção, com os resumos padrão. Os três relatórios de exemplo já dão quatro: troca de placa mãe, troca de pilha interna, troca do módulo Bluetooth e troca do botão liga/desliga.
3. **Confirmar com a Qualidade** que o REV 02 é mesmo o vigente e que o texto de Comentários é o de um parágrafo.
