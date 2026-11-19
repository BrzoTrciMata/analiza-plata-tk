"""Interaktivni dashboard: Plate u institucijama Tuzlanskog kantona.

Pokretanje:  streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from src import analysis as A
from src.clean import MIN_PLATA_PUNO_RV, SEKTOR_RED, SPREMA_RED, clean, ucitaj
from src.download import latest_raw

ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed" / "zaposleni.csv"
st.set_page_config(page_title="Plate u institucijama TK", page_icon="📊", layout="wide")

# ------------------------------------------------------------------ tema (svijetla / tamna)
# Tema se bira u meniju ⋮ → Settings. Boje grafikona i okvira prate izabranu temu
# (tamna tema koristi posebno odabrane nijanse iste palete, a ne obrnute boje).
TAMNA = (getattr(st.context, "theme", None) is not None and st.context.theme.type == "dark")
T = dict(
    plava="#3987e5", narandzasta="#d95926", tekst="#f0efec", tekst2="#c3c2b7", tekst3="#8f8e86",
    mreza="#33332f", staza="#262730", linija="#f0efec", povrsina="#0e1117",
) if TAMNA else dict(
    plava="#2a78d6", narandzasta="#eb6834", tekst="#0b0b0b", tekst2="#52514e", tekst3="#8a8983",
    mreza="#ebeae6", staza="#efeee9", linija="#0b0b0b", povrsina="#ffffff",
)
PLAVA, NARANDZASTA, STAZA = T["plava"], T["narandzasta"], T["staza"]
SEKV = (["#13253d", "#163463", "#184f95", "#1c5cab", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4"] if TAMNA else
        ["#e6f0fc", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])

# ------------------------------------------------------------------ izgled
# Okviri koriste poluprozirne boje i nasljeđuju boju teksta, pa izgledaju dobro u obje teme.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stDataFrame, button, input { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 2.2rem; max-width: 1400px; }
h1 { font-weight: 800 !important; letter-spacing: -0.02em; }
h2, h3 { font-weight: 700 !important; letter-spacing: -0.01em; }
.hero-sub { opacity: .72; font-size: 1.02rem; margin-top: -0.6rem; margin-bottom: 1.4rem; }
.kpi { background: rgba(128,128,128,.06); border: 1px solid rgba(128,128,128,.22); border-radius: 16px;
       padding: 18px 20px; height: 100%; }
.kpi .lab { opacity: .7; font-size: .82rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
.kpi .val { font-size: 1.75rem; font-weight: 800; margin-top: 4px; letter-spacing: -0.02em; }
.kpi .note { opacity: .55; font-size: .8rem; margin-top: 2px; }
.info { background: rgba(57,135,229,.10); border-left: 4px solid #3987e5; border-radius: 10px; padding: 12px 16px;
        font-size: .92rem; line-height: 1.55; margin: 4px 0 18px 0; }
.info b.t { color: #3987e5; font-size: .74rem; letter-spacing: .08em; display: block; margin-bottom: 2px; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid rgba(128,128,128,.22); }
.stTabs [data-baseweb="tab"] { height: 44px; padding: 0 16px; border-radius: 10px 10px 0 0; font-weight: 600; }
.stTabs [aria-selected="true"] { background: rgba(57,135,229,.10); }
[data-testid="stExpander"] { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

pio.templates["tk"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, sans-serif", size=13, color=T["tekst"]),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(gridcolor=T["mreza"], zeroline=False, showline=False, ticks="", tickfont=dict(color=T["tekst2"])),
    yaxis=dict(gridcolor=T["mreza"], zeroline=False, showline=False, ticks="", tickfont=dict(color=T["tekst"])),
    hoverlabel=dict(font=dict(family="Inter", size=13)),
    legend=dict(orientation="h", y=1.06, x=0, font=dict(size=12)),
    margin=dict(l=10, r=10, t=40, b=10), separators=",.", bargap=0.32,
))
pio.templates.default = "tk"


def km(v, dec=0):
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".") + " KM"


def br(v, dec=0):
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def info(tekst: str, naslov="KAKO ČITATI"):
    st.markdown(f'<div class="info"><b class="t">{naslov}</b>{tekst}</div>', unsafe_allow_html=True)


def kpi(col, lab, val, note=""):
    col.markdown(f'<div class="kpi"><div class="lab">{lab}</div><div class="val">{val}</div>'
                 f'<div class="note">{note}</div></div>', unsafe_allow_html=True)


_KEY = iter(range(10_000))


def pc(target, fig):
    """plotly_chart s jedinstvenim ključem (izbjegava duplikat ID-a kad dva grafa imaju iste podatke)."""
    target.plotly_chart(fig, width="stretch", key=f"chart{next(_KEY)}", config={"displayModeBar": False})


def tabela(target, t: pd.DataFrame, visina=None):
    """Tabela s formatiranim brojevima i trakom u koloni medijana."""
    cfg = {}
    for c in t.columns:
        if c == "Medijan (KM)":
            cfg[c] = st.column_config.ProgressColumn(c, format="%.0f KM", min_value=0,
                                                     max_value=float(t[c].max() or 1), help=A.POJMOVI.get(c))
        elif "(KM)" in c or c in {"Q1 (25%)", "Q3 (75%)", "Std. devijacija", "Razlika prosjek−medijan"}:
            cfg[c] = st.column_config.NumberColumn(c, format="%.0f KM", help=A.POJMOVI.get(c))
        elif c == "Udio (%)":
            cfg[c] = st.column_config.NumberColumn(c, format="%.1f %%", help=A.POJMOVI.get(c))
        elif c == "N":
            cfg[c] = st.column_config.NumberColumn("N", format="%d", help=A.POJMOVI["N"])
    kol = [c for c in ["N", "Udio (%)", "Medijan (KM)", "Prosjek (KM)", "Q1 (25%)", "Q3 (75%)", "Std. devijacija"]
           if c in t.columns] + [c for c in t.columns if c not in cfg and c != "Razlika prosjek−medijan"]
    target.dataframe(t[list(dict.fromkeys(kol))], width="stretch", column_config=cfg,
                     height=visina or min(38 * (len(t) + 1) + 3, 520))


OBJ_BAR = ("<b>Plavi stubić</b> je medijan (polovina zaposlenih ima manju, polovina veću platu). "
           "<b>Narandžasta tačka</b> je prosjek. <b>Crna linija</b> je raspon u kojem je srednjih 50% zaposlenih "
           "(Q1–Q3) – što je duža, plate u grupi su raznolikije. Pređi mišem preko stubića za detalje.")


def bar_medijan(t: pd.DataFrame, visina=None, sort=True):
    t = t.sort_values("Medijan (KM)") if sort else t.iloc[::-1]
    lab = [str(i) for i in t.index]
    xmax = float(max(t["Q3 (75%)"].max(), t["Prosjek (KM)"].max()) * 1.08)
    fig = go.Figure()
    fig.add_bar(y=lab, x=[xmax] * len(t), orientation="h", marker_color=STAZA, hoverinfo="skip", showlegend=False)
    fig.add_bar(y=lab, x=t["Medijan (KM)"], orientation="h", name="Medijan", marker=dict(color=PLAVA, cornerradius=5),
                text=[br(v) for v in t["Medijan (KM)"]], textposition="inside", insidetextanchor="start",
                textfont=dict(color="white", size=12),
                customdata=np.stack([t["N"], t["Q1 (25%)"], t["Q3 (75%)"], t["Prosjek (KM)"]], axis=1),
                hovertemplate="<b>%{y}</b><br>Medijan: %{x:,.0f} KM<br>Prosjek: %{customdata[3]:,.0f} KM"
                              "<br>Srednjih 50%: %{customdata[1]:,.0f} – %{customdata[2]:,.0f} KM"
                              "<br>Broj zaposlenih: %{customdata[0]}<extra></extra>")
    fig.add_scatter(y=lab, x=t["Prosjek (KM)"], mode="markers", name="Prosjek",
                    error_x=dict(type="data", symmetric=False, array=t["Q3 (75%)"] - t["Prosjek (KM)"],
                                 arrayminus=t["Prosjek (KM)"] - t["Q1 (25%)"], color=T["linija"], thickness=1.3, width=4),
                    marker=dict(color=NARANDZASTA, size=10, line=dict(color=T["povrsina"], width=2)), hoverinfo="skip")
    fig.update_layout(height=visina or max(300, 34 * len(t) + 110), barmode="overlay",
                      xaxis=dict(title="Osnovna plata (KM)", range=[0, xmax]), yaxis=dict(automargin=True))
    return fig


@st.cache_data
def podaci() -> pd.DataFrame:
    if not PROCESSED.exists():
        raw = latest_raw(ROOT / "data" / "raw")
        if raw is None:
            st.error("Nema preuzetih podataka. Pokreni prvo: `python main.py`")
            st.stop()
        clean(raw, PROCESSED)
    df = ucitaj(PROCESSED)
    if "grupa_radnog_mjesta" not in df.columns:   # stari format – ponovo očisti
        clean(latest_raw(ROOT / "data" / "raw"), PROCESSED)
        df = ucitaj(PROCESSED)
    return df


df_svi = podaci()

# ------------------------------------------------------------------ filteri
with st.sidebar:
    st.markdown("### 🔎 Filteri")
    sektori = st.multiselect("Sektor", SEKTOR_RED, placeholder="Svi sektori")
    gradovi = st.multiselect("Grad (sjedište institucije)", sorted(df_svi["grad"].unique()), placeholder="Svi gradovi")
    spreme = st.multiselect("Stručna sprema", SPREMA_RED, placeholder="Svi nivoi")
    grupe = st.multiselect("Vrsta posla", sorted(df_svi["grupa_radnog_mjesta"].unique()), placeholder="Sve vrste")
    ugovori = st.multiselect("Vrsta ugovora", ["Neodređeno", "Određeno"], placeholder="Obje")
    st.markdown("---")
    st.markdown("### ⚙️ Postavke analize")
    prag = st.slider("Minimalna plata za puno radno vrijeme (KM)", 0, 1000, int(MIN_PLATA_PUNO_RV), 50,
                     help="Plate ispod praga uglavnom su nepuna norma (npr. nastavnici s nekoliko časova) i ne ulaze u analizu.")
    samo_aktivni = st.checkbox("Samo aktivni radni odnosi", True,
                               help="Isključuje zaposlene kojima je radni odnos već prestao.")
    st.markdown("---")
    st.caption(f"🔒 Imena zaposlenih nisu preuzeta. Grupe s manje od {A.MIN_N} zaposlenih se ne prikazuju.")

d = df_svi[(df_svi["plata"] >= max(prag, 0.01))]
if samo_aktivni:
    d = d[d["aktivan"]]
for col, vals in [("sektor", sektori), ("grad", gradovi), ("sprema", spreme), ("grupa_radnog_mjesta", grupe),
                  ("ugovor", ugovori)]:
    if vals:
        d = d[d[col].isin(vals)]

# ------------------------------------------------------------------ zaglavlje
st.title("Plate u institucijama Tuzlanskog kantona")
st.markdown('<div class="hero-sub">Analiza osnovnih plata iz javnog Registra zaposlenih '
            '(anticorruptk.ba) · prosjek i medijan po stručnoj spremi, sektoru, instituciji, vrsti posla i zvanju</div>',
            unsafe_allow_html=True)

if len(d) < A.MIN_N:
    st.warning("Premalo zaposlenih za odabrane filtere.")
    st.stop()

o = A.opis(d["plata"])
c = st.columns(5)
kpi(c[0], "Zaposlenih", br(o["N"]), f"od {br(len(df_svi))} u registru")
kpi(c[1], "Medijalna plata", km(o["Medijan (KM)"]), "pola ima manje, pola više")
kpi(c[2], "Prosječna plata", km(o["Prosjek (KM)"]), "zbir plata / broj zaposlenih")
kpi(c[3], "Srednjih 50%", f"{br(o['Q1 (25%)'])}–{br(o['Q3 (75%)'])}", "raspon plata (Q1–Q3), KM")
kpi(c[4], "Gini koeficijent", br(o["Gini koeficijent"], 2), "0 = jednake plate, 1 = maks. nejednakost")
st.write("")

tabs = st.tabs(["📈 Raspodjela", "🎓 Stručna sprema", "🏛️ Sektori i institucije", "💼 Radna mjesta i zvanja",
                "⏳ Staž i ugovor", "🧪 Statistički testovi", "📘 Metodologija"])

# ------------------------------------------------------------------ 1 Raspodjela
with tabs[0]:
    st.subheader("Kako su raspoređene plate?")
    fig = go.Figure(go.Histogram(x=d["plata"], xbins=dict(size=100), marker=dict(color=PLAVA, line=dict(color="rgba(0,0,0,0)", width=1)),
                                 hovertemplate="%{x} KM: %{y} zaposlenih<extra></extra>"))
    for v, lab, boja, pos in [(o["Medijan (KM)"], "Medijan", T["tekst"], "top left"),
                              (o["Prosjek (KM)"], "Prosjek", NARANDZASTA, "top right")]:
        fig.add_vline(v, line_dash="dash", line_color=boja, line_width=1.6,
                      annotation_text=f"<b>{lab} {km(v)}</b>", annotation_position=pos, annotation_font_color=boja)
    fig.update_layout(xaxis_title="Osnovna plata (KM)", yaxis_title="Broj zaposlenih", height=440, bargap=0.06)
    pc(st, fig)
    p9010 = br(o["Omjer P90/P10"], 1)
    info(f"Svaki stubić pokazuje koliko zaposlenih ima platu u rasponu od 100 KM. <b>Medijan</b> ({km(o['Medijan (KM)'])}) "
         f"dijeli zaposlene na dvije jednake polovine; <b>prosjek</b> ({km(o['Prosjek (KM)'])}) je zbir svih plata podijeljen "
         f"brojem zaposlenih. Polovina zaposlenih ima platu između <b>{km(o['Q1 (25%)'])}</b> i <b>{km(o['Q3 (75%)'])}</b>. "
         f"Plata na granici 10% najplaćenijih je <b>{p9010}×</b> veća od plate na granici 10% najslabije plaćenih. "
         "Vrhovi oko ~1.050 KM i ~1.550 KM su tipične plate za SSS i VSS.")
    with st.expander("📋 Tabela: opšta statistika"):
        op = pd.DataFrame({"Vrijednost": A.opis(d["plata"])}).round(2)
        op["Šta znači"] = [A.POJMOVI.get(k, A.POJMOVI.get("Min / Max", "")) if k not in {"Min", "Max"} else A.POJMOVI["Min / Max"]
                           for k in op.index]
        st.dataframe(op, width="stretch")

# ------------------------------------------------------------------ 2 Stručna sprema
with tabs[1]:
    t = A.po_grupi(d[d["sprema"] != "Nepoznato"], "sprema", sort=None)
    t = t.reindex([s for s in SPREMA_RED if s in t.index])
    st.subheader("Plata po nivou stručne spreme")
    pc(st, bar_medijan(t, sort=False))
    info(OBJ_BAR + " Ovdje se vidi jasan trend: što je viša sprema, to je viša plata. Doktori nauka su većinom "
                   "profesori na Univerzitetu.")
    tabela(st, t)

    st.subheader("Raspon plata unutar svake spreme")
    dd = d[d["sprema"] != "Nepoznato"].copy()
    dd["sprema"] = dd["sprema"].cat.remove_unused_categories()
    fig = go.Figure()
    for s in [x for x in SPREMA_RED if x in dd["sprema"].cat.categories]:
        fig.add_box(y=dd.loc[dd["sprema"] == s, "plata"], name=s, marker_color=PLAVA, line_width=1.4,
                    fillcolor="rgba(57,135,229,.28)", boxpoints=False, showlegend=False)
    fig.update_layout(yaxis_title="Osnovna plata (KM)", height=420)
    pc(st, fig)
    info("<b>Kutija</b> obuhvata srednjih 50% zaposlenih (od Q1 do Q3), a linija u kutiji je medijan. "
         "<b>Brkovi</b> pokazuju uobičajeni raspon plata. Niska kutija = plate u grupi su slične; visoka kutija = "
         "velike razlike unutar iste spreme (npr. VSS radi na vrlo različitim poslovima).")

    st.subheader("Odgovara li sprema zaposlenog traženoj spremi za radno mjesto?")
    tabela(st, A.po_grupi(d, "usklađenost_spreme"))
    info("„Viša od tražene“ znači da zaposleni ima višu spremu nego što radno mjesto zahtijeva (npr. VSS na mjestu "
         "za SSS). Takvi zaposleni imaju nižu platu od onih na odgovarajućem mjestu, jer plata zavisi od radnog mjesta, "
         "a ne od same diplome.")

# ------------------------------------------------------------------ 3 Sektori i institucije
with tabs[2]:
    st.subheader("Sektori")
    ts_ = A.po_grupi(d, "sektor")
    pc(st, bar_medijan(ts_))
    info(OBJ_BAR + " Kad je prosjek mnogo desno od medijana (npr. zdravstvo, Univerzitet), mali broj visokih plata "
                   "(ljekari specijalisti, profesori) podiže prosjek.")
    with st.expander("📋 Tabela: sektori"):
        tabela(st, ts_)

    st.subheader("Stručna sprema × sektor (medijan plate)")
    hm = A.ukrstena(d, "sprema", "sektor").reindex([s for s in SPREMA_RED if s in d["sprema"].unique()])
    fig = go.Figure(go.Heatmap(z=hm.values, x=list(hm.columns), y=list(hm.index), colorscale=SEKV, xgap=3, ygap=3,
                               text=hm.map(lambda v: "" if pd.isna(v) else br(v)).values, texttemplate="%{text}",
                               hovertemplate="%{y} · %{x}<br>Medijan: %{z:,.0f} KM<extra></extra>", showscale=False))
    fig.update_layout(height=470, xaxis=dict(side="top", showgrid=False), yaxis=dict(showgrid=False, autorange="reversed"))
    pc(st, fig)
    info("Svako polje je medijan plate za kombinaciju spreme (red) i sektora (kolona); tamnija boja = viša plata. "
         "Čitaj red slijeva nadesno da vidiš kako se plata za <b>istu spremu</b> razlikuje po sektorima. "
         "Prazno polje = manje od 10 zaposlenih u toj kombinaciji.")

    st.subheader("Institucije")
    min_inst = st.slider("Minimalan broj zaposlenih u instituciji", 5, 100, 30, 5,
                         help="Male institucije imaju nepouzdan medijan (zavisi od par osoba).")
    ti = A.po_grupi(d, "institucija", min_n=min_inst)
    k1, k2 = st.columns(2)
    k1.markdown("**⬆️ Najviši medijan**")
    pc(k1, bar_medijan(ti.head(15)))
    k2.markdown("**⬇️ Najniži medijan**")
    pc(k2, bar_medijan(ti.tail(15)))
    info(OBJ_BAR + f" Prikazano je po 15 institucija s najvišim i najnižim medijanom, od {len(ti)} institucija koje "
                   f"imaju najmanje {min_inst} zaposlenih. Sve su u tabeli ispod.")
    with st.expander(f"📋 Sve institucije ({len(ti)})"):
        tabela(st, ti)

    st.subheader("Detalji jedne institucije")
    inst = st.selectbox("Izaberi instituciju", sorted(d["institucija"].unique()))
    di = d[d["institucija"] == inst]
    if len(di) >= A.MIN_N:
        oi = A.opis(di["plata"])
        m = st.columns(4)
        kpi(m[0], "Zaposlenih", br(oi["N"]))
        kpi(m[1], "Medijan", km(oi["Medijan (KM)"]))
        kpi(m[2], "Prosjek", km(oi["Prosjek (KM)"]))
        kpi(m[3], "Srednjih 50%", f"{br(oi['Q1 (25%)'])}–{br(oi['Q3 (75%)'])}")
        st.write("")
        g = A.po_grupi(di, "grupa_radnog_mjesta")
        if len(g):
            st.markdown(f"**Po vrsti posla** (grupe s najmanje {A.MIN_N} zaposlenih)")
            tabela(st, g)
        ri = A.po_grupi(di, "radno_mjesto")
        if len(ri):
            st.markdown(f"**Po pojedinačnom radnom mjestu** (s najmanje {A.MIN_N} zaposlenih)")
            tabela(st, ri)
    else:
        st.info(f"Institucija ima manje od {A.MIN_N} zaposlenih uz odabrane filtere.")

    st.subheader("Gradovi (sjedište institucije)")
    pc(st, bar_medijan(A.po_grupi(d[d["grad"] != "Nepoznato"], "grad")))
    info(OBJ_BAR + " Tuzla ima više plate jer su tamo sjedišta Univerziteta, UKC-a i kantonalnih organa – razlika "
                   "dolazi od vrste institucija, a ne od samog grada.")

# ------------------------------------------------------------------ 4 Radna mjesta i zvanja
with tabs[3]:
    n_naziva = d["radno_mjesto"].nunique()
    pokr = 100 * (1 - (d["grupa_radnog_mjesta"] == "Ostala radna mjesta").mean())
    st.subheader("Plate po vrsti posla")
    tg = A.po_grupi(d, "grupa_radnog_mjesta")
    pc(st, bar_medijan(tg))
    info(f"U registru postoji <b>{br(n_naziva)}</b> različitih naziva radnih mjesta, jer je isti posao upisan na "
         "mnogo načina (npr. „Nastavnik engleskog jezika“, „Prof. engleskog jezika“, „Nast.engleskog jezika“). "
         f"Zato su nazivi grupisani u {len(tg)} vrsta posla, čime je obuhvaćeno <b>{br(pokr, 1)}%</b> zaposlenih. "
         + OBJ_BAR, naslov="ZAŠTO GRUPE?")
    with st.expander("📋 Tabela: vrste posla"):
        tabela(st, tg)

    st.subheader("Pojedinačna radna mjesta")
    k1, k2 = st.columns([1, 3])
    broj = k1.slider("Broj prikazanih", 10, 40, 20, 5, key="rm_b")
    min_n = k1.slider("Najmanje zaposlenih", 5, 100, 20, 5, key="rm_n")
    grupa_f = k1.selectbox("Vrsta posla", ["Sve"] + sorted(d["grupa_radnog_mjesta"].unique()), key="rm_g")
    trazi = k1.text_input("Pretraga naziva", key="rm_q", placeholder="npr. nastavnik, sestra…")
    dd = d[d["radno_mjesto"] != "Nepoznato"]
    if grupa_f != "Sve":
        dd = dd[dd["grupa_radnog_mjesta"] == grupa_f]
    if trazi:
        dd = dd[dd["radno_mjesto"].str.contains(trazi, case=False, na=False)]
    t = A.po_grupi(dd, "radno_mjesto", min_n=min_n, sort="N") if len(dd) else pd.DataFrame()
    if len(t):
        pc(k2, bar_medijan(t.head(broj)))
        udio = 100 * t.head(broj)["N"].sum() / len(d)
        info(f"Prikazano je {min(broj, len(t))} najčešćih naziva (ukupno {br(udio, 1)}% zaposlenih). "
             f"Većina od {br(n_naziva)} naziva ima samo 1–2 osobe, pa se pojedinačno ne prikazuje "
             f"(premalo podataka i zaštita privatnosti). Povećaj broj prikazanih, smanji minimum ili koristi "
             "pretragu – ili pogledaj vrste posla iznad.", naslov="ZAŠTO NISU SVA RADNA MJESTA?")
        with st.expander(f"📋 Sva radna mjesta s najmanje {A.MIN_N} zaposlenih"):
            sve = A.po_grupi(dd, "radno_mjesto")
            sve.insert(0, "Vrsta posla", dd.groupby("radno_mjesto")["grupa_radnog_mjesta"].first().reindex(sve.index))
            tabela(st, sve)
    else:
        k2.info("Nema radnih mjesta koja zadovoljavaju uslove.")

    st.subheader("Zvanja")
    k1, k2 = st.columns([1, 3])
    broj_z = k1.slider("Broj prikazanih", 10, 40, 20, 5, key="zv_b")
    trazi_z = k1.text_input("Pretraga zvanja", key="zv_q", placeholder="npr. ekonomista, pravnik…")
    dz = d[d["zvanje"] != "Nepoznato"]
    if trazi_z:
        dz = dz[dz["zvanje"].str.contains(trazi_z, case=False, na=False)]
    tz = A.po_grupi(dz, "zvanje", min_n=10, sort="N") if len(dz) else pd.DataFrame()
    if len(tz):
        pc(k2, bar_medijan(tz.head(broj_z)))
    else:
        k2.info("Nema zvanja koja zadovoljavaju uslove.")
    info("<b>Zvanje</b> opisuje stečeno obrazovanje ili titulu (npr. „Diplomirani ekonomista“), a ne posao koji "
         "osoba obavlja. Zato isto zvanje može imati širok raspon plata – npr. profesor biologije s nepunom normom. "
         + OBJ_BAR)

# ------------------------------------------------------------------ 5 Staž i ugovor
with tabs[4]:
    st.subheader("Plata i godine rada u instituciji")
    ts = A.staz_grupe(d)
    x = [f"{i} god." for i in ts.index.astype(str)]
    fig = go.Figure()
    fig.add_scatter(x=x + x[::-1], y=list(ts["Q3 (75%)"]) + list(ts["Q1 (25%)"])[::-1], fill="toself",
                    fillcolor="rgba(57,135,229,.16)", line=dict(width=0), name="Srednjih 50%", hoverinfo="skip")
    fig.add_scatter(x=x, y=ts["Medijan (KM)"], name="Medijan", mode="lines+markers",
                    line=dict(color=PLAVA, width=2.6), marker=dict(size=9, line=dict(color=T["povrsina"], width=2)))
    fig.add_scatter(x=x, y=ts["Prosjek (KM)"], name="Prosjek", mode="lines+markers",
                    line=dict(color=NARANDZASTA, width=2.6), marker=dict(size=9, line=dict(color=T["povrsina"], width=2)))
    fig.update_layout(xaxis_title="Godine od zasnivanja radnog odnosa u instituciji", yaxis_title="KM",
                      height=420, hovermode="x unified")
    pc(st, fig)
    rho = A.spearman_staz(d)["rho"]
    info(f"Linije pokazuju medijan i prosjek plate prema broju godina u instituciji; svijetloplava traka je raspon "
         f"srednjih 50% zaposlenih. Spearmanova korelacija je <b>ρ = {br(rho, 2)}</b> – veza je slaba: dužina rada "
         "malo utiče na osnovnu platu (minuli rad se isplaćuje kao dodatak i nije dio osnovne plate). "
         "Računa se rad u ovoj instituciji, ne ukupan radni staž.")
    with st.expander("📋 Tabela: godine u instituciji"):
        tabela(st, ts)

    st.subheader("Vrsta ugovora")
    tu = A.po_grupi(d, "ugovor")
    pc(st, bar_medijan(tu, visina=230))
    info("Zaposleni na <b>određeno</b> vrijeme imaju nižu platu – dijelom zato što su češće mlađi, na nižim pozicijama "
         "ili zamjene. Regresija (kartica „Statistički testovi“) pokazuje da razlika postoji i kad se uzmu u obzir "
         "sprema i sektor.")
    tabela(st, tu)

# ------------------------------------------------------------------ 6 Statistički testovi
with tabs[5]:
    st.subheader("Jesu li razlike u platama stvarne ili slučajne?")
    info("Statistički test provjerava da li je razlika koju vidimo mogla nastati slučajno. Ako je <b>p &lt; 0,05</b>, "
         "razlika je <b>statistički značajna</b>. Ali značajno ne znači i veliko – zato se gleda i "
         "<b>veličina efekta</b> (ε², r, ρ), koja kaže koliko je razlika važna u praksi. Korišteni su neparametarski "
         "testovi jer plate nisu normalno raspodijeljene (vidi histogram).", naslov="UKRATKO")
    tt = A.testovi_s_tumacenjem(d)
    if len(tt):
        st.dataframe(tt, width="stretch", hide_index=True,
                     column_config={"Tumačenje": st.column_config.TextColumn(width="large"),
                                    "Šta se provjerava": st.column_config.TextColumn(width="medium")})

    if len(d) >= 50 and d["sprema"].nunique() > 1:
        st.subheader("Šta najviše određuje visinu plate? (višestruka regresija)")
        model, koef = A.regresija_s_tumacenjem(d)
        c1, c2, c3 = st.columns(3)
        kpi(c1, "R² modela", br(model.rsquared, 2), f"objašnjava {br(100 * model.rsquared)}% razlika u platama")
        kpi(c2, "Zaposlenih u modelu", br(model.nobs))
        rf = model.referentne
        kpi(c3, "Referentna grupa", rf["sprema"], f"{rf['sektor']} · ugovor na {rf['ugovor'].lower()}")
        st.write("")
        k = koef.drop(index=[i for i in koef.index if i.startswith("godine")]).sort_values("Efekat (%)")
        fig = go.Figure(go.Bar(x=k["Efekat (%)"], y=list(k.index), orientation="h",
                               marker=dict(color=[PLAVA if v >= 0 else NARANDZASTA for v in k["Efekat (%)"]], cornerradius=4),
                               text=[f"{v:+.0f}%" for v in k["Efekat (%)"]], textposition="outside",
                               customdata=k["Tumačenje"], hovertemplate="%{customdata}<extra></extra>"))
        fig.update_layout(height=620, xaxis=dict(title="Razlika u plati u odnosu na referentnu grupu (%)", ticksuffix="%"))
        pc(st, fig)
        god = koef.loc["godine_u_instituciji", "Efekat (%)"]
        info("Model poredi zaposlene koji se razlikuju <b>samo po jednom faktoru</b>, dok su ostali isti. Svaki stubić "
             f"je razlika u plati u odnosu na referentnu grupu ({rf['sprema']}, {rf['sektor']}, ugovor na "
             f"{rf['ugovor'].lower()}). Npr. „sprema: VSS +57%“ znači oko 57% veću platu od zaposlenog sa SSS u istom "
             f"sektoru i s istom vrstom ugovora. Svaka dodatna godina u instituciji donosi {br(god, 2)}%. "
             "Pređi mišem preko stubića za tumačenje.")
        with st.expander("📋 Tabela regresije s tumačenjem"):
            st.dataframe(koef, width="stretch", column_config={
                "Tumačenje": st.column_config.TextColumn(width="large"),
                "Efekat (%)": st.column_config.NumberColumn(format="%+.1f %%"),
                "Koeficijent (log)": st.column_config.NumberColumn(format="%.4f"),
                "p": st.column_config.NumberColumn(format="%.4f")})

    with st.expander("📘 Rječnik pojmova", expanded=False):
        st.dataframe(pd.DataFrame({"Šta znači": A.POJMOVI}), width="stretch",
                     column_config={"Šta znači": st.column_config.TextColumn(width="large")})

# ------------------------------------------------------------------ 7 Metodologija
with tabs[6]:
    nalazi = ROOT / "output" / "kljucni_nalazi.md"
    if nalazi.exists():
        st.markdown(nalazi.read_text(encoding="utf-8"))
    st.subheader("Kvalitet podataka")
    st.dataframe(A.kvalitet_podataka(df_svi, df_svi[df_svi["aktivan"] & df_svi["puno_rv"]]), width="stretch")
    st.subheader("Kako su svedeni zapisi stručne spreme")
    mp = (df_svi.groupby("sprema", observed=True)["sprema_izvorno"]
          .agg(lambda x: ", ".join(x.value_counts().head(6).index)).rename("Najčešći izvorni zapisi"))
    st.dataframe(mp, width="stretch")
    st.subheader("Kako su grupisana radna mjesta")
    mg = (df_svi.groupby("grupa_radnog_mjesta")["radno_mjesto"]
          .agg(lambda x: ", ".join(x.value_counts().head(5).index)).rename("Primjeri naziva"))
    st.dataframe(mg, width="stretch")
