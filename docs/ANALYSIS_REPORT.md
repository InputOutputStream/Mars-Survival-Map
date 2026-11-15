# Mars Survival Map: sources and assumptions

Updated 2026-11-10. Generated from `web/sources.json`; edit that file, not this one.

## Data sources

### D1 HiRISE stereo DTM ESP_023524_1985 / ESP_023379_1985, Jezero crater
*University of Arizona HiRISE / NASA MRO*  
- Link: https://www.uahirise.org/dtm/ESP_023524_1985
- Exact file: https://www.uahirise.org/PDS/DTM/ESP/ORB_023500_023599/ESP_023524_1985_ESP_023379_1985/DTEEC_023524_1985_023379_1985_U01.IMG
- Data taken: Elevation raster DTEEC_023524_1985_023379_1985_U01.IMG: 21258 x 8235 pixels, 1.0097 m/px, float32 metres above the Mars 2000 datum, valid range -2694.83 to -2510.19 m. We read only a window over HTTP range requests (the server supports them, checked 2026-11-06).
- Used for: Every site-scale number: elevation, slope, roughness, hazard classes, route cost, 3D view.
- Status: Downloaded by the team (window) and header read; page confirms Jezero, centre 18.3°N 77.53°E.

### D2 MSR Terrain-Relative-Navigation HiRISE DTM and ortho mosaics, Jezero
*USGS Astrogeology*  
- Link: https://astrogeology.usgs.gov/search/map/mars-sample-return-terrain-relative-navigation-hirise-dtm-mosaic
- Data taken: Candidate: 1 m/px DTM mosaic with confidence layer (5.3 GB zip), Jezero lat 18.135 to 18.588, lon 77.057 to 77.380.
- Used for: Not used yet. Preferred later for a wider, explicitly Jezero-controlled terrain and an uncertainty layer.
- Status: Page read only.

### D3 MGS MOLA MEGDR topography, 4 pixel/degree (global)
*NASA PDS Geosciences Node, from the MOLA Team*  
- Link: https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg004/
- Exact file: https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg004/megt90n000cb.img
- Data taken: 720 x 1440 big-endian int16, metres above the GMM3 areoid, 0.25 degree pixels, lat +90 at top, lon 0..360 from the left (checked against the PDS label).
- Used for: Globe elevation layer (2 x 2 block mean to the 0.5 degree grid), and pressure and radiation derived from it.
- Status: Label read by the team's assistant; file downloaded by scripts/build_globe.py on your machine (about 2 MB). Replaces the earlier 463 m candidate for the globe.

### D4 Mars 2020 MEDA calibrated environmental data (CAL_ATS air temperature, CAL_PS pressure)
*NASA PDS Atmospheres Node (NMSU)*  
- Link: https://atmos.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/data_calibrated_env/
- Data taken: Per-sol CSV files. CAL_ATS: ATS_LOCAL_TEMP1..5 in kelvin. CAL_PS: BAROCAP1..3_PRESSURE in pascal, version 2.0 (reprocessed for drift, 2021-10-29). Units confirmed from the PDS4 labels.
- Used for: Air temperature mean and daily swing for the sol planner; pressure baseline.
- Status: Folder listings and sol 1 labels read by the team; sol 100 columns read; sampled sols downloaded by the team.

### D5 Odyssey GRS special product: epithermal neutron flux ns_epithermal_020917
*NASA PDS Geosciences Node (Feldman et al. 2002, Science 297:75-78)*  
- Link: https://pds-geosciences.wustl.edu/ody/urn-nasa-pds-odyssey_grs_special/data/
- Exact file: https://pds-geosciences.wustl.edu/ody/urn-nasa-pds-odyssey_grs_special/data/ns_epithermal_020917.tab
- Data taken: 259,200 text rows 'lon, lat, flux' (counts/s), one per 0.5 degree cell, lon 0..360. Less flux means more hydrogen. First 25.7 days of mapping only. Rows with flux exactly 0.000 are treated as no data (our reading).
- Used for: Globe hydrogen proxy layer epithermal_cps, scored between its 5th and 95th percentile (team choice, written to config/scoring.json by scripts/build_globe.py).
- Status: Label and first rows read by the team's assistant; table downloaded by scripts/build_globe.py on your machine. Not calibrated to water-equivalent hydrogen; seasonal CO2 frost mixes in at high latitude. A full-mission water-equivalent hydrogen map would be better: no verified PDS file found yet.

