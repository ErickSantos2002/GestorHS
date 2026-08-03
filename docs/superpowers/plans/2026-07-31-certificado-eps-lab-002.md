# Certificado EPS-LAB-002 com cálculo de incerteza — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emitir o certificado de calibração no formato EPS-LAB-002 da Qualidade, com 5 medições, erro por medição, incerteza expandida (k = 2) e rastreabilidade do cilindro de gás usado.

**Architecture:** A matemática vive num módulo puro (`core/certificado_calculo.py`), testável isolado e sem I/O, cujo teste de aceitação é a própria planilha da Qualidade. Os parâmetros do cálculo ficam numa tabela singleton (`certificado_config`) editável na aba Configurações, e os cilindros de gás numa tabela com vigência (`certificado_padrao`), de modo que regerar um certificado antigo mantenha o cilindro original. Os valores calculados **não** são persistidos — entram no HTML gerado, que já é o snapshot do documento emitido.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · pytest · React 19 · TypeScript · Vite 8 · Tailwind v4 · Vitest.

**Spec:** [`docs/superpowers/specs/2026-07-31-certificado-eps-lab-002-design.md`](../specs/2026-07-31-certificado-eps-lab-002-design.md)

## Global Constraints

- **Idioma do domínio é PT-BR.** Modelos, rotas, variáveis e mensagens em português. Mensagens de commit em português **sem acentos** (ASCII), uma linha só, sem corpo e sem trailer de co-autor.
- **Commits** seguem Conventional Commits: `tipo(escopo): descricao`. Escopo desta entrega: `cert`.
- **Testes de backend rodam em SQLite in-memory** (`tests/conftest.py`), via `Base.metadata.create_all` — **as migrações Alembic NÃO rodam nos testes**. Todo default de dado precisa existir no modelo, não só na migração.
- **Fixtures de autenticação são clients já autenticados**, não headers: `client_admin`, `client_lab`, `client_com`, `client_fin`, `client_exp` — todos injetam o `Authorization` no próprio `client`. Não existe fixture `auth_admin`/`auth_lab`; não invente uma. Um teste usa **um** desses clients, porque eles mutam o mesmo objeto `client`.
- **Fixtures de OS:** `os_base` (dict com `cliente` e `equipamento_cliente`), `os_no_lab` (id de OS em fase 5), `caixa_lab_com_calibracao`. Os testes de certificado montam a OS com helpers locais (`_os_com_modelo` em `test_certificado_os_api.py`, `_os_com_dados` em `test_certificado_contexto.py`) — reaproveitá-los em vez de criar outro.
- **`Numeric` no SQLite volta como `Decimal` com precisão imprevisível.** Em asserção de resposta JSON, comparar com `float(...)`, nunca com a string exata (`"0.1000"` pode vir `"0.1"`).
- **`core/certificado_calculo.py` é puro:** sem `Session`, sem import de `app.models`, sem I/O. É o que permite testar a matemática contra a planilha.
- **Arredondamento só na apresentação.** O cálculo roda com precisão de `float` cheia; a formatação é o último passo.
- **Números de referência da planilha** (teste de aceitação, 5 medições de 0,16 · referência 0,1 · resolução 0,1 · incerteza temp 0,052 · k 2): erro = `0.06` em todas · desvio padrão = `0.0` · `uc` = `0.06507431649019962` · `U` = `0.13014863298039925`.
- **Regra de função:** leitura da config é liberada a qualquer usuário interno (o modal precisa dos limites); escrita é **Administrador**. Espelhar em `frontend/src/auth/roles.ts` — o projeto exige os dois lados.
- **Nenhum token pode faltar em `_montar_contexto`.** Token ausente do contexto sai **literalmente escrito** no PDF do cliente.
- **Migração:** `0024`, `down_revision = "0023_caixa_numero_proposta"`.
- **Verificação de frontend antes de commitar:** `npm run lint && npx tsc -b --noEmit && npm run build`.

---

## Estrutura de arquivos

**Criar:**

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/core/certificado_calculo.py` | matemática pura: erro, desvio padrão, incerteza combinada e expandida, formatação |
| `backend/app/core/certificado_config.py` | acesso à config singleton e resolução do padrão vigente por data (toca `Session`) |
| `backend/app/models/certificado_config.py` | modelo `CertificadoConfig` |
| `backend/app/models/certificado_padrao.py` | modelo `CertificadoPadrao` |
| `backend/app/schemas/certificado_config.py` | schemas de config, padrão e prévia de cálculo |
| `backend/app/api/certificados_config.py` | router: config, CRUD de padrões, prévia de cálculo |
| `backend/alembic/versions/0024_certificado_config_padroes.py` | migração |
| `backend/tests/test_certificado_calculo.py` | matemática contra a planilha |
| `backend/tests/test_certificado_config.py` | singleton, vigência do padrão, API, 403 |
| `frontend/src/app/certificados/ConfiguracoesTab.tsx` | aba Configurações (parâmetros + padrões) |
| `frontend/src/app/certificados/ConfiguracoesTab.test.tsx` | teste da aba |
| `docs/modelo-certificado-eps-lab-002.html` | template de referência para o cadastro em Modelos |

**Modificar:**

| Arquivo | O quê |
|---|---|
| `backend/app/models/ordem.py` | `calib_teste4`, `calib_teste5`, `padrao_id` |
| `backend/app/models/equipamento_cliente.py` | `calib_teste4`, `calib_teste5` (espelho da frota) |
| `backend/app/models/__init__.py` | registrar os dois modelos novos |
| `backend/app/main.py` | `include_router(certificados_config.router)` |
| `backend/app/api/ordens_acoes.py` | `_CAMPOS_CALIB` ganha teste4/teste5 |
| `backend/app/api/certificados_os.py` | `_CAMPOS_CALIB`, gravar `padrao_id` ao gerar |
| `backend/app/schemas/ordens.py` | `GerarCertificadoIn` e `CertificadoCamposOut` ganham teste4/teste5 |
| `backend/app/core/certificado_gerar.py` | tokens novos em `CAMPOS` e em `_montar_contexto` |
| `backend/tests/test_certificado_os_api.py` | 5 medições gravadas, `padrao_id` |
| `backend/tests/test_certificado_contexto.py` | tokens novos, OS antiga, paridade OS/avulso |
| `frontend/src/lib/calibragem.ts` | `mediaTestes` variádica |
| `frontend/src/app/certificados/valoresCertificado.ts` | `t4`, `t5` |
| `frontend/src/app/certificados/CamposCertificado.tsx` | 5 medições, aviso fora de faixa, painel de prévia |
| `frontend/src/app/certificados/CertificadosPage.tsx` | aba Configurações |
| `frontend/src/app/certificados/api.ts` | `CAMPOS_CERTIFICADO` + endpoints de config, padrões e prévia |
| `frontend/src/auth/roles.ts` | `podeEditarConfigCertificado` |
| `frontend/src/app/changelog/data.ts` | entrada v1.37.0 |

---

## Task 1: Módulo puro de cálculo

**Files:**
- Create: `backend/app/core/certificado_calculo.py`
- Test: `backend/tests/test_certificado_calculo.py`

**Interfaces:**
- Consumes: nada (primeira task, sem dependências).
- Produces:
  - `ParametrosCalculo` — dataclass frozen: `valor_referencia: float | None`, `resolucao_instrumento: float | None`, `incerteza_padrao_temp: float | None`, `resolucao_pressao: float | None`, `incerteza_padrao_pressao: float | None`, `fator_k: float`
  - `ResultadoCalculo` — dataclass frozen: `medicoes: list[float]`, `erros: list[float | None]`, `media: float | None`, `desvio_padrao: float`, `incerteza_combinada: float`, `incerteza_expandida: float`, `fator_k: float`
  - `calcular(medicoes_texto: Sequence[str | None], parametros: ParametrosCalculo) -> ResultadoCalculo`
  - `formatar_numero(valor: float | None, casas: int = 4) -> str`
  - `desvio_padrao_amostral(medicoes: Sequence[float]) -> float`
  - `componente_retangular(valor: float | None) -> float`

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_certificado_calculo.py`:

```python
"""A planilha da Qualidade (docs/Certificado Iblow.xlsx, aba BASE DE CALCULO) e a
fonte da verdade destes numeros. Se um teste daqui falhar, a implementacao esta
errada — nao a planilha."""
import pytest

from app.core.certificado_calculo import (
    ParametrosCalculo,
    calcular,
    componente_retangular,
    desvio_padrao_amostral,
    formatar_numero,
)

# Parametros do exemplo da planilha: B1=0,1 / B10=0,1 / B11=0,052 / B12 e B13 vazios / k=2
PARAMS_PLANILHA = ParametrosCalculo(
    valor_referencia=0.1,
    resolucao_instrumento=0.1,
    incerteza_padrao_temp=0.052,
    resolucao_pressao=None,
    incerteza_padrao_pressao=None,
    fator_k=2.0,
)


def test_caso_da_planilha_bate_casa_por_casa():
    r = calcular(["0.16", "0.16", "0.16", "0.16", "0.16"], PARAMS_PLANILHA)
    assert r.erros == [pytest.approx(0.06)] * 5
    assert r.media == pytest.approx(0.16)
    assert r.desvio_padrao == pytest.approx(0.0)
    assert r.incerteza_combinada == pytest.approx(0.06507431649019962)
    assert r.incerteza_expandida == pytest.approx(0.13014863298039925)
    assert r.fator_k == 2.0


def test_desvio_padrao_e_amostral_nao_populacional():
    # amostral (n-1) de [0.15, 0.17] = 0.01414...; populacional seria 0.01
    assert desvio_padrao_amostral([0.15, 0.17]) == pytest.approx(0.014142135623730951)


def test_desvio_padrao_com_menos_de_duas_medicoes_e_zero():
    # STDEV do Excel sobre celula unica/vazia nao explode: aqui tambem nao
    assert desvio_padrao_amostral([]) == 0.0
    assert desvio_padrao_amostral([0.16]) == 0.0


def test_componente_vazio_contribui_zero():
    assert componente_retangular(None) == 0.0
    assert componente_retangular(0.1) == pytest.approx(0.057735026918962584)


def test_medicao_em_branco_e_ignorada_e_seu_erro_sai_none():
    # OS antiga: 3 medicoes preenchidas, 4 e 5 vazias. O erro das vazias e None
    # (sai em branco no certificado), nao -0.1.
    r = calcular(["0.16", "0.16", "0.16", "", None], PARAMS_PLANILHA)
    assert r.medicoes == [pytest.approx(0.16)] * 3
    assert r.erros == [pytest.approx(0.06), pytest.approx(0.06), pytest.approx(0.06), None, None]
    assert r.media == pytest.approx(0.16)


def test_aceita_virgula_como_separador_decimal():
    r = calcular(["0,16"], PARAMS_PLANILHA)
    assert r.medicoes == [pytest.approx(0.16)]


def test_texto_nao_numerico_e_tratado_como_branco():
    r = calcular(["0.16", "abc"], PARAMS_PLANILHA)
    assert r.medicoes == [pytest.approx(0.16)]
    assert r.erros == [pytest.approx(0.06), None]


def test_sem_medicao_nenhuma_nao_explode():
    r = calcular(["", "", "", "", ""], PARAMS_PLANILHA)
    assert r.medicoes == []
    assert r.erros == [None] * 5
    assert r.media is None
    assert r.desvio_padrao == 0.0
    # sem medicao, a incerteza vem so dos componentes fixos
    assert r.incerteza_combinada == pytest.approx(0.06507431649019962)


def test_sem_valor_de_referencia_nao_ha_erro_a_calcular():
    params = ParametrosCalculo(
        valor_referencia=None, resolucao_instrumento=0.1, incerteza_padrao_temp=0.052,
        resolucao_pressao=None, incerteza_padrao_pressao=None, fator_k=2.0,
    )
    r = calcular(["0.16"], params)
    assert r.erros == [None]


def test_formatar_numero_usa_virgula_e_corta_zero_a_direita():
    assert formatar_numero(0.13014863298039925) == "0,1301"
    assert formatar_numero(0.06) == "0,06"
    assert formatar_numero(0.16) == "0,16"
    assert formatar_numero(2.0) == "2"
    assert formatar_numero(None) == ""
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_calculo.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core.certificado_calculo'`

