# Mars Survival Map

A survival map of Mars, built only from **real NASA data** and documented physics.
Project of the Red Circle team for NASA Space Apps 2026, challenge "Interplanetary Survival Guide: Martian Map".

Three levels:

- **Site** (`web/index.html`): one place a few km wide, at metre resolution. First real site: **Jezero crater**.
  Slope, roughness, hazard classes, least-energy routes, flat sites, elevation profile, outing planner
  (sun and temperature), 2D and 3D views, Earth / Jezero clock.
- **Overview** (`web/overview.html`): the whole Jezero region at 20 m/px with the detail windows drawn on it; click one to open it.
- **Globe** (`web/globe.html`): global screening on a ~30 km grid, same layout and palette. Real layers: MOLA elevation
  and Odyssey neutron flux (a hydrogen proxy); temperature and its day/night swing are MRO MCS measurements (processed by Wang & Jin 2025); thermal inertia is real (MGS TES); dust opacity comes from the Mars Climate Database dust climatology; the rest is absent or derived from elevation (see section 6).

> **Team rule.** Data must be openly downloadable (no login, no paywall). Measurements are preferred; models and reanalyses
> are allowed if they are open and are labelled as models. Every number comes from a source listed in `web/sources.json` (page `web/sources.html`,
> report `docs/ANALYSIS_REPORT.md`), or is declared a **team assumption**. A value measured on Earth or the Moon and
> used on Mars is a hypothesis, and the interface says so (chips "NASA data", "Physics model", "Team assumption").

---

## 1. Repository contents

```
mars-survival-map/
├── README.md, pyproject.toml, requirements.txt, vercel.json
├── config/                      layers.json (globe), scoring.example.json
├── src/mars_survival/
│   ├── pds3.py                  reads a remote PDS3 DTM with HTTP Range requests (a window only, not 130 MB)
│   ├── physics.py               energy cost of walking (Minetti 2002), Mars gravity scaling (Cavagna 2000)
│   ├── traverse.py              walker (mass, power), roughness multiplier, Dijkstra routing on energy
│   ├── site.py                  slope, roughness, hazard, flat sites, web exports (.bin, PNG, site.json)
│   ├── eva.py                   exact sun geometry + outing windows (temperature = sinusoid fed by MEDA)
│   ├── cli.py                   commands: demo, site-demo, site, score, sensitivity, scrape, rasterize, serve
│   ├── thermal.py               energy-balance temperature (cross-check of the MCS layer, not shown)
│   ├── globe_data.py            parsers for the MOLA, Odyssey, TES thermal inertia, MCS temperature and dust files
│   ├── overview.py, photo.py    overview level (CTX DEM, detail-window list) and photo level (HiRISE orthoimage crop)
│   ├── schema.py, rasterize.py, export.py, scraper.py, demo.py     globe pipeline
├── scripts/                     real-data pipeline for Jezero (see section 3)
│   ├── fetch_dtm_window.py      HiRISE DTM: downloads a window -> data/jezero/dem.npy + dem.json
│   ├── fetch_meda.py            MEDA (CAL_ATS, CAL_PS): per-sol files -> data/meda/
│   ├── analyse_meda.py          median over channels, per-sol stats -> data/meda_jezero.json
│   ├── build_jezero.py          assembles everything -> web/data/site/ (+ provenance.json)
│   ├── build_overview.py        CTX DEM -> web/data/overview/ + web/data/sites.json
│   ├── fetch_ortho_window.py    HiRISE orthoimage window -> photo.jpg for a built site (a picture, not elevation)
│   ├── build_globe.py           real globe: MOLA, Odyssey neutrons, TES thermal inertia, MCS temperature, dust -> data/grid -> web/data
│   └── make_report.py           web/sources.json -> docs/ANALYSIS_REPORT.md
├── web/                         static site, served as is (Vercel)
│   ├── index.html               THE MAP: left sidebar (navigation), map, right sidebar (details)
│   ├── globe.html               globe viewer (same layout and palette as the map)
│   ├── sources.html, sources.json   every source, assumption and piece of software
│   ├── route.mjs, route.worker.js   energy routing (A*, parity tested under Node) and the Web Worker that runs it off the main thread
│   ├── survival.mjs             reach, radio line of sight, shadows, time budget
│   ├── overview.html, tour.js, sw.js, lang/   overview page, tutorial tour, offline service worker, languages (en, fr, ewo)
│   ├── marsclock.mjs            Mars time from Earth time (Allison & McEwen 2000)
│   ├── common.js, basemaps.json
│   ├── vendor/                  Leaflet, three.js, fonts (Public Sans, Bricolage Grotesque): works offline
│   └── data/site/               output of build_jezero.py (commit it for deployment)
├── tests/                       pytest + Node scripts (routing parity, Mars clock, survival tools)
├── data/                        local downloads (ignored by git)
└── docs/                        SOURCES.md, SITE_SCALE.md, ANALYSIS_REPORT.md, RESEARCH_IDEAS.md, latex/ (technical report + slides)
```

