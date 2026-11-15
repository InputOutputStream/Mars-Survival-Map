# Research and ideas: how to make the Mars survival map better

Findings come from the pages listed under "Sources"; ideas marked (idea) are ours, not taken from those pages.

## 1. What similar tools do

| Tool | What it does well | What we can borrow |
|---|---|---|
| NASA Mars Trek (JPL) | Web portal for current and future Mars missions: many data layers over one map | A layer catalogue with plain-language descriptions; measurement and profile tools |
| Where is Perseverance? (JPL) | 2D map: rover position, drawn route, stops labelled by sol, toggleable layers, refreshed after each drive | Route with labelled stops (sol / time), a "you are here" marker, layer toggles |
| Explore with Perseverance (JPL) | 3D scene with a ground-level view, points of interest, simplified from the science team's software | Ground-level (first-person) camera, points of interest |
| NASA lunar traverse planning (Kring et al.) | Dijkstra + Monte Carlo on 5 m LOLA terrain, minimises workload, slopes < 20 degrees, boulders avoided, line of sight to the lander, return to start within 2 km, pace from Apollo records | Return-trip constraint, range from shelter, line-of-sight layer, comparing many route options |
| Perseverance "Mars Global Localization" | No GPS on Mars: the rover matches its camera images to an orbital map in about 2 minutes, to about 25 cm; before that, dead reckoning drifted by up to about 35 m | Our tracker takes a position from one entry point, so a drifting estimate can be corrected against the map |
| Gaia GPS / CalTopo | Slope-angle shading (steeper = darker), used on a phone for off-trail course corrections; CalTopo free on desktop | Slope shading is already ours; add offline use and a "next turn" read-out (done) |

## 2. Ideas, ranked by value for a survival map

1. **Return-to-shelter planning** (idea, from the lunar tool). Mark a base or shelter, show the radius a person can walk and still get back on the energy and oxygen they carry. Needs consumables as a stated assumption.
2. **Time budget on the route** (idea). Combine the sun planner with the route: warn when the walk ends after sunset or when the air is below the cold limit. Data already exists (sun geometry, MEDA temperature).
3. **Line-of-sight / radio layer** (from the lunar tool). Which cells can see the base antenna. Computable from the DTM, no new data.
4. **Shadow and shelter layer** (idea). Cast shadows from the DTM at a chosen hour, for cold and thermal planning.
5. **Several sites**, searchable (see section 3).
6. **Compare two routes** side by side (lunar tool compares many options).
7. **Ground-level 3D camera** along the route (Perseverance 3D tool).
8. **Share and print**: a link that restores the plan; a one-page printable route card.
9. **Offline use**: the site is static and vendored, so a service worker can make the map work with no network.
10. **Confidence layer**: show where the DTM is poor (USGS Mars 2020 TRN DTM has one).

## 3. More than one site

Today the search box finds places inside Jezero only. We can do more:

- a `web/data/sites/index.json` listing sites (name, centre, bounds, status) and one folder per site with the same files `build_jezero.py` writes;
- the search box and a site picker switch between them;
- a new build script takes the DTM URL and the window as arguments, so a site is one command.

Candidate sites (to verify before use, each needs an openly downloadable HiRISE DTM and a documented source entry): other landing-site candidates and well-studied areas such as Gale crater, Oxia Planum, Mawrth Vallis. Rule stays: no site is added until its DTM link has been opened and checked.

Open question for the team: which two or three sites matter for the Space Apps story?

## 4. Position tracking (built)

Mars has no GPS, so the tracker is honest about it: a simulated walker follows the planned route at the model's pace, with a heading pointer, the route wiped behind it, turn-by-turn text, distance left, arrival time and energy used, in 2D and 3D. "Correct my position" re-plans from where the person really is. A real position source (dead reckoning, or image-to-map matching like Perseverance) can later feed the single function `setNavTime` / position entry.

## Sources

- NASA JPL, Mars Trek: https://www.jpl.nasa.gov/news/new-online-exploring-tools-bring-nasas-journey-to-mars-to-new-generation/
- NASA JPL, Explore with Perseverance and Where is Perseverance?: https://www.jpl.nasa.gov/news/take-a-3d-spin-on-mars-and-track-nasas-perseverance-rover/
- Space.com, Perseverance Mars Global Localization: https://www.space.com/space-exploration/mars-rovers/nasas-perseverance-rover-now-has-its-own-gps-on-mars-weve-given-the-rover-a-new-ability
- Phys.org, lunar astronauts' easy trails (traverse planning): https://phys.org/news/2023-10-lunar-astronauts-easy-trails-moon.pdf
- Section Hiker, slope angle shading in Gaia GPS and CalTopo: https://sectionhiker.com/slope-angle-shading-in-gaiagps-and-caltopo/
