import numpy as np
import pandas as pd
import pytest

from src.analysis import gini, po_grupi
from src.clean import mapiraj_sektor, mapiraj_spremu, parse_datum, parse_plata, grad_iz_sjedista


@pytest.mark.parametrize("raw, ocekivano", [
    ("VSS", "VSS"), ("VSS - VII stepen", "VSS"), ("VSS 240 ECTS", "VSS"), ("I ciklus 180 ECTS", "VSS"),
    ("VŠS", "VŠS"), ("VŠS - VI stepen", "VŠS"), ("VISA", "VŠS"), ("VSS VI stepen - predbolonjski", "VŠS"),
    ("SSS", "SSS"), ("SSS - IV stepen", "SSS"), ("Gimnazija", "SSS"),
    ("SSS - III stepen", "KV"), ("KV - Kvalificirani radnik", "KV"), ("VKV", "VKV"),
    ("NK", "NK / osnovna škola"), ("Osnovna škola", "NK / osnovna škola"), ("PK", "PK / NSS"),
    ("Magistar nauka", "Magistar / II ciklus"), ("VSS - II CIKLUS", "Magistar / II ciklus"), ("Mr.sci.", "Magistar / II ciklus"),
    ("Doktor nauka", "Doktor nauka"), ("Dr.sci.", "Doktor nauka"), ("Magistar nauka Doktor nauka", "Doktor nauka"),
    ("Dr. medicine", "VSS"), ("SSS/VSS", "VSS"), ("", "Nepoznato"), (np.nan, "Nepoznato"), ("-", "Nepoznato"),
])
def test_sprema(raw, ocekivano):
    assert mapiraj_spremu(raw) == ocekivano


def test_plata():
    s = parse_plata(pd.Series(["1 545,93 KM", "717,32 KM", "0,00 KM", "1.234,50 KM"]))
    assert s.tolist() == [1545.93, 717.32, 0.0, 1234.5]


def test_datum_formati():
    d = parse_datum(pd.Series(["27.11.1995.", "2025-10-07T00:00:00", "2024-03-11 00:00:00", "09.01.0997.", None]))
    assert d.iloc[0] == pd.Timestamp("1995-11-27")
    assert d.iloc[1] == pd.Timestamp("2025-10-07")
    assert d.iloc[2] == pd.Timestamp("2024-03-11")
    assert pd.isna(d.iloc[3]) and pd.isna(d.iloc[4])


def test_sektor():
    assert mapiraj_sektor("JU OŠ Sapna") == "Osnovne škole"
    assert mapiraj_sektor("JU MSŠ Živinice") == "Srednje škole"
    assert mapiraj_sektor("JZU Univerzitetski klinički centar Tuzla") == "Zdravstvo"
    assert mapiraj_sektor("Ministarstvo zdravstva") == "Kantonalni organi uprave"
    assert mapiraj_sektor("Uprava policije") == "Policija"
    assert mapiraj_sektor("JP Međunarodni aerodrom Tuzla") == "Javna preduzeća"


def test_grad():
    assert grad_iz_sjedista("Mula Mustafe Bašeskije 2, 75320 Gračanica") == "Gračanica"
    assert grad_iz_sjedista("Omladinskih radnih brigada 4 , 75290 Banovići") == "Banovići"


def test_gini():
    assert gini([100, 100, 100]) == pytest.approx(0)
    assert gini([0, 0, 0, 100]) == pytest.approx(0.75)


def test_privatnost_male_grupe_skrivene():
    df = pd.DataFrame({"g": ["a"] * 10 + ["b"] * 2, "plata": range(12)})
    t = po_grupi(df, "g")
    assert "b" not in t.index and "a" in t.index


@pytest.mark.parametrize("naziv, grupa", [
    ("Nastavnik engleskog jezika", "Nastavnici predmetne nastave"),
    ("Prof. engleskog jezika", "Nastavnici predmetne nastave"),
    ("Nastavnik razredne nastave", "Nastavnici razredne nastave"),
    ("Asistent u nastavi", "Asistenti u nastavi"),
    ("Nastavnik/ vanredni profesor", "Univerzitetski nastavnici"),
    ("Doktor medicine-specijalista", "Doktori medicine i stomatologije"),
    ("Odgovorna medicinska sestra-tehničar", "Medicinske sestre, tehničari i laboranti"),
    ("Higijeničar", "Higijeničari, spremači, praonice"),
    ("Šef odjeljenja", "Rukovodioci (direktor, šef, pomoćnik)"),
    ("Referent za administrativne poslove", "Administrativni radnici i referenti"),
    ("Vozač", "Vozači"),
    ("Odjeljenje hirurgije", "Ostala radna mjesta"),
])
def test_grupa_radnog_mjesta(naziv, grupa):
    from src.clean import mapiraj_grupu_rm
    assert mapiraj_grupu_rm(naziv) == grupa