---

## 2. Installation

Python 3.10+, Node 18+ (only for the parity tests).

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt            # same as: pip install -e ".[geo,dev]" (installs the project itself, netCDF4, rasterio, pytest)
```

`rasterio` is only needed for `rasterize` (globe) and GeoTIFF export. If the package is not installed, prefix commands
with `PYTHONPATH=src`.

---

## 3. Build the real Jezero site

Run every command **from the repository root**. 
The server cuts long transfers; the scripts retry automatically for slow connections.

```bash
# The two data links, defined once (HiRISE stereo pair ESP_023524_1985 / ESP_023379_1985; Windows PowerShell: $DTM = "..." and use $DTM)
DTM="https://www.uahirise.org/PDS/DTM/ESP/ORB_023500_023599/ESP_023524_1985_ESP_023379_1985/DTEEC_023524_1985_023379_1985_U01.IMG"
ORTHO="https://www.uahirise.org/PDS/DTM/ESP/ORB_023500_023599/ESP_023524_1985_ESP_023379_1985/ESP_023524_1985_RED_A_01_ORTHO.JP2"    # photo, 0.2524 m/px (checked with --inspect)

# 1. HiRISE DTM DTEEC_023524_1985_023379_1985_U01 (1.0097 m/px, centred on Jezero), 6 km window
python scripts/fetch_dtm_window.py "$DTM" \
  --lat 18.44 --lon 77.52 --size-m 6000 --out data/jezero
#    (the DTM covers lat 18.16-18.52, lon 77.453-77.598; the point must lie inside it)
#    (add --inspect to print the PDS3 label if something goes wrong)

# 2. MEDA weather: one sol in 30, sol 1 to sol 1800
python scripts/fetch_meda.py --sols 1 1800 --every 30 --out data/meda

# 3. Mean temperature and day/night swing
python scripts/analyse_meda.py data/meda --out data/meda_jezero.json

# 4. Build: slope, roughness, hazard, routes, flat sites, outing plan
python scripts/build_jezero.py            # writes web/data/site/ and provenance.json