- [ ] **Step 3: Implementar o módulo**

Criar `backend/app/core/certificado_calculo.py`:

```python
"""Matematica do certificado de calibracao — espelha a aba BASE DE CALCULO da
planilha da Qualidade (docs/Certificado Iblow.xlsx).

Modulo PURO: sem Session, sem I/O, sem import de app.models. E o que permite
testar as formulas contra a planilha isoladamente.
"""
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

# Divisor da distribuicao retangular usado em cada componente de incerteza
# (na planilha, o /SQRT(3) das celulas C10:C13).
_RAIZ_3 = math.sqrt(3)


@dataclass(frozen=True)
class ParametrosCalculo:
    """Os valores da aba Configuracoes que entram no calculo."""
    valor_referencia: float | None
    resolucao_instrumento: float | None
    incerteza_padrao_temp: float | None
    resolucao_pressao: float | None
    incerteza_padrao_pressao: float | None
    fator_k: float


@dataclass(frozen=True)
class ResultadoCalculo:
    medicoes: list[float]            # so as medicoes validas
    erros: list[float | None]        # alinhado com a ENTRADA: None onde estava em branco
    media: float | None
    desvio_padrao: float
    incerteza_combinada: float
    incerteza_expandida: float
    fator_k: float


def _para_float(valor: str | float | None) -> float | None:
    """Texto do formulario -> float. Aceita virgula decimal. Branco/lixo -> None."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def componente_retangular(valor: float | None) -> float:
    """Componente de incerteza tipo B, distribuicao retangular: valor / sqrt(3).

    Componente ausente contribui ZERO, nao erro — B12/B13 estao vazias na planilha
    e entram como zero na SUMSQ.
    """
    if valor is None:
        return 0.0
    return valor / _RAIZ_3


def desvio_padrao_amostral(medicoes: Sequence[float]) -> float:
    """Desvio padrao AMOSTRAL (n-1) — e o que a funcao STDEV do Excel calcula.

    Com pstdev (populacional) os numeros da planilha nao batem. Com menos de duas
    medicoes retorna 0, em vez de estourar como statistics.stdev faria — o Excel
    tambem trata celula vazia como zero aqui.
    """
    if len(medicoes) < 2:
        return 0.0
    return statistics.stdev(medicoes)


def calcular(medicoes_texto: Sequence[str | None], parametros: ParametrosCalculo) -> ResultadoCalculo:
    valores = [_para_float(m) for m in medicoes_texto]
    medicoes = [v for v in valores if v is not None]

    ref = parametros.valor_referencia
    erros: list[float | None] = [
        None if (v is None or ref is None) else v - ref for v in valores
    ]

    media = statistics.fmean(medicoes) if medicoes else None
    desvio = desvio_padrao_amostral(medicoes)

    componentes = [
        componente_retangular(parametros.resolucao_instrumento),
        componente_retangular(parametros.incerteza_padrao_temp),
        componente_retangular(parametros.resolucao_pressao),
        componente_retangular(parametros.incerteza_padrao_pressao),
    ]
    # uc = sqrt(u_medicao^2 + SUMSQ(componentes))  — celula B15 da planilha
    uc = math.sqrt(desvio**2 + sum(c**2 for c in componentes))
    # U = uc * k  — celula B16
    expandida = uc * parametros.fator_k

    return ResultadoCalculo(
        medicoes=medicoes,
        erros=erros,
        media=media,
        desvio_padrao=desvio,
        incerteza_combinada=uc,
        incerteza_expandida=expandida,
        fator_k=parametros.fator_k,
    )


def formatar_numero(valor: float | None, casas: int = 4) -> str:
    """Numero -> texto do certificado, em PT-BR, sem zeros inuteis a direita.

    ULTIMO passo do pipeline: o calculo roda com precisao cheia e so aqui arredonda.
    Arredondar no meio muda o U na terceira casa.
    """
    if valor is None:
        return ""
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    if texto in ("", "-"):
        texto = "0"
    return texto.replace(".", ",")
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_calculo.py -v`
Expected: PASS — 11 testes.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/certificado_calculo.py backend/tests/test_certificado_calculo.py
git commit -m "feat(cert): modulo puro de calculo de incerteza espelhando a planilha da qualidade"
```

---

## Task 2: Modelos, migração e acesso à configuração

**Files:**
- Create: `backend/app/models/certificado_config.py`, `backend/app/models/certificado_padrao.py`, `backend/app/core/certificado_config.py`, `backend/alembic/versions/0024_certificado_config_padroes.py`, `backend/tests/test_certificado_config.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/models/ordem.py`, `backend/app/models/equipamento_cliente.py`

**Interfaces:**
- Consumes: `ParametrosCalculo` de `app.core.certificado_calculo` (Task 1).
- Produces:
  - `CertificadoConfig` — modelo com as colunas da tabela abaixo
  - `CertificadoPadrao` — modelo com as colunas da tabela abaixo
  - `obter_config(db: Session) -> CertificadoConfig` — singleton, cria com os defaults se não existir
  - `parametros_de(config: CertificadoConfig) -> ParametrosCalculo`
  - `padrao_vigente(db: Session, data: date | None) -> CertificadoPadrao | None`
  - `Ordem.calib_teste4`, `Ordem.calib_teste5`, `Ordem.padrao_id`
  - `EquipamentoCliente.calib_teste4`, `EquipamentoCliente.calib_teste5`

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_certificado_config.py`:

```python
from datetime import date

from app.core.certificado_config import obter_config, padrao_vigente, parametros_de
from app.models import CertificadoPadrao


def test_config_e_singleton_e_nasce_com_os_valores_da_planilha(db_session):
    c1 = obter_config(db_session)
    assert float(c1.valor_referencia) == 0.1
    assert float(c1.limite_minimo) == 0.15
    assert float(c1.limite_maximo) == 0.19
    assert float(c1.resolucao_instrumento) == 0.1
    assert float(c1.incerteza_padrao_temp) == 0.052
    assert float(c1.fator_k) == 2
    assert c1.tecnico_nome == "Walbert Santos"

    # segunda chamada devolve a MESMA linha — nao cria outra
    c2 = obter_config(db_session)
    assert c2.id == c1.id
    assert db_session.query(type(c1)).count() == 1


def test_parametros_de_converte_decimal_para_float(db_session):
    p = parametros_de(obter_config(db_session))
    assert p.valor_referencia == 0.1
    assert p.resolucao_instrumento == 0.1
    assert p.incerteza_padrao_temp == 0.052
    assert p.resolucao_pressao is None
    assert p.fator_k == 2.0


def _padrao(db, **kw):
    dados = dict(
        numero_cilindro="CC747704", numero_certificado="202231419",
        concentracao=100.1, incerteza_concentracao=2.0, unidade="µmol/mol",
        vigencia_inicio=date(2025, 1, 1), vigencia_fim=None, ativo=True,
    )
    dados.update(kw)
    obj = CertificadoPadrao(**dados)
    db.add(obj)
    db.commit()
    return obj


def test_padrao_vigente_resolve_pela_data(db_session):
    antigo = _padrao(db_session, numero_cilindro="ANTIGO",
                     vigencia_inicio=date(2024, 1, 1), vigencia_fim=date(2024, 12, 31))
    atual = _padrao(db_session, vigencia_inicio=date(2025, 1, 1), vigencia_fim=None)

    assert padrao_vigente(db_session, date(2024, 6, 1)).id == antigo.id
    assert padrao_vigente(db_session, date(2026, 6, 1)).id == atual.id


def test_padrao_vigente_sem_correspondencia_devolve_none(db_session):
    # OS antiga, anterior a qualquer cilindro cadastrado: nao inventa padrao
    _padrao(db_session, vigencia_inicio=date(2025, 1, 1))
    assert padrao_vigente(db_session, date(2020, 1, 1)) is None
    assert padrao_vigente(db_session, None) is None


def test_padrao_inativo_e_ignorado(db_session):
    _padrao(db_session, ativo=False)
    assert padrao_vigente(db_session, date(2026, 1, 1)) is None


def test_ordem_tem_as_colunas_novas(db_session):
    from app.models import Ordem
    assert hasattr(Ordem, "calib_teste4")
    assert hasattr(Ordem, "calib_teste5")
    assert hasattr(Ordem, "padrao_id")


def test_equipamento_cliente_tem_as_colunas_novas():
    from app.models import EquipamentoCliente
    assert hasattr(EquipamentoCliente, "calib_teste4")
    assert hasattr(EquipamentoCliente, "calib_teste5")
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_config.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core.certificado_config'`

- [ ] **Step 3: Criar o modelo `CertificadoConfig`**

Criar `backend/app/models/certificado_config.py`:

```python
from sqlalchemy import Column, Integer, Numeric, String, Text

from app.models.database import Base


class CertificadoConfig(Base):
    """Parametros globais do certificado de calibracao — linha UNICA (singleton).

    Os defaults sao os valores da planilha EPS-LAB-002 enviada pela Qualidade.
    Ficam aqui, no modelo, e nao so na migracao, porque os testes criam o schema
    com Base.metadata.create_all — a migracao nao roda neles.
    """
    __tablename__ = "certificado_config"

    id = Column(Integer, primary_key=True, index=True)
    # parametros do calculo
    valor_referencia = Column(Numeric(10, 4), nullable=True, default=0.1)
    limite_minimo = Column(Numeric(10, 4), nullable=True, default=0.15)
    limite_maximo = Column(Numeric(10, 4), nullable=True, default=0.19)
    resolucao_instrumento = Column(Numeric(10, 4), nullable=True, default=0.1)
    incerteza_padrao_temp = Column(Numeric(10, 4), nullable=True, default=0.052)
    resolucao_pressao = Column(Numeric(10, 4), nullable=True)
    incerteza_padrao_pressao = Column(Numeric(10, 4), nullable=True)
    fator_k = Column(Numeric(4, 2), nullable=True, default=2)
    # identidade do laboratorio
    tecnico_nome = Column(String(100), nullable=True, default="Walbert Santos")
    tecnico_cargo = Column(String(100), nullable=True, default="Técnico em Metrologia")
    equipamentos_auxiliares = Column(Text, nullable=True)
    margem_temperatura = Column(String(50), nullable=True, default="20 ºC ~ 24 ºC")
```

- [ ] **Step 4: Criar o modelo `CertificadoPadrao`**

Criar `backend/app/models/certificado_padrao.py`:

```python
from sqlalchemy import Boolean, Column, Date, Integer, Numeric, String

from app.models.database import Base


class CertificadoPadrao(Base):
    """Cilindro de gas padrao usado na calibracao, com vigencia.

    A OS grava qual cilindro foi usado (ordens.padrao_id), para que regerar um
    certificado antigo mantenha a rastreabilidade correta em vez de apontar para
    o cilindro que estiver em uso hoje.
    """
    __tablename__ = "certificado_padrao"

    id = Column(Integer, primary_key=True, index=True)
    numero_cilindro = Column(String(50), nullable=False)
    numero_certificado = Column(String(50), nullable=True)
    concentracao = Column(Numeric(10, 4), nullable=True)
    incerteza_concentracao = Column(Numeric(10, 4), nullable=True)
    unidade = Column(String(20), nullable=True, default="µmol/mol")
    vigencia_inicio = Column(Date, nullable=True)
    vigencia_fim = Column(Date, nullable=True)   # nulo = ainda vigente
    ativo = Column(Boolean, nullable=False, default=True)
```

- [ ] **Step 5: Registrar os modelos e adicionar as colunas novas**

Em `backend/app/models/__init__.py`, adicionar os imports depois de `from app.models.certificado_geral import CertificadoGeral`:

```python
from app.models.certificado_config import CertificadoConfig
from app.models.certificado_padrao import CertificadoPadrao
```

e acrescentar `"CertificadoConfig", "CertificadoPadrao",` ao `__all__`, na linha que já tem `"TransferenciaEquipamento", "CertificadoAvulso", "CertificadoVenda", "CertificadoGeral",`.

Em `backend/app/models/ordem.py`, logo após a linha `calib_teste3 = Column(String(50), nullable=True)`:

```python
    calib_teste4 = Column(String(50), nullable=True)
    calib_teste5 = Column(String(50), nullable=True)
```

e depois de `cert_overrides = Column(JSON, nullable=True)`:

