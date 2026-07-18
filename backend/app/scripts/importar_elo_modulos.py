"""Carga do elo Phoebus<->Modulo a partir da planilha de dispositivos.

Le um .xlsx (via `zipfile` + `xml.etree`, sem dependencia nova), aplica as
regras de `resolver_elos` (Task 1) e grava/atualiza `instalacoes_modulo`
(Task 2). E' aditivo: nunca mexe em equipamentos, clientes ou OS.

Uso: python -m app.scripts.importar_elo_modulos <arquivo.xlsx> [--origem TEXTO]
     [--phoebus-id 36] [--modulo-id 47] [--dry-run] [--pendencias CAMINHO.csv]
"""
import argparse
import csv
import re
import unicodedata
import zipfile
from collections import Counter
from datetime import date
from xml.etree import ElementTree as ET

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.elo_modulos import resolver_elos
from app.models import EquipamentoCliente, InstalacaoModulo
from app.models.database import SessionLocal

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

_PHOEBUS_ID_PADRAO = 36

_CABECALHOS = {
    "numero de serie": "serie_aparelho",
    "numero de serie do modulo": "serie_modulo",
    "proxima calibracao": "prox_calib",
    "nome da empresa": "empresa",
}


def _normalizar_cabecalho(texto: str) -> str:
    """Minusculo, sem acento, espacos colapsados — tolera variacao de escrita."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.strip().lower()
    return re.sub(r"\s+", " ", texto)


def _col_letra(ref: str) -> str:
    """'B7' -> 'B'."""
    return re.match(r"[A-Z]+", ref).group(0)


def ler_planilha(caminho: str) -> list[dict]:
    """Le a primeira planilha do .xlsx e devolve linhas mapeadas pelo cabecalho.

    Cada item: {"linha", "serie_aparelho", "serie_modulo", "prox_calib", "empresa"}.
    """
    with zipfile.ZipFile(caminho) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{_NS}si"):
                textos = si.findall(f".//{_NS}t")
                shared.append("".join(t.text or "" for t in textos))

        nomes_sheet = sorted(
            n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml", n)
        )
        if not nomes_sheet:
            raise ValueError("Planilha invalida: nenhuma xl/worksheets/sheet*.xml encontrada.")
        sheet_root = ET.fromstring(z.read(nomes_sheet[0]))

        def valor_celula(c):
            tipo = c.get("t")
            if tipo == "inlineStr":
                t = c.find(f"{_NS}is/{_NS}t")
                return t.text if t is not None else ""
            v = c.find(f"{_NS}v")
            texto = v.text if v is not None else ""
            if tipo == "s":
                idx = int(texto) if texto else 0
                return shared[idx] if idx < len(shared) else ""
            return texto

        linhas_raw = []
        for row in sheet_root.findall(f".//{_NS}sheetData/{_NS}row"):
            num_linha = int(row.get("r"))
            celulas = {}
            for c in row.findall(f"{_NS}c"):
                celulas[_col_letra(c.get("r"))] = valor_celula(c)
            linhas_raw.append((num_linha, celulas))

        if not linhas_raw:
            return []

        linhas_raw.sort(key=lambda x: x[0])
        num_cabecalho, cabecalho_cols = linhas_raw[0]

        mapa_col_campo: dict[str, str] = {}
        for col, texto in cabecalho_cols.items():
            campo = _CABECALHOS.get(_normalizar_cabecalho(texto or ""))
            if campo:
                mapa_col_campo[col] = campo

        linhas = []
        for num_linha, celulas in linhas_raw[1:]:
            item = {"linha": num_linha, "serie_aparelho": None, "serie_modulo": None,
                     "prox_calib": None, "empresa": None}
            for col, campo in mapa_col_campo.items():
                valor = celulas.get(col)
                item[campo] = valor.strip() if isinstance(valor, str) else valor
            linhas.append(item)
        return linhas


def aplicar(db: Session, elos: list[dict], origem: str, dry_run: bool) -> dict:
    """Aplica os elos resolvidos em `instalacoes_modulo`. Idempotente.

    Para cada elo: se ja existe instalacao aberta identica (mesmo modulo e
    mesmo phoebus), nao faz nada. Senao, fecha as instalacoes abertas
    daquele modulo e daquele phoebus e abre a nova. Em dry_run, so conta
    (nao grava nem commita).
    """
    contagem = {"criados": 0, "fechados": 0, "inalterados": 0}
    hoje = date.today()

    for elo in elos:
        modulo_id = elo["modulo_id"]
        phoebus_id = elo["phoebus_id"]

        aberta_modulo = (
            db.query(InstalacaoModulo)
            .filter(InstalacaoModulo.modulo == modulo_id, InstalacaoModulo.saiu_em.is_(None))
            .first()
        )
        aberta_phoebus = (
            db.query(InstalacaoModulo)
            .filter(InstalacaoModulo.phoebus == phoebus_id, InstalacaoModulo.saiu_em.is_(None))
            .first()
        )

        if aberta_modulo is not None and aberta_modulo.phoebus == phoebus_id:
            # Indices unicos garantem que aberta_phoebus e' a mesma linha aqui.
            contagem["inalterados"] += 1
            continue

        abertas_para_fechar = {
            row.id: row for row in (aberta_modulo, aberta_phoebus) if row is not None
        }
        for row in abertas_para_fechar.values():
            row.saiu_em = hoje
            contagem["fechados"] += 1
            if not dry_run:
                db.add(row)

        nova = InstalacaoModulo(modulo=modulo_id, phoebus=phoebus_id, entrou_em=hoje,
                                 saiu_em=None, origem=origem)
        contagem["criados"] += 1
        if not dry_run:
            db.add(nova)

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return contagem


def _montar_series(db: Session, equipamento_id: int) -> dict:
    """serie (nao vazia) -> id, para o catalogo `equipamento_id` dado (regra 3)."""
    linhas = (
        db.query(EquipamentoCliente.serie, EquipamentoCliente.id)
        .filter(EquipamentoCliente.equipamento == equipamento_id)
        .all()
    )
    return {serie.strip(): id_ for serie, id_ in linhas if serie and serie.strip()}


def _escrever_csv_pendencias(caminho: str, pendencias: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["linha", "serie_aparelho", "serie_modulo", "empresa", "motivo"])
        writer.writeheader()
        for p in pendencias:
            writer.writerow(p)


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga do elo Phoebus<->Modulo a partir da planilha.")
    parser.add_argument("arquivo", help="Caminho do .xlsx")
    parser.add_argument("--origem", default="planilha", help="Texto gravado em instalacoes_modulo.origem")
    parser.add_argument("--phoebus-id", type=int, default=_PHOEBUS_ID_PADRAO,
                         help="Id do equipamento (catalogo) do Phoebus")
    parser.add_argument("--modulo-id", type=int, default=settings.EQUIPAMENTO_MODULO_ID,
                         help="Id do equipamento (catalogo) do Modulo de calibracao")
    parser.add_argument("--dry-run", action="store_true", help="Calcula mas nao grava")
    parser.add_argument("--pendencias", default=None, help="Caminho do CSV de pendencias")
    args = parser.parse_args()

    linhas = ler_planilha(args.arquivo)
    total_lidas = len(linhas)
    sem_modulo = sum(1 for l in linhas if not (l.get("serie_modulo") or "").strip())

    db = SessionLocal()
    try:
        series_phoebus = _montar_series(db, args.phoebus_id)
        series_modulo = _montar_series(db, args.modulo_id)

        elos, pendencias = resolver_elos(linhas, series_phoebus, series_modulo)
        contagem = aplicar(db, elos, origem=args.origem, dry_run=args.dry_run)
    finally:
        db.close()

    caminho_pendencias = args.pendencias or f"docs/pendencias-elo-{date.today().isoformat()}.csv"
    _escrever_csv_pendencias(caminho_pendencias, pendencias)

    motivos = Counter(p["motivo"] for p in pendencias)

    print(f"Linhas lidas: {total_lidas}")
    print(f"Ignoradas sem serie de modulo: {sem_modulo}")
    print(f"Elos: {contagem['criados']} criados, {contagem['fechados']} fechados, "
          f"{contagem['inalterados']} inalterados"
          + (" (dry-run, nada gravado)" if args.dry_run else ""))
    print(f"Pendencias: {len(pendencias)} (gravadas em {caminho_pendencias})")
    for motivo, qtd in motivos.most_common():
        print(f"  - {motivo}: {qtd}")


if __name__ == "__main__":
    main()