# 5. View the result
python -m mars_survival serve             # http://localhost:8000  (map)  and  /globe.html
```

The DTM is block-averaged (`--max-dim 1000`) so routing runs in the browser; the resulting pixel size is stored in
`site.json` and shown in the interface ("4.0 m per pixel after averaging").

Another DTM (tif, asc, npy, 16-bit png): `python -m mars_survival site --dem file --px-m 1 --lat 18.4 --lon 77.5`.
Guide: `docs/SITE_SCALE.md`.

## 4. Overview and detail windows

`overview.html` shows the whole Jezero region at 20 m/px (USGS CTX DEM mosaic, public domain, source P14) with each detail window
drawn on it; click a window, then **Open detail map**. The map page itself is unchanged; `index.html?site=<id>` opens a window stored
in `web/data/sites/<id>/` (the default `web/data/site/` is `jezero`).

```bash
python scripts/build_overview.py            # downloads the 87 MB CTX DEM once, writes web/data/overview/ and web/data/sites.json
# add another detail window: fetch + build into its own folder, then refresh the list
python scripts/fetch_dtm_window.py "$DTM" --lat .. --lon .. --size-m 6000 --out data/<id>
python scripts/build_jezero.py --dem data/<id>/dem.npy --meta data/<id>/dem.json --out web/data/sites/<id>
python scripts/build_overview.py --sites-only
```

Note: Jezero crater is about 45 km **across** (about 1,600 km2), not 45 km2. HiRISE stereo DTMs only cover part of it, so
detail windows exist only where a HiRISE DTM does.

## 5. Detail levels (tiers)

Elevation is never finer than the 1 m HiRISE DTM, so the tiers are real, not interpolated:

| Tier | Data | How |
|---|---|---|
| 4 m, whole window (current map, 4 km) | DTM block-averaged x4 | `build_jezero.py` (default `--max-dim 1000`) |
| 1 m native, smaller window (about 1.5 to 2 km) | DTM at native resolution | `fetch_dtm_window.py ... --size-m 1500 --out data/jezero_1m`, then `build_jezero.py --dem data/jezero_1m/dem.npy --meta data/jezero_1m/dem.json --max-dim 1500 --out web/data/sites/jezero-1m`, then `build_overview.py --sites-only` |
| 0.25 m photo (a picture, not elevation) | HiRISE orthoimage (P15) | `fetch_ortho_window.py "$ORTHO" --inspect` (check its resolution!), then `fetch_ortho_window.py "$ORTHO" --site-dir web/data/sites/jezero-1m` |

The map shows a "Detail level" switcher when several windows cover the same place, and a "Photo" layer when a window has `photo.jpg`.
A 1 m window of 1500 x 1500 pixels (2.25 million cells) makes routing in the browser slower: test it on the machine you will demo on.

## 6. Build the real globe

```bash
python scripts/build_globe.py             # downloads about 460 MB (dust: 7 Mars years of about 55 MB; `--dust-years 29 31` for fewer) into data/globe/, scores, writes web/data/
python -m mars_survival serve             # http://localhost:8000/globe.html
```

It prints, for each layer, its coverage and value range, plus the thresholds it chose. Check that:

- the elevation range is close to MOLA's known −8200 to +21200 m (a little smaller after averaging);
- the thermal inertia median is a few hundred tiu;
- the global mean temperature is near the NASA Fact Sheet's 214 K;
- the dust medians are plausible (visible optical depth of a few tenths);
- the zero-flux share of the neutron table is small.

Five layers are measured or processed from open data (elevation, neutron flux, thermal inertia, temperature with its
day/night swing, dust). Pressure and radiation are derived from elevation. Rock abundance, slope, water ice depth and wind
are absent, so the score is **partial**: each cell shows its data coverage, and the viewer lists the sources. The Odyssey
table is the first 25.7 days of mapping and mixes seasonal CO2 frost with water ice at high latitude, so read high
latitudes with care.

### Offline (SYNTHETIC data, to test the interface)

```bash
python -m mars_survival site-demo         # made-up terrain, red banner "Synthetic terrain. Not Mars data."
python -m mars_survival demo              # synthetic globe
```

Draw no scientific conclusion from these demos.

---

## 7. Safety tools (site map)

- **Safety tab**: set a shelter, then (1) *Return to shelter*: how far a person can go and still walk back, from Apollo suit consumables (8 h, mean 273 W) with a reserve; (2) *Radio line of sight* from the shelter antenna, Mars curvature included; (3) *Shadows* at any local solar hour and season.
- **Time budget** (right panel, under the route): does the walk end after sunset or fall below the cold limit; safe start times.
- **Saved places**: name, description, type; searchable, on the 2D and 3D maps, stored in the browser, export and import as JSON.
- **Walker's view** (3D), **Print route card**, **offline use** (`web/sw.js`, network first, cache as fallback).
- Not done: a DTM confidence layer (our HiRISE DTM has no error map; the USGS Mars 2020 TRN DTM has one). Position sync between two people (idea, not built): `docs/SYNC_IDEA.md`. Ideas: `docs/RESEARCH_IDEAS.md`.

## 8. All commands, from zero to the full map

Run from the repository root. Each block says what it adds to the map. Downloads run on your machine; the scripts resume interrupted transfers.

```bash
# --- 0. Setup (once) -------------------------------------------------------------------------------------------------
python -m venv .venv && source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt                            # = pip install -e ".[geo,dev]"
# optional: Node 18+ for the Node tests; a LaTeX install (pdflatex) for docs/latex

