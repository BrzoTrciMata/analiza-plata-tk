# Analiza plata zaposlenih u institucijama Tuzlanskog kantona

## Interaktivna web aplikacija (Live Demo)

**[Otvori interaktivni Streamlit dashboard]((https://8dgdzkqotviz4c2vvcfnfb.streamlit.app/))**

Aplikacija je javno dostupna u pregledniku i prikazuje rezultate analize nad podacima preuzetim **19. 11. 2026.** (omogućava filtriranje po sektoru, gradu, stručnoj spremi, vrsti ugovora i pragu nepune norme, uz ključne pokazatelje, grafikone i statističke testove). Za preuzimanje novijeg stanja registra lokalno se koristi `python main.py --osvjezi`.

Analiziraju se prosječne i medijalne osnovne plate prema
stručnoj spremi, sektoru, instituciji, radnom mjestu, zvanju, gradu, vrsti ugovora i dužini rada u instituciji.

**Izvor podataka:** [Registar zaposlenih u institucijama Tuzlanskog kantona](https://anticorruptk.ba/registri/registar-zaposlenih)

---

## Lokalno pokretanje

Ako želite preuzeti repozitorij i pokrenuti kompletnu obradu podataka ili dashboard na svom računaru:
```bash
# jednom: instalacija biblioteka (u PyCharmu je .venv već podešen)
pip install -r requirements.txt

# cijela analiza: preuzimanje (ako nema podataka) → čišćenje → statistika → grafikoni
python main.py

# ponovno preuzimanje najnovijih podataka sa stranice
python main.py --osvjezi

# interaktivni dashboard za prezentaciju (otvara se u pregledniku)
streamlit run app.py

# testovi
python -m pytest tests
```

## Šta se dobija

| Lokacija | Sadržaj |
|---|---|
| `output/kljucni_nalazi.md` | Sažetak ključnih nalaza i metodologije |
| `output/figures/*.png` | 14 grafikona spremnih za slajdove; svaki ima okvir „Kako čitati“ s objašnjenjem |
| `output/tables/rezultati_analize.xlsx` | Sve tabele s opisom na vrhu svakog lista, list „Objašnjenja“ (rječnik pojmova), statistički testovi i regresija s tumačenjem |
| `app.py` | Dashboard s filterima (sektor, grad, sprema, ugovor, prag nepune norme) |

## Struktura

```
main.py            pokreće cijeli tok analize
app.py             Streamlit dashboard
src/download.py    preuzimanje registra (bez imena i prezimena)
src/clean.py       čišćenje: plate, datumi, svođenje stručne spreme, sektori, gradovi
src/analysis.py    deskriptivna statistika, Gini, Kruskal-Wallis, Mann-Whitney, Spearman, OLS regresija
src/figures.py     grafikoni za prezentaciju
src/excel.py       formatiran Excel izvještaj s objašnjenjima
tests/             jedinični testovi čišćenja
data/raw/          preuzeti podaci  ·  data/processed/  očišćeni podaci
```

## Metodologija (ukratko)

1. **Preuzimanje** – podaci se preuzimaju preko javnog servisa koji puni tablicu na stranici, u blokovima od
   1.000 zapisa s pauzom između zahtjeva.
2. **Privatnost** – imena i prezimena se odbacuju već pri preuzimanju i nigdje se ne spremaju. Svi rezultati su
   zbirni; grupe s manje od 5 zaposlenih se ne prikazuju (u ukrštenim tabelama manje od 10).
3. **Čišćenje**
   - plate iz formata `1 545,93 KM` u broj; datumi iz tri različita formata;
   - 346 različitih zapisa stručne spreme svedeno na 9 nivoa (NK → Doktor nauka); kod višestrukih navoda uzima se najviši;
   - 170 institucija razvrstano u 10 sektora; grad iz poštanskog broja sjedišta;
   - ~2.500 različitih naziva radnih mjesta (isti posao upisan na više načina) svedeno na 26 vrsta posla
     (obuhvaćeno ~98% zaposlenih); pojedinačni nazivi prikazuju se samo ako imaju ≥ 5 zaposlenih;
   - isključeni zapisi s datumom prestanka radnog odnosa u prošlosti;
   - plate ispod 500 KM tretiraju se kao **nepuna norma** (najčešće nastavnici s malim brojem časova) i
     isključuju iz glavne analize – prag je podesiv u dashboardu.
4. **Analiza** – prosjek, medijan, kvartili, Gini koeficijent, omjer P90/P10; neparametarski testovi
   (plate nisu normalno raspodijeljene); višestruka regresija log(plate).

## Ograničenja

- Analizira se **osnovna** plata kako ju je institucija unijela u registar (bez dodataka, minulog rada, toplog obroka).
- Registar ne sadrži podatak o radnom vremenu/normi, pa je prag od 500 KM procjena – dio plata između 500 i ~1.000 KM
  u školama vjerovatno je i dalje nepuna norma.
- „Godine u instituciji" nisu ukupan radni staž, već vrijeme od zasnivanja radnog odnosa u toj instituciji.
- Kvalitet podataka zavisi od institucija koje ih unose (npr. različiti zapisi iste spreme, nerealni datumi).
- Polja *spol* i *status* su u registru prazna, pa analiza po spolu nije moguća.
