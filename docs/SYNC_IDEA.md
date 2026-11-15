# Idea: two people find each other after a dust storm

Status: idea, refined with sources. Not built (it cannot be tested without two real devices and real orbiter data).

## The problem
After a dust storm, visibility is poor, cameras and sun sensors degrade, and two people (or a person and a shelter) may have lost track of each other. What can restore a shared position?

## What is known (sources at the end)
1. **Mars has no GPS.** Perseverance localises by matching camera images to an orbital map (Mars Global Localization, about 25 cm in about 2 minutes). Before that, dead reckoning drifted by up to about 35 m. Dust blocks cameras, so the image method degrades in a storm.
2. **Radio keeps working in dust** better than optics. Orbiters already relay surface radio today (Electra UHF payload).
3. **NASA has studied a Mars navigation constellation** (MRNSS): relay orbiters broadcast GPS-like ranging signals; **differencing two ranges to the same orbiter cancels shared errors**, and the study reports relative positioning 200 to 400 times better than absolute positioning in simulation. So two people near each other could know their relative position well even if their absolute position is poor. That is exactly the "find each other" case.
4. **Orbiters pass over a site only in short windows** a few times per sol. Real pass times need real ephemerides, so any pass prediction must be labelled and sourced before it is shown.

## Options, from simplest to most ambitious
| Level | What it does | Needs | Honest limit |
|---|---|---|---|
| 0 Share a code (offline) | Each phone shows a short text code with site, position estimate, time and its uncertainty; the other person types it in. The app shows the line between them and a meet-up point. | Nothing new. | Position comes from the estimate, which may be the problem. |
| 1 Meet halfway | One-to-all least-energy fields from both people; the meeting cell minimises the longer of the two walks. | Already in the app (`costField`). | Assumes both positions are known. |
| 2 Beacon and range | A shelter or lander beacon gives each person a range; two ranges plus terrain narrow the position. | Hardware assumption. | Needs a beacon. |
| 3 Orbiter-aided relative position | Both users range to the same orbiter pass and compare. | A relay constellation like MRNSS, which does not exist yet. | Concept study only. |

## Suggested next step
Build level 0 and 1 (no new data, no new hardware, can be tested now), and describe level 3 as the research direction in the project write-up, citing the NASA study. Ask the team which scenario to demonstrate.

## Sources
- NASA NTRS 20210008406, MRNSS: https://ntrs.nasa.gov/citations/20210008406
- Space.com, Perseverance Mars Global Localization: https://www.space.com/space-exploration/mars-rovers/nasas-perseverance-rover-now-has-its-own-gps-on-mars-weve-given-the-rover-a-new-ability
- Electra radio (UHF relay payload): https://en.wikipedia.org/wiki/Electra_(radio)