### D6 Mars Trek MOLA colourised shaded relief tiles
*NASA JPL Mars Trek*  
- Link: https://trek.nasa.gov/tiles/Mars/EQ/Mars_MGS_MOLA_ClrShade_merge_global_463m/1.0.0/default/default028mm/0/0/0.jpg
- Data taken: Image tiles, scheme {z}/{row}/{col}.jpg, 2^(z+1) columns by 2^z rows, row 0 at the north.
- Used for: Optional global basemap.
- Status: Tiles z0 and z1 opened by the team. Maximum zoom and cross-site (CORS) use untested.

### D7 Derived Jezero air temperatures from MEDA ATS, first 700 sols
*Hueso, Munguira et al. (Zenodo)*  
- Link: https://doi.org/10.5281/zenodo.11198655
- Data taken: Per-sol CSV of derived temperatures (Fourier fits).
- Used for: Candidate to replace the sinusoid in the sol planner.
- Status: Record opened by the team; not used yet.

### D8 MEDA surface pressure at Jezero, sols 1 to 414
*Finnish Meteorological Institute (B2SHARE)*  
- Link: https://fmi.b2share.csc.fi/records/axmwh-rjx51
- Data taken: Pressure in Pa, 32 files, 67 MB; accuracy under 3.5 Pa.
- Used for: Candidate cross-check of the MEDA pressure we compute.
- Status: Page read; not used yet.

### D9 MGS TES derived thermal inertia maps (Putzig & Mellon 2007)
*NASA PDS Geosciences Node (Putzig, Mellon, Heet, Ward; V1.0, 2009)*  
- Link: https://pds-geosciences.wustl.edu/missions/mgs/tes-timap.html
- Exact file: https://pds-geosciences.wustl.edu/mgs/mgs-m-tes-5-timap-v1/mgst_9001/data/global_ti_night_2007.img
- Data taken: 3600 x 7200 big-endian int16, 20 pixel/degree, lon -180..180, units J m-2 K-1 s-1/2; derived range 5 to 5000. Night map used. Label, readme and datainfo read by the team's assistant; the label states no scaling or missing value, so raw integers are taken as tiu and values outside 5..5000 as no data.
- Used for: Planet-map layer thermal_inertia_tiu (loose dust versus firm ground), scored 100 to 300 tiu.
- Status: Downloaded by scripts/build_globe.py on your machine (52 MB). The script warns if the median is outside 50 to 800 tiu.

## Physics sources

### P1 Minetti et al. 2002, Energy cost of walking and running at extreme uphill and downhill slopes
*Journal of Applied Physiology 93:1039-1046*  
- Link: https://doi.org/10.1152/japplphysiol.01177.2001
- Data taken: Cw(i) = 280.5 i^5 - 58.7 i^4 - 76.8 i^3 + 51.9 i^2 + 19.6 i + 2.5 J/(kg m), valid for slopes i from -0.45 to +0.45; 10 athletes, treadmill, no load.
- Used for: Energy per metre of walking at every slope (physics.py). Slope part scaled by g_Mars/g_Earth. The tests reproduce the paper's Table 2.
- Status: Paper supplied by the team. Earth data: using it on Mars is a hypothesis.

### P2 Cavagna, Willems and Heglund 2000, The role of gravity in human walking
*Journal of Physiology 528:657-668*  
- Link: https://doi.org/10.1111/j.1469-7793.2000.00657.x
- Data taken: External mechanical work minimum 0.30 J/(kg m) at 1 g (4.5 km/h) and 0.15 at 0.4 g (2.5 km/h); best pendular recovery speed 5.5, 3.5 and about 6.5 km/h at 1, 0.4 and 1.5 g.
- Used for: Flat-ground cost factor 0.75 and the pace of 3.4 km/h (speed proportional to the square root of gravity).
- Status: Paper supplied by the team. Mechanical work, not metabolic; three men; no suit. The DOI is from memory: check it.

### P3 Apollo 16 Time and Motion Study (NASA MSC M72-6)
*NASA*  
- Link: https://ntrs.nasa.gov/api/citations/19730008098/downloads/19730008098.pdf
- Data taken: Suited astronaut metabolic power on the Moon: walking at about 3 ft/s, 1112 to 1185 BTU/h (326 to 347 W); carrying 41 lb, up to 2300 BTU/h (674 W).
- Used for: Default sustained power (326 W) and a pace cross-check (3 ft/s = 3.3 km/h).
- Status: Report supplied by the team. Several values were damaged in the PDF text: re-check against the page images. It analysed no slope effect.

