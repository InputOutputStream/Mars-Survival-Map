"""
cli.py - entry point: python -m mars_survival <command>   (or `mars-survival <command>`)

  demo        full chain on synthetic data (no network)
  scrape      data collection (see `scrape --help`)
  rasterize   rasters in data/files -> grid layers in data/grid (per config/layers.json)
  score       compute scores + exports (PNG, GeoTIFF, CSV, web manifest)
  sensitivity which weight assumptions change the ranking the most?
  site-demo   analysis of a site ("city" ~4 km) on SYNTHETIC terrain: slope, hazard, routes, EVA
  site        same on a real local DEM (--dem file.tif|.asc|.npy|.png --px-m 5)
  serve       serves the web viewers: / (globe) and / (site scale)
"""
from __future__ import annotations

import argparse
import functools
import json
import http.server
import socketserver
from pathlib import Path

import numpy as np

from . import eva, export, rasterize, scraper
from . import site as sitemod
from .demo import synthetic_layers
from .schema import (LAYERS, PROFILES, Grid, apply_overrides, compute, derive_from_elevation, init_db,
                     weight_sensitivity)

PROFILE_LABELS = {"habitat": "habitat (long-term settlement)", "landing": "landing"}


def load_scoring(root: Path, path: str | None):
    """Scoring layers, with optional overrides (config/scoring.json if it exists, or --scoring)."""
    cfg_path = Path(path) if path else root / "config" / "scoring.json"
    if cfg_path.exists():
        print(f"Scoring: overrides read from {cfg_path}")
        return apply_overrides(json.loads(cfg_path.read_text(encoding="utf-8")))
    if path:
        raise SystemExit(f"scoring file not found: {path}")
    return LAYERS


def run_score(root: Path, profiles=PROFILES, n_sites: int = 25, min_sep: float = 8.0,
              db_path: str | None = None, synthetic: bool = False, scoring: str | None = None,
              min_coverage: float = 0.5) -> None:
    layers = load_scoring(root, scoring)
    grid, data = rasterize.load_layers(root / "data" / "grid")
    if "elevation_m" in data:
        for k, v in derive_from_elevation(data["elevation_m"]).items():
            data.setdefault(k, v)  # never overwrites a real measurement
    web, out = root / "web" / "data", root / "data" / "out"
    overlays, sites_files, layer_scores = [], {}, {}
    results = {}
    for prof in profiles:
        try:
            r = compute(data, prof, layers=layers, min_coverage=min_coverage)
        except ValueError as e:
            print(f"[{prof}] skipped: {e}")
            continue
        results[prof] = r
        out.mkdir(parents=True, exist_ok=True)
        np.save(out / f"score_{prof}.npy", r["score"])
        export.save_png(r["score"], web / f"score_{prof}.png", r["excluded"])
        export.save_geotiff(r["score"], out / f"score_{prof}.tif", grid)
        sites = export.top_sites(r["score"], r["limiting_idx"], r["limiting_keys"], r["coverage"], grid,
                                 n=n_sites, min_sep_deg=min_sep)
        export.write_sites(sites, out / f"sites_{prof}.csv", web / f"sites_{prof}.json")
        sites_files[prof] = f"data/sites_{prof}.json"
        overlays.append({"id": f"score_{prof}", "label": f"Score - {PROFILE_LABELS[prof]}",
                         "png": f"data/score_{prof}.png", "profile": prof})
        layer_scores.update(r["layer_scores"])
        best = sites[0] if sites else None
        print(f"[{prof}] excluded {r['excluded'].mean():.0%} | best site: "
              + (f"lat {best['lat']}, lon {best['lon']}, score {best['score']}, limiting {best['limiting_layer']}"
                 if best else "none"))
    labels = {L.key: L.label for L in layers}
    for key, arr in layer_scores.items():
        export.save_png(arr, web / "layers" / f"{key}.png")
        overlays.append({"id": key, "label": f"Layer - {labels.get(key, key)}", "png": f"data/layers/{key}.png"})
    bins = web / "bins"
    for key in layer_scores:                                   # click-to-inspect: scores + raw values
        export.save_u8(layer_scores[key], bins / f"score_{key}.u8")
        export.save_f32(data[key], bins / f"raw_{key}.f32")
    prof_meta = {}
    for prof, r in results.items():
        export.save_u8(r["score"], bins / f"total_{prof}.u8")
        export.save_u8(r["coverage"], bins / f"cov_{prof}.u8")
        export.save_u8(r["excluded"].astype(float), bins / f"excl_{prof}.u8")
        r["limiting_idx"].astype(np.uint8).tofile(bins / f"lim_{prof}.u8")
        prof_meta[prof] = {"label": PROFILE_LABELS[prof], "keys": r["limiting_keys"]}
    extra = {"layers": [L.describe() for L in layers if L.key in layer_scores], "profiles": prof_meta}
    src_file = root / "data" / "grid" / "sources.json"       # written by scripts/build_globe.py
    if src_file.exists():
        extra["sources"] = json.loads(src_file.read_text(encoding="utf-8"))
    export.write_manifest(web, overlays, sites_files, grid, synthetic, extra)
    if db_path:
        db = init_db(db_path, grid)
        la, lo, ar = grid.lats(), grid.lons(), grid.cell_area_m2()
        h, w = grid.shape
        db.executemany("INSERT OR REPLACE INTO cell VALUES(?,?,?,?,?)",
                       ((r, c, float(la[r]), float(lo[c]), float(ar[r, c])) for r in range(h) for c in range(w)))
        for prof, r in results.items():
            db.executemany(
                "INSERT OR REPLACE INTO cell_score(row,col,profile,score,coverage,excluded,limiting_layer) VALUES(?,?,?,?,?,?,?)",
                ((i, j, prof, float(r["score"][i, j]), float(r["coverage"][i, j]), int(r["excluded"][i, j]),
                  r["limiting_keys"][int(r["limiting_idx"][i, j])])
                 for i, j in zip(*np.where(np.isfinite(r["score"])))))
        db.commit()
        print(f"SQLite written: {db_path}")
    print(f"Viewer: python -m mars_survival serve  ->  http://localhost:8000")


