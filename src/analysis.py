"""Statističke analize plata – sve funkcije vraćaju zbirne (agregirane) rezultate."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

# Grupe s manje zaposlenih od ovoga se ne prikazuju (zaštita privatnosti:
# plata pojedinca ne smije biti očitljiva iz zbirnog prikaza).
MIN_N = 5


def gini(x) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))


def opis(x: pd.Series) -> dict:
    return {
        "N": int(x.count()),
        "Prosjek (KM)": x.mean(),
        "Medijan (KM)": x.median(),
        "Std. devijacija": x.std(),
        "Min": x.min(),
        "Q1 (25%)": x.quantile(0.25),
        "Q3 (75%)": x.quantile(0.75),
        "P90": x.quantile(0.90),
        "Max": x.max(),
        "Gini koeficijent": gini(x),
        "Omjer P90/P10": x.quantile(0.9) / x.quantile(0.1),
    }


def po_grupi(df: pd.DataFrame, col: str, min_n: int = MIN_N, sort: str | None = "Medijan (KM)") -> pd.DataFrame:
    g = df.groupby(col, observed=True)["plata"]
    t = pd.DataFrame({
        "N": g.size(),
        "Prosjek (KM)": g.mean(),
        "Medijan (KM)": g.median(),
        "Q1 (25%)": g.quantile(0.25),
        "Q3 (75%)": g.quantile(0.75),
        "Std. devijacija": g.std(),
    })
    t = t[t["N"] >= min_n]
    t["Udio (%)"] = 100 * t["N"] / len(df)
    t["Razlika prosjek−medijan"] = t["Prosjek (KM)"] - t["Medijan (KM)"]
    if sort:
        t = t.sort_values(sort, ascending=False)
    t.index.name = col
    return t.round(2)


def ukrstena(df: pd.DataFrame, red: str, kol: str, min_n: int = 10) -> pd.DataFrame:
    """Medijan plate za kombinacije dviju kategorija (prazno ako je grupa < min_n)."""
    med = df.pivot_table(index=red, columns=kol, values="plata", aggfunc="median", observed=True)
    n = df.pivot_table(index=red, columns=kol, values="plata", aggfunc="size", observed=True)
    return med.where(n >= min_n).round(0)


def kruskal(df: pd.DataFrame, col: str, min_n: int = MIN_N) -> dict:
    grupe = [g["plata"].values for _, g in df.groupby(col, observed=True) if len(g) >= min_n]
    if len(grupe) < 2:
        return {"test": f"Kruskal-Wallis ({col})", "H": np.nan, "p": np.nan, "grupa": len(grupe)}
    h, p = stats.kruskal(*grupe)
    n, k = sum(map(len, grupe)), len(grupe)
    eps2 = (h - k + 1) / (n - k)  # epsilon² – veličina efekta
    return {"test": f"Kruskal-Wallis ({col})", "H": h, "p": p, "grupa": k, "N": n, "epsilon²": eps2}


def mann_whitney(df: pd.DataFrame, col: str, a: str, b: str) -> dict:
    x, y = df.loc[df[col] == a, "plata"], df.loc[df[col] == b, "plata"]
    u, p = stats.mannwhitneyu(x, y, alternative="two-sided")
    r = 1 - 2 * u / (len(x) * len(y))  # rang-biserijska korelacija
    return {"test": f"Mann-Whitney U ({a} vs {b})", "U": u, "p": p,
            f"medijan {a}": x.median(), f"medijan {b}": y.median(), "rang-biserijski r": -r}


def spearman_staz(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["godine_u_instituciji"])
    rho, p = stats.spearmanr(d["godine_u_instituciji"], d["plata"])
    return {"test": "Spearman (godine u instituciji ~ plata)", "rho": rho, "p": p, "N": len(d)}


def regresija(df: pd.DataFrame):
    """OLS: log(plata) ~ stručna sprema + sektor + godine u instituciji + vrsta ugovora."""
    d = df[df["sprema"] != "Nepoznato"].dropna(subset=["godine_u_instituciji"]).copy()
    d["sprema"] = d["sprema"].astype(str)
    d["sektor"] = d["sektor"].astype(str)
    d["log_plata"] = np.log(d["plata"])
    # Referentna grupa: uobičajena (SSS, osnovne škole, neodređeno) ako postoji u podacima, inače najčešća.
    ref = {}
    for col, zadano in [("sprema", "SSS"), ("sektor", "Osnovne škole"), ("ugovor", "Neodređeno")]:
        ref[col] = zadano if (d[col] == zadano).any() else d[col].mode().iat[0]
    clanovi = [f"C({c}, Treatment({ref[c]!r}))" for c in ["sprema", "sektor", "ugovor"] if d[c].nunique() > 1]
    model = smf.ols("log_plata ~ " + " + ".join(clanovi + ["godine_u_instituciji"]), data=d).fit(cov_type="HC3")
    model.referentne = ref
    koef = pd.DataFrame({
        "koeficijent": model.params,
        "efekat (%)": 100 * (np.exp(model.params) - 1),
        "p": model.pvalues,
    })
    koef.index = (koef.index.str.replace(r"C\((\w+), Treatment\('[^']+'\)\)\[T\.", r"\1: ", regex=True)
                  .str.rstrip("]"))
    return model, koef.round(4)


def kvalitet_podataka(svi: pd.DataFrame, analiticki: pd.DataFrame) -> pd.DataFrame:
    rows = [
        ("Ukupno zapisa u registru", len(svi)),
        ("Radni odnos prestao (datum prestanka u prošlosti)", int((~svi["aktivan"]).sum())),
        ("Aktivni zaposleni", int(svi["aktivan"].sum())),
        ("Aktivni s platom 0 KM ili bez plate", int((svi["aktivan"] & (svi["plata"].fillna(0) <= 0)).sum())),
        ("Aktivni s platom ispod praga (nepuna norma)", int((svi["aktivan"] & ~svi["puno_rv"] & (svi["plata"] > 0)).sum())),
        ("U glavnoj analizi (aktivni, puno radno vrijeme)", len(analiticki)),
        ("Različitih zapisa stručne spreme (prije čišćenja)", svi["sprema_izvorno"].nunique()),
        ("Nivoa stručne spreme (poslije čišćenja)", svi["sprema"].nunique()),
        ("Institucija", svi["institucija"].nunique()),
        ("Različitih naziva radnih mjesta", svi["radno_mjesto"].nunique()),
        ("Različitih zvanja", svi["zvanje"].nunique()),
    ]
    return pd.DataFrame(rows, columns=["Pokazatelj", "Vrijednost"]).set_index("Pokazatelj")


def staz_grupe(df: pd.DataFrame) -> pd.DataFrame:
    bins = [0, 2, 5, 10, 15, 20, 25, 30, 50]
    labels = ["0–2", "2–5", "5–10", "10–15", "15–20", "20–25", "25–30", "30+"]
    d = df.assign(staz=pd.cut(df["godine_u_instituciji"], bins, labels=labels, right=False))
    return po_grupi(d, "staz", sort=None)


# ================================================================ tumačenja (objašnjenja rezultata)

POJMOVI = {
    "N": "Broj zaposlenih u grupi.",
    "Udio (%)": "Koliki dio svih zaposlenih u analizi pripada ovoj grupi.",
    "Prosjek (KM)": "Aritmetička sredina: zbir svih plata podijeljen brojem zaposlenih. Osjetljiv je na vrlo visoke ili vrlo niske plate.",
    "Medijan (KM)": "Srednja plata: polovina zaposlenih ima manje, a polovina više. Bolje od prosjeka opisuje „tipičnu“ platu.",
    "Q1 (25%)": "Prvi kvartil: 25% zaposlenih ima platu nižu od ove vrijednosti.",
    "Q3 (75%)": "Treći kvartil: 75% zaposlenih ima platu nižu od ove vrijednosti (25% ima višu).",
    "Interkvartilni raspon": "Raspon od Q1 do Q3 – u njemu je srednjih 50% zaposlenih. Što je širi, plate u grupi su raznolikije.",
    "Std. devijacija": "Standardna devijacija: prosječno odstupanje plata od prosjeka. Veća vrijednost = veće razlike u plati unutar grupe.",
    "Razlika prosjek−medijan": "Pozitivna: nekoliko visokih plata podiže prosjek. Negativna: nekoliko niskih plata ga spušta.",
    "Min / Max": "Najniža i najviša plata u grupi.",
    "P90": "90. percentil: 10% zaposlenih ima platu veću od ove vrijednosti.",
    "Gini koeficijent": "Mjera nejednakosti od 0 (svi imaju istu platu) do 1 (jedna osoba ima sve). Ispod 0,25 se smatra niskom/umjerenom nejednakošću.",
    "Omjer P90/P10": "Koliko je puta plata na granici 10% najplaćenijih veća od plate na granici 10% najslabije plaćenih.",
    "p-vrijednost": "Vjerovatnoća da bismo ovakvu razliku dobili slučajno, kad stvarne razlike ne bi bilo. Ako je p < 0,05, razlika je statistički značajna.",
    "Kruskal-Wallis H": "Test koji provjerava razlikuju li se plate između tri ili više grupa. Ne pretpostavlja normalnu raspodjelu plata.",
    "ε² (epsilon²)": "Veličina efekta za Kruskal-Wallis: koliki dio razlika u platama „objašnjava“ grupa. ≈0,01 mali, ≈0,08 srednji, ≥0,26 veliki efekat.",
    "Mann-Whitney U": "Test koji poredi plate dvije grupe (npr. ugovor na određeno i na neodređeno).",
    "Rang-biserijski r": "Veličina efekta za Mann-Whitney: od 0 (nema razlike) do 1. ≈0,1 mali, ≈0,3 srednji, ≥0,5 veliki efekat.",
    "Spearman ρ": "Korelacija: povezanost dvije veličine (−1 do 1). Pozitivna = obje rastu zajedno. |ρ| < 0,3 je slaba veza.",
    "Regresija – efekat (%)": "Za koliko je posto plata veća ili manja u odnosu na referentnu grupu, kad su ostali faktori isti.",
    "R²": "Koliki dio ukupnih razlika u platama model objašnjava (0–1). 0,54 = 54%.",
}


def _br(v, dec=2):
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def p_tekst(p) -> str:
    if pd.isna(p):
        return "–"
    return "p < 0,001" if p < 0.001 else f"p = {_br(p, 3)}"


def _velicina(v, granice) -> str:
    v = abs(v)
    return "zanemariv" if v < granice[0] else "mali" if v < granice[1] else "srednji" if v < granice[2] else "veliki"


NAZIVI_KOLONA = {"sprema": "nivoa stručne spreme", "sektor": "sektora", "grupa_radnog_mjesta": "grupa radnih mjesta",
                 "grad": "gradova"}


def testovi_s_tumacenjem(df: pd.DataFrame) -> pd.DataFrame:
    """Statistički testovi u čitljivom obliku: šta se provjerava, rezultat i tumačenje običnim riječima."""
    redovi = []
    for col in ["sprema", "sektor", "grupa_radnog_mjesta"]:
        r = kruskal(df[df[col].astype(str) != "Nepoznato"], col)
        if pd.isna(r["p"]):
            continue
        vel = _velicina(r["epsilon²"], (0.01, 0.08, 0.26))
        znac = "statistički značajne" if r["p"] < 0.05 else "nisu statistički značajne"
        redovi.append({
            "Test": "Kruskal-Wallis",
            "Šta se provjerava": f"Razlikuju li se plate između {NAZIVI_KOLONA[col]}?",
            "Rezultat": f"H = {_br(r['H'], 0)}, {p_tekst(r['p'])}, ε² = {_br(r['epsilon²'])}",
            "Tumačenje": f"Razlike u platama između {NAZIVI_KOLONA[col]} su {znac}; efekat je {vel} "
                         f"(grupa objašnjava oko {_br(100 * r['epsilon²'], 0)}% razlika u platama).",
        })
    if df["ugovor"].nunique() == 2:
        r = mann_whitney(df, "ugovor", "Neodređeno", "Određeno")
        vel = _velicina(r["rang-biserijski r"], (0.1, 0.3, 0.5))
        redovi.append({
            "Test": "Mann-Whitney U",
            "Šta se provjerava": "Imaju li zaposleni na neodređeno i određeno različite plate?",
            "Rezultat": f"{p_tekst(r['p'])}, r = {_br(r['rang-biserijski r'])}",
            "Tumačenje": f"Medijan na neodređeno je {_br(r['medijan Neodređeno'], 0)} KM, a na određeno "
                         f"{_br(r['medijan Određeno'], 0)} KM. Razlika je "
                         f"{'statistički značajna' if r['p'] < 0.05 else 'nije statistički značajna'}, ali je efekat {vel}.",
        })
    r = spearman_staz(df)
    if not pd.isna(r["rho"]):
        redovi.append({
            "Test": "Spearmanova korelacija",
            "Šta se provjerava": "Je li plata veća što je zaposleni duže u instituciji?",
            "Rezultat": f"ρ = {_br(r['rho'])}, {p_tekst(r['p'])}",
            "Tumačenje": f"Veza je {dict(zanemariv='zanemariva', mali='slaba', srednji='umjerena', veliki='jaka')[_velicina(r['rho'], (0.1, 0.3, 0.5))]} i "
                         f"{'pozitivna' if r['rho'] > 0 else 'negativna'}: duži rad u instituciji tek neznatno prati veću platu.",
        })
    return pd.DataFrame(redovi)


def regresija_s_tumacenjem(df: pd.DataFrame):
    model, koef = regresija(df)
    k = koef.drop("Intercept").copy()
    r = model.referentne
    ref = {"sprema": f"sa spremom {r['sprema']}", "sektor": f"u sektoru „{r['sektor']}“",
           "ugovor": f"na {r['ugovor'].lower()}"}

    def tekst(idx, row):
        if idx.startswith("godine"):
            return f"Svaka dodatna godina u instituciji: plata u prosjeku {_br(row['efekat (%)'])}% veća."
        faktor, kat = idx.split(": ", 1)
        smjer = "veća" if row["efekat (%)"] >= 0 else "manja"
        opis = {"sprema": f"Zaposleni sa spremom {kat}", "sektor": f"Zaposleni u sektoru „{kat}“",
                "ugovor": f"Zaposleni na {kat.lower()}"}[faktor]
        return f"{opis}: plata oko {_br(abs(row['efekat (%)']), 0)}% {smjer} nego {ref[faktor]}, uz iste ostale faktore."

    k["Tumačenje"] = [tekst(i, r) for i, r in k.iterrows()]
    k["Značajno (p < 0,05)"] = np.where(k["p"] < 0.05, "da", "ne")
    k = k.rename(columns={"efekat (%)": "Efekat (%)", "koeficijent": "Koeficijent (log)"})
    k.index.name = "Faktor"
    return model, k[["Efekat (%)", "Značajno (p < 0,05)", "Tumačenje", "Koeficijent (log)", "p"]]