### P4 Soule and Goldman 1972; Pandolf, Givoni and Goldman 1977, terrain coefficients
*Journal of Applied Physiology 32(5):706-708 and 43(4):577-581*  
- Link: https://en.wikipedia.org/wiki/Pandolf_equation
- Data taken: Earth terrain factors: blacktop 1.0, dirt road 1.1, light brush 1.2, heavy brush 1.5, swampy bog 1.8, loose sand 2.1, soft snow 15/25/35 cm 2.5/3.3/4.1.
- Used for: Sanity anchor for the rough-ground multiplier (a team hypothesis).
- Status: Values read on Wikipedia; verify in the papers.

### P5 Hassler et al. 2013, Mars' surface radiation environment measured with the MSL RAD
*Science*  
- Link: https://www.swri.org/press-release/swri-scientists-publish-first-radiation-measurements-surface-mars
- Data taken: 0.67 mSv/day at Gale crater surface (cruise 1.8 mSv/day).
- Used for: Radiation baseline for the globe scoring.
- Status: Press summary read.

### P6 Lunar Roving Vehicle design slopes
*Jacob et al., LPSC 57 (2026), NASA NTRS*  
- Link: https://ntrs.nasa.gov/citations/20250011301
- Data taken: Design slope 20 to 23° favourable, maximum 25°.
- Used for: Echoed by the 20° (hazardous) and 25° (forbidden) hazard limits. Not a Mars walking limit.
- Status: Page read.

### P7 Steepest slope driven by a Mars rover (Opportunity, 32°)
*NASA JPL*  
- Link: https://www.jpl.nasa.gov/news/rover-takes-on-steepest-slope-ever-tried-on-mars
- Data taken: 32° tilt.
- Used for: Hard ceiling for rover-class vehicles.
- Status: Page read.

### P8 Allison and McEwen 2000, areocentric solar coordinates and Mars time recipes (Mars24)
*Planetary and Space Science 48:215-235; NASA GISS Mars24*  
- Link: https://www.giss.nasa.gov/tools/mars24/help/algorithm.html
- Data taken: Mars Sol Date from Julian date: MSD = (JD_TT - 2451549.5)/1.0274912517 + 44796.0 - 0.0009626; local mean solar time = MTC + east longitude/15; equation of time and solar longitude Ls from the paper's series (mean anomaly, fictitious mean Sun, 7 planetary perturbation terms); true solar time = mean + EOT.
- Used for: The map clock (web/marsclock.mjs): Jezero local true solar time from Earth time.
- Status: Coefficients typed from the paper: compare each one with the NASA GISS Mars24 page. Tests: EOT stays within about ±51 min over a year; the Perseverance touchdown (20:44 UTC, signal delay removed) gives about 15:15 true solar time, mid-afternoon as reported (my memory, verify). Leap seconds: 37 s assumed.

### P9 NASA Mars Fact Sheet (orbit and radiation constants)
*NASA NSSDC*  
- Link: https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html
- Data taken: Solar irradiance 586.2 W/m2, Bond albedo 0.250, eccentricity 0.0935, obliquity 25.19 deg, mean surface temperature about 214 K.
- Used for: Energy-balance temperature layer (src/mars_survival/thermal.py) and its sanity check.
- Status: Page read 2026-11-07. Ls of perihelion (251 deg) comes from Allison & McEwen, to verify; emissivity 1 and the 148 K CO2 frost point are our choices, not from that page.

### P10 Apollo 15-17 PLSS (portable life support system) consumables
*Wikipedia, summarising NASA documents (secondary; primary: NASA ALSJ, Apollo Flight PLSS)*  
- Link: https://en.wikipedia.org/wiki/Primary_life_support_system
- Data taken: Design EVA duration: 4 h (Apollo 11-14) and 8 h (Apollo 15-17); battery 390 Wh, cooling water 5.2 L, LiOH 1.42 kg for the J-missions.
- Used for: Suit autonomy (8 h default) of the return-to-shelter calculation.
- Status: Page read. Secondary source: check the primary NASA ALSJ document (history.nasa.gov/alsj/ALSJ-FlightPLSS.pdf) before publication.

