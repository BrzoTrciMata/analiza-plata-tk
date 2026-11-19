"""Grafikoni za prezentaciju (PNG, 16:9, 200 dpi).

Svaki grafikon ima: naslov s glavnim zaključkom, podnaslov, okvir „Kako čitati“ s objašnjenjem
i izvor podataka. Stubići imaju zaobljen kraj, mreža je diskretna, vrijednosti su upisane direktno.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, Rectangle

from src import analysis as A
from src.clean import MIN_PLATA_PUNO_RV, SPREMA_RED

# Paleta (validirana referentna paleta: plava = glavna serija, narandžasta = druga)
PLAVA = "#2a78d6"
PLAVA_SVIJETLA = "#cde2fb"
NARANDZASTA = "#eb6834"
SIVA = "#c9c8c2"
STAZA = "#efeee9"          # pozadinska "staza" iza stubića
TEKST = "#0b0b0b"
TEKST2 = "#52514e"
TEKST3 = "#8a8983"
POZADINA = "#ffffff"
PANEL = "#f4f7fb"          # okvir s objašnjenjem
MREZA = "#ebeae6"
SEKV = ["#e6f0fc", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

W, H_STD = 12.8, 7.6       # 16:9 (+ prostor za objašnjenje)


def _br(v, dec=0):
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


KM = mticker.FuncFormatter(lambda x, _: _br(x))


def _font() -> str:
    dostupni = {f.name for f in font_manager.fontManager.ttflist}
    for f in ["Avenir Next", "Helvetica Neue", "Inter", "Arial", "DejaVu Sans"]:
        if f in dostupni:
            return f
    return "DejaVu Sans"


def _stil():
    plt.rcParams.update({
        "figure.facecolor": POZADINA, "axes.facecolor": POZADINA, "savefig.facecolor": POZADINA,
        "font.family": _font(), "font.size": 12,
        "axes.edgecolor": MREZA, "axes.labelcolor": TEKST2, "axes.labelsize": 11.5,
        "xtick.color": TEKST2, "ytick.color": TEKST, "xtick.labelsize": 11, "ytick.labelsize": 11.5,
        "xtick.major.size": 0, "ytick.major.size": 0, "xtick.major.pad": 6, "ytick.major.pad": 8,
        "axes.grid": True, "grid.color": MREZA, "grid.linewidth": 0.9, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
        "axes.spines.bottom": False, "legend.frameon": False, "legend.fontsize": 11,
    })


# ------------------------------------------------------------------ okvir slike

def _okvir(naslov: str, podnaslov: str, objasnjenje: str, n: int, h: float = H_STD, w: float = W):
    """Napravi sliku sa zaglavljem i podnožjem; vraća (fig, ax) gdje ax zauzima srednji dio."""
    fig = plt.figure(figsize=(w, h))
    linije = textwrap.wrap(objasnjenje, width=150)
    h_obj = (0.50 + 0.30 * len(linije)) / h       # visina okvira s objašnjenjem (udio visine slike)
    h_head = 1.30 / h
    dno = 0.045 + h_obj + 0.85 / h                 # prostor za oznake i naziv x-ose
    ax = fig.add_axes([0.0, dno, 1.0, 1 - h_head - dno - 0.02])

    x0 = 0.035
    fig.text(x0, 1 - 0.32 / h, naslov, fontsize=20, fontweight="bold", color=TEKST, va="top")
    fig.text(x0, 1 - 0.78 / h, podnaslov, fontsize=12.5, color=TEKST2, va="top")

    # okvir "Kako čitati"
    y_obj = 0.045
    fig.patches.append(FancyBboxPatch((x0, y_obj), 1 - 2 * x0, h_obj, transform=fig.transFigure,
                                      boxstyle="round,pad=0,rounding_size=0.012", facecolor=PANEL,
                                      edgecolor="none", zorder=0, mutation_aspect=w / h))
    fig.patches.append(Rectangle((x0, y_obj), 0.004, h_obj, transform=fig.transFigure, facecolor=PLAVA,
                                 edgecolor="none"))
    fig.text(x0 + 0.018, y_obj + h_obj - 0.17 / h, "KAKO ČITATI", fontsize=9.5, fontweight="bold", color=PLAVA,
             va="top")
    fig.text(x0 + 0.018, y_obj + h_obj - 0.42 / h, "\n".join(linije), fontsize=10.5, color=TEKST, va="top",
             linespacing=1.4)
    fig.text(x0, 0.014, f"Izvor: Registar zaposlenih u institucijama Tuzlanskog kantona (anticorruptk.ba) · "
                        f"N = {_br(n)} zaposlenih · osnovna plata", fontsize=9, color=TEKST3)
    return fig, ax


def _ax_unutra(fig, ax, lijevo=0.035, desno=0.035):
    """Suzi ose tako da imaju prostor za oznake (ax je inicijalno pune širine)."""
    p = ax.get_position()
    ax.set_position([lijevo, p.y0, 1 - lijevo - desno, p.height])


def _spremi(fig, path: Path):
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _skrati(s: str, n=46) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# ------------------------------------------------------------------ zaobljeni stubići

def _zaobljeni_barh(ax, y, vrijednosti, visina=0.62, boja=PLAVA, xmax=None):
    """Horizontalni stubići s blago zaobljenim krajem (početak ostaje ravan na osi)."""
    fig = ax.figure
    fig.canvas.draw()
    bb = ax.get_window_extent()
    x_raspon = np.diff(ax.get_xlim())[0]
    y_raspon = np.diff(ax.get_ylim())[0]
    px_x = bb.width / x_raspon          # piksela po jedinici x
    px_y = bb.height / abs(y_raspon)    # piksela po jedinici y
    r_px = 4 * fig.dpi / 72             # ~4 pt radijus
    r_x = r_px / px_x
    for yi, v in zip(y, vrijednosti):
        if v <= 0:
            continue
        r = min(r_x, v / 2)
        ax.add_patch(FancyBboxPatch((0, yi - visina / 2), v, visina,
                                    boxstyle=f"round,pad=0,rounding_size={r}", mutation_aspect=px_x / px_y,
                                    facecolor=boja, edgecolor="none", zorder=2))
        ax.add_patch(Rectangle((0, yi - visina / 2), max(v - r, 0), visina, facecolor=boja, edgecolor="none",
                               zorder=2))


def bar_medijan(t: pd.DataFrame, naslov: str, podnaslov: str, objasnjenje: str, path: Path, n_ukupno: int,
                label_w=46, sort=True):
    """Medijan (stubić) + interkvartilni raspon (linija) + prosjek (tačka) za svaku grupu."""
    t = (t.sort_values("Medijan (KM)") if sort else t.iloc[::-1]).copy()
    h = max(6.6, 0.40 * len(t) + 5.4)
    fig, ax = _okvir(naslov, podnaslov, objasnjenje, n_ukupno, h=h)
    y = np.arange(len(t))
    xmax = max(t["Q3 (75%)"].max(), t["Prosjek (KM)"].max()) * 1.12
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.7, len(t) - 0.3)
    _ax_unutra(fig, ax, lijevo=0.36 if label_w > 30 else 0.22, desno=0.075)
    ax.barh(y, [xmax] * len(t), height=0.62, color=STAZA, zorder=1)          # staza
    _zaobljeni_barh(ax, y, t["Medijan (KM)"].values)
    ax.hlines(y, t["Q1 (25%)"], t["Q3 (75%)"], color=TEKST, lw=1.4, alpha=0.75, zorder=3)
    for yi, a, b in zip(y, t["Q1 (25%)"], t["Q3 (75%)"]):
        ax.vlines([a, b], yi - 0.13, yi + 0.13, color=TEKST, lw=1.4, alpha=0.75, zorder=3)
    ax.scatter(t["Prosjek (KM)"], y, s=58, color=NARANDZASTA, edgecolor="white", linewidth=1.8, zorder=4)
    for yi, v in zip(y, t["Medijan (KM)"]):
        ax.text(xmax * 0.008, yi, _br(v), va="center", ha="left", color="white", fontsize=10,
                fontweight="bold", zorder=5)
    ax.set_yticks(y, [_skrati(str(i), label_w) for i in t.index])
    for yi, nn in zip(y, t["N"]):
        ax.text(1.003, yi, f"n={_br(nn)}", transform=ax.get_yaxis_transform(), va="center", fontsize=9,
                color=TEKST3)
    ax.xaxis.set_major_formatter(KM)
    ax.set_xlabel("Osnovna plata (KM)")
    ax.grid(axis="y", visible=False)
    # legenda (ručno, iznad grafikona)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=PLAVA, label="Medijan"),
                       Line2D([], [], marker="o", ls="", color=NARANDZASTA, markeredgecolor="white", ms=8, label="Prosjek"),
                       Line2D([], [], color=TEKST, lw=1.4, label="Srednjih 50% zaposlenih (Q1–Q3)")],
              loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, fontsize=10.5, handlelength=1.4,
              columnspacing=1.6)
    _spremi(fig, path)


OBJ_BAR = ("Plavi stubić je medijan: polovina zaposlenih u grupi ima manju, a polovina veću platu. Narandžasta tačka je "
           "prosjek. Tanka crna linija pokazuje raspon u kojem je srednjih 50% zaposlenih (od Q1 do Q3) – što je "
           "duža, to se plate unutar grupe više razlikuju. Ako je tačka desno od kraja stubića, nekoliko visokih "
           "plata podiže prosjek. n = broj zaposlenih u grupi.")


# ------------------------------------------------------------------ svi grafikoni

def napravi_sve(svi: pd.DataFrame, d: pd.DataFrame, out: Path) -> list[Path]:
    _stil()
    out.mkdir(parents=True, exist_ok=True)
    for stari in out.glob("*.png"):
        stari.unlink()
    n = len(d)
    files: list[Path] = []
    o = A.opis(d["plata"])

    def f(ime):
        files.append(out / ime)
        return files[-1]

    # 1. Raspodjela -------------------------------------------------------------
    akt = svi[svi["aktivan"] & (svi["plata"] > 0)]
    fig, ax = _okvir(
        f"Tipična osnovna plata je oko {_br(o['Medijan (KM)'])} KM",
        "Raspodjela osnovnih plata svih aktivnih zaposlenih",
        f"Svaki stubić pokazuje koliko zaposlenih ima platu u rasponu od 100 KM. Medijan ({_br(o['Medijan (KM)'])} KM) "
        f"dijeli zaposlene na dvije jednake polovine, a prosjek ({_br(o['Prosjek (KM)'])} KM) je zbir svih plata "
        f"podijeljen brojem zaposlenih. Sivi stubići (ispod {MIN_PLATA_PUNO_RV:.0f} KM) su uglavnom nepuna norma, npr. "
        "nastavnici s nekoliko časova, i nisu uključeni u ostale analize. Vrhovi kod ~1.050 i ~1.550 KM su "
        "tipične plate za SSS i VSS.", len(akt))
    _ax_unutra(fig, ax, 0.075, 0.035)
    bins = np.arange(0, akt["plata"].max() + 100, 100)
    ax.hist(akt.loc[akt["plata"] < MIN_PLATA_PUNO_RV, "plata"], bins=bins, color=SIVA, edgecolor="white",
            linewidth=1.2, label="Nepuna norma (izuzeto iz analize)")
    ax.hist(d["plata"], bins=bins, color=PLAVA, edgecolor="white", linewidth=1.2, label="Puno radno vrijeme")
    ymax = ax.get_ylim()[1]
    ax.set_ylim(0, ymax * 1.08)
    for v, lab, c, ha, dx in [(o["Medijan (KM)"], "Medijan", TEKST, "right", -35),
                              (o["Prosjek (KM)"], "Prosjek", NARANDZASTA, "left", 35)]:
        ax.axvline(v, color=c, lw=1.6, ls=(0, (4, 3)))
        ax.text(v + dx, ymax * 1.03, f"{lab}  {_br(v)} KM", color=c, fontsize=11, fontweight="bold", ha=ha,
                va="top", bbox={"facecolor": "white", "edgecolor": "none", "pad": 2})
    ax.xaxis.set_major_formatter(KM)
    ax.yaxis.set_major_formatter(KM)
    ax.set_xlabel("Osnovna plata (KM)")
    ax.set_ylabel("Broj zaposlenih")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    _spremi(fig, f("01_raspodjela_plata.png"))

    # 2. Stručna sprema ---------------------------------------------------------
    t = A.po_grupi(d[d["sprema"] != "Nepoznato"], "sprema", sort=None)
    t = t.reindex([s for s in SPREMA_RED if s in t.index])
    bar_medijan(t, "Plata raste sa stručnom spremom",
                "Osnovna plata po nivou stručne spreme zaposlenog (od najniže do najviše spreme)",
                OBJ_BAR + " Doktori nauka su većinom profesori na Univerzitetu, pa imaju izrazito visoke plate.",
                f("02_plata_po_strucnoj_spremi.png"), n, label_w=24, sort=False)

    # 3. Sektor -----------------------------------------------------------------
    bar_medijan(A.po_grupi(d, "sektor"), "Plate po sektorima",
                "170 institucija razvrstano je u 10 sektora; sortirano po medijanu",
                OBJ_BAR + " U zdravstvu je prosjek mnogo veći od medijana: većina su medicinske sestre i tehničari, "
                          "a manji broj ljekara specijalista ima visoke plate.",
                f("03_plata_po_sektoru.png"), n, label_w=42)

    # 4. Boxplot po spremi --------------------------------------------------------
    dd = d[d["sprema"] != "Nepoznato"].copy()
    dd["sprema"] = dd["sprema"].cat.remove_unused_categories()
    fig, ax = _okvir(
        "Koliko se razlikuju plate unutar iste spreme?",
        "Raspon plata za svaki nivo stručne spreme (box-plot)",
        "Pravougaonik (kutija) obuhvata srednjih 50% zaposlenih: donja ivica je Q1, gornja Q3. Bijela linija u "
        "kutiji je medijan. „Brkovi“ (tanke linije) pokazuju uobičajeni raspon plata, a pojedinačne tačke su "
        "neuobičajeno niske ili visoke plate (ekstremi). Niska kutija = plate u grupi su slične; visoka kutija = "
        "velike razlike (npr. VSS radi na vrlo različitim poslovima).", len(dd))
    _ax_unutra(fig, ax, 0.075, 0.035)
    sns.boxplot(data=dd, x="sprema", y="plata", color=PLAVA, width=0.5, fliersize=2.5, linewidth=1.1,
                flierprops={"markerfacecolor": SIVA, "markeredgecolor": "none", "alpha": 0.6},
                medianprops={"color": "white", "lw": 2.2}, boxprops={"edgecolor": PLAVA},
                whiskerprops={"color": TEKST2}, capprops={"color": TEKST2}, ax=ax)
    ax.yaxis.set_major_formatter(KM)
    ax.set_xlabel("")
    ax.set_ylabel("Osnovna plata (KM)")
    ax.grid(axis="x", visible=False)
    _spremi(fig, f("04_boxplot_strucna_sprema.png"))

    # 5–6. Institucije --------------------------------------------------------------
    ti = A.po_grupi(d, "institucija", min_n=30)
    obj_inst = (OBJ_BAR + f" Prikazane su samo institucije s najmanje 30 zaposlenih ({len(ti)} od "
                f"{d['institucija'].nunique()}), da rezultat ne bi zavisio od par osoba. Sve institucije su u Excel "
                "tabeli i u dashboardu.")
    bar_medijan(ti.head(15), "15 institucija s najvišim medijanom plate", "Institucije s najmanje 30 zaposlenih",
                obj_inst, f("05_institucije_najvise.png"), n)
    bar_medijan(ti.tail(15), "15 institucija s najnižim medijanom plate", "Institucije s najmanje 30 zaposlenih",
                obj_inst, f("06_institucije_najnize.png"), n)

    # 7. Grupe radnih mjesta (svi zaposleni) ---------------------------------------------
    tg = A.po_grupi(d, "grupa_radnog_mjesta")
    pokriveno = 100 * (1 - (d["grupa_radnog_mjesta"] == "Ostala radna mjesta").mean())
    bar_medijan(tg, "Plate po vrsti posla",
                f"{_br(d['radno_mjesto'].nunique())} različitih naziva radnih mjesta svedeno je na {len(tg)} grupa",
                OBJ_BAR + f" Isti posao je u registru upisan na mnogo načina (npr. „Nastavnik engleskog jezika“, „Prof. "
                          f"engleskog jezika“), pa su nazivi grupisani prema vrsti posla. Tako je obuhvaćeno "
                          f"{_br(pokriveno, 1)}% zaposlenih.",
                f("07_plata_po_grupi_radnog_mjesta.png"), n)

    # 8. Najčešća pojedinačna radna mjesta ------------------------------------------------
    tr = A.po_grupi(d, "radno_mjesto", min_n=30, sort="N").head(20)
    udio20 = 100 * tr["N"].sum() / n
    bar_medijan(tr, "20 najčešćih radnih mjesta",
                "Pojedinačni nazivi radnih mjesta kako su upisani u registar",
                OBJ_BAR + f" Ovdje je samo 20 najčešćih naziva ({_br(udio20, 0)}% zaposlenih). Većina od "
                          f"{_br(d['radno_mjesto'].nunique())} naziva ima tek 1–2 osobe, pa se ne prikazuje "
                          "pojedinačno – za cjelovitu sliku pogledaj grafikon „Plate po vrsti posla“.",
                f("08_najcesca_radna_mjesta.png"), n)

    # 9. Zvanja ---------------------------------------------------------------------------
    tz = A.po_grupi(d[d["zvanje"] != "Nepoznato"], "zvanje", min_n=30, sort="N").head(20)
    bar_medijan(tz, "20 najčešćih zvanja", "Zvanje = stečeno obrazovanje ili titula zaposlenog (npr. diplomirani pravnik)",
                OBJ_BAR + " Zvanje opisuje šta je osoba završila, a ne posao koji obavlja – npr. profesor biologije može "
                          "raditi s nepunom normom ili na drugom radnom mjestu, pa je raspon plata širok.",
                f("09_najcesca_zvanja.png"), n)

    # 10. Grad ----------------------------------------------------------------------------
    bar_medijan(A.po_grupi(d[d["grad"] != "Nepoznato"], "grad"), "Plate po gradu/općini",
                "Prema sjedištu institucije; sortirano po medijanu",
                OBJ_BAR + " Tuzla ima više plate jer su tamo sjedišta Univerziteta, UKC-a i kantonalnih organa – "
                          "razlika je zbog vrste institucija, a ne samog grada.",
                f("10_plata_po_gradu.png"), n, label_w=24)

    # 11. Heatmapa ------------------------------------------------------------------------
    hm = A.ukrstena(dd, "sprema", "sektor", min_n=10)
    hm = hm.loc[[s for s in SPREMA_RED if s in hm.index][::-1]]
    fig, ax = _okvir(
        "Ista sprema, različit sektor – različita plata",
        "Medijan osnovne plate (KM) za svaku kombinaciju stručne spreme i sektora",
        "Svako polje je medijan plate zaposlenih s datom spremom u datom sektoru. Tamnija boja = viša plata. "
        "Čitaj red slijeva nadesno da vidiš kako se plata za istu spremu mijenja po sektorima (npr. VSS u osnovnoj "
        "školi i VSS u kantonalnoj upravi). Prazno polje znači da u toj kombinaciji ima manje od 10 zaposlenih, pa "
        "rezultat nije prikazan.", len(dd), h=8.4)
    p = ax.get_position()
    ax.set_position([0.17, p.y0 - 0.6 / 8.4, 0.80, p.height - 0.35 / 8.4])   # mjesto za nazive kolona gore
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("plava", SEKV)
    oznake = hm.map(lambda v: "" if pd.isna(v) else _br(v))
    sns.heatmap(hm, annot=oznake, fmt="", cmap=cmap, linewidths=3, linecolor="white", cbar=False, ax=ax,
                annot_kws={"fontsize": 10.5, "fontweight": "bold"})
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.xaxis.tick_top()
    ax.set_xticklabels([textwrap.fill(t.get_text(), 14) for t in ax.get_xticklabels()], rotation=0, fontsize=9.5,
                       color=TEKST2)
    ax.grid(False)
    _spremi(fig, f("11_heatmapa_sprema_sektor.png"))

    # 12. Godine u instituciji ------------------------------------------------------------
    ts = A.staz_grupe(d)
    rho = A.spearman_staz(d)["rho"]
    fig, ax = _okvir(
        "Plata i dužina rada u instituciji",
        "Medijan i prosjek osnovne plate prema godinama od zasnivanja radnog odnosa u instituciji",
        f"Svaka tačka je medijan (plavo) ili prosjek (narandžasto) za zaposlene s datim brojem godina u instituciji. "
        f"Plata raste prvih 10–15 godina, a zatim stagnira. Spearmanova korelacija ρ = {_br(rho, 2)} znači da je veza "
        "slaba: dužina rada malo utiče na osnovnu platu (minuli rad se obračunava kao dodatak, a nije dio osnovne "
        "plate). Napomena: računa se rad u ovoj instituciji, ne ukupan radni staž.", int(ts["N"].sum()))
    _ax_unutra(fig, ax, 0.075, 0.09)
    x = np.arange(len(ts))
    ax.fill_between(x, ts["Q1 (25%)"], ts["Q3 (75%)"], color=PLAVA_SVIJETLA, alpha=0.6, lw=0,
                    label="Srednjih 50% zaposlenih")
    for col, boja, lab in [("Prosjek (KM)", NARANDZASTA, "Prosjek"), ("Medijan (KM)", PLAVA, "Medijan")]:
        ax.plot(x, ts[col], color=boja, lw=2.4, marker="o", ms=8, markeredgecolor="white", markeredgewidth=2,
                label=lab, zorder=3)
        ax.text(x[-1] + 0.15, ts[col].iloc[-1], lab, color=boja, va="center", fontsize=11, fontweight="bold")
    ax.set_xticks(x, [f"{i} god.\nn={_br(k)}" for i, k in zip(ts.index, ts["N"])], fontsize=10)
    ax.set_xlim(-0.3, len(ts) - 0.4)
    ax.yaxis.set_major_formatter(KM)
    ax.set_ylabel("Osnovna plata (KM)")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", ncol=3)
    _spremi(fig, f("12_plata_i_staz.png"))

    # 13. Prosjek vs medijan --------------------------------------------------------------
    t = A.po_grupi(d, "sektor").sort_values("Medijan (KM)")
    fig, ax = _okvir(
        "Prosjek ili medijan? Razlika otkriva nejednakost",
        "Prosjek i medijan osnovne plate po sektoru",
        "Ako je prosjek (narandžasto) desno od medijana (plavo), mali broj visokih plata „vuče“ prosjek gore – "
        "npr. profesori na Univerzitetu ili ljekari specijalisti u zdravstvu. Ako je lijevo, niže plate ga spuštaju – "
        "u školama su to zaposleni s nepunom normom. Zato je medijan bolji pokazatelj plate „tipičnog“ zaposlenog. "
        "Što je siva linija duža, to je razlika veća.", n)
    _ax_unutra(fig, ax, 0.36, 0.04)
    y = np.arange(len(t))
    ax.hlines(y, t[["Prosjek (KM)", "Medijan (KM)"]].min(axis=1), t[["Prosjek (KM)", "Medijan (KM)"]].max(axis=1),
              color=SIVA, lw=4, zorder=1, capstyle="round")
    ax.scatter(t["Medijan (KM)"], y, s=130, color=PLAVA, zorder=3, label="Medijan", edgecolor="white", linewidth=2)
    ax.scatter(t["Prosjek (KM)"], y, s=130, color=NARANDZASTA, zorder=3, label="Prosjek", edgecolor="white",
               linewidth=2)
    for yi, (_, r) in zip(y, t.iterrows()):
        razl = r["Prosjek (KM)"] - r["Medijan (KM)"]
        ax.text(max(r["Prosjek (KM)"], r["Medijan (KM)"]) + 25, yi, f"{'+' if razl >= 0 else '−'}{_br(abs(razl))} KM",
                va="center", fontsize=9.5, color=TEKST2)
    ax.set_yticks(y, t.index)
    ax.set_xlim(t[["Prosjek (KM)", "Medijan (KM)"]].min().min() - 100, t[["Prosjek (KM)", "Medijan (KM)"]].max().max() + 220)
    ax.xaxis.set_major_formatter(KM)
    ax.set_xlabel("Osnovna plata (KM)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    _spremi(fig, f("13_prosjek_vs_medijan.png"))

    # 14. Regresija -----------------------------------------------------------------------
    model, koef = A.regresija(d)
    k = koef.drop("Intercept")
    god = koef.loc["godine_u_instituciji", "efekat (%)"]
    k = k[~k.index.str.startswith("godine")].sort_values("efekat (%)")
    fig, ax = _okvir(
        "Šta najviše određuje visinu plate?",
        f"Višestruka regresija: model objašnjava {_br(100 * model.rsquared)}% razlika u platama (R² = {_br(model.rsquared, 2)})",
        "Model poredi zaposlene koji se razlikuju samo po jednom faktoru, dok su ostali isti. Svaki stubić pokazuje za "
        "koliko je posto plata veća (plavo) ili manja (narandžasto) od referentne grupe: SSS, osnovne škole, ugovor "
        f"na neodređeno. Npr. „Sprema: VSS +57%“ znači da zaposleni s VSS ima oko 57% veću platu od zaposlenog sa "
        f"SSS u istom sektoru i s istom vrstom ugovora. Svaka dodatna godina u instituciji donosi samo {_br(god, 2)}%.",
        int(model.nobs), h=9.2)
    _ax_unutra(fig, ax, 0.36, 0.06)
    yk = np.arange(len(k))
    boje = [PLAVA if v >= 0 else NARANDZASTA for v in k["efekat (%)"]]
    ax.barh(yk, k["efekat (%)"], color=boje, height=0.64, zorder=2)
    ax.axvline(0, color=TEKST2, lw=1)
    lab = [i.replace("sprema: ", "Sprema: ").replace("sektor: ", "Sektor: ").replace("ugovor: ", "Ugovor: ")
           for i in k.index]
    ax.set_yticks(yk, lab)
    for yi, v in enumerate(k["efekat (%)"]):
        ax.text(v + (2 if v >= 0 else -2), yi, f"{'+' if v >= 0 else '−'}{_br(abs(v))}%", va="center",
                ha="left" if v >= 0 else "right", fontsize=10, color=TEKST, fontweight="bold")
    ax.set_xlim(k["efekat (%)"].min() - 18, k["efekat (%)"].max() + 18)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:+.0f}%".replace("-", "−")))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Razlika u plati u odnosu na referentnu grupu")
    _spremi(fig, f("14_regresija_efekti.png"))

    return files