```python
    # cilindro de gas usado nesta calibracao — gravado na geracao para que regerar
    # o certificado no futuro nao troque o padrao pelo que estiver vigente entao
    padrao_id = Column(Integer, ForeignKey("certificado_padrao.id"), nullable=True)
```

Em `backend/app/models/equipamento_cliente.py`, logo após `calib_teste3 = Column(String(50), nullable=True)`:

```python
    calib_teste4 = Column(String(50), nullable=True)
    calib_teste5 = Column(String(50), nullable=True)
```

- [ ] **Step 6: Criar `core/certificado_config.py`**

Criar `backend/app/core/certificado_config.py`:

```python
"""Acesso a configuracao do certificado e ao padrao (cilindro) vigente.

Toca a Session — por isso fica separado de certificado_calculo.py, que e puro.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.core.certificado_calculo import ParametrosCalculo
from app.models import CertificadoConfig, CertificadoPadrao


def _f(valor) -> float | None:
    """Numeric do SQLAlchemy volta como Decimal — o calculo trabalha em float."""
    return None if valor is None else float(valor)


def obter_config(db: Session) -> CertificadoConfig:
    """A linha unica de configuracao, criando-a com os defaults se ainda nao existir.

    Criar sob demanda e o que mantem o singleton verdadeiro nos dois mundos: em
    producao a migracao 0024 ja insere a linha; nos testes, que montam o schema com
    create_all e sem migracao, ela nasce aqui.
    """
    config = db.query(CertificadoConfig).order_by(CertificadoConfig.id).first()
    if config is None:
        config = CertificadoConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def parametros_de(config: CertificadoConfig) -> ParametrosCalculo:
    return ParametrosCalculo(
        valor_referencia=_f(config.valor_referencia),
        resolucao_instrumento=_f(config.resolucao_instrumento),
        incerteza_padrao_temp=_f(config.incerteza_padrao_temp),
        resolucao_pressao=_f(config.resolucao_pressao),
        incerteza_padrao_pressao=_f(config.incerteza_padrao_pressao),
        fator_k=_f(config.fator_k) or 2.0,
    )


def padrao_vigente(db: Session, data: date | None) -> CertificadoPadrao | None:
    """O cilindro ativo cuja vigencia contem `data`. Sem correspondencia -> None.

    Devolver None em vez de cair no cilindro atual e deliberado: preencher um
    certificado de 2024 com o cilindro de 2026 seria rastreabilidade falsa.
    """
    if data is None:
        return None
    return (
        db.query(CertificadoPadrao)
        .filter(
            CertificadoPadrao.ativo.is_(True),
            CertificadoPadrao.vigencia_inicio <= data,
            (CertificadoPadrao.vigencia_fim.is_(None)) | (CertificadoPadrao.vigencia_fim >= data),
        )
        .order_by(CertificadoPadrao.vigencia_inicio.desc())
        .first()
    )
```

- [ ] **Step 7: Rodar os testes para confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_config.py -v`
Expected: PASS — 7 testes.

- [ ] **Step 8: Criar a migração**

Criar `backend/alembic/versions/0024_certificado_config_padroes.py`:

```python
"""certificado: tabelas de configuracao e de padroes (cilindros), 5 medicoes na OS"""
import sqlalchemy as sa
from alembic import op

