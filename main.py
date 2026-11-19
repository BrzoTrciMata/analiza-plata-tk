"""Analiza plata zaposlenih u institucijama Tuzlanskog kantona.

Pokretanje:
    python main.py              # koristi već preuzete podatke (ili ih preuzme ako ih nema)
    python main.py --osvjezi    # ponovo preuzima podatke s anticorruptk.ba
Dashboard:
    streamlit run app.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src import analysis as A
from src.clean import MIN_PLATA_PUNO_RV, SPREMA_RED, analiticki_skup, clean
from src.download import download, latest_raw
from src.excel import napisi as napisi_excel
from src.figures import napravi_sve

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed" / "zaposleni.csv"
OUT = ROOT / "output"


def fmt(v, dec=0):
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--osvjezi", action="store_true", help="ponovo preuzmi podatke sa stranice")
    args = ap.parse_args()

    raw = latest_raw(RAW)
    if args.osvjezi or raw is None:
        print("1/4 Preuzimanje podataka…")
        raw = download(RAW)
    else:
        print(f"1/4 Koristim preuzete podatke: {raw.name}")

    print("2/4 Čišćenje podataka…")
    svi = clean(raw, PROCESSED)
    d = analiticki_skup(svi)

    print("3/4 Statističke analize i tabele…")
    tdir = OUT / "tables"
    tdir.mkdir(parents=True, exist_ok=True)
    for stari in tdir.glob("*"):
        stari.unlink()
    spr = A.po_grupi(d, "sprema", sort=None)
    spr = spr.reindex([s for s in SPREMA_RED + ["Nepoznato"] if s in spr.index])
    rm = A.po_grupi(d, "radno_mjesto")
    rm.insert(0, "Grupa radnog mjesta", d.groupby("radno_mjesto")["grupa_radnog_mjesta"].first().reindex(rm.index))
    testovi = pd.DataFrame([
        A.kruskal(d, "sprema"), A.kruskal(d, "sektor"),
        A.mann_whitney(d, "ugovor", "Neodređeno", "Određeno"), A.spearman_staz(d),
    ]).set_index("test")
    model, koef = A.regresija_s_tumacenjem(d)
    OBJ = ("Medijan = srednja plata (pola zaposlenih ima manje, pola više); prosjek = zbir plata / broj zaposlenih. "
           "Q1–Q3 = raspon u kojem je srednjih 50% zaposlenih. Std. devijacija = koliko se plate u grupi razlikuju. "
           "Razlika prosjek−medijan > 0 znači da nekoliko visokih plata podiže prosjek. "
           f"Grupe s manje od {A.MIN_N} zaposlenih nisu prikazane (privatnost). Detaljnije: list „Objašnjenja“.")
    lista = [
        ("Kvalitet podataka", A.kvalitet_podataka(svi, d), "Kvalitet i obim podataka",
         "Koliko je zapisa preuzeto, koliko je isključeno iz analize i zašto, te koliko je različitih zapisa svedeno na kategorije."),
        ("Opšta statistika", pd.DataFrame(A.opis(d["plata"]), index=["Vrijednost"]).T.round(2), "Opšta statistika osnovnih plata",
         "Osnovni pokazatelji za sve zaposlene u analizi. Gini koeficijent mjeri nejednakost (0 = svi isto, 1 = maksimalna "
         "nejednakost); P90/P10 = koliko je puta plata na granici 10% najplaćenijih veća od one na granici 10% najslabije plaćenih."),
        ("Stručna sprema", spr, "Plate po stručnoj spremi", OBJ),
        ("Sektor", A.po_grupi(d, "sektor"), "Plate po sektorima", OBJ),
        ("Grupa radnog mjesta", A.po_grupi(d, "grupa_radnog_mjesta"), "Plate po vrsti posla (grupe radnih mjesta)",
         f"{d['radno_mjesto'].nunique()} različitih naziva radnih mjesta svedeno je na grupe sličnih poslova, jer je isti posao "
         "upisan na mnogo načina. " + OBJ),
        ("Radno mjesto", rm, f"Plate po pojedinačnom radnom mjestu (svi nazivi s ≥{A.MIN_N} zaposlenih)",
         "Nazivi radnih mjesta kako su upisani u registar. Nazivi s manje od 5 zaposlenih nisu prikazani zbog privatnosti – "
         "oni su obuhvaćeni preko kolone/lista „Grupa radnog mjesta“. " + OBJ),
        ("Zvanje", A.po_grupi(d, "zvanje"), f"Plate po zvanju (≥{A.MIN_N} zaposlenih)",
         "Zvanje = stečeno obrazovanje ili titula (npr. diplomirani ekonomista), ne posao koji osoba obavlja. " + OBJ),
        ("Institucija", A.po_grupi(d, "institucija"), "Plate po instituciji", OBJ),
        ("Grad", A.po_grupi(d, "grad"), "Plate po gradu/općini sjedišta institucije", OBJ),
        ("Vrsta ugovora", A.po_grupi(d, "ugovor"), "Plate prema vrsti ugovora", OBJ),
        ("Usklađenost spreme", A.po_grupi(d, "usklađenost_spreme"), "Odgovara li sprema zaposlenog spremi traženoj za radno mjesto",
         "„Viša od tražene“ = zaposleni ima višu spremu nego što radno mjesto traži (npr. VSS na mjestu za SSS). " + OBJ),
        ("Godine u instituciji", A.staz_grupe(d), "Plate prema godinama rada u instituciji",
         "Godine od prvog zasnivanja radnog odnosa u toj instituciji (ne ukupan radni staž). " + OBJ),
        ("Sprema x sektor", A.ukrstena(d, "sprema", "sektor"), "Medijan plate (KM): stručna sprema × sektor",
         "Svako polje je medijan plate za kombinaciju spreme (red) i sektora (kolona). Prazno = manje od 10 zaposlenih."),
        ("Statistički testovi", A.testovi_s_tumacenjem(d).set_index("Test"), "Statistički testovi s tumačenjem",
         "p < 0,05 znači da razlika vjerovatno nije slučajna. Veličina efekta (ε², r, ρ) govori koliko je razlika velika u praksi. "
         "Korišteni su neparametarski testovi jer plate nisu normalno raspodijeljene."),
        ("Regresija", koef, f"Višestruka regresija (R² = {model.rsquared:.2f})".replace(".", ","),
         "Model: log(plata) ~ stručna sprema + sektor + godine u instituciji + vrsta ugovora. Efekat (%) = razlika u plati u odnosu "
         "na referentnu grupu (SSS, osnovne škole, ugovor na neodređeno) kad su ostali faktori isti. "
         f"R² = {model.rsquared:.2f} znači da model objašnjava {100 * model.rsquared:.0f}% razlika u platama.".replace("0.", "0,")),
    ]
    tabele = {ime: t for ime, t, _, _ in lista}
    xlsx = tdir / "rezultati_analize.xlsx"
    napisi_excel(xlsx, lista, A.POJMOVI)
    for ime, t in tabele.items():
        t.to_csv(tdir / f"{ime.lower().replace(' ', '_')}.csv")

    print("4/4 Grafikoni…")
    figs = napravi_sve(svi, d, OUT / "figures")

    # Sažetak ključnih nalaza
    o = A.opis(d["plata"])
    sek = tabele["Sektor"]
    ks = testovi.loc["Kruskal-Wallis (sprema)"]
    sazetak = f"""# Ključni nalazi

