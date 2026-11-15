# Sources & physics provenance (v0.3 draft)

Rule for this project: **no number without a source.** Every entry says what exact data/value we take, and what we use it for.
Status legend: **Page read** = I read the publisher's page and quote it; **Not verified** = could not be checked, do not rely on it.
NOTE (2026-11-07): the live source registry is `web/sources.json` (shown on `web/sources.html`, exported to `docs/ANALYSIS_REPORT.md`). This file is the research log: reasoning, checks and dated updates. Where they differ, `web/sources.json` is newer.

## A. Data sources

| ID | Name (publisher) | Full URL | Exact data taken | Use in the project | Licence / citation | Status |
|---|---|---|---|---|---|---|
| D1 | HiRISE DTM, stereo pair ESP_023524_1985 / ESP_023379_1985, "Proposed Landing Site in Jezero Crater" (UA HiRISE) | https://www.uahirise.org/dtm/ESP_023524_1985 | `DTEEC_023524_1985_023379_1985_U01.IMG` (700 MB, 1.00 m/px) and ortho `ESP_023524_1985_RED_C_01_ORTHO.JP2` (60 MB). Direct: https://www.uahirise.org/PDS/DTM/ESP/ORB_023500_023599/ESP_023524_1985_ESP_023379_1985/DTEEC_023524_1985_023379_1985_U01.IMG | Site-scale terrain: slope, roughness, route cost, 3D view | PDS/HiRISE product credit | **Confirmed Jezero** (page: centre lat 18.3°, lon 77.53°, 1.00 m/px; checked in browser by the team). Ortho variants: RED_C_01 (60 MB), RED_A_01 (766 MB) — meaning of C vs A to read in the DTM Extras Read-me |
| D2 | MSR Terrain-Relative-Navigation HiRISE DTM + ortho mosaics (USGS Astrogeology) | https://astrogeology.usgs.gov/search/map/mars-sample-return-terrain-relative-navigation-hirise-dtm-mosaic | Mosaics zip (5.3 GB): DTM, ortho, confidence GeoTIFFs; Jezero lat 18.135–18.588, lon 77.057–77.380; 1 m/px; equirectangular, planetocentric, MOLA-controlled. https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/Mars/MSR_TRN_HiRISE_soc_003_USGS_release_aug2024/MSR_TRN_HiRISE_soc_003_USGS_release_aug2024_mosaics.zip | Preferred explicit-Jezero terrain; confidence layer = DTM uncertainty | DOI https://doi.org/10.5066/P13CPYYU | Page read |
| D3 | MGS MOLA DEM 463 m (USGS, from MOLA Team/GSFC) | https://astrogeology.usgs.gov/search/map/mars_mgs_mola_dem_463m | GeoTIFF ~2 GB, 463.08 m/px, heights above areoid in m, vertical uncertainty ≥ ±3 m, 16-bit. https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif | Global elevation; regional context; elevation-driven pressure/radiation proxy | CC0. Smith et al. 2001, JGR 106(E10), doi:10.1029/2000JE001364 | Page read |
| D4 | Mars 2020 MEDA bundle (NASA PDS Atmospheres) | https://pds.nasa.gov/data/pds4/releases/atmos/mars2020_meda-20260811/ | Collections `data_calibrated_env`, `data_derived_env` (pressure, humidity, wind, TIRS channels), CSV + PDS4 XML, one file per sol | Real Jezero weather ground-truth: compute temperature / pressure statistics ourselves from the data | PDS citation per product | Directory opened by the team: it holds only collection inventories/labels (e.g. `collection_data_derived_env.csv` 690 KB, `collection_data_calibrated_env.csv` 1.0 MB, `readme.txt`), **no data folders** → the per-sol data files live elsewhere; location still to find |
| D5 | MEDA surface pressure at Jezero, sols 1–414 (FMI, B2SHARE) | https://fmi.b2share.csc.fi/records/axmwh-rjx51 (files: https://fmi.b2share.csc.fi/api/records/axmwh-rjx51/files-archive) | PS sensor pressure in Pa; accuracy < 3.5 Pa, resolution 0.13 Pa; 32 files, 67 MB | Jezero pressure baseline + seasonal cycle (small, easy first download) | CC-BY 4.0, DOI 10.57707/fmi-b2share.fb7b51ad29484eeab913d426652d890c | Page read |
| D6 | Derived Jezero air temperatures from MEDA ATS, first 700 sols (Hueso, Munguira et al., Zenodo) | https://doi.org/10.5281/zenodo.11198655 | Derived near-surface temperature tables incl. Fourier-series fits | Diurnal/seasonal temperature curve for the EVA planner, replacing my sinusoid | Cite Munguira et al. 2024 (JGR Planets, "in revision" when listed) | Opened by the team: file `ATS_DER up to sol 700.zip` of per-sol CSVs (`WE__0001___DER_ATS___P02.CSV`, 4 kB–10 MB each). Downloadable; no numbers extracted yet |
| D7 | Odyssey GRS special products (NASA PDS Geosciences) | https://pds-geosciences.wustl.edu/ody/urn-nasa-pds-odyssey_grs_special/readme.txt | Global maps of neutron flux / gamma spectra showing hydrogen peaks (ASCII tables) | Water-ice potential layer (water-equivalent hydrogen) | PDS; Boynton/Feldman/Mitrofanov et al. 2002, Science | **Confirmed by team in browser**: bundle holds 6 ASCII tables = global **neutron-flux maps and gamma-ray hydrogen-peak data** (Boynton, Feldman, Mitrofanov 2002, Science 297), NOT a ready water-equivalent-hydrogen map. We can use epithermal-neutron flux as a hydrogen proxy (less flux = more hydrogen) |
| D8 | Mars Trek tiles, MOLA colorized shaded relief (NASA JPL) | https://trek.nasa.gov/tiles/Mars/EQ/Mars_MGS_MOLA_ClrShade_merge_global_463m/1.0.0/default/default028mm/0/0/0.jpg | Tile z0 loads in the team's browser (whole planet in one 256×256 tile). Directory listing `/tiles/Mars/EQ/` returns 403 (normal) | Optional web basemap | per layer | **Partly verified**: tile URL pattern works; the tile matrix (how many tiles at z≥1) and cross-site (CORS) use are still to test |