### P11 NASA TN D-7883, metabolic expenditures for Apollo lunar surface EVA (Table I)
*NASA (hosted by the Apollo Lunar Surface Journal)*  
- Link: https://www.nasa.gov/wp-content/uploads/static/history/alsj/tnD7883Metabolic.pdf
- Data taken: Mean total metabolic rate of the listed Apollo EVAs: 930 Btu/h (980 kJ/h) = 272.6 W. Apollo 15-17 individual EVAs: 780 to 1100 Btu/h.
- Used for: Energy budget of the return-to-shelter calculation (mean metabolic rate x usable walking time).
- Status: Table read. Measured on the Moon, so a hypothesis on Mars.

### P12 Apollo Lunar Roving Vehicle: greatest range from the lunar module
*NASA NSSDC*  
- Link: https://nssdc.gsfc.nasa.gov/planetary/lunar/apollo_lrv.html
- Data taken: Greatest range from the LM: 5.0 km (Apollo 15), 4.5 km (Apollo 16), 7.6 km (Apollo 17).
- Used for: Comparison line shown beside the computed reach. Not an input.
- Status: Page read.

### P13 Mars Regional Navigation Satellite System (in-situ navigation and timing at a human Mars landing site)
*NASA NTRS 20210008406*  
- Link: https://ntrs.nasa.gov/citations/20210008406
- Data taken: Concept: relay orbiters broadcast GPS-like ranging signals; relative positioning by differencing two ranges is reported 200 to 400 times more accurate than absolute positioning (simulation).
- Used for: Background for the position-sync idea (docs/SYNC_IDEA.md). Not used in the app.
- Status: Abstract read.

### P14 Mars 2020 Science Investigation CTX DEM Mosaic
*USGS Astrogeology Science Center (F. Calef, 2021), from Mars Reconnaissance Orbiter CTX stereo*  
- Link: https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif
- Data taken: 20 m/px GeoTIFF (87 MB), lat 17.58 to 19.29, lon 76.99 to 78.58 (whole Jezero crater region). Product page: https://astrogeology.usgs.gov/search/map/mars_2020_science_investigation_ctx_dem_mosaic. Public domain; the page asks to cite the authors (Calef 2021; Mangold et al. 2021, Science, doi:10.1126/science.abl4051).
- Used for: Overview level of the map (overview.html): hillshade of the whole crater with the 1 m detail windows drawn on it. Not used for routing or hazards.
- Status: Real data. Vertical datum not named on the page (localised to MOLA); only relative relief is shown.