revision = "0024_certificado_config_padroes"
down_revision = "0023_caixa_numero_proposta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    config = op.create_table(
        "certificado_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("valor_referencia", sa.Numeric(10, 4), nullable=True),
        sa.Column("limite_minimo", sa.Numeric(10, 4), nullable=True),
        sa.Column("limite_maximo", sa.Numeric(10, 4), nullable=True),
        sa.Column("resolucao_instrumento", sa.Numeric(10, 4), nullable=True),
        sa.Column("incerteza_padrao_temp", sa.Numeric(10, 4), nullable=True),
        sa.Column("resolucao_pressao", sa.Numeric(10, 4), nullable=True),
        sa.Column("incerteza_padrao_pressao", sa.Numeric(10, 4), nullable=True),
        sa.Column("fator_k", sa.Numeric(4, 2), nullable=True),
        sa.Column("tecnico_nome", sa.String(100), nullable=True),
        sa.Column("tecnico_cargo", sa.String(100), nullable=True),
        sa.Column("equipamentos_auxiliares", sa.Text(), nullable=True),
        sa.Column("margem_temperatura", sa.String(50), nullable=True),
    )
    # linha unica com os valores da planilha EPS-LAB-002 como ponto de partida
    op.bulk_insert(config, [{
        "id": 1,
        "valor_referencia": 0.1,
        "limite_minimo": 0.15,
        "limite_maximo": 0.19,
        "resolucao_instrumento": 0.1,
        "incerteza_padrao_temp": 0.052,
        "resolucao_pressao": None,
        "incerteza_padrao_pressao": None,
        "fator_k": 2,
        "tecnico_nome": "Walbert Santos",
        "tecnico_cargo": "Técnico em Metrologia",
        "equipamentos_auxiliares": (
            "• TESTO 622 - Monitorização de ambientes científicos - Termo-Higrômetro "
            "digital 39533693 - Certificado: 95239/1, 95239/2 e LV06079-33193-22-R0."
        ),
        "margem_temperatura": "20 ºC ~ 24 ºC",
    }])

    op.create_table(
        "certificado_padrao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero_cilindro", sa.String(50), nullable=False),
        sa.Column("numero_certificado", sa.String(50), nullable=True),
        sa.Column("concentracao", sa.Numeric(10, 4), nullable=True),
        sa.Column("incerteza_concentracao", sa.Numeric(10, 4), nullable=True),
        sa.Column("unidade", sa.String(20), nullable=True),
        sa.Column("vigencia_inicio", sa.Date(), nullable=True),
        sa.Column("vigencia_fim", sa.Date(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.add_column("ordens", sa.Column("calib_teste4", sa.String(50), nullable=True))
    op.add_column("ordens", sa.Column("calib_teste5", sa.String(50), nullable=True))
    op.add_column("ordens", sa.Column("padrao_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_ordens_padrao_id", "ordens", "certificado_padrao", ["padrao_id"], ["id"]
    )

    op.add_column("equipamentos_cliente", sa.Column("calib_teste4", sa.String(50), nullable=True))
    op.add_column("equipamentos_cliente", sa.Column("calib_teste5", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("equipamentos_cliente", "calib_teste5")
    op.drop_column("equipamentos_cliente", "calib_teste4")
    op.drop_constraint("fk_ordens_padrao_id", "ordens", type_="foreignkey")
    op.drop_column("ordens", "padrao_id")
    op.drop_column("ordens", "calib_teste5")
    op.drop_column("ordens", "calib_teste4")
    op.drop_table("certificado_padrao")
    op.drop_table("certificado_config")
```

**Não aplicar a migração agora.** O `DATABASE_URL` desta máquina aponta para o banco de **produção**. O `alembic upgrade head` é passo de deploy, combinado com o Erick — não parte da implementação.

- [ ] **Step 9: Rodar a suíte inteira e comparar com a baseline**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: os testes novos passam. **Baseline medida nesta máquina em 03/08/2026: `4 failed, 909 passed`.** As 4 falhas são `PermissionError` de filesystem em `test_certificados_gerais.py` (2) e `test_publico_certificado_geral.py` (2) — não são regressão. Qualquer falha além dessas quatro é problema desta task.

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/certificado_config.py backend/app/models/certificado_padrao.py \
        backend/app/models/__init__.py backend/app/models/ordem.py \
        backend/app/models/equipamento_cliente.py backend/app/core/certificado_config.py \
        backend/alembic/versions/0024_certificado_config_padroes.py \
        backend/tests/test_certificado_config.py
git commit -m "feat(cert): tabelas de configuracao e padroes de calibracao com 5 medicoes na os"
```

---

## Task 3: API de configuração, padrões e prévia de cálculo

**Files:**
- Create: `backend/app/schemas/certificado_config.py`, `backend/app/api/certificados_config.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_certificado_config.py` (acrescentar)

**Interfaces:**
- Consumes: `obter_config`, `parametros_de`, `padrao_vigente` (Task 2); `calcular`, `formatar_numero` (Task 1).
- Produces:
  - `GET /certificado-config` → `CertificadoConfigOut` (qualquer usuário interno)
  - `PUT /certificado-config` → `CertificadoConfigOut` (Administrador)
  - `GET /certificado-padroes` → `list[CertificadoPadraoOut]` (qualquer usuário interno)
  - `POST /certificado-padroes` → `CertificadoPadraoOut` 201 (Administrador)
  - `PATCH /certificado-padroes/{padrao_id}` → `CertificadoPadraoOut` (Administrador)
  - `DELETE /certificado-padroes/{padrao_id}` → 204 (Administrador)
  - `POST /certificado-calculo-previa` → `CalculoPreviaOut` (qualquer usuário interno)

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `backend/tests/test_certificado_config.py`:

```python
def test_get_config_devolve_os_valores(client_admin):
    r = client_admin.get("/certificado-config")
    assert r.status_code == 200
    # Numeric no SQLite volta como Decimal de precisao imprevisivel: comparar em float
    assert float(r.json()["valor_referencia"]) == 0.1
    assert r.json()["tecnico_nome"] == "Walbert Santos"


def test_put_config_grava_e_continua_singleton(client_admin, db_session):
    from app.models import CertificadoConfig
    r = client_admin.put("/certificado-config", json={
        "valor_referencia": "0.17", "limite_minimo": "0.15", "limite_maximo": "0.19",
        "resolucao_instrumento": "0.01", "incerteza_padrao_temp": "0.052",
        "resolucao_pressao": None, "incerteza_padrao_pressao": None, "fator_k": "2",
        "tecnico_nome": "Outro Tecnico", "tecnico_cargo": "Tecnico em Metrologia",
        "equipamentos_auxiliares": "TESTO 622", "margem_temperatura": "20 ºC ~ 24 ºC",
    })
    assert r.status_code == 200
    assert r.json()["tecnico_nome"] == "Outro Tecnico"
    assert float(r.json()["resolucao_instrumento"]) == 0.01
    assert db_session.query(CertificadoConfig).count() == 1


def test_put_config_negado_para_nao_admin(client_lab):
    r = client_lab.put("/certificado-config", json={"tecnico_nome": "X"})
    assert r.status_code == 403


def test_lab_le_a_config_para_o_modal(client_lab):
    # o modal precisa dos limites para destacar medicao fora da faixa
    assert client_lab.get("/certificado-config").status_code == 200


def test_crud_de_padroes(client_admin):
    r = client_admin.post("/certificado-padroes", json={
        "numero_cilindro": "CC747704", "numero_certificado": "202231419",
        "concentracao": "100.1", "incerteza_concentracao": "2.0",
        "unidade": "µmol/mol", "vigencia_inicio": "2025-01-01",
        "vigencia_fim": None, "ativo": True,
    })
    assert r.status_code == 201
    padrao_id = r.json()["id"]

    assert len(client_admin.get("/certificado-padroes").json()) == 1

    r = client_admin.patch(f"/certificado-padroes/{padrao_id}", json={"vigencia_fim": "2026-12-31"})
    assert r.status_code == 200
    assert r.json()["vigencia_fim"] == "2026-12-31"

    assert client_admin.delete(f"/certificado-padroes/{padrao_id}").status_code == 204
    assert client_admin.get("/certificado-padroes").json() == []


def test_criar_padrao_negado_para_nao_admin(client_lab):
    r = client_lab.post("/certificado-padroes", json={"numero_cilindro": "X"})
    assert r.status_code == 403


def test_previa_de_calculo_devolve_os_numeros_da_planilha(client_lab):
    r = client_lab.post("/certificado-calculo-previa",
                        json={"medicoes": ["0.16", "0.16", "0.16", "0.16", "0.16"]})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["erros"] == ["0,06"] * 5
    assert corpo["media"] == "0,16"
    assert corpo["incerteza_expandida"] == "0,1301"
    assert corpo["fator_k"] == "2"
    assert corpo["limite_minimo"] == "0,15"
    assert corpo["limite_maximo"] == "0,19"
    assert corpo["fora_da_faixa"] == [False] * 5


def test_previa_marca_medicao_fora_da_faixa(client_lab):
    r = client_lab.post("/certificado-calculo-previa",
                        json={"medicoes": ["0.16", "0.016", "", "", ""]})
    assert r.json()["fora_da_faixa"] == [False, True, False, False, False]
    # medicao em branco nao e "fora da faixa" — e ausencia de medicao
    assert r.json()["erros"][2] == ""
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_config.py -v`
Expected: FAIL — 404 nas rotas novas (o router ainda não existe).

- [ ] **Step 3: Criar os schemas**

Criar `backend/app/schemas/certificado_config.py`:

```python
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CertificadoConfigIn(BaseModel):
    valor_referencia: Decimal | None = None
    limite_minimo: Decimal | None = None
    limite_maximo: Decimal | None = None
    resolucao_instrumento: Decimal | None = None
    incerteza_padrao_temp: Decimal | None = None
    resolucao_pressao: Decimal | None = None
    incerteza_padrao_pressao: Decimal | None = None
    fator_k: Decimal | None = None
    tecnico_nome: str | None = None
    tecnico_cargo: str | None = None
    equipamentos_auxiliares: str | None = None
    margem_temperatura: str | None = None


class CertificadoConfigOut(CertificadoConfigIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CertificadoPadraoIn(BaseModel):
    numero_cilindro: str = Field(min_length=1)
    numero_certificado: str | None = None
    concentracao: Decimal | None = None
    incerteza_concentracao: Decimal | None = None
    unidade: str | None = "µmol/mol"
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    ativo: bool = True


class CertificadoPadraoUpdate(BaseModel):
    numero_cilindro: str | None = None
    numero_certificado: str | None = None
    concentracao: Decimal | None = None
    incerteza_concentracao: Decimal | None = None
    unidade: str | None = None
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    ativo: bool | None = None


class CertificadoPadraoOut(CertificadoPadraoIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CalculoPreviaIn(BaseModel):
    medicoes: list[str | None] = Field(default_factory=list)


class CalculoPreviaOut(BaseModel):
    """Tudo em texto ja formatado em PT-BR: a tela apenas exibe, nao recalcula nada."""
    erros: list[str]
    media: str
    desvio_padrao: str
    incerteza_combinada: str
    incerteza_expandida: str
    fator_k: str
    limite_minimo: str
    limite_maximo: str
    fora_da_faixa: list[bool]
```

- [ ] **Step 4: Criar o router**

Criar `backend/app/api/certificados_config.py`:

```python
"""Configuracao do certificado (linha unica) e cadastro dos padroes (cilindros).

Leitura liberada a qualquer usuario interno — o modal de gerar certificado precisa
dos limites para destacar medicao fora da faixa. Escrita e so do Administrador:
sao os numeros que definem a incerteza de todo certificado emitido.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario, require_funcao
from app.core.certificado_calculo import calcular, formatar_numero
from app.core.certificado_config import obter_config, parametros_de
from app.models import CertificadoPadrao, Usuario
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
    for chave, valor in dados.model_dump(exclude_unset=True).items():
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
    db.delete(_padrao_ou_404(db, padrao_id))
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
        erros=[formatar_numero(e) for e in resultado.erros],
        media=formatar_numero(resultado.media),
        desvio_padrao=formatar_numero(resultado.desvio_padrao),
        incerteza_combinada=formatar_numero(resultado.incerteza_combinada),
        incerteza_expandida=formatar_numero(resultado.incerteza_expandida),
        fator_k=formatar_numero(resultado.fator_k, casas=2),
        limite_minimo=formatar_numero(minimo),
        limite_maximo=formatar_numero(maximo),
        fora_da_faixa=fora,
    )
```

- [ ] **Step 5: Registrar o router**

Em `backend/app/main.py`, adicionar `certificados_config` ao import dos routers de `app.api` e, junto das outras linhas de certificado (depois de `app.include_router(certificados_gerais.router)`):

```python
app.include_router(certificados_config.router)
```

- [ ] **Step 6: Rodar os testes para confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_config.py -v`
Expected: PASS — todos.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/certificado_config.py backend/app/api/certificados_config.py \
        backend/app/main.py backend/tests/test_certificado_config.py
git commit -m "feat(cert): api de configuracao, padroes e previa de calculo do certificado"
```

---

## Task 4: Cinco medições no fluxo da OS

**Files:**
- Modify: `backend/app/schemas/ordens.py`, `backend/app/api/certificados_os.py`, `backend/app/api/ordens_acoes.py`
- Test: `backend/tests/test_certificado_os_api.py` (acrescentar)

**Interfaces:**
- Consumes: `padrao_vigente` (Task 2); colunas `calib_teste4/5`, `padrao_id` (Task 2).
- Produces: `GerarCertificadoIn.calib_teste4/calib_teste5`, `CertificadoCamposOut.calib_teste4/calib_teste5`, e `ordens.padrao_id` gravado na geração.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `backend/tests/test_certificado_os_api.py`, reaproveitando os helpers locais `_headers` e `_os_com_modelo` que já existem no arquivo:

```python
def test_gerar_grava_as_cinco_medicoes_e_o_padrao_vigente(client, usuario_admin, db_session):
    from datetime import date
    from app.models import CertificadoPadrao, Ordem

    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")

    padrao = CertificadoPadrao(
        numero_cilindro="CC747704", numero_certificado="202231419",
        concentracao=100.1, incerteza_concentracao=2.0, unidade="µmol/mol",
        vigencia_inicio=date(2020, 1, 1), vigencia_fim=None, ativo=True,
    )
    db_session.add(padrao)
    db_session.commit()

    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h, json={
        "data_calibracao": "2026-07-31",
        "calib_teste1": "0.16", "calib_teste2": "0.16", "calib_teste3": "0.16",
        "calib_teste4": "0.16", "calib_teste5": "0.16",
    })
    assert r.status_code == 200

    ordem = db_session.query(Ordem).filter(Ordem.id == oid).first()
    assert ordem.calib_teste4 == "0.16"
    assert ordem.calib_teste5 == "0.16"
    assert ordem.padrao_id == padrao.id


def test_gerar_sem_padrao_cadastrado_grava_none_e_nao_falha(client, usuario_admin, db_session):
    from app.models import Ordem
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")

    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h, json={
        "data_calibracao": "2026-07-31", "calib_teste1": "0.16",
    })
    assert r.status_code == 200
    ordem = db_session.query(Ordem).filter(Ordem.id == oid).first()
    assert ordem.padrao_id is None


def test_certificado_campos_devolve_as_cinco_medicoes(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    corpo = client.get(f"/ordens/{oid}/certificado-campos", headers=h).json()
    assert "calib_teste4" in corpo
    assert "calib_teste5" in corpo
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_os_api.py -v`
Expected: FAIL — `calib_teste4` é ignorado pelo schema / `padrao_id` fica `None` no primeiro teste.

- [ ] **Step 3: Ampliar os schemas**

Em `backend/app/schemas/ordens.py`, dentro de `GerarCertificadoIn`, depois de `calib_teste3: str | None = None`:

```python
    calib_teste4: str | None = None
    calib_teste5: str | None = None
```

E o mesmo dentro de `CertificadoCamposOut`, depois de `calib_teste3: str | None = None`.

- [ ] **Step 4: Ampliar as tuplas de campos e gravar o padrão**

Em `backend/app/api/certificados_os.py`, trocar `_CAMPOS_CALIB` por:

```python
_CAMPOS_CALIB = (
    "calib_cert", "calib_temp", "calib_pressao",
    "calib_teste1", "calib_teste2", "calib_teste3", "calib_teste4", "calib_teste5",
    "calib_teste_media", "calib_situacao",
)
```

Acrescentar o import no topo do arquivo:

```python
from app.core.certificado_config import padrao_vigente
```

Em `certificado_campos`, acrescentar ao `CertificadoCamposOut(...)`, junto dos outros testes:

```python
        calib_teste4=ordem.calib_teste4, calib_teste5=ordem.calib_teste5,
```

Em `gerar`, dentro do bloco `if dados is not None:`, logo depois do `elif ordem.data_calibracao is None: ordem.data_calibracao = agora()` e antes do `overrides = ...`:

```python
        # Congela o cilindro usado NESTA calibracao. Sem isso, regerar o certificado
        # meses depois apontaria para o cilindro vigente naquele momento — rastreabilidade
        # falsa num documento da Qualidade.
        data_ref = ordem.data_calibracao.date() if ordem.data_calibracao else None
        padrao = padrao_vigente(db, data_ref)
        ordem.padrao_id = padrao.id if padrao else None
```

Em `backend/app/api/ordens_acoes.py`, trocar `_CAMPOS_CALIB` por:

```python
_CAMPOS_CALIB = (
    "calib_cert", "calib_temp", "calib_pressao", "calib_teste1", "calib_teste2",
    "calib_teste3", "calib_teste4", "calib_teste5", "calib_teste_media", "calib_situacao",
)
```

- [ ] **Step 5: Rodar os testes para confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_os_api.py tests/test_frota_os_certificados.py -v`
Expected: PASS. `test_frota_os_certificados.py` entra aqui porque `_CAMPOS_CALIB` de `ordens_acoes.py` é o espelho para a frota — mudou a tupla, esse teste é quem prova que o espelho continua correto.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/ordens.py backend/app/api/certificados_os.py \
        backend/app/api/ordens_acoes.py backend/tests/test_certificado_os_api.py
git commit -m "feat(cert): cinco medicoes na os e gravacao do cilindro usado na calibracao"
```

---

## Task 5: Tokens novos no motor de certificado

**Files:**
- Modify: `backend/app/core/certificado_gerar.py`
- Test: `backend/tests/test_certificado_contexto.py` (acrescentar)

**Interfaces:**
- Consumes: `calcular`, `formatar_numero`, `ParametrosCalculo` (Task 1); `obter_config`, `parametros_de` (Task 2); `ordens.padrao_id` (Task 4).
- Produces: os tokens `calibteste4`, `calibteste5`, `erro1`…`erro5`, `mediamedicoes`, `incertezaexpandida`, `fatork`, `drygasppm`, `limitemin`, `limitemax`, `padraocilindro`, `padraocertificado`, `padraoconcentracao`, `padraoincerteza`, `tecnico`, `tecnicocargo`, `equipamentosauxiliares`, `margemtemp` no contexto de **todos** os caminhos.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `backend/tests/test_certificado_contexto.py`, reaproveitando o helper local `_os_com_dados(db_session, os_base)` que já existe no arquivo. O arquivo já importa `CAMPOS`, `montar_contexto` e `montar_contexto_avulso`:

```python
def test_contexto_da_os_traz_todos_os_tokens_de_CAMPOS(db_session, os_base):
    ordem = _os_com_dados(db_session, os_base)
    ctx = montar_contexto(db_session, ordem)
    # Token que falta no contexto sai LITERALMENTE escrito no PDF do cliente.
    # `pulapagina` fica de fora de proposito: preencher() o trata fora do laco.
    faltando = [nome for nome, _ in CAMPOS if nome not in ctx and nome != "pulapagina"]
    assert faltando == []


def test_contexto_do_avulso_traz_as_mesmas_chaves_do_da_os(db_session, os_base):
    ordem = _os_com_dados(db_session, os_base)
    assert set(montar_contexto(db_session, ordem)) == set(montar_contexto_avulso(db_session, {}))


def test_contexto_calcula_o_erro_e_a_incerteza_da_planilha(db_session, os_base):
    ordem = _os_com_dados(db_session, os_base)
    for i in range(1, 6):
        setattr(ordem, f"calib_teste{i}", "0.16")
    db_session.commit()
    ctx = montar_contexto(db_session, ordem)
    assert ctx["erro1"] == "0,06"
    assert ctx["erro5"] == "0,06"
    assert ctx["mediamedicoes"] == "0,16"
    assert ctx["incertezaexpandida"] == "0,1301"
    assert ctx["fatork"] == "2"


def test_os_antiga_com_tres_medicoes_deixa_erro4_e_erro5_em_branco(db_session, os_base):
    ordem = _os_com_dados(db_session, os_base)   # nasce com 3 medicoes, sem teste4/5
    for i in range(1, 4):
        setattr(ordem, f"calib_teste{i}", "0.16")
    ordem.calib_teste4 = None
    ordem.calib_teste5 = None
    db_session.commit()
    ctx = montar_contexto(db_session, ordem)
    assert ctx["erro1"] == "0,06"
    # nao inventa medicao: erro em branco, nao "-0,1"
    assert ctx["erro4"] == ""
    assert ctx["erro5"] == ""
    assert ctx["calibteste4"] == ""


def test_os_sem_padrao_deixa_os_campos_do_cilindro_vazios(db_session, os_base):
    ordem = _os_com_dados(db_session, os_base)
    ordem.padrao_id = None
    db_session.commit()
    ctx = montar_contexto(db_session, ordem)
    assert ctx["padraocilindro"] == ""
    assert ctx["padraocertificado"] == ""
    assert ctx["drygasppm"] == ""
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_contexto.py -v`
Expected: FAIL — `KeyError: 'erro1'` / lista de tokens faltando não vazia.

- [ ] **Step 3: Ampliar `CAMPOS`**

Em `backend/app/core/certificado_gerar.py`, dentro da lista `CAMPOS`, logo depois de `("calibteste3", "Teste 3")`:

```python
    ("calibteste4", "Teste 4"),
    ("calibteste5", "Teste 5"),
```

e, logo antes de `("pulapagina", "Quebra de página (impressão)")`:

```python
    ("erro1", "Erro da medição 1"),
    ("erro2", "Erro da medição 2"),
    ("erro3", "Erro da medição 3"),
    ("erro4", "Erro da medição 4"),
    ("erro5", "Erro da medição 5"),
    ("mediamedicoes", "Média das medições (calculada)"),
    ("incertezaexpandida", "Incerteza expandida (U)"),
    ("fatork", "Fator de abrangência (k)"),
    ("drygasppm", "Dry gas ppm (concentração do padrão)"),
    ("limitemin", "Limite mínimo"),
    ("limitemax", "Limite máximo"),
    ("padraocilindro", "Nº do cilindro"),
    ("padraocertificado", "Nº do certificado do cilindro"),
    ("padraoconcentracao", "Concentração do padrão"),
    ("padraoincerteza", "Incerteza da concentração do padrão"),
    ("tecnico", "Técnico responsável"),
    ("tecnicocargo", "Cargo do técnico"),
    ("equipamentosauxiliares", "Equipamentos auxiliares"),
    ("margemtemp", "Margem de temperatura padrão"),
```

- [ ] **Step 4: Ampliar `_montar_contexto`**

Em `backend/app/core/certificado_gerar.py`, acrescentar ao topo do arquivo:

```python
from app.core.certificado_calculo import ParametrosCalculo, calcular, formatar_numero
```

Trocar a assinatura de `_montar_contexto` para receber os campos novos — acrescentar aos parâmetros nomeados, depois de `t3: str = ""`:

```python
    t4: str = "", t5: str = "",
    calc: dict[str, str] | None = None,
```

E, dentro do `return {...}` de `_montar_contexto`, acrescentar antes de `"datacli": hoje,`:

```python
        "calibteste4": t4,
        "calibteste5": t5,
        # bloco calculado + padrao + config; vazio quando o caminho nao tem calibracao
        # (avulso, venda e certificado geral). Nunca AUSENTE — token ausente sai
        # literalmente escrito no PDF.
        **_bloco_calculado(calc),
```

E acrescentar, logo acima de `_montar_contexto`, a função que garante o conjunto completo de chaves:

```python
# Chaves calculadas/derivadas do certificado EPS-LAB-002. Declaradas em UM lugar para
# que todos os caminhos (OS, avulso, venda, geral) emitam exatamente o mesmo conjunto.
_CHAVES_CALCULADAS = (
    "erro1", "erro2", "erro3", "erro4", "erro5",
    "mediamedicoes", "incertezaexpandida", "fatork",
    "drygasppm", "limitemin", "limitemax",
    "padraocilindro", "padraocertificado", "padraoconcentracao", "padraoincerteza",
    "tecnico", "tecnicocargo", "equipamentosauxiliares", "margemtemp",
)


def _bloco_calculado(calc: dict[str, str] | None) -> dict[str, str]:
    """Completa com string vazia toda chave calculada que o caminho nao informou."""
    calc = calc or {}
    return {chave: calc.get(chave, "") for chave in _CHAVES_CALCULADAS}
```

- [ ] **Step 5: Calcular e preencher no caminho da OS**

Ainda em `backend/app/core/certificado_gerar.py`, acrescentar acima de `montar_contexto`:

```python
def _calcular_para_os(db: Session, ordem) -> dict[str, str]:
    """Bloco calculado do certificado: erros, incerteza, padrao e textos da config.

    Os valores NAO sao persistidos: entram no HTML gerado, que ja e o snapshot do
    documento emitido. Persistir numero calculado criaria uma segunda verdade.
    """
    from app.core.certificado_config import obter_config, parametros_de
    from app.models import CertificadoPadrao

    config = obter_config(db)
    medicoes = [getattr(ordem, f"calib_teste{i}", None) for i in range(1, 6)]
    resultado = calcular(medicoes, parametros_de(config))

    padrao = db.get(CertificadoPadrao, ordem.padrao_id) if ordem.padrao_id else None

    bloco = {
        "mediamedicoes": formatar_numero(resultado.media),
        "incertezaexpandida": formatar_numero(resultado.incerteza_expandida),
        "fatork": formatar_numero(resultado.fator_k, casas=2),
        "limitemin": formatar_numero(None if config.limite_minimo is None else float(config.limite_minimo)),
        "limitemax": formatar_numero(None if config.limite_maximo is None else float(config.limite_maximo)),
        "padraocilindro": (padrao.numero_cilindro if padrao else "") or "",
        "padraocertificado": (padrao.numero_certificado if padrao else "") or "",
        "padraoconcentracao": formatar_numero(
            None if (padrao is None or padrao.concentracao is None) else float(padrao.concentracao)
        ),
        "padraoincerteza": formatar_numero(
            None if (padrao is None or padrao.incerteza_concentracao is None)
            else float(padrao.incerteza_concentracao)
        ),
        "tecnico": config.tecnico_nome or "",
        "tecnicocargo": config.tecnico_cargo or "",
        "equipamentosauxiliares": config.equipamentos_auxiliares or "",
        "margemtemp": config.margem_temperatura or "",
    }
    # DRY GAS PPM e a propria concentracao do padrao (na planilha, A82 = $D$72)
    bloco["drygasppm"] = bloco["padraoconcentracao"]
    for i, erro in enumerate(resultado.erros, start=1):
        bloco[f"erro{i}"] = formatar_numero(erro)
    return bloco
```

E, em `montar_contexto`, acrescentar à chamada de `_montar_contexto(...)`, junto de `t3=ordem.calib_teste3 or ""`:

```python
        t4=ordem.calib_teste4 or "",
        t5=ordem.calib_teste5 or "",
        calc=_calcular_para_os(db, ordem),
```

`montar_contexto_avulso` e `montar_contexto_venda` **não mudam** — sem passar `calc`, `_bloco_calculado` preenche todas as chaves com string vazia, que é o comportamento correto para caminhos que não têm medição de calibração.

- [ ] **Step 6: Rodar os testes para confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_contexto.py tests/test_certificado_contexto_venda.py tests/test_certificado_gerar.py -v`
Expected: PASS. Os três entram porque compartilham `_montar_contexto` — se o bloco de chaves novas quebrar a paridade entre OS, avulso e venda, é aqui que aparece.

- [ ] **Step 7: Rodar a suíte inteira**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: `4 failed` (as mesmas quatro `PermissionError` da baseline de 03/08/2026), nenhuma nova.

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/certificado_gerar.py backend/tests/test_certificado_contexto.py
git commit -m "feat(cert): tokens de erro, incerteza, padrao e tecnico no motor de certificado"
```

---

## Task 6: Frontend — aba Configurações

**Files:**
- Create: `frontend/src/app/certificados/ConfiguracoesTab.tsx`, `frontend/src/app/certificados/ConfiguracoesTab.test.tsx`
- Modify: `frontend/src/app/certificados/api.ts`, `frontend/src/app/certificados/CertificadosPage.tsx`, `frontend/src/auth/roles.ts`

**Interfaces:**
- Consumes: os endpoints da Task 3.
- Produces:
  - `certificadosApi.config()`, `certificadosApi.salvarConfig()`, `certificadosApi.padroes()`, `certificadosApi.criarPadrao()`, `certificadosApi.excluirPadrao()`, `certificadosApi.calculoPrevia()`
  - tipos `CertificadoConfig`, `CertificadoPadrao`, `CalculoPrevia`
  - `podeEditarConfigCertificado(user)` em `roles.ts`

- [ ] **Step 1: Escrever o teste que falha**

Criar `frontend/src/app/certificados/ConfiguracoesTab.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { ConfiguracoesTab } from './ConfiguracoesTab'

vi.mock('./api', () => ({
  certificadosApi: {
    config: vi.fn(),
    salvarConfig: vi.fn(),
    padroes: vi.fn(),
    criarPadrao: vi.fn(),
    excluirPadrao: vi.fn(),
  },
}))

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { funcao: 'Administrador' } }),
}))

import { certificadosApi } from './api'

const CONFIG = {
  id: 1, valor_referencia: '0.1000', limite_minimo: '0.1500', limite_maximo: '0.1900',
  resolucao_instrumento: '0.1000', incerteza_padrao_temp: '0.0520',
  resolucao_pressao: null, incerteza_padrao_pressao: null, fator_k: '2.00',
  tecnico_nome: 'Walbert Santos', tecnico_cargo: 'Técnico em Metrologia',
  equipamentos_auxiliares: 'TESTO 622', margem_temperatura: '20 ºC ~ 24 ºC',
}

describe('ConfiguracoesTab', () => {
  beforeEach(() => {
    vi.mocked(certificadosApi.config).mockResolvedValue(CONFIG)
    vi.mocked(certificadosApi.padroes).mockResolvedValue([{
      id: 7, numero_cilindro: 'CC747704', numero_certificado: '202231419',
      concentracao: '100.1000', incerteza_concentracao: '2.0000',
      unidade: 'µmol/mol', vigencia_inicio: '2025-01-01', vigencia_fim: null, ativo: true,
    }])
  })

  it('carrega e mostra os parametros do calculo', async () => {
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByLabelText(/valor de refer/i)).toHaveValue('0.1000'))
    expect(screen.getByLabelText(/t.cnico respons/i)).toHaveValue('Walbert Santos')
  })

  it('lista os cilindros cadastrados', async () => {
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByText('CC747704')).toBeInTheDocument())
    expect(screen.getByText('202231419')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `cd frontend && npx vitest run src/app/certificados/ConfiguracoesTab.test.tsx`
Expected: FAIL — módulo `./ConfiguracoesTab` não encontrado.

- [ ] **Step 3: Publicar os tokens novos no editor de modelos**

`frontend/src/app/certificados/api.ts` mantém `CAMPOS_CERTIFICADO`, uma **segunda lista de tokens** que alimenta a paleta do editor em Certificados › Modelos. Ela duplica `CAMPOS` do backend: token que não estiver aqui existe no motor mas **fica invisível** para quem monta o modelo.

Acrescentar, depois de `{ campo: '[calibteste3]', desc: 'Teste 3' },`:

```ts
  { campo: '[calibteste4]', desc: 'Teste 4' },
  { campo: '[calibteste5]', desc: 'Teste 5' },
```

e, antes de `{ campo: '[pulapagina]', desc: 'Quebra de página (impressão)' },`:

```ts
  { campo: '[erro1]', desc: 'Erro da medição 1' },
  { campo: '[erro2]', desc: 'Erro da medição 2' },
  { campo: '[erro3]', desc: 'Erro da medição 3' },
  { campo: '[erro4]', desc: 'Erro da medição 4' },
  { campo: '[erro5]', desc: 'Erro da medição 5' },
  { campo: '[mediamedicoes]', desc: 'Média das medições (calculada)' },
  { campo: '[incertezaexpandida]', desc: 'Incerteza expandida (U)' },
  { campo: '[fatork]', desc: 'Fator de abrangência (k)' },
  { campo: '[drygasppm]', desc: 'Dry gas ppm (concentração do padrão)' },
  { campo: '[limitemin]', desc: 'Limite mínimo' },
  { campo: '[limitemax]', desc: 'Limite máximo' },
  { campo: '[padraocilindro]', desc: 'Nº do cilindro' },
  { campo: '[padraocertificado]', desc: 'Nº do certificado do cilindro' },
  { campo: '[padraoconcentracao]', desc: 'Concentração do padrão' },
  { campo: '[padraoincerteza]', desc: 'Incerteza da concentração do padrão' },
  { campo: '[tecnico]', desc: 'Técnico responsável' },
  { campo: '[tecnicocargo]', desc: 'Cargo do técnico' },
  { campo: '[equipamentosauxiliares]', desc: 'Equipamentos auxiliares' },
  { campo: '[margemtemp]', desc: 'Margem de temperatura padrão' },
```

A lista tem de ficar **na mesma ordem e com as mesmas descrições** de `CAMPOS` em `backend/app/core/certificado_gerar.py`. Conferir com:

```bash
cd /home/ericks/github/GestorHS && \
  grep -o '("[a-z0-9]*"' backend/app/core/certificado_gerar.py | tr -d '("' | sort -u > /tmp/back.txt && \
  grep -o "campo: '\[[a-z0-9]*\]'" frontend/src/app/certificados/api.ts | grep -o '\[[a-z0-9]*\]' | tr -d '[]' | sort -u > /tmp/front.txt && \
  diff /tmp/back.txt /tmp/front.txt && echo "as duas listas batem"
```

- [ ] **Step 4: Estender o cliente de API**

Em `frontend/src/app/certificados/api.ts`, acrescentar os tipos junto dos outros e os métodos ao objeto exportado `certificadosApi`:

```ts
export interface CertificadoConfig {
  id: number
  valor_referencia: string | null
  limite_minimo: string | null
  limite_maximo: string | null
  resolucao_instrumento: string | null
  incerteza_padrao_temp: string | null
  resolucao_pressao: string | null
  incerteza_padrao_pressao: string | null
  fator_k: string | null
  tecnico_nome: string | null
  tecnico_cargo: string | null
  equipamentos_auxiliares: string | null
  margem_temperatura: string | null
}

export interface CertificadoPadrao {
  id: number
  numero_cilindro: string
  numero_certificado: string | null
  concentracao: string | null
  incerteza_concentracao: string | null
  unidade: string | null
  vigencia_inicio: string | null
  vigencia_fim: string | null
  ativo: boolean
}

/** Tudo em texto ja formatado pelo backend: a tela exibe, nao recalcula. */
export interface CalculoPrevia {
  erros: string[]
  media: string
  desvio_padrao: string
  incerteza_combinada: string
  incerteza_expandida: string
  fator_k: string
  limite_minimo: string
  limite_maximo: string
  fora_da_faixa: boolean[]
}
```

E os métodos:

```ts
  config: (): Promise<CertificadoConfig> => apiJson<CertificadoConfig>('/certificado-config'),

  salvarConfig: (dados: Partial<CertificadoConfig>): Promise<CertificadoConfig> =>
    apiJson<CertificadoConfig>('/certificado-config', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados),
    }),

  padroes: (): Promise<CertificadoPadrao[]> => apiJson<CertificadoPadrao[]>('/certificado-padroes'),

  criarPadrao: (dados: Omit<CertificadoPadrao, 'id'>): Promise<CertificadoPadrao> =>
    apiJson<CertificadoPadrao>('/certificado-padroes', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados),
    }),

  excluirPadrao: (id: number): Promise<void> =>
    apiVoid(`/certificado-padroes/${id}`, { method: 'DELETE' }),

  calculoPrevia: (medicoes: (string | null)[]): Promise<CalculoPrevia> =>
    apiJson<CalculoPrevia>('/certificado-calculo-previa', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ medicoes }),
    }),
