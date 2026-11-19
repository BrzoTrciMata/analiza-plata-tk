"""Čišćenje i priprema podataka iz Registra zaposlenih TK."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

# Plate ispod ovog iznosa najčešće se odnose na nepunu normu / nepuno radno
# vrijeme (npr. nastavnici s nekoliko časova), pa se ne miješaju s platama za
# puno radno vrijeme u glavnoj analizi.
MIN_PLATA_PUNO_RV = 500.0

SPREMA_RED = [
    "NK / osnovna škola",
    "PK / NSS",
    "KV",
    "SSS",
    "VKV",
    "VŠS",
    "VSS",
    "Magistar / II ciklus",
    "Doktor nauka",
]

SEKTOR_RED = [
    "Osnovne škole",
    "Srednje škole",
    "Zdravstvo",
    "Univerzitet",
    "Kantonalni organi uprave",
    "Policija",
    "Javna preduzeća",
    "Kultura i baština",
    "Socijalna zaštita i posebno obrazovanje",
    "Ostale javne ustanove",
]


# ---------------------------------------------------------------- pomoćne

def parse_plata(s: pd.Series) -> pd.Series:
    t = (
        s.astype(str)
        .str.replace("KM", "", regex=False)
        .str.replace(r"[\s .]", "", regex=True)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(t, errors="coerce")


def parse_datum(s: pd.Series) -> pd.Series:
    """Datumi dolaze u više formata: '27.11.1995.', '2025-10-07T00:00:00', '2025-09-01 00:00:00'."""
    s = s.astype("string").str.strip()
    a = pd.to_datetime(s.str.rstrip("."), format="%d.%m.%Y", errors="coerce")
    b = pd.to_datetime(s.str.slice(0, 10), format="%Y-%m-%d", errors="coerce")
    d = a.fillna(b)
    # Nerealne vrijednosti (npr. godina 0997 ili 2029) tretiramo kao nepoznate.
    return d.where((d >= "1960-01-01") & (d <= pd.Timestamp.today()))


def _txt(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


# ---------------------------------------------------------------- stručna sprema

def mapiraj_spremu(raw) -> str:
    """Svodi stotine različitih zapisa stručne spreme na 9 standardnih nivoa.

    Kad zapis navodi više nivoa (npr. 'SSS/VSS'), uzima se najviši navedeni.
    """
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return "Nepoznato"
    s = _txt(raw).lower()
    if s in {"", "-", "nan"}:
        return "Nepoznato"

    medicina = re.search(r"dr\.? ?med", s)
    if not medicina and (
        "doktor" in s
        or re.search(r"\bdr\.? ?(sc|nauka)", s)
        or re.fullmatch(r"dr\.?", s)
        or s.startswith("dr, ")
    ):
        return "Doktor nauka"
    if (
        "magist" in s
        or re.search(r"\bmr\b|\bmr\.|\bma\b|vssma|master|\bmag\.", s)
        or re.search(r"\bii ciklus|drugi ciklus|300 ?ects|\+ ?60|viii", s)
    ):
        return "Magistar / II ciklus"
    # 'VSS VI stepen' = stari VI stepen (viša sprema)
    if re.search(r"vss\W*vi\b", s) and not re.search(r"vii|240|(?<!pred)bolonj|ciklus", s):
        return "VŠS"
    if (
        "vss" in s
        or re.search(r"\bvii\b|vii ?stepen|visok|fakultet|diplom|profesor|nastavnik|bachelor|\bba\b|bakal", s)
        or re.search(r"\bi ciklus|prvi ciklus|ects|etcs|ecst|\bbol\b|inžinj|dr\.? ?med|studij", s)
    ):
        return "VSS"
    if re.search(r"všs|vsš|všš|viša|\bvisa\b|\bvs\b|\bvš\b|\bvi\b|vi ?stepen|vi/1", s):
        return "VŠS"
    if re.search(r"vkv|\bvk\b|vkc|\bv stepen|v/1", s):
        return "VKV"
    if re.search(r"\biii\b", s) and not re.search(r"\biv\b", s):
        return "KV"
    if re.search(r"sss|sšs|ssp|\biv\b|gimnazij|srednj|medres|apsolvent|imatrikul", s):
        return "SSS"
    if re.search(r"\bkv\b|kv\b|^kv", s):
        return "KV"
    if re.search(r"\bpk\b|\bnss\b|\bns\b|polukv", s):
        return "PK / NSS"
    if re.search(r"nk|osnovn|\boš\b|\bos\b|razreda", s):
        return "NK / osnovna škola"
    return "Nepoznato"


# ---------------------------------------------------------------- sektor

def mapiraj_sektor(inst: str) -> str:
    s = _txt(inst).lower()
    if re.search(r"\boš\b|osnovna škola|osnovna muzička", s) or s.startswith("ju oš"):
        return "Osnovne škole"
    if re.search(r"\bmsš\b|\bms\b|gimnazij|srednja|škola", s):
        return "Srednje škole"
    if re.search(r"klinički|bolnica|zdravstv|jzu", s) and not s.startswith("ministarstvo"):
        return "Zdravstvo"
    if "univerzitet u tuzli" in s:
        return "Univerzitet"
    if re.search(r"unutrašnjih poslova|uprava policije", s):
        return "Policija"
    if s.startswith("jp ") or re.search(r"\bd\.d\.|rudnik", s):
        return "Javna preduzeća"
    if re.search(r"pozorište|biblioteka|muzej|arhiv|kulturni centar|naslijeđ|pejzaž|radiotelevizija", s):
        return "Kultura i baština"
    if re.search(r"dom za djecu|odgojni centar|autizam|rehabilitacij|smetnjama|slušanja", s):
        return "Socijalna zaštita i posebno obrazovanje"
    if re.search(
        r"ministarstvo|ured|uprava|skupština|pravobranilaštvo|agencija|komisija|direkcija robnih|pedagoški zavod|zavod za pružanje",
        s,
    ):
        return "Kantonalni organi uprave"
    return "Ostale javne ustanove"


def grad_iz_sjedista(adresa) -> str:
    if adresa is None or (isinstance(adresa, float) and np.isnan(adresa)):
        return "Nepoznato"
    m = re.search(r"\b7\d{4}\s+([A-Za-zČĆŽŠĐčćžšđ ]+)", str(adresa))
    return m.group(1).strip().title() if m else "Nepoznato"


def normaliziraj_naziv(s) -> str:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return "Nepoznato"
    t = _txt(s).strip(" .,-")
    return t[:1].upper() + t[1:].lower() if t else "Nepoznato"


# ---------------------------------------------------------------- grupe radnih mjesta
# Isto radno mjesto upisano je na mnogo načina (npr. "Nastavnik engleskog jezika",
# "Prof. engleskog jezika", "Nast.engleskog jezika"), pa se ~2.500 naziva svodi na
# ~25 grupa sličnih poslova. Pravila se provjeravaju redom – prvo pravilo koje odgovara pobjeđuje.
GRUPE_RM = [
    ("Rukovodioci (direktor, šef, pomoćnik)", r"direktor|šef|rukovodi|načelnik|pomoćnik ministra|ministar|sekretar ministar|premijer"
     r"|predsjedavaj|koordinator|glavn[ai] sestr|pročelnik|komandir|dekan|prodekan|rektor|prorektor|upravnik|smjenovođ|poslovođ"),
    ("Univerzitetski nastavnici", r"redovni profesor|vanredni profesor|docent|profesor emeritus"),
    ("Asistenti i saradnici na univerzitetu", r"viši asistent|asistent(?! u nastavi)|lektor|stručni saradnik u nastavi"),
    ("Doktori medicine i stomatologije", r"doktor medicine|doktor na specijal|doktor stomatolog|specijalist|ljekar|subspecijal|dr\.? med|doktor dentalne"),
    ("Medicinske sestre, tehničari i laboranti", r"medicinsk[aio]? ?sestr|tehničar|babica|primalja|fizioterapeut|laborant|laboratorij|radiolog"
     r"|instrumentar|farmac|biolog|biohemi|terapeut|dijaliz"),
    ("Nastavnici razredne nastave", r"razredn[ae] nastav|učitelj"),
    ("Asistenti u nastavi", r"asistent u nastavi"),
    ("Nastavnici predmetne nastave", r"nastavnik|nastavnica|profesor|prof\.|nast\.|vjeroučitelj|instruktor|majstor praktične|predmetn"
     r"|odgajatelj|vaspitač"),
    ("Pedagozi, psiholozi, defektolozi, soc. radnici", r"pedagog|psiholog|defektolog|logoped|socijaln|surdo|rehabilit|edukator"),
    ("Bibliotekari, arhivisti, muzejski radnici", r"bibliotek|arhiv|knjižni|muzej|kustos|dokumentalist"),
    ("Inspektori", r"inspektor"),
    ("Pravnici", r"pravn|pravobranil"),
    ("Ekonomisti, računovođe, finansije", r"ekonomist|računovo|finansij|knjigovo|blagajn|platn|komercijal|nabav|budžet|revizor|likvidator"
     r"|obračun|faktur"),
    ("Informatičari", r"informati|programer|sistem administrator|administrator sistema|računar"),
    ("Administrativni radnici i referenti", r"administrativ|referent|sekretar|daktilograf|kurir|dostavljač|operater|evidenc|protokol"
     r"|recepcion|telefonist|dokumentacij"),
    ("Stručni saradnici i savjetnici", r"savjetnik|stručni saradnik|saradnik|samostalni|stručni"),
    ("Higijeničari, spremači, praonice", r"higijeničar|spremač|čistač|pralja|perač|peglanje|vešer|pratilac bolesnika"),
    ("Domari, ložači i održavanje", r"domar|ložač|kućni majstor|održavanj|tehnička služba|majstor|mehaničar|električar|elektri|vodoinstalat"
     r"|bravar|stolar|kotlovnič|serviser|zavarivač|limar|moler|monter|rukovalac"),
    ("Kuhari i ishrana", r"kuhar|kuvar|servir|ekonom|ishran|pekar|kantin|kuhinj"),
    ("Vozači", r"vozač|šofer|kočijaš"),
    ("Čuvari, portiri, nadzornici", r"čuvar|portir|zaštitar|stražar|vratar|nadzornik|signalist"),
    ("Šumarstvo i rudarstvo (radnici)", r"šum|lugar|sjekač|rudar|rudnik|eksploat|kopač|motorist|traktor|pilan|primač|otpremač|drvn|sortiment"),
    ("Inženjeri i tehničko osoblje", r"inženjer|inžinjer|inžener|tehnolog|geodet|arhitekt|projektant|građevin|dispečer|kontrolor"
     r"|vatrogas"),
    ("Novinari, kultura i mediji", r"novinar|urednik|spiker|realizator|snimatelj|glumac|glumica|muzičar|kompozitor|dramaturg|režiser"
     r"|scenograf|kamerman|montažer|producent"),
    ("Pomoćni i fizički radnici", r"radnik|pomoćni|nekvalifik|manipulant|fizički|nosač|skladišt|magacin"),
]
_GRUPE_RE = [(g, re.compile(p)) for g, p in GRUPE_RM]


def mapiraj_grupu_rm(naziv) -> str:
    s = str(naziv).lower()
    for g, p in _GRUPE_RE:
        if p.search(s):
            return g
    return "Ostala radna mjesta"


# ---------------------------------------------------------------- glavno

def clean(raw_path: Path, out_path: Path) -> pd.DataFrame:
    df = pd.read_csv(raw_path, dtype=str)
    n0 = len(df)

    out = pd.DataFrame({"id": df["id"]})
    out["institucija"] = df["Institucija"].map(_txt)
    out["sektor"] = out["institucija"].map(mapiraj_sektor)
    out["grad"] = df["Sjediste_organa"].map(grad_iz_sjedista)
    out["radno_mjesto"] = df["Naziv_radnog_mjesta"].map(normaliziraj_naziv)
    out["grupa_radnog_mjesta"] = out["radno_mjesto"].map(mapiraj_grupu_rm)
    out["zvanje"] = df["Zvanje_zaposlenog_lica"].map(normaliziraj_naziv)
    out["sprema_izvorno"] = df["Strucna_sprema_zaposlenika"].map(lambda x: _txt(x) if isinstance(x, str) else "")
    out["sprema"] = df["Strucna_sprema_zaposlenika"].map(mapiraj_spremu)
    out["sprema_za_mjesto"] = df["Strucna_sprema_za_radno_mjesto"].map(mapiraj_spremu)
    out["plata"] = parse_plata(df["Osnovna_plata"])

    neod_od = parse_datum(df["Datum_zasnivanja_radnog_odnosa_na_neodredeno_vrijeme"])
    neod_do = parse_datum(df["Datum_prestanka_radnog_odnosa_na_neodredeno_vrijeme"])
    od_od = parse_datum(df["Datum_zasnivanja_radnog_odnosa_na_odredeno_vrijeme"])
    od_do = parse_datum(df["Datum_prestanka_radnog_odnosa_na_odredeno_vrijeme"])

    out["ugovor"] = np.where(df["Datum_zasnivanja_radnog_odnosa_na_neodredeno_vrijeme"].notna(),
                             "Neodređeno", "Određeno")
    # Prvi datum zasnivanja radnog odnosa u instituciji (određeno ili neodređeno).
    out["datum_zaposlenja"] = pd.concat([neod_od, od_od], axis=1).min(axis=1)
    danas = pd.Timestamp.today().normalize()
    out["godine_u_instituciji"] = ((danas - out["datum_zaposlenja"]).dt.days / 365.25).round(1)
    out["godina_zaposlenja"] = out["datum_zaposlenja"].dt.year

    # Radni odnos je prestao ako postoji datum prestanka u prošlosti
    # (za neodređeno, ili za određeno kad nema kasnijeg prelaska na neodređeno).
    prestao = (neod_do.notna() & (neod_do < danas)) | (
        out["ugovor"].eq("Određeno") & od_do.notna() & (od_do < danas)
    )
    out["aktivan"] = ~prestao

    nivo = {k: i for i, k in enumerate(SPREMA_RED)}
    a = out["sprema"].map(nivo)
    b = out["sprema_za_mjesto"].map(nivo)
    out["usklađenost_spreme"] = np.select(
        [a.isna() | b.isna(), a > b, a < b], ["Nepoznato", "Viša od tražene", "Niža od tražene"], "Odgovara"
    )

    out["puno_rv"] = out["plata"] >= MIN_PLATA_PUNO_RV
    out["sprema"] = pd.Categorical(out["sprema"], SPREMA_RED + ["Nepoznato"], ordered=True)
    out["sektor"] = pd.Categorical(out["sektor"], SEKTOR_RED, ordered=True)

    out.attrs["n_izvorno"] = n0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False) if out_path.suffix == ".parquet" else out.to_csv(out_path, index=False)
    return out


def ucitaj(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["datum_zaposlenja"])
    df["sprema"] = pd.Categorical(df["sprema"], SPREMA_RED + ["Nepoznato"], ordered=True)
    df["sektor"] = pd.Categorical(df["sektor"], SEKTOR_RED, ordered=True)
    return df


def analiticki_skup(df: pd.DataFrame) -> pd.DataFrame:
    """Skup za glavnu analizu: aktivni zaposleni, puno radno vrijeme (plata ≥ prag)."""
    return df[df["aktivan"] & df["puno_rv"]].copy()


if __name__ == "__main__":
    from src.download import latest_raw

    root = Path(__file__).resolve().parents[1]
    d = clean(latest_raw(root / "data" / "raw"), root / "data" / "processed" / "zaposleni.csv")
    print(d.head())