# (the two variables DTM and ORTHO come from the block in section 3; define them again in a new terminal)
# The two data links, defined once (HiRISE stereo pair ESP_023524_1985 / ESP_023379_1985; Windows PowerShell: $DTM = "..." and use $DTM)
DTM="https://www.uahirise.org/PDS/DTM/ESP/ORB_023500_023599/ESP_023524_1985_ESP_023379_1985/DTEEC_023524_1985_023379_1985_U01.IMG"
ORTHO="https://www.uahirise.org/PDS/DTM/ESP/ORB_023500_023599/ESP_023524_1985_ESP_023379_1985/ESP_023524_1985_RED_A_01_ORTHO.JP2"    # photo, 0.2524 m/px (checked with --inspect)

# --- 1. Site map: Jezero at 4 m/px (needs 1a + 1b) -----------------------------------------------------------------
python scripts/fetch_dtm_window.py "$DTM" \
  --lat 18.44 --lon 77.52 --size-m 4000 --out data/jezero    # 1a: elevation window (add --inspect to print the label)
python scripts/fetch_meda.py --sols 1 1800 --every 30 --out data/meda       # 1b: real weather
python scripts/analyse_meda.py data/meda --out data/meda_jezero.json
python scripts/build_jezero.py                             # -> web/data/site/ (slope, roughness, hazard, routes, flat sites, sun plan)

# --- 2. Overview of the whole crater (adds overview.html and the detail-window list) ---------------------------------
python scripts/build_overview.py                           # downloads the 87 MB CTX DEM once -> web/data/overview/, web/data/sites.json

# --- 3. Detail tiers: 1 m native window + 0.25 m photo layer (adds the "Detail level" switcher and "Photo" layer) -----
python scripts/fetch_dtm_window.py "$DTM" --lat 18.44 --lon 77.52 --size-m 1500 --out data/jezero_1m
python scripts/build_jezero.py --dem data/jezero_1m/dem.npy --meta data/jezero_1m/dem.json --max-dim 1500 --out web/data/sites/jezero-1m
python scripts/fetch_ortho_window.py "$ORTHO" --inspect          # CHECK the pixel size first (page does not state it)
python scripts/fetch_ortho_window.py "$ORTHO" --site-dir web/data/sites/jezero-1m
#   if it stops with "opj_decode() failed" (a cut transfer): re-run it (it retries each strip), or download once with  curl -C - -O "$ORTHO"  and pass the local .JP2 file instead of "$ORTHO"
python scripts/build_overview.py --sites-only              # refresh web/data/sites.json after adding or removing a window

# --- 4. Globe: global screening (adds globe.html layers; about 460 MB) -------------------------------------------------
python scripts/build_globe.py                              # --dust-years 29 31 for fewer downloads; --min-coverage 0.3 default

# --- 5. Look at it ----------------------------------------------------------------------------------------------------
python -m mars_survival serve                              # http://localhost:8000  (/ site, /overview.html, /globe.html, /sources.html)

# --- 6. Check ---------------------------------------------------------------------------------------------------------
PYTHONPATH=src python -m pytest -q
node tests/marsclock_test.mjs && node tests/survival_test.mjs

# --- 7. Documents -----------------------------------------------------------------------------------------------------
python scripts/make_report.py                              # web/sources.json -> docs/ANALYSIS_REPORT.md

# --- 8. Deploy --------------------------------------------------------------------------------------------------------
git add web/data && git commit -m "Rebuild data" && git push    # Vercel publishes web/ (no build step)
# or: npx vercel --prod. Then open the site and check that no "Synthetic" banner is shown.