```

- [ ] **Step 5: Adicionar a regra de função**

Em `frontend/src/auth/roles.ts`, junto das outras funções de certificado:

```ts
// Espelha require_funcao("Administrador") em backend/app/api/certificados_config.py —
// mudou la, mude aqui. Sao os numeros que definem a incerteza de todo certificado emitido.
export function podeEditarConfigCertificado(user: User | null): boolean {
  return isAdmin(user)
}
```

- [ ] **Step 6: Criar a aba**

Criar `frontend/src/app/certificados/ConfiguracoesTab.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { useAuth } from '../../auth/AuthContext'
import { podeEditarConfigCertificado } from '../../auth/roles'
import { hojeISO } from './valoresCertificado'
import { certificadosApi, type CertificadoConfig, type CertificadoPadrao } from './api'

const secao = 'text-xs font-semibold text-slate-500 uppercase tracking-wide'

/** Campos numericos do calculo. Um array em vez de JSX repetido: sao oito campos
 *  com o mesmo comportamento, e a lista e o que garante que nenhum fique de fora. */
const CAMPOS_NUMERICOS = [
  ['valor_referencia', 'Valor de referência'],
  ['limite_minimo', 'Limite mínimo'],
  ['limite_maximo', 'Limite máximo'],
  ['resolucao_instrumento', 'Resolução do instrumento'],
  ['incerteza_padrao_temp', 'Incerteza do padrão (temperatura)'],
  ['resolucao_pressao', 'Resolução (pressão)'],
  ['incerteza_padrao_pressao', 'Incerteza do padrão (pressão)'],
  ['fator_k', 'Fator k'],
] as const

