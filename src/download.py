"""Preuzimanje javnog Registra zaposlenih u institucijama Tuzlanskog kantona.

Izvor: https://anticorruptk.ba/registri/registar-zaposlenih
Podaci se preuzimaju preko istog javnog servisa koji koristi tablica na stranici,
u blokovima i s pauzom između zahtjeva (da se server ne opterećuje).

Zaštita privatnosti: imena i prezimena se NE spremaju – uklanjaju se odmah
pri preuzimanju. Sprema se samo ono što je potrebno za zbirnu analizu.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

BASE = "https://anticorruptk.ba/fmreg/"
PAGE_URL = BASE + "registar_zaposlenih.php"
DATA_URL = BASE + "reg_zaposlenih/get_zaposleni.php"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.0 Safari/605.1.15"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "bs,hr;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": PAGE_URL,
}

# Polja koja zadržavamo (bez imena i prezimena).
KEEP = [
    "id",
    "Institucija",
    "Sjediste_organa",
    "Naziv_radnog_mjesta",
    "Strucna_sprema_zaposlenika",
    "Strucna_sprema_za_radno_mjesto",
    "Zvanje_zaposlenog_lica",
    "Osnovna_plata",
    "Spol",
    "Status",
    "Status_opis",
    "Datum_zasnivanja_radnog_odnosa_na_neodredeno_vrijeme",
    "Datum_prestanka_radnog_odnosa_na_neodredeno_vrijeme",
    "Datum_zasnivanja_radnog_odnosa_na_odredeno_vrijeme",
    "Datum_prestanka_radnog_odnosa_na_odredeno_vrijeme",
]

PAGE_SIZE = 1000
DELAY_S = 2.0


def _parse(text: str) -> dict:
    # Server ponekad iza JSON-a doda dodatni tekst – čitamo samo prvi JSON objekt.
    obj, _ = json.JSONDecoder().raw_decode(text.lstrip())
    return obj


def _fetch_page(session: requests.Session, start: int, length: int, draw: int) -> dict:
    payload = {
        "draw": draw,
        "start": start,
        "length": length,
        "search[value]": "",
        "search[regex]": "false",
        "order[0][column]": "0",
        "order[0][dir]": "asc",
        "columns[0][data]": "Ime",
        "search_ime": "", "search_prezime": "", "search_institucija": "",
        "search_min_prihod": "", "search_max_prihod": "", "search_st_sprema": "",
        "search_status": "", "search_godina": "", "search_mjesec": "",
    }
    for attempt in range(4):
        try:
            r = session.post(DATA_URL, data=payload, timeout=60)
            r.raise_for_status()
            return _parse(r.text)
        except (requests.RequestException, ValueError) as e:
            wait = 5 * (attempt + 1)
            print(f"  greška ({e}); ponavljam za {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Nije uspjelo preuzimanje bloka od zapisa {start}")


def download(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    first = _fetch_page(session, 0, PAGE_SIZE, 1)
    total = int(first["recordsTotal"])
    print(f"Ukupno zapisa u registru: {total}")
    rows = [{k: r.get(k) for k in KEEP} for r in first["data"]]

    draw = 2
    for start in range(PAGE_SIZE, total, PAGE_SIZE):
        time.sleep(DELAY_S)
        print(f"  preuzimam {start}–{min(start + PAGE_SIZE, total)} / {total}")
        page = _fetch_page(session, start, PAGE_SIZE, draw)
        rows.extend({k: r.get(k) for k in KEEP} for r in page["data"])
        draw += 1

    df = pd.DataFrame(rows).drop_duplicates(subset="id")
    stamp = datetime.now().strftime("%Y-%m-%d")
    path = out_dir / f"registar_{stamp}.csv"
    df.to_csv(path, index=False, encoding="utf-8")
    (out_dir / "latest.txt").write_text(path.name, encoding="utf-8")
    print(f"Spremljeno {len(df)} zapisa (od {total}) u {path}")
    return path


def latest_raw(out_dir: Path) -> Path | None:
    marker = out_dir / "latest.txt"
    if marker.exists():
        p = out_dir / marker.read_text(encoding="utf-8").strip()
        if p.exists():
            return p
    return None


if __name__ == "__main__":
    download(Path(__file__).resolve().parents[1] / "data" / "raw")