## B. Physics anchors (what the thresholds may be based on)

| Quantity | Value | Kind | Source (URL) | Use |
|---|---|---|---|---|
| Surface GCR dose equivalent, Gale crater, Aug 2012–Jun 2013 | **0.67 mSv/day** (cruise: 1.8 mSv/day) | Measured (MSL RAD) | Hassler et al., *Science*, 9 Dec 2013, summarised at https://www.swri.org/press-release/swri-scientists-publish-first-radiation-measurements-surface-mars | Radiation baseline; ~1 Sv for a 500-day surface stay (as stated there) |
| Dose depends on pressure (thermal tides, season) and solar modulation | model, coefficients not yet read | Measured + model | Guo et al. 2015, ApJ 810:24, doi:10.1088/0004-637X/810/1/24, https://arxiv.org/abs/1507.03473 | Needed to turn elevation → radiation correctly (**TODO: read coefficients**) |
| Steepest slope driven by any Mars rover | **32°** tilt (Opportunity, 10 Mar 2016) | Measured event, not a safe limit | https://www.jpl.nasa.gov/news/rover-takes-on-steepest-slope-ever-tried-on-mars | Hard physical ceiling for rover-class vehicles |
| Lunar Roving Vehicle design slope | **20–23°** favourable, **max 25°** | NASA design figure (Moon, vehicle) | Jacob et al., LPSC 57 (2026), https://ntrs.nasa.gov/citations/20250011301 | Anchor for "hazardous" (20°) and "forbidden" (25°) slope classes |
| Perseverance autonomous drive rate | ≈ **110 m/h**; max wheel speed 4.2 cm/s | Design/measured (rover) | https://robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-2020-rover/m2020mobility/ | Rover-mode travel time |
| Metabolic cost of walking vs slope (Earth, treadmill, 10 elite mountain athletes, 61 kg, no load) | `Cw(i)=280.5i⁵−58.7i⁴−76.8i³+51.9i²+19.6i+2.5` J/(kg·m), valid i∈[−0.45,+0.45]; measured 1.64 (level, min) … 17.33 (i=+0.45); uphill mechanical efficiency 0.243 | Measured (peer-reviewed) | Minetti et al. 2002, J Appl Physiol 93:1039, doi:10.1152/japplphysiol.01177.2001 (PDF supplied by the team) | Energy and pace per metre of a route (`physics.py`, tested against the paper's Table 2) |
| Suited astronaut metabolic power, lunar surface (1/6 g) | Traverse ≈ 3.0 ft/s: 1112–1185 BTU/h (326–347 W); carry 41 lb: up to 2300 BTU/h (674 W); LRV riding 442–633 BTU/h | Measured (NASA, Apollo 16) | Kubis et al., Apollo 16 Time and Motion Study, NASA MSC M72-6 (1972), https://ntrs.nasa.gov/api/citations/19730008098/downloads/19730008098.pdf. Several values OCR-damaged in the PDF: re-check against the page images | Calibration milestones for the EVA power budget; slope effect NOT analysed in that report |
| MOLA vertical uncertainty | ≥ ±3 m | Measured | D3 | Error bar on elevation-derived values |

## C. Gaps — honest list (no value invented)
1. **No NASA numeric slope limit for a walking, suited human on Mars** found. New approach (team decision): derive effort from walking biomechanics (Minetti 2002) scaled to Mars gravity, calibrated against measured Apollo suit power. Slope *danger* classes (slipping, tipping) remain separate and still need a source; the 10° class is a **team assumption** until then.
2. **EVA duration and suit temperature limits**: not found. Walking speed will now come from `physics.speed_for_power` (power budget from Apollo 16 data) instead of the fixed 2 km/h. The −90 °C floor stays a **team assumption**.
2b. **Physics hypotheses** H1–H4 are listed in `physics.py` (gravity scaling of the slope part only; flat cost unscaled; sand not modelled; speed cap). H2 is now set from Cavagna, Willems & Heglund 2000 (J Physiol 528:657, flat cost x0.75, see physics.py [C00]); their 1998 Nature note is not needed; suit+equipment mass is unknown and must be a user input.
3. **Roughness thresholds (0.25/0.6/1.5 m)**: no NASA source yet. Candidate: rock-height / clearance figures for Mars 2020 ENav (not found on the page read).
4. **Water-equivalent hydrogen product** (D7): exact file not identified.
5. **Dust opacity**: no layer. The sources that offered one (LMD dust climatology, CC BY-SA 3.0; MCS temperatures, CC BY 4.0; EMARS, no stated licence) were removed because they are not freely usable without restriction / OSI-licensed as the Space Apps 2026 rules require.
6. **Elevation → radiation/pressure** relations in `schema.derive_from_elevation` are my approximations; replace with Guo et al. 2015 + MEDA pressure data.

## D. Software resources
| Name | URL | Use | Licence |
|---|---|---|---|
| Leaflet 1.9.4 | https://leafletjs.com | 2D map viewer (vendored) | BSD-2-Clause |
| three.js r160 | https://threejs.org | 3D terrain view (vendored) | MIT |
| GDAL | https://gdal.org | Read/clip/convert PDS `.IMG` and GeoTIFF; can read a window of a remote file via `/vsicurl/` (untested here) | MIT/X |
| NumPy | https://numpy.org | Raster maths | BSD |
| Pillow | https://python-pillow.org | PNG output | HPND |
| Requests | https://requests.readthedocs.io | Polite downloads | Apache-2.0 |


## Update 2026-11-06 — browser tests and Cavagna 2000
| Item | Result | Use |
|---|---|---|
| Mars Trek MOLA tiles, `.../default028mm/{z}/{row}/{col}.jpg` | z1 rows 0-1, cols 0-3 all load (5 tiles tested, features match lon/lat: Olympus Mons row0/col0, Elysium row0/col3, Argyre row1/col1). Scheme = 2^(z+1) cols x 2^z rows, row 0 north | `web/basemaps.json` verified=true |
| MEDA PDS4 bundle `https://atmos.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/` | folders `data_calibrated_env`, `data_derived_env`, `data_raw_env`, `data_partially_processed_env`, `data_skycam`, `document`, `context`, `browse_skycam`; real data present | pressure/temperature per sol (to inspect next) |
| Odyssey GRS special `https://pds-geosciences.wustl.edu/ody/urn-nasa-pds-odyssey_grs_special/data/` | `ns_epithermal_020917.tab`, `ns_fast_`, `ns_thermal_` (~6.7 MB each), `hend_epithermal`, `hend_fast`, `grs_h_peaks_020917.tab` | epithermal neutron map = hydrogen/ice proxy |
| HiRISE DTM `.../DTEEC_023524_1985_023379_1985_U01.IMG` | `Content-Length: 700271460` (700 MB) and `Accept-Ranges: bytes` | streaming by HTTP range (GDAL /vsicurl/) possible; no 5.3 GB zip needed |
| Cavagna, Willems, Heglund 2000, J Physiol 528:657-668 | W_ext min 0.30 (1 g, 4.5 km/h) vs 0.15 J/(kg m) (0.4 g, 2.5 km/h); max pendular recovery 5.5 / 3.5 / ~6.5 km/h at 1 / 0.4 / 1.5 g | `physics.py` LEVEL_SCALE_MARS=0.75 and `optimal_speed_kmh` (v proportional to sqrt g, matches 3.5 km/h; Apollo 3 ft/s = 3.3 km/h) |
Caveat: Cavagna measured mechanical work (3 men, 0.4 g in parabolic flight, no suit), not metabolic cost. The 0.75 factor assumes internal work is unchanged; it is an upper bound.

## Update 2026-11-06 (2) — MEDA labels, terrain multiplier
| Item | Result | Use |
|---|---|---|
| MEDA CAL_ATS label (sol 1), `https://atmos.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/data_calibrated_env/sol_0000_0089/sol_0001/` | `ATS_LOCAL_TEMP1..5`, unit **kelvin**; sensors on the RSM (50°, 155°, 290°) and RFB (port, starboard); title "Mars 2020 MEDA Air Temperature Sensor Calibrated Data"; reference doc `urn:nasa:pds:mars2020_meda:document:meda_env_rdr_sis` | air temperature per sol (median of 5 sensors) |
| MEDA CAL_PS label (sol 1), same folder | `BAROCAP1/2/3_PRESSURE`, unit **pascal**; `THERMOCAP1/2_TEMP` kelvin; `PRESSURE_MEASUREMENT_MODE`, `TRANSDUCER`; product **version 2.0, reprocessed for barocap drift compensation (2021-10-29)** | surface pressure per sol (median of 3 barocaps). Open point: channels differ by ~9 Pa on sol 100, cause not yet documented |
| Soule & Goldman 1972, J Appl Physiol 32(5):706-708; Pandolf, Givoni & Goldman 1977, J Appl Physiol 43(4):577-581 | Earth terrain factors: blacktop 1.0, dirt road 1.1, light brush 1.2, heavy brush 1.5, swampy bog 1.8, loose sand 2.1, soft snow 15/25/35 cm 2.5/3.3/4.1 (values read from https://en.wikipedia.org/wiki/Pandolf_equation; verify in the papers) | sanity anchor for `traverse.terrain_multiplier` (hypothesis, see traverse.py header) |