const PADRAO_NOVO = {
  numero_cilindro: '', numero_certificado: '', concentracao: '', incerteza_concentracao: '',
  unidade: 'µmol/mol', vigencia_inicio: hojeISO(), vigencia_fim: null as string | null, ativo: true,
}

/** Um cilindro esta vigente se esta ativo e hoje cai dentro da vigencia.
 *  Espelha padrao_vigente() em backend/app/core/certificado_config.py. */
function estaVigente(p: CertificadoPadrao): boolean {
  const hoje = hojeISO()
  if (!p.ativo || !p.vigencia_inicio) return false
  return p.vigencia_inicio <= hoje && (p.vigencia_fim === null || p.vigencia_fim >= hoje)
}

export function ConfiguracoesTab() {
  const { user } = useAuth()
  const podeEditar = podeEditarConfigCertificado(user)

  const [config, setConfig] = useState<CertificadoConfig | null>(null)
  const [padroes, setPadroes] = useState<CertificadoPadrao[]>([])
  const [novo, setNovo] = useState({ ...PADRAO_NOVO })
  const [salvando, setSalvando] = useState(false)
  const [aviso, setAviso] = useState('')

  useEffect(() => {
    certificadosApi.config().then(setConfig).catch(() => setAviso('Falha ao carregar a configuração.'))
    certificadosApi.padroes().then(setPadroes).catch(() => setPadroes([]))
  }, [])

  function alterar(patch: Partial<CertificadoConfig>) {
    setConfig((atual) => (atual ? { ...atual, ...patch } : atual))
  }

  async function salvar() {
    if (!config) return
    setSalvando(true)
    setAviso('')
    try {
      setConfig(await certificadosApi.salvarConfig(config))
      setAviso('Configuração salva.')
    } catch {
      setAviso('Falha ao salvar a configuração.')
    } finally {
      setSalvando(false)
    }
  }

  async function adicionarPadrao() {
    if (!novo.numero_cilindro.trim()) return
    try {
      const criado = await certificadosApi.criarPadrao(novo)
      setPadroes((atual) => [criado, ...atual])
      setNovo({ ...PADRAO_NOVO })
    } catch {
      setAviso('Falha ao cadastrar o cilindro.')
    }
  }

  async function excluirPadrao(id: number) {
    try {
      await certificadosApi.excluirPadrao(id)
      setPadroes((atual) => atual.filter((p) => p.id !== id))
    } catch {
      setAviso('Falha ao excluir o cilindro.')
    }
  }

  if (!config) return <p className="text-sm text-slate-500">Carregando…</p>

  return (
    <div className="space-y-8">
      {!podeEditar && (
        <p className="text-xs text-amber-400">
          Somente o Administrador pode alterar estes valores — eles definem a incerteza de todo certificado emitido.
        </p>
      )}
      {aviso && <p className="text-xs text-slate-400">{aviso}</p>}

      <div className="space-y-3">
        <p className={secao}>Parâmetros do cálculo</p>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          {CAMPOS_NUMERICOS.map(([chave, rotulo]) => (
            <Input key={chave} id={chave} label={rotulo} disabled={!podeEditar}
              value={config[chave] ?? ''}
              onChange={(e) => alterar({ [chave]: e.target.value || null } as Partial<CertificadoConfig>)} />
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <p className={secao}>Laboratório</p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input id="tecnico_nome" label="Técnico responsável" disabled={!podeEditar}
            value={config.tecnico_nome ?? ''}
            onChange={(e) => alterar({ tecnico_nome: e.target.value })} />
          <Input id="tecnico_cargo" label="Cargo do técnico" disabled={!podeEditar}
            value={config.tecnico_cargo ?? ''}
            onChange={(e) => alterar({ tecnico_cargo: e.target.value })} />
          <Input id="margem_temperatura" label="Margem de temperatura" disabled={!podeEditar}
            value={config.margem_temperatura ?? ''}
            onChange={(e) => alterar({ margem_temperatura: e.target.value })} />
        </div>
        <label htmlFor="equipamentos_auxiliares" className="block text-xs text-slate-400">
          Equipamentos auxiliares
        </label>
        <textarea id="equipamentos_auxiliares" rows={3} disabled={!podeEditar}
          className="w-full rounded-lg bg-background-elevated border border-slate-700 p-2 text-sm text-slate-200"
          value={config.equipamentos_auxiliares ?? ''}
          onChange={(e) => alterar({ equipamentos_auxiliares: e.target.value })} />
        {podeEditar && (
          <Button onClick={salvar} disabled={salvando}>{salvando ? 'Salvando…' : 'Salvar'}</Button>
        )}
      </div>

      <div className="space-y-3">
        <p className={secao}>Padrões (cilindros de gás)</p>
        <table className="w-full text-sm text-slate-300">
          <thead className="text-xs text-slate-500 uppercase">
            <tr>
              <th className="text-left py-1">Cilindro</th>
              <th className="text-left py-1">Certificado</th>
              <th className="text-left py-1">Concentração</th>
              <th className="text-left py-1">Vigência</th>
              <th className="text-left py-1">Situação</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {padroes.map((p) => (
              <tr key={p.id} className="border-t border-slate-800">
                <td className="py-1.5">{p.numero_cilindro}</td>
                <td>{p.numero_certificado ?? '—'}</td>
                <td>{p.concentracao ?? '—'} {p.unidade ?? ''}</td>
                <td>{p.vigencia_inicio ?? '—'} → {p.vigencia_fim ?? 'vigente'}</td>
                <td>{estaVigente(p)
                  ? <span className="text-emerald-400 text-xs font-medium">Em uso</span>
                  : <span className="text-slate-500 text-xs">—</span>}</td>
                <td className="text-right">
                  {podeEditar && (
                    <button onClick={() => excluirPadrao(p.id)}
                      className="text-xs text-red-400 hover:text-red-300">Excluir</button>
                  )}
                </td>
              </tr>
            ))}
            {padroes.length === 0 && (
              <tr><td colSpan={6} className="py-3 text-slate-500">Nenhum cilindro cadastrado.</td></tr>
            )}
          </tbody>
        </table>

        {podeEditar && (
          <div className="grid grid-cols-1 sm:grid-cols-6 gap-3 items-end">
            <Input id="novo_cilindro" label="Cilindro" value={novo.numero_cilindro}
              onChange={(e) => setNovo({ ...novo, numero_cilindro: e.target.value })} />
            <Input id="novo_certificado" label="Certificado" value={novo.numero_certificado}
              onChange={(e) => setNovo({ ...novo, numero_certificado: e.target.value })} />
            <Input id="nova_concentracao" label="Concentração" value={novo.concentracao}
              onChange={(e) => setNovo({ ...novo, concentracao: e.target.value })} />
            <Input id="nova_incerteza" label="± Incerteza" value={novo.incerteza_concentracao}
              onChange={(e) => setNovo({ ...novo, incerteza_concentracao: e.target.value })} />
            <Input id="nova_vigencia" label="Vigência a partir de" type="date" value={novo.vigencia_inicio}
              onChange={(e) => setNovo({ ...novo, vigencia_inicio: e.target.value })} />
            <Button onClick={adicionarPadrao}>Adicionar</Button>
          </div>
        )}
      </div>
    </div>
  )
}
```

Antes de escrever, conferir as assinaturas reais de `Input` e `Button` em `frontend/src/components/ui/` — se `Input` não aceitar `disabled` ou `Button` usar outra prop, ajustar. Os `id`/`label` são obrigatórios: o teste usa `getByLabelText`.

- [ ] **Step 7: Registrar a aba na página**

Em `frontend/src/app/certificados/CertificadosPage.tsx`:

```tsx
const ABAS = ['Modelos', 'Imagens', 'Em branco', 'Gerais', 'Configurações'] as const
```

e trocar a linha de renderização por:

```tsx
      {aba === 'Modelos' ? <ModelosTab />
        : aba === 'Imagens' ? <ImagensTab />
        : aba === 'Em branco' ? <AvulsosTab />
        : aba === 'Gerais' ? <CertificadosGeraisTab />
        : <ConfiguracoesTab />}
```

com o import correspondente no topo.

- [ ] **Step 8: Rodar o teste para confirmar que passa**

Run: `cd frontend && npx vitest run src/app/certificados/ConfiguracoesTab.test.tsx`
Expected: PASS — 2 testes.

- [ ] **Step 9: Verificação completa de frontend**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/app/certificados/ConfiguracoesTab.tsx \
        frontend/src/app/certificados/ConfiguracoesTab.test.tsx \
        frontend/src/app/certificados/api.ts \
        frontend/src/app/certificados/CertificadosPage.tsx \
        frontend/src/auth/roles.ts
git commit -m "feat(cert): aba de configuracoes com parametros de calculo e cadastro de cilindros"
```

---

## Task 7: Frontend — 5 medições, aviso fora de faixa e prévia

**Files:**
- Modify: `frontend/src/lib/calibragem.ts`, `frontend/src/app/certificados/valoresCertificado.ts`, `frontend/src/app/certificados/CamposCertificado.tsx`
- Test: `frontend/src/app/certificados/CamposCertificado.test.tsx` (acrescentar), `frontend/src/lib/calibragem.test.ts` (se existir; senão criar)

**Interfaces:**
- Consumes: `certificadosApi.calculoPrevia` (Task 6).
- Produces: `ValoresCertificado.t4`, `ValoresCertificado.t5`; `mediaTestes(...vals: string[])`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `frontend/src/app/certificados/CamposCertificado.test.tsx` (manter os mocks já existentes no arquivo; se ele ainda não mocka `./api`, acrescentar o mock de `certificadosApi.calculoPrevia`):

```tsx
it('mostra cinco campos de medicao', () => {
  render(<CamposCertificado valores={valoresIniciais()} onChange={() => {}} />)
  expect(screen.getByLabelText('Teste 1')).toBeInTheDocument()
  expect(screen.getByLabelText('Teste 4')).toBeInTheDocument()
  expect(screen.getByLabelText('Teste 5')).toBeInTheDocument()
})

it('destaca medicao fora da faixa sem impedir a geracao', async () => {
  vi.mocked(certificadosApi.calculoPrevia).mockResolvedValue({
    erros: ['0,06', '', '', '', ''], media: '0,16', desvio_padrao: '0',
    incerteza_combinada: '0,0651', incerteza_expandida: '0,1301', fator_k: '2',
    limite_minimo: '0,15', limite_maximo: '0,19',
    fora_da_faixa: [true, false, false, false, false],
  })
  const valores = { ...valoresIniciais(), t1: '0.016' }
  render(<CamposCertificado valores={valores} onChange={() => {}} />)
  await waitFor(() => expect(screen.getByText(/fora da faixa/i)).toBeInTheDocument())
  // o aviso NAO desabilita nada: o certificado de aparelho reprovado tambem precisa existir
  expect(screen.getByLabelText('Teste 1')).not.toBeDisabled()
})

it('exibe a incerteza expandida vinda do backend', async () => {
  vi.mocked(certificadosApi.calculoPrevia).mockResolvedValue({
    erros: ['0,06', '0,06', '0,06', '0,06', '0,06'], media: '0,16', desvio_padrao: '0',
    incerteza_combinada: '0,0651', incerteza_expandida: '0,1301', fator_k: '2',
    limite_minimo: '0,15', limite_maximo: '0,19', fora_da_faixa: [false, false, false, false, false],
  })
  const valores = { ...valoresIniciais(), t1: '0.16', t2: '0.16', t3: '0.16', t4: '0.16', t5: '0.16' }
  render(<CamposCertificado valores={valores} onChange={() => {}} />)
  await waitFor(() => expect(screen.getByText('0,1301')).toBeInTheDocument())
})
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `cd frontend && npx vitest run src/app/certificados/CamposCertificado.test.tsx`
Expected: FAIL — `Teste 4` não encontrado.

- [ ] **Step 3: Tornar `mediaTestes` variádica**

Em `frontend/src/lib/calibragem.ts`, substituir a função por:

```ts
/** Média das medições de calibração, formatada como no certificado.
 *
 * Variádica para atender as 5 medições do certificado EPS-LAB-002 sem quebrar as
 * chamadas de 3 argumentos que já existiam. Arredonda para até 3 casas decimais e
 * remove os zeros à direita, para acompanhar a precisão digitada.
 * Retorna '' quando alguma medição está vazia ou não é número (usado para só
 * preencher automaticamente enquanto o usuário não editou a média à mão).
 */
export function mediaTestes(...valores: string[]): string {
  if (valores.length === 0) return ''
  if (valores.some((v) => v.trim() === '')) return ''
  const nums = valores.map((v) => Number(v.replace(',', '.')))
  if (nums.some((n) => Number.isNaN(n))) return ''
  const media = (nums.reduce((a, b) => a + b, 0) / nums.length)
    .toFixed(3)
    .replace(/0+$/, '')   // remove zeros à direita (0,180 → 0,18)
    .replace(/\.$/, '')   // e o ponto solto, se sobrar (1,000 → 1)
  return media.replace('.', ',')
}
```

- [ ] **Step 4: Adicionar `t4` e `t5` aos valores**

Em `frontend/src/app/certificados/valoresCertificado.ts`, na interface, depois de `t3: string`:

```ts
  t4: string
  t5: string
```

e em `valoresIniciais()`, trocar `t1: '', t2: '', t3: '', media: '',` por:

```ts
    t1: '', t2: '', t3: '', t4: '', t5: '', media: '',
```

- [ ] **Step 5: Ampliar o formulário**

Em `frontend/src/app/certificados/CamposCertificado.tsx`:

Trocar o `useEffect` da média por:

```tsx
  useEffect(() => {
    if (mediaEditada) return
    onChange({ media: mediaTestes(valores.t1, valores.t2, valores.t3, valores.t4, valores.t5) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valores.t1, valores.t2, valores.t3, valores.t4, valores.t5, mediaEditada])
```

Trocar o grid dos 3 testes por um de 5:

```tsx
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {([1, 2, 3, 4, 5] as const).map((n) => {
            const chave = `t${n}` as 't1' | 't2' | 't3' | 't4' | 't5'
            const fora = previa?.fora_da_faixa[n - 1] ?? false
            return (
              <Input key={n} id={chave} label={`Teste ${n}`} value={valores[chave]}
                className={fora ? 'border-red-500 focus:border-red-500' : undefined}
                // chave computada a partir de uma uniao de literais: o TS infere
                // { [x: string]: string } e nao casa com Partial<ValoresCertificado>
                onChange={(e) => onChange({ [chave]: e.target.value } as Partial<ValoresCertificado>)} />
            )
          })}
        </div>
```

Acrescentar o estado e o efeito da prévia, com debounce (o técnico digita rápido; sem debounce é uma requisição por tecla):

```tsx
  const [previa, setPrevia] = useState<CalculoPrevia | null>(null)

  const medicoes = [valores.t1, valores.t2, valores.t3, valores.t4, valores.t5]
  const chaveMedicoes = medicoes.join('|')

  useEffect(() => {
    if (medicoes.every((m) => m.trim() === '')) { setPrevia(null); return }
    const timer = setTimeout(() => {
      certificadosApi.calculoPrevia(medicoes)
        .then(setPrevia)
        // a previa e informativa: falhar nela nao pode travar a geracao do certificado
        .catch(() => setPrevia(null))
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveMedicoes])
```

E, logo abaixo do campo de média, o painel read-only:

```tsx
        {previa && (
          <div className="rounded-lg border border-slate-700 bg-background-elevated p-3 space-y-2">
            <p className={secao}>Cálculo (somente leitura)</p>
            {previa.fora_da_faixa.some(Boolean) && (
              <p className="text-xs text-red-400">
                Medição fora da faixa {previa.limite_minimo} – {previa.limite_maximo}. Confira antes de gerar.
              </p>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs text-slate-400">
              {previa.erros.map((erro, i) => (
                <span key={i}>Erro {i + 1}: <strong className="text-slate-200">{erro || '—'}</strong></span>
              ))}
            </div>
            <p className="text-xs text-slate-400">
              Incerteza expandida (U): <strong className="text-slate-200">{previa.incerteza_expandida}</strong>
              {' '}· k = {previa.fator_k} (95% de confiança)
            </p>
          </div>
        )}
```

com os imports de `certificadosApi` e do tipo `CalculoPrevia` de `./api`, e o de `type ValoresCertificado` de `./valoresCertificado` (o arquivo hoje importa só o tipo `ValoresCertificado` — confirmar que o import cobre o uso no cast).

- [ ] **Step 6: Rodar os testes para confirmar que passam**

Run: `cd frontend && npx vitest run src/app/certificados/`
Expected: PASS — incluindo os testes que já existiam no arquivo.

- [ ] **Step 7: Rodar a suíte de frontend inteira**

Run: `cd frontend && npm test`
Expected: PASS. Se algum teste de `CertificadoAvulsoModal` ou do modal de venda quebrar por causa de `t4`/`t5`, corrigir o mock/fixture daquele teste — os dois modais compartilham `CamposCertificado` e agora recebem 5 medições.

- [ ] **Step 8: Verificação completa de frontend**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/calibragem.ts frontend/src/app/certificados/valoresCertificado.ts \
        frontend/src/app/certificados/CamposCertificado.tsx \
        frontend/src/app/certificados/CamposCertificado.test.tsx
git commit -m "feat(cert): cinco medicoes no modal com aviso fora da faixa e previa do calculo"
```

---

## Task 8: Template de referência e changelog

**Files:**
- Create: `docs/modelo-certificado-eps-lab-002.html`
- Modify: `frontend/src/app/changelog/data.ts`

**Interfaces:**
- Consumes: todos os tokens da Task 5.
- Produces: nada consumido por código — é conteúdo para o cadastro em Certificados › Modelos.

- [ ] **Step 1: Montar o HTML de referência**

Criar `docs/modelo-certificado-eps-lab-002.html` com o conteúdo abaixo. Os textos fixos foram transcritos das células `A22`, `A23`, `A32`, `A33`, `A37`, `A56` e `A91` da aba `CERTIFICADO` da planilha:

```html
<style>
  .cert { font-family: Arial, Helvetica, sans-serif; font-size: 11px; color: #000; }
  .cert h2 { font-size: 12px; background: #d9d9d9; padding: 3px 5px; margin: 10px 0 4px; }
  .cert table { width: 100%; border-collapse: collapse; }
  .cert td, .cert th { border: 1px solid #000; padding: 3px 5px; vertical-align: top; }
  .cert .cab td { border: 1px solid #000; text-align: center; font-weight: bold; }
  .cert .rot { background: #f2f2f2; font-weight: bold; width: 22%; }
  .cert .bloco { border: 1px solid #000; padding: 6px; white-space: pre-line; }
  .cert .assin { margin-top: 40px; text-align: center; }
</style>

<div class="cert">
  <table class="cab">
    <tr>
      <td rowspan="2" style="width:25%">HEALTH &amp; SAFETY</td>
      <td>EPS-LAB-002</td>
      <td style="width:20%">Revisão: 02</td>
    </tr>
    <tr>
      <td>Título: Certificado de Calibração [modelo]</td>
      <td>Páginas: 1 de 2</td>
    </tr>
  </table>

  <p style="text-align:center;font-weight:bold;font-size:13px;margin:10px 0">
    CERTIFICAÇÃO DE CALIBRAÇÃO N° [calibcert]
  </p>

  <h2>1 - DADOS DO SOLICITANTE</h2>
  <table>
    <tr><td class="rot">CLIENTE:</td><td colspan="3">[nomecli]</td></tr>
    <tr><td class="rot">CNPJ:</td><td colspan="3">[cnpj]</td></tr>
    <tr><td class="rot">ENDEREÇO:</td><td colspan="3">[endcli]</td></tr>
  </table>

  <h2>2 - INSTRUMENTO CALIBRADO</h2>
  <table>
    <tr><td class="rot">N° SÉRIE:</td><td>[serie]</td><td class="rot">EQUIPAMENTO:</td><td>[modelo]</td></tr>
    <tr><td class="rot">DATA DE VENDA:</td><td>[datacompra]</td><td class="rot">MARCA:</td><td>[marca]</td></tr>
    <tr><td class="rot">ORDEM DE SERVIÇO:</td><td>[os]</td><td class="rot">MODELO:</td><td>[modelo]</td></tr>
    <tr><td class="rot">DATA CALIBRAÇÃO:</td><td>[datacali]</td><td class="rot">SITUAÇÃO:</td><td>[situcalib]</td></tr>
  </table>

  <h2>3 - IDENTIFICAÇÃO DA CALIBRAÇÃO</h2>
  <table>
    <tr><td class="rot">DATA DO RECEBIMENTO:</td><td>[dataentr]</td></tr>
    <tr><td class="rot">LOCAL DA CALIBRAÇÃO:</td><td>Health &amp; Safety</td></tr>
    <tr><td class="rot">ENDEREÇO:</td><td>Rua Viscondessa do Livramento, Nº 54. 3º andar - Sala G, Bairro: Derby, Recife - PE, CEP: 52010-065</td></tr>
  </table>

  <h2>4 - CONDIÇÕES AMBIENTAIS DURANTE A CALIBRAÇÃO</h2>
  <table>
    <tr>
      <th>TEMPERATURA °C</th><th>PRESSÃO BAROMÉTRICA hPa</th><th>MARGEM DE TEMPERATURA PADRÃO</th>
    </tr>
    <tr>
      <td style="text-align:center">[calibtemp]</td>
      <td style="text-align:center">[calibpressao]</td>
      <td style="text-align:center">[margemtemp]</td>
    </tr>
  </table>

  <h2>5 - RESUMO DO MÉTODO DE CALIBRAÇÃO</h2>
  <div class="bloco">MÉTODO: FLX-LAB-002 elaborado conforme documento INMETRO NIT-SEFIQ-018 VERIFICAÇÃO E INSPEÇÃO DE ETILOMETROS revisão 05

DESCRIÇÃO DO MÉTODO: A CALIBRAÇÃO FOI REALIZADA CONFORME O MÉTODO DE CALIBRAÇÃO ACIMA, COMPARADO COM O PROCEDIMENTO DO FORNECEDOR.</div>

  <h2>6 - COMENTÁRIOS</h2>
  <div class="bloco">Seu aparelho foi construído para medir o álcool já metabolizado pelo organismo, nunca utilize álcool puro ou de bebidas alcoólicas para testar o aparelho, isso pode danificá-lo permanentemente. Não realizar testes no aparelho após fumar, realizar o teste do bafômetro após 15 minutos de ingestão de bebida alcoólica. Essas notas são explicadas pelo fabricante e conforme a legislação de trânsito, ditas pela Organização Mundial de Saúde.
• Este certificado tem validade de 12 meses.

Termos de Garantia:
A garantia não cobre danos ou defeitos decorrentes de mau uso, tornando-se nula, conforme abaixo:
• Quedas, impactos ou batidas.
• Infiltração de líquidos ou exposição a condições inadequadas de temperatura e umidade.
• Alterações ou modificações não autorizadas no produto.
• Uso em desacordo com as instruções do manual do fabricante.
• Violação de lacres ou selos de segurança.
• Em casos de mau uso, qualquer reparo ou substituição de peças será cobrado do cliente, mesmo que esteja dentro do prazo de garantia.</div>
</div>

[pulapagina]

<div class="cert">
  <table class="cab">
    <tr>
      <td rowspan="2" style="width:25%">HEALTH &amp; SAFETY</td>
      <td>EPS-LAB-002</td>
      <td style="width:20%">Revisão: 02</td>
    </tr>
    <tr>
      <td>Título: Certificado de Calibração [modelo]</td>
      <td>Páginas: 2 de 2</td>
    </tr>
  </table>

  <div class="bloco" style="margin-top:10px">1. Observação: A análise técnica realizada por nossa equipe será conclusiva para caracterizar ou não o mau uso.
* Calibração: No momento da calibração o aparelho obteve resposta conforme procedimentos estabelecidos pelo fabricante e liberado em conformidade.
* Garantia da Calibração: Não se responsabiliza pelo uso decorrente, danos ou peças.
* Aparelho em Manutenção: Cobertura das peças substituídas, caso ocorra, garantia de mão de obra de 90 dias.
* Aparelhos sem conserto: Dentro do prazo de garantia, será observado o dano de acordo com a observação Nº 1.</div>

  <h2>7 - EQUIPAMENTOS AUXILIARES</h2>
  <div class="bloco">[equipamentosauxiliares]</div>

  <h2>8 - PADRÕES UTILIZADOS NA CALIBRAÇÃO</h2>
  <table>
    <tr><td class="rot">N° CERTIFICADO:</td><td>[padraocertificado]</td></tr>
    <tr><td class="rot">N° DO CILINDRO:</td><td>[padraocilindro]</td></tr>
    <tr><td class="rot">CONCENTRAÇÃO:</td><td>[padraoconcentracao] ± [padraoincerteza]</td></tr>
  </table>

  <h2>9 - RESULTADOS OBTIDOS</h2>
  <table>
    <tr><th>TÉCNICO(A)</th><th>DATA</th><th>N° SÉRIE</th><th>CLIENTE</th></tr>
    <tr>
      <td>[tecnico]</td><td>[datacali]</td><td>[serie]</td><td>[nomecli]</td>
    </tr>
  </table>
  <table style="margin-top:6px">
    <tr><th>PRESSÃO BAROMÉTRICA (hPa)</th><th>TEMPERATURA (°C)</th></tr>
    <tr><td style="text-align:center">[calibpressao]</td><td style="text-align:center">[calibtemp]</td></tr>
  </table>
  <table style="margin-top:6px">
    <tr><th>DRY GAS PPM</th><th>LIMITE MÍNIMO</th><th>LIMITE MÁXIMO</th></tr>
    <tr>
      <td style="text-align:center">[drygasppm]</td>
      <td style="text-align:center">[limitemin]</td>
      <td style="text-align:center">[limitemax]</td>
    </tr>
  </table>
  <table style="margin-top:6px">
    <tr><th colspan="5">MEDIÇÕES</th></tr>
    <tr><th>Test 1</th><th>Test 2</th><th>Test 3</th><th>Test 4</th><th>Test 5</th></tr>
    <tr>
      <td style="text-align:center">[calibteste1]</td>
      <td style="text-align:center">[calibteste2]</td>
      <td style="text-align:center">[calibteste3]</td>
      <td style="text-align:center">[calibteste4]</td>
      <td style="text-align:center">[calibteste5]</td>
    </tr>
    <tr><th colspan="5">ERRO DE MEDIÇÃO</th></tr>
    <tr>
      <td style="text-align:center">[erro1]</td>
      <td style="text-align:center">[erro2]</td>
      <td style="text-align:center">[erro3]</td>
      <td style="text-align:center">[erro4]</td>
      <td style="text-align:center">[erro5]</td>
    </tr>
  </table>
  <table style="margin-top:6px">
    <tr>
      <td class="rot">INCERTEZA EXPANDIDA (U)</td>
      <td style="text-align:center">[incertezaexpandida]</td>
      <td class="rot">k = [fatork] (95% DE CONFIANÇA)</td>
    </tr>
  </table>

  <h2>NOTAS E INFORMAÇÕES PERTINENTES</h2>
  <div class="bloco">1. Os resultados apresentados neste certificado referem-se exclusivamente ao item calibrado e às condições de medição especificadas.
2. O erro de medição foi determinado pela diferença entre o valor medido e o valor de referência obtido por padrão rastreável a padrões nacionais/internacionais, conforme critérios estabelecidos no procedimento de calibração aplicável.
3. A incerteza expandida de medição (U) foi calculada de acordo com o Guia para a Expressão da Incerteza de Medição (GUM), adotando-se um fator de abrangência k = 2, correspondente a um nível de confiança de aproximadamente 95%.
4. A incerteza informada representa a melhor estimativa do laboratório para o resultado obtido e deve ser considerada na interpretação da conformidade do item calibrado.
5. A rastreabilidade metrológica dos padrões utilizados é assegurada por calibrações realizadas em laboratórios acreditados pela RBC/Inmetro ou organismos equivalentes reconhecidos internacionalmente.</div>

  <div class="assin">
    _______________________________________<br />
    [tecnico] — [tecnicocargo]
  </div>
</div>
```

Dois pontos deliberados: `[modelo]` aparece tanto em "EQUIPAMENTO" quanto em "MODELO" porque o catálogo do GestorHS tem um único campo de descrição do aparelho — na planilha eram "Bafômetro" e "iBlow10", uma distinção que o cadastro não faz. E `[situcalib]` alimenta "SITUAÇÃO" (na planilha, "Aparelho subsequente"), que é exatamente o que o `Select` do modal já oferece.

- [ ] **Step 2: Conferir que nenhum token ficou órfão**

Run:
```bash
cd /home/ericks/github/GestorHS && \
  grep -o '\[[a-z0-9]*\]' docs/modelo-certificado-eps-lab-002.html | sort -u
```
Expected: todo token listado deve existir em `CAMPOS` de `backend/app/core/certificado_gerar.py`. Conferir um a um — token que não existe no contexto sai **literalmente escrito** no PDF do cliente.

- [ ] **Step 3: Atualizar o changelog**

Em `frontend/src/app/changelog/data.ts`, inserir como **primeira** entrada do array `CHANGELOG` (a primeira é sempre a versão atual). O tipo é `VersaoChangelog`: `data` no formato **DD/MM/AAAA** e `itens` do tipo `MudancaItem[]`, com `tipo` (`'novidade' | 'melhoria' | 'correcao'`) e `texto` — **não** uma lista de strings:

```ts
  {
    versao: '1.37.0',
    data: '31/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Certificado de calibração no formato EPS-LAB-002: cinco medições, erro por medição e incerteza expandida (k = 2, 95% de confiança).' },
      { tipo: 'novidade', texto: 'Nova aba Configurações em Certificados: parâmetros do cálculo, técnico responsável e cadastro dos cilindros de gás com vigência.' },
      { tipo: 'melhoria', texto: 'O modal de gerar certificado destaca medição fora da faixa e mostra o cálculo antes de gerar.' },
      { tipo: 'melhoria', texto: 'A OS grava qual cilindro foi usado, para que regerar um certificado antigo mantenha a rastreabilidade correta.' },
    ],
  },
```

- [ ] **Step 4: Verificação completa de frontend**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro.

- [ ] **Step 5: Commit**

```bash
git add docs/modelo-certificado-eps-lab-002.html frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.37.0 — certificado eps-lab-002 com calculo de incerteza"
```

---

## Depois do plano — o que fica com o Erick

Três coisas que a implementação **não** faz, de propósito:

1. **`alembic upgrade head`** — o `DATABASE_URL` desta máquina aponta para o banco de produção. Aplicar a migração é passo de deploy.
2. **Cadastrar o cilindro `CC747704`** e conferir os parâmetros na aba Configurações — os valores da migração são o ponto de partida da planilha, e os três pontos levantados na spec (o `valor_referencia = 0,1`, a `resolucao = 0,1` que produz um `U` maior que a faixa de tolerância, e o `B2 = 0,2002` que não entra em fórmula nenhuma) continuam sem resposta da Qualidade.
3. **Colar o HTML EPS-LAB-002 nos modelos de cada aparelho**, em Certificados › Modelos. É trabalho de cadastro; com um template por aparelho, é o que a decisão de arquitetura implica.