def run_site(root: Path, st: "sitemod.Site", routes_xy: list[tuple[float, float, float, float]] | None = None,
             temp_mean_k: float = 215.0, temp_diurnal_k: float = 80.0, out: Path | None = None) -> None:
    """Full analysis of a site + exports to web/data/site (or `out`)."""
    params = sitemod.TraverseParams()
    res = sitemod.analyse(st, params)
    h, w = st.shape
    flats = sitemod.find_flat_sites(res["slope"], res["rough"], st.px_m, radius_m=max(60.0, 8 * st.px_m), n=5,
                                  max_bad_frac=0.05)   # team assumption: 5% of the disc may exceed the limits
    for f in flats:
        f["latlon"] = sitemod.local_to_latlon(st, f["row"], f["col"])
    pairs = [((int(y / st.px_m), int(x / st.px_m)), (int(y2 / st.px_m), int(x2 / st.px_m)))
             for x, y, x2, y2 in (routes_xy or [])]
    if not pairs and len(flats) >= 2:   # by default: the two flat sites farthest apart (non-trivial route)
        a, b = max(((p, q) for i, p in enumerate(flats) for q in flats[i + 1:]),
                   key=lambda pq: (pq[0]["row"] - pq[1]["row"]) ** 2 + (pq[0]["col"] - pq[1]["col"]) ** 2)
        pairs = [((a["row"], a["col"]), (b["row"], b["col"]))]
    elif not pairs:
        pairs = [((int(h * .1), int(w * .1)), (int(h * .9), int(w * .9)))]
    from dataclasses import asdict
    from . import traverse
    walker = traverse.Walker()
    tmult = traverse.terrain_multiplier(res["rough"], walker)
    routes = []
    for i, (a, b) in enumerate(pairs, 1):
        r = traverse.find_route_energy(st.dem, tmult, st.px_m, a, b, walker)
        if r is not None:
            legacy = sitemod.route_stats(st.dem, tmult, st.px_m, r["path"])
            legacy.pop("time_h", None); legacy.pop("length_m", None)
            r.update(legacy)
        if r is None:
            print(f"[route {i}] NO passable route between {a} and {b}")
            continue
        r["name"] = f"route-{i}"
        routes.append(r)
        print(f"[route {i}] {r['length_m']/1000:.2f} km (straight line {r['straight_m']/1000:.2f} km), "
              f"max slope {r['max_slope_deg']:.1f}°, ascent {r['ascent_m']:.0f} m, energy {r['energy_kwh']:.2f} kWh, "
              f"duration {r['time_h']:.1f} h (energy model, see traverse.py)")
    plans = eva.seasonal_plans(st.center_lat, temp_mean_k, temp_diurnal_k) if st.center_lat is not None else None
    dest = out or root / "web" / "data" / "site"
    sitemod.export_site(st, res, dest, params, routes, flats, {"plans": plans} if plans else None,
                        walker=asdict(walker), tmult=tmult)
    hz = np.bincount(res["hazard"].ravel(), minlength=4) / res["hazard"].size
    print(f"[site] {w}x{h} px of {st.px_m:g} m ({w*st.px_m/1000:.1f}x{h*st.px_m/1000:.1f} km) | "
          + " ".join(f"{n}: {v:.0%}" for n, v in zip(sitemod.HAZARD_LABELS, hz)) + f" | flat sites: {len(flats)}")
    print(f"Files: {dest}  (heightmap16.png + optional OBJ)  ->  http://localhost:8000/")