### P15 HiRISE orthoimages of the Jezero stereo pair (UA/HiRISE)
*University of Arizona HiRISE (NASA/JPL MRO)*  
- Link: https://www.uahirise.org/PDS/DTM/ESP/ORB_023500_023599/ESP_023524_1985_ESP_023379_1985/ESP_023524_1985_RED_A_01_ORTHO.JP2
- Data taken: Window of the orthorectified RED image (candidates on https://www.uahirise.org/dtm/ESP_023524_1985: RED_A 766 MB, RED_C 60 MB). Measured with scripts/fetch_ortho_window.py --inspect on RED_A: 32938 x 85030 px, pixel 0.2524 m, equirectangular Mars, central meridian 77.53 deg, sphere radius 3 394 839.8 m (written in the file).
- Used for: Optional "Photo" layer (up to 0.25 m/px) to see boulders and texture. Picture only: never used for slope, hazard or routes.
- Status: Resolution verified (0.25 m/px). Co-registration with the DTM not yet checked on the map: compare the photo with the hillshade.

## Team assumptions

### A1 Suit and gear mass
*Red Circle team*  
- Value: 170 kg
- Why it is a guess: Unknown for any real Mars suit. User input.
- Status: Team assumption: replace when a source is found.

### A2 Rough-ground multiplier
*Red Circle team*  
- Value: 1 + (roughness / 0.25 m)^2; impassable above 1.5 m
- Why it is a guess: No Mars source. Earth anchors in P4; HiRISE 1 m/px cannot see boulders.
- Status: Team assumption: replace when a source is found.

### A3 Hazard class limits
*Red Circle team*  
- Value: slope 10 / 20 / 25°, roughness 0.25 / 0.6 / 1.5 m
- Why it is a guess: No NASA slip or tip limit for a walking human. 20 and 25° echo P6.
- Status: Team assumption: replace when a source is found.

### A4 Outdoor window rules
*Red Circle team*  
- Value: sun above 5°, air above -90 °C, dust optical depth below 3
- Why it is a guess: Not from a NASA suit specification.
- Status: Team assumption: replace when a source is found.

### A5 Daily temperature shape
*Red Circle team*  
- Value: sine wave peaking at 14 h local solar time
- Why it is a guess: Simplification; mean and swing come from D4.
- Status: Team assumption: replace when a source is found.

### A6 Gravity scaling of the slope cost
*Red Circle team*  
- Value: slope part x g_Mars/g_Earth (0.378)
- Why it is a guess: Hypothesis; flat part uses P2. Not tested on Mars or with a suit.
- Status: Team assumption: replace when a source is found.

### A7 Flat-site tolerance
*Red Circle team*  
- Value: A disc 120 m across counts as flat if at most 5% of it exceeds 5° slope or 0.25 m roughness
- Why it is a guess: With zero tolerance the first real Jezero build found no flat site at all. No NASA landing-site rule is used; replace with one.
- Status: Team assumption.

### A8 Globe: partial scoring and thresholds
*Red Circle team*  
- Value: Cells are scored when the measured or derived layers carry at least 30% of the total weight (--min-coverage 0.3). Only elevation and epithermal flux are measured; pressure and radiation come from elevation.
- Why it is a guess: Without this the real globe would be empty. Pressure and radiation follow elevation, so the score mostly says 'low and hydrogen-rich'. Every cell's coverage is shown.
- Status: Team assumption: add temperature, thermal inertia, rocks and slope layers, then raise the threshold.

### A9 Globe temperature processing
*Red Circle team*  
- Value: Median over Mars years; daily mean = (T03 + T15)/2; swing = T15 - T03; values outside 130-320 K dropped; seasons weighted by duration; 75% of the year required; 5 degree nodes treated as points and interpolated
- Why it is a guess: The two local times only approximate the daily mean and the swing (the swing is smaller than the true max minus min). Polar and winter gaps stay empty.
- Status: Team assumptions. The energy-balance model (src/mars_survival/thermal.py) is kept only as a cross-check.

### A10 Thermal inertia scoring ramp
*Red Circle team*  
- Value: score 0 at 100 tiu, 1 at 300 tiu; night map; weights habitat 0.5, landing 1.5
- Why it is a guess: No sourced engineering limit yet (landing-site workshop criteria are a candidate). Very high values (bare rock) are not penalised.
- Status: Team assumption.

### A12 Reserve kept on the walking time
*Red Circle team*  
- Value: 25% of the suit autonomy is kept unspent (adjustable 0 to 50%).
- Why it is a guess: Round-trip limit = autonomy x (1 - reserve). No NASA value was found for Apollo walk-back margins.
- Status: Team assumption.

### A13 Mean Apollo metabolic rate as the sustainable walking energy
*Red Circle team*  
- Value: Round-trip walking energy (Minetti model) must stay under 272.6 W x usable time. Time and energy limits are both applied; the stricter one is reported.
- Why it is a guess: Return-to-shelter reach.
- Status: Team assumption.

### A14 Antenna heights and radio line of sight
*Red Circle team*  
- Value: Shelter antenna 3 m, suit antenna 1.8 m above ground (adjustable). Straight line with Mars curvature (radius 3389.5 km); no atmosphere, no antenna pattern, no radio frequency.
- Why it is a guess: Line-of-sight layer. Geometry only, not a link budget.
- Status: Team assumption.

### A15 Shadow and time-budget model
*Red Circle team*  
- Value: Shadows: ray march along the sun azimuth on the DTM (no sky light, no cast shadow from beyond the window). Time budget: hourly sun elevation and temperature from the Sun plan (simplified sinusoid fed by MEDA); sunset = sun below 0 degrees; caution below the planner minimum sun elevation (5 degrees); cold = below the planner limit.
- Why it is a guess: Time-budget card and shadow layer.
- Status: Team assumption on simplified models.

## Software and fonts

### S1 Leaflet 1.9.4
- Link: https://leafletjs.com
- Used for: 2D map
- Status: Licence: BSD-2-Clause

### S2 three.js r160
- Link: https://threejs.org
- Used for: 3D terrain
- Status: Licence: MIT

### S3 Public Sans (variable)
- Link: https://github.com/uswds/public-sans
- Used for: Interface typeface (US Web Design System)
- Status: Licence: SIL OFL 1.1

### S4 Bricolage Grotesque (variable)
- Link: https://github.com/ateliertriay/bricolage
- Used for: Brand and figures typeface
- Status: Licence: SIL OFL 1.1

### S5 NumPy, Pillow, Requests
- Link: https://numpy.org
- Used for: Raster maths, images, polite downloads
- Status: Licence: BSD / HPND / Apache-2.0