*Podaci preuzeti: {raw.stem.replace('registar_', '')} · Izvor: Registar zaposlenih u institucijama TK*

- U registru je **{fmt(len(svi))}** zapisa iz **{svi['institucija'].nunique()}** institucija;
  u glavnoj analizi je **{fmt(len(d))}** aktivnih zaposlenih s platom za puno radno vrijeme (≥ {MIN_PLATA_PUNO_RV:.0f} KM).
- **Prosječna** osnovna plata je **{fmt(o['Prosjek (KM)'])} KM**, a **medijalna {fmt(o['Medijan (KM)'])} KM**.
  Polovina zaposlenih ima između {fmt(o['Q1 (25%)'])} i {fmt(o['Q3 (75%)'])} KM.
- Nejednakost je umjerena: Gini = {fmt(o['Gini koeficijent'], 2)}; plata na granici 10% najplaćenijih (P90)
  je {fmt(o['Omjer P90/P10'], 1)}× veća od plate na granici 10% najslabije plaćenih (P10).
- **Stručna sprema** je najjači pojedinačni faktor (Kruskal-Wallis, ε² = {fmt(ks['epsilon²'], 2)}, p < 0,001):
  medijan raste od {fmt(spr.loc['NK / osnovna škola', 'Medijan (KM)'])} KM (NK) i {fmt(spr.loc['SSS', 'Medijan (KM)'])} KM (SSS)
  do {fmt(spr.loc['VSS', 'Medijan (KM)'])} KM (VSS) i {fmt(spr.loc['Doktor nauka', 'Medijan (KM)'])} KM (doktori nauka).
- Najviši medijan ima sektor **{sek.index[0]}** ({fmt(sek.iloc[0]['Medijan (KM)'])} KM),
  a najniži **{sek.index[-1]}** ({fmt(sek.iloc[-1]['Medijan (KM)'])} KM).
- Gdje je prosjek znatno iznad medijana (npr. Univerzitet, Zdravstvo), manji broj visokih plata
  (profesori, ljekari specijalisti) „vuče“ prosjek gore – zato je medijan bolji pokazatelj „tipične“ plate.
- Zaposleni na **određeno** vrijeme imaju medijan {fmt(testovi.iloc[2]['medijan Određeno'])} KM naspram
  {fmt(testovi.iloc[2]['medijan Neodređeno'])} KM za neodređeno.
- Regresijski model (sprema + sektor + godine u instituciji + ugovor) objašnjava **{100 * model.rsquared:.0f}%**
  varijacije (logaritma) plate.

## Napomene o metodologiji
- Imena i prezimena nisu preuzeta niti spremljena; svi rezultati su zbirni, a grupe s manje od {A.MIN_N}
  zaposlenih se ne prikazuju.
- Zapisi s datumom prestanka radnog odnosa u prošlosti isključeni su iz analize.
- Plate ispod {MIN_PLATA_PUNO_RV:.0f} KM (najčešće nastavnici s nepunom normom) i plate od 0 KM isključene su
  iz glavne analize; u dashboardu se prag može mijenjati.
- {svi['sprema_izvorno'].nunique()} različitih zapisa stručne spreme svedeno je na {len(SPREMA_RED)} standardnih nivoa
  (kod višestrukih navoda uzet je najviši).
- „Godine u instituciji" računaju se od prvog datuma zasnivanja radnog odnosa u toj instituciji, a ne od ukupnog staža.
- Analizira se **osnovna** plata kako je unesena u registar (bez dodataka, toplog obroka i sl.).
"""
    (OUT / "kljucni_nalazi.md").write_text(sazetak, encoding="utf-8")
    print(sazetak)
    print(f"Tabele: {xlsx}\nGrafikoni: {len(figs)} u {OUT / 'figures'}\nDashboard: streamlit run app.py")


if __name__ == "__main__":
    main()
