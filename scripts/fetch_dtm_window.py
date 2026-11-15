#!/usr/bin/env python3
"""Lit une fenêtre d'un MNT HiRISE distant (HTTP Range) et l'enregistre en .npy + .json de provenance.

  python scripts/fetch_dtm_window.py URL --inspect                       # affiche l'étiquette PDS3 (à nous envoyer si erreur)
  python scripts/fetch_dtm_window.py URL --lat 18.44 --lon 77.45 --size-m 6000 --out data/jezero
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mars_survival import pds3

ap = argparse.ArgumentParser()
ap.add_argument("url"); ap.add_argument("--inspect", action="store_true")
ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
ap.add_argument("--size-m", type=float, default=6000.0); ap.add_argument("--out", default="data/site")
a = ap.parse_args()
if a.inspect:
    import requests
    h = pds3._get(requests.Session(), a.url, 0, 65535, exact=False).decode("ascii", "replace")
    print(h.split("\nEND\n")[0][:30000]); sys.exit()
r = pds3.open_remote(a.url)
print(f"raster {r.lines}x{r.samples}, {r.px_m} m/px, centre projection {r.center_lat},{r.center_lon}")
c0 = r.pixel_to_lonlat(0, 0); c1 = r.pixel_to_lonlat(r.lines, r.samples)
print(f"coins estimés : haut-gauche lat {c0[0]:.4f} lon {c0[1]:.4f} ; bas-droite lat {c1[0]:.4f} lon {c1[1]:.4f}")
if a.lat is None:
    a.lat, a.lon = r.pixel_to_lonlat(r.lines / 2, r.samples / 2); print(f"centre du raster utilisé : {a.lat:.4f}, {a.lon:.4f}")
row, col = r.lonlat_to_pixel(a.lat, a.lon)
print(f"pixel demandé (ligne, colonne) = ({row:.0f}, {col:.0f}) ; raster = {r.lines} x {r.samples}")
if not (0 <= row < r.lines and 0 <= col < r.samples):
    sys.exit("point demandé hors du raster : choisissez un point dans les coins ci-dessus (ou omettez --lat/--lon)")
half = int(a.size_m / r.px_m / 2)
half = min(half, int(row), int(col), r.lines - int(row), r.samples - int(col))
z = pds3.read_window(r, int(row) - half, int(row) + half, int(col) - half, int(col) + half)
print(f"fenêtre {z.shape}, z = {np.nanmin(z):.1f}..{np.nanmax(z):.1f} m, NaN {np.isnan(z).mean():.1%}")
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
np.save(out / "dem.npy", z.astype(np.float32))
json.dump({"source_url": a.url, "px_m": r.px_m, "center_lat": a.lat, "center_lon": a.lon, "shape": list(z.shape),
           "label_keys": {k: r.label[k] for k in ("MAP_SCALE", "A_AXIS_RADIUS", "MAP_PROJECTION_TYPE") if k in r.label}},
          open(out / "dem.json", "w"), indent=1)
print("écrit", out / "dem.npy")
