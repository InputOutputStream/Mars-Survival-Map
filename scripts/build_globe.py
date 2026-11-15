#!/usr/bin/env python3
"""Builds the REAL planet map from NASA PDS files and scores it.

  python scripts/build_globe.py            # downloads about 9 MB (cached in data/globe/), writes data/grid, web/data

Steps: download MOLA MEGDR topography and the Odyssey epithermal neutron table -> grid layers
-> (data-driven) thresholds for the neutron layer -> score both profiles -> web/data for web/globe.html.
Layers we have no real data for yet are simply absent: the viewer shows the coverage of every cell.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path
import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mars_survival import cli, globe_data, rasterize, thermal
from mars_survival.schema import Grid

BASE_MOLA = "https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg004/"
BASE_TI = "https://pds-geosciences.wustl.edu/mgs/mgs-m-tes-5-timap-v1/mgst_9001/data/"
BASE_GRS = "https://pds-geosciences.wustl.edu/ody/urn-nasa-pds-odyssey_grs_special/data/"
FILES = {"topo": BASE_MOLA + "megt90n000cb.img", "topo_label": BASE_MOLA + "megt90n000cb.lbl",
         "ti": BASE_TI + "global_ti_night_2007.img", "ti_label": BASE_TI + "global_ti_night_2007.lbl",
         "ns": BASE_GRS + "ns_epithermal_020917.tab", "ns_label": BASE_GRS + "ns_epithermal_020917.lbl"}


def get(url: str, dest: Path, tries: int = 6) -> bytes:
    if dest.exists():
        return dest.read_bytes()
    s = requests.Session(); s.headers["User-Agent"] = "mars-survival-map (NASA Space Apps 2026, Red Circle team)"
    for i in range(tries):
        try:
            r = s.get(url, timeout=120); r.raise_for_status()
            if "content-length" in r.headers and len(r.content) != int(r.headers["content-length"]):
                raise IOError(f"truncated: {len(r.content)} of {r.headers['content-length']} bytes")
            dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(r.content); return r.content
        except Exception as e:
            print(f"[attempt {i + 1}/{tries}] {url.rsplit('/', 1)[1]}: {e}"); time.sleep(2 * (i + 1))
    raise SystemExit(f"could not download {url}")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--min-coverage", type=float, default=0.3)
    ap.add_argument("--no-score", action="store_true")
    a = ap.parse_args()
    cache = ROOT / "data" / "globe"
    topo_raw = get(FILES["topo"], cache / "megt90n000cb.img")
    get(FILES["topo_label"], cache / "megt90n000cb.lbl")
    ns_raw = get(FILES["ns"], cache / "ns_epithermal_020917.tab").decode("ascii")
    get(FILES["ns_label"], cache / "ns_epithermal_020917.lbl")
    ti_raw = get(FILES["ti"], cache / "global_ti_night_2007.img")          # 52 MB: slow connections need patience
    get(FILES["ti_label"], cache / "global_ti_night_2007.lbl")

    grid = Grid()
    elev = globe_data.topography_to_grid(topo_raw, grid)
    flux, nzero = globe_data.parse_ns_table(ns_raw)
    print(f"elevation: {np.nanmin(elev):.0f} to {np.nanmax(elev):.0f} m (MOLA says about -8200 to +21200 m at full resolution)")
    print(f"epithermal flux: {np.isfinite(flux).mean():.1%} of cells with data, {nzero} zero-flux rows treated as no data; "
          f"range {np.nanmin(flux):.3f} to {np.nanmax(flux):.3f} counts/s")
    ti, ti_bad = globe_data.thermal_inertia_to_grid(ti_raw)
    print(f"thermal inertia: {np.isfinite(ti).mean():.1%} of cells with data, {ti_bad:.1%} of pixels outside 5..5000 treated as no data; "
          f"median {np.nanmedian(ti):.0f} tiu, 5th-95th percentile {np.nanpercentile(ti, 5):.0f}-{np.nanpercentile(ti, 95):.0f}")
    if not 50 < np.nanmedian(ti) < 800:
        print("WARNING: the median thermal inertia is far from the usual few hundred tiu: check the file's scaling before trusting this layer")
    temp = thermal.mean_surface_temperature(grid.lats())[:, None] * np.ones(grid.shape)      # PHYSICS MODEL (latitude only), not a measurement
    j = (int((90 - 18.44) / 0.5), int((77.45 + 180) / 0.5))
    print(f"temp_mean_k (energy-balance model, upper estimate, about +-10 K): {np.nanmin(temp):.0f} to {np.nanmax(temp):.0f} K; at Jezero {temp[j]:.1f} K (MEDA air mean 221.7 K)")
    rasterize.save_layers({"elevation_m": elev, "epithermal_cps": flux, "temp_mean_k": temp, "thermal_inertia_tiu": ti}, ROOT / "data" / "grid", grid)

    # Data-driven thresholds for the neutron layer (team choice: 5th to 95th percentile of the real values).
    lo, hi = (float(x) for x in np.nanpercentile(flux, [5, 95]))
    cfg_path = ROOT / "config" / "scoring.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    cfg.setdefault("layers", {})["epithermal_cps"] = {"lo": round(lo, 3), "hi": round(hi, 3)}
    cfg_path.write_text(json.dumps(cfg, indent=2))
    print(f"scoring thresholds for epithermal_cps: lo {lo:.3f} (score 1, most hydrogen) hi {hi:.3f} (score 0) -> {cfg_path}")

    sha = lambda b: hashlib.sha256(b).hexdigest()
    (ROOT / "data" / "grid" / "sources.json").write_text(json.dumps({"layers": [
        {"key": "elevation_m", "name": "MGS MOLA MEGDR topography, 4 pixel/degree", "url": FILES["topo"], "label": FILES["topo_label"],
         "sha256": sha(topo_raw), "taken": "megt90n000cb.img: elevation in metres above the GMM3 areoid, block-averaged 2 x 2 to 0.5 degree",
         "status": "NASA data"},
        {"key": "thermal_inertia_tiu", "name": "MGS TES thermal inertia, night map (Putzig & Mellon 2007)", "url": FILES["ti"], "label": FILES["ti_label"],
         "sha256": sha(ti_raw), "taken": "global_ti_night_2007.img: 16-bit integers, 20 pixel/degree, J m-2 K-1 s-1/2; values outside 5..5000 treated as no data; mean of valid pixels per 0.5 degree cell",
         "status": "NASA data (PDS). Scoring ramp 100 to 300 tiu is a team assumption"},
        {"key": "temp_mean_k", "name": "Annual mean surface temperature from an energy balance (Red Circle model)", "url": "https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html",
         "taken": "solar irradiance 586.2 W/m2, Bond albedo 0.250, eccentricity 0.0935, obliquity 25.19 deg (NASA Mars Fact Sheet); see src/mars_survival/thermal.py",
         "status": "Physics model, latitude only, an upper estimate with errors of about 10 K; not a measurement"},
        {"key": "pressure_pa, radiation_msv_day", "name": "Derived from elevation (not measured)", "url": "",
         "taken": "P = 610 Pa x exp(-h / 11.1 km); dose = 0.67 mSv/day x (P / 850 Pa)^-0.25 anchored on one MSL RAD value (Gale crater)",
         "status": "Physics model, exponent is a team hypothesis"},
        {"key": "epithermal_cps", "name": "Odyssey GRS ns_epithermal_020917 (Feldman et al. 2002)", "url": FILES["ns"], "label": FILES["ns_label"],
         "sha256": sha(ns_raw.encode()), "taken": "epithermal neutron flux, counts/s, 0.5 degree cells, first 25.7 days of mapping; zero rows treated as no data",
         "status": "NASA data; relative hydrogen proxy, not calibrated to water-equivalent hydrogen; seasonal CO2 frost mixes in at high latitude"}]}, indent=1))

    if not a.no_score:
        cli.run_score(ROOT, synthetic=False, min_coverage=a.min_coverage)


if __name__ == "__main__":
    main()
