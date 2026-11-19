"""Uredan Excel izvještaj: naslov i objašnjenje na vrhu svakog lista, stilizovano zaglavlje,
formati brojeva, trake u koloni medijana i poseban list s objašnjenjima pojmova."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

PLAVA = "2A78D6"
TAMNA = "0D366B"
SVIJETLA = "F4F7FB"
LINIJA = "E3E6EB"

F_NASLOV = Font(name="Calibri", size=16, bold=True, color=TAMNA)
F_OPIS = Font(name="Calibri", size=10.5, color="52514E", italic=True)
F_ZAGLAVLJE = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
F_TEKST = Font(name="Calibri", size=11, color="0B0B0B")
F_INDEKS = Font(name="Calibri", size=11, bold=True, color="0B0B0B")
FILL_ZAG = PatternFill("solid", fgColor=PLAVA)
FILL_TRAKA = PatternFill("solid", fgColor=SVIJETLA)
DONJA = Border(bottom=Side(style="thin", color=LINIJA))


def _format(kolona: str) -> str | None:
    k = kolona.lower()
    if "(km)" in k or k in {"q1 (25%)", "q3 (75%)", "p90", "min", "max", "std. devijacija", "razlika prosjek−medijan"}:
        return '#,##0" KM"'
    if "%" in k:
        return '0.0"%"'
    if k in {"n", "vrijednost", "grupa"}:
        return "#,##0"
    if k in {"p"}:
        return "0.0000"
    return None


LIJEPA_IMENA = {"radno_mjesto": "Radno mjesto", "sprema": "Stručna sprema", "sektor": "Sektor",
                "grupa_radnog_mjesta": "Vrsta posla", "zvanje": "Zvanje", "institucija": "Institucija", "grad": "Grad",
                "ugovor": "Vrsta ugovora", "usklađenost_spreme": "Usklađenost spreme", "staz": "Godine u instituciji",
                "index": "", "Grupa radnog mjesta": "Vrsta posla"}
REDOSLIJED = ["N", "Udio (%)", "Medijan (KM)", "Prosjek (KM)", "Q1 (25%)", "Q3 (75%)", "Std. devijacija",
              "Razlika prosjek−medijan"]


def _list(wb: Workbook, ime: str, t: pd.DataFrame, naslov: str, opis: str):
    ws = wb.create_sheet(ime[:31])
    if "N" in t.columns and "Medijan (KM)" in t.columns:
        ost = [c for c in t.columns if c not in REDOSLIJED]
        t = t[ost + [c for c in REDOSLIJED if c in t.columns]]
    t = t.reset_index().rename(columns=LIJEPA_IMENA)
    ncol = len(t.columns)
    ws["A1"] = naslov
    ws["A1"].font = F_NASLOV
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(ncol, 6))
    ws["A2"] = opis
    ws["A2"].font = F_OPIS
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = 15 * max(2, len(opis) // 110 + 1)

    r0 = 4
    for j, c in enumerate(t.columns, 1):
        cell = ws.cell(r0, j, str(c))
        cell.font, cell.fill = F_ZAGLAVLJE, FILL_ZAG
        cell.alignment = Alignment(horizontal="center" if j > 1 else "left", vertical="center", wrap_text=True)
    ws.row_dimensions[r0].height = 32

    for i, row in enumerate(t.itertuples(index=False), r0 + 1):
        for j, v in enumerate(row, 1):
            if isinstance(v, float) and pd.isna(v):
                v = None
            cell = ws.cell(i, j, v.item() if hasattr(v, "item") else (str(v) if not isinstance(v, (int, float, str, type(None))) else v))
            cell.font = F_INDEKS if j == 1 else F_TEKST
            cell.border = DONJA
            if (i - r0) % 2 == 0:
                cell.fill = FILL_TRAKA
            fmt = _format(str(t.columns[j - 1]))
            if fmt and isinstance(cell.value, (int, float)):
                cell.number_format = fmt
            if isinstance(cell.value, str) and len(cell.value) > 60:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

    # širine kolona
    for j, c in enumerate(t.columns, 1):
        vals = [str(c)] + [str(v) for v in t.iloc[:, j - 1].head(200)]
        sirina = min(max(len(v) for v in vals) + 2, 70 if j == 1 else 60)
        if pd.api.types.is_numeric_dtype(t.iloc[:, j - 1]):
            sirina = max(12, min(sirina, 16))
        ws.column_dimensions[get_column_letter(j)].width = sirina

    # trake (data bars) u koloni medijana
    if "Medijan (KM)" in t.columns and len(t):
        col = get_column_letter(list(t.columns).index("Medijan (KM)") + 1)
        ws.conditional_formatting.add(f"{col}{r0 + 1}:{col}{r0 + len(t)}",
                                      DataBarRule(start_type="num", start_value=0, end_type="max", color=PLAVA))
    ws.freeze_panes = ws.cell(r0 + 1, 2)
    ws.sheet_view.showGridLines = False


def napisi(path: Path, tabele: list[tuple[str, pd.DataFrame, str, str]], pojmovi: dict[str, str]):
    """tabele: lista (ime lista, tabela, naslov, objašnjenje)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Objašnjenja"
    ws["A1"] = "Objašnjenje pojmova i kolona"
    ws["A1"].font = F_NASLOV
    ws["A2"] = "Kratak rječnik statističkih pojmova koji se pojavljuju u tabelama i grafikonima."
    ws["A2"].font = F_OPIS
    for j, h in enumerate(["Pojam", "Šta znači"], 1):
        c = ws.cell(4, j, h)
        c.font, c.fill = F_ZAGLAVLJE, FILL_ZAG
    for i, (k, v) in enumerate(pojmovi.items(), 5):
        a, b = ws.cell(i, 1, k), ws.cell(i, 2, v)
        a.font, b.font = F_INDEKS, F_TEKST
        b.alignment = Alignment(wrap_text=True, vertical="top")
        a.alignment = Alignment(vertical="top")
        a.border = b.border = DONJA
        if i % 2 == 0:
            a.fill = b.fill = FILL_TRAKA
        ws.row_dimensions[i].height = 15 * (len(v) // 95 + 1) + 4
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 110
    ws.sheet_view.showGridLines = False

    # sadržaj
    r = len(pojmovi) + 7
    ws.cell(r, 1, "Listovi u ovom dokumentu").font = Font(bold=True, size=12, color=TAMNA)
    for i, (ime, _, naslov, _) in enumerate(tabele, r + 1):
        ws.cell(i, 1, ime).font = F_INDEKS
        ws.cell(i, 2, naslov).font = F_TEKST

    for ime, t, naslov, opis in tabele:
        _list(wb, ime, t, naslov, opis)
    wb.save(path)