# --- Offline demo with SYNTHETIC data (interface test only, no scientific value) ------------------------------------------
python -m mars_survival site-demo
python -m mars_survival demo
```

What each step turns on: step 1 gives the site map with every tool (terrain, routes, safety, time budget, walker, 3D, saved places); step 2 the overview page; step 3 the detail levels and photo; step 4 the globe. Steps 2 to 4 are independent of each other; step 1 is needed before 3.

## 9. What the map computes

| Quantity | Method | Status |
|---|---|---|
| Elevation | real HiRISE DTM, block-averaged | NASA data |
| Slope, roughness | finite differences on the DTM; roughness = local standard deviation of elevation after removing the fitted slope plane (60 m window) | Computed from NASA data |
| Walking cost | Minetti 2002 (Earth); slope part × g_Mars/g_Earth, flat part × 0.75 (Cavagna 2000) | Physics model, **hypothesis on Mars** |
| Walking pace | 3.4 km/h = 5.5 km/h × √(g_Mars/g_Earth) | Physics model |
| Suit power | 326 W (Apollo 16 suit, on the Moon); mass 170 kg | Assumptions (adjustable in the interface) |
| Rough ground | cost × (1 + (roughness / 0.25 m)²), impassable above 1.5 m | **Team hypothesis**, no NASA source |
| Hazard classes | slope 10 / 20 / 25°, roughness 0.25 / 0.6 / 1.5 m | Team assumptions (20° and 25° echo Lunar Roving Vehicle slopes) |
| Flat sites | disc 120 m across (60 m radius); at most 5% outside the limits (≤ 5°, ≤ 0.25 m) | Team assumption |
| Return to shelter | one-to-all least-energy fields out and back; limits: time = autonomy × (1 − reserve), energy = 272.6 W × that time | Apollo data (P10, P11) + **team assumptions** (A12, A13) |
| Radio line of sight | straight line, Mars curvature, antennas 3 m and 1.8 m | Geometry + team assumption (A14) |
| Shadows, time budget | ray march along the sun azimuth; hourly sun and temperature of the Sun plan | Physics model + team assumption (A15) |
| Sun | exact geometry (declination, hour angle) | Physics model |
| Air temperature | mean and day/night swing from MEDA; sinusoidal shape, peak at 14:00 | NASA data + simplification |
| Clock | Earth time (your device) and Jezero local true solar time (Mars24 algorithm, equation of time included) | NASA GISS model |

Each source in full (name, URL, data taken, use, status) is in `web/sources.json`.
The assumptions are discussed in the headers of `src/mars_survival/traverse.py` and `physics.py`.

**Known limits.** The DTM (1 m native, 4 m in the current Jezero build) cannot see boulders, so roughness is underestimated. The MEDA pressure channels disagree
by ~9 Pa (unexplained). Cavagna's cost is mechanical, not metabolic. The site calculation has no cast shadows, radio
link, consumables or radiation. Radiation is only derived from elevation (one MSL RAD anchor). See `docs/SOURCES.md`.

---

## 10. Deployment (Vercel)

Static site: `vercel.json` publishes the `web/` folder with no build step.

1. Run the Jezero build (section 3) on your machine and **commit `web/data/site/`**.
2. Import the GitHub repository into Vercel (framework: "Other"), or run `npx vercel --prod` from the root.
3. Check that no "Synthetic" banner appears: if one does, `web/data/site/` came from a demo.

---

## 11. Tests

```bash
PYTHONPATH=src python -m pytest -q        # 80 tests (some skipped without rasterio)
node tests/marsclock_test.mjs             # Mars clock
node tests/survival_test.mjs              # reach, line of sight, shadows, time budget
# the Python / JS routing parity is run by pytest itself (tests/js_energy_parity.mjs needs a data file, do not run it alone)
```

They cover: slope and roughness on exact shapes, the Minetti polynomial (Table 2 of the paper), routing,
PDS3 reading against a server that cuts transfers, MEDA units (real sol 1 file), the clock.

---

## 12. Status and to do

**Done:** simulated walker (2D, 3D, walker's view), tutorial tour, English and French, safety tools (reach, radio, shadows, time budget), saved places, route card, offline mode, overview page, detail tiers and photo layer, routing in a Web Worker, walking-speed and line-thickness.


**Open work:**
- A GitHub workflow that rebuilds the data.
- More detail windows (another HiRISE DTM site) and a site picker on the overview.
- Confidence layer: replace the HiRISE DTM by the USGS Mars 2020 TRN DTM (it has an error map).
- Globe: rock abundance, slope, wind, and a full-mission hydrogen map.
- Temperature: replace the sinusoid by the published fits (Zenodo, Hueso et al.).
- Check the Mars24 coefficients and the perihelion $L_s$ used by the clock against the primary paper.
- Trek basemap: test CORS and maximum zoom.
- Team assumptions that still lack a source: 25% reserve, antenna heights (3 m, 1.8 m), roughness thresholds, terrain multiplier.