def _xy4(txt: str) -> tuple[float, float, float, float]:
    v = [float(t) for t in txt.split(",")]
    if len(v) != 4:
        raise argparse.ArgumentTypeError("expected format: x1,y1,x2,y2 (meters, x=east, y=south from the north-west corner)")
    return tuple(v)  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="mars-survival", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="repository root (default: current directory)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo")
    d.add_argument("--res", type=float, default=1.0)
    sub.add_parser("scrape", add_help=False)
    r = sub.add_parser("rasterize")
    r.add_argument("--config", default="config/layers.json")
    s = sub.add_parser("score")
    s.add_argument("--profile", choices=PROFILES, action="append")
    s.add_argument("--sites", type=int, default=25)
    s.add_argument("--min-sep", type=float, default=8.0, help="minimum separation between sites (degrees)")
    s.add_argument("--min-coverage", type=float, default=0.5, help="a cell is scored only if the layers present carry at least this share of the total weight (real data is partial: 0.3 is typical)")
    s.add_argument("--db", help="path of a SQLite database to fill")
    s.add_argument("--scoring", help="JSON overriding thresholds/weights (default: config/scoring.json if it exists)")
    sn = sub.add_parser("sensitivity", help="which weight assumptions drive the ranking?")
    sn.add_argument("--profile", choices=PROFILES, default="habitat")
    sn.add_argument("--top", type=float, default=0.02, help="fraction of the best cells compared")
    sn.add_argument("--scoring")
    sd = sub.add_parser("site-demo")
    sd.add_argument("--size", type=int, default=320)
    sd.add_argument("--px-m", type=float, default=12.0)
    sd.add_argument("--seed", type=int, default=1)
    sd.add_argument("--route", type=_xy4, action="append", help="x1,y1,x2,y2 in meters from the NW corner")
    st_ = sub.add_parser("site")
    st_.add_argument("--dem", required=True, help="local DEM: .tif .asc .npy .png (16-bit)")
    st_.add_argument("--px-m", type=float, help="pixel size (m) if not readable from the file")
    st_.add_argument("--zmin", type=float); st_.add_argument("--zmax", type=float)
    st_.add_argument("--nodata", type=float)
    st_.add_argument("--name", default="site")
    st_.add_argument("--lat", type=float, help="latitude of the center (used for EVA and coordinates)")
    st_.add_argument("--lon", type=float)
    st_.add_argument("--route", type=_xy4, action="append")
    st_.add_argument("--tmean", type=float, default=215.0, help="mean temperature (K) for the EVA model")
    st_.add_argument("--tdiurnal", type=float, default=80.0, help="day/night max-min range (K)")
    sv = sub.add_parser("serve")
    sv.add_argument("--port", type=int, default=8000)
    a, rest = ap.parse_known_args(argv)
    root = Path(a.root).resolve()

    if a.cmd == "scrape":
        scraper.main(rest)
        return
    if rest:
        ap.error(f"unknown arguments: {rest}")
    if a.cmd == "demo":
        grid = Grid(res_deg=a.res)
        rasterize.save_layers(synthetic_layers(grid), root / "data" / "grid", grid)
        print("SYNTHETIC layers generated in data/grid (do not interpret scientifically).")
        run_score(root, synthetic=True)
    elif a.cmd == "rasterize":
        rasterize.ingest(root / a.config, root)
    elif a.cmd == "score":
        run_score(root, tuple(a.profile or PROFILES), a.sites, a.min_sep, a.db, scoring=a.scoring, min_coverage=a.min_coverage)
    elif a.cmd == "sensitivity":
        layers = load_scoring(root, a.scoring)
        grid, data = rasterize.load_layers(root / "data" / "grid")
        if "elevation_m" in data:
            for k, v in derive_from_elevation(data["elevation_m"]).items():
                data.setdefault(k, v)
        rows = weight_sensitivity(data, a.profile, layers, a.top)
        print(f"Profile {a.profile} — stability of the top {a.top:.0%} if the layer weight is ×0.5 / ×2 (1.00 = unchanged)")
        for r in rows:
            print(f"  {r['layer']:24s} weight {r['weight']:<4g} mean Jaccard {r['jaccard_mean']:.2f}  min {r['jaccard_min']:.2f}")
        out = root / "data" / "out"; out.mkdir(parents=True, exist_ok=True)
        (out / f"sensitivity_{a.profile}.json").write_text(json.dumps(rows, indent=1))
    elif a.cmd == "site-demo":
        run_site(root, sitemod.synthetic_site(a.size, a.px_m, a.seed), a.route)
        print("SYNTHETIC terrain: no scientific value.")
    elif a.cmd == "site":
        if not Path(a.dem).exists():
            ap.error(f"DEM not found: {a.dem}")
        dem, px = sitemod.load_dem(a.dem, a.px_m, a.zmin, a.zmax, a.nodata)
        if not px:
            ap.error("--px-m is required (pixel size in meters): cannot be inferred from this file")
        st = sitemod.Site(dem, px, a.name, a.lat, a.lon)
        run_site(root, st, a.route, a.tmean, a.tdiurnal)
    elif a.cmd == "serve":
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root / "web"))
        with socketserver.TCPServer(("", a.port), handler) as httpd:
            print(f"http://localhost:{a.port}  (Ctrl+C to stop)")
            httpd.serve_forever()
