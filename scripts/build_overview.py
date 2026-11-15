"""Build the overview level: coarse hillshade of the whole Jezero region + the list of detail windows.

    python scripts/build_overview.py                 # downloads the 87 MB CTX DEM once into data/overview/
    python scripts/build_overview.py --sites-only    # only refresh web/data/sites.json after adding a detail window

Writes web/data/overview/{hillshade.png, overview.json} and web/data/sites.json. Run from the repository root."""
import argparse, json, sys
from pathlib import Path

import numpy as np
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mars_survival.overview import CTX_URL, block_mean, geo_bounds, hillshade, metres_per_px, scan_sites  # noqa: E402


def download(url: str, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(12):
        have = dst.stat().st_size if dst.exists() else 0
        r = requests.get(url, headers={"Range": f"bytes={have}-"} if have else {}, stream=True, timeout=60)
        if r.status_code == 416:
            return                                           # already complete
        if r.status_code == 200 and have:
            have = 0                                         # server ignored Range: start over
        elif r.status_code not in (200, 206):
            raise SystemExit(f"HTTP {r.status_code} for {url}")
        try:
            with open(dst, "wb" if have == 0 else "ab") as f:
                for c in r.iter_content(1 << 20):
                    f.write(c)
            return
        except requests.exceptions.RequestException as e:
            print("transfer cut, resuming:", e)
    raise SystemExit("download kept failing")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=CTX_URL); ap.add_argument("--raw", default=str(ROOT / "data/overview/ctx_dem_20m.tif"))
    ap.add_argument("--max-dim", type=int, default=1400); ap.add_argument("--out", default=str(ROOT / "web/data/overview"))
    ap.add_argument("--sites-only", action="store_true")
    a = ap.parse_args(); web_data = ROOT / "web/data"
    if not a.sites_only:
        import rasterio
        raw = Path(a.raw)
        if not raw.exists():
            print("downloading", a.url); download(a.url, raw)
        with rasterio.open(raw) as ds:
            z = ds.read(1).astype("float64"); nd = ds.nodata; (la0, la1, lo0, lo1), bsrc = geo_bounds(tuple(ds.bounds), ds.crs); print("extent", la0, la1, lo0, lo1, "from", bsrc)
        if nd is not None: z[z == nd] = np.nan
        z[np.abs(z) > 1e5] = np.nan
        f = max(1, int(np.ceil(max(z.shape) / a.max_dim))); zz = block_mean(z, f)
        px, py = metres_per_px(la0, la1, lo0, lo1, zz.shape[1], zz.shape[0])
        hs = hillshade(zz, px, py)
        lo, hi = np.nanpercentile(zz, [2, 98]); t = np.clip((zz - lo) / (hi - lo), 0, 1)[..., None]
        tint = (1 - t) * np.array([150, 105, 85]) + t * np.array([235, 200, 170])      # low = dark rust, high = pale
        rgb = np.where(np.isfinite(hs)[..., None], tint * (.35 + .65 * hs[..., None]), 200).clip(0, 255).astype("uint8")
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True); Image.fromarray(rgb).save(out / "hillshade.png", optimize=True)
        meta = {"lat_min": la0, "lat_max": la1, "lon_min": lo0, "lon_max": lo1, "extent_source": bsrc, "width": zz.shape[1], "height": zz.shape[0],
                "px_x_m": px, "px_y_m": py, "native_px_m": 20, "downsample": f, "zmin": float(np.nanmin(zz)), "zmax": float(np.nanmax(zz)),
                "source": {"name": "Mars 2020 Science Investigation CTX DEM Mosaic (USGS Astrogeology, Calef 2021)", "url": a.url,
                           "page": "https://astrogeology.usgs.gov/search/map/mars_2020_science_investigation_ctx_dem_mosaic", "licence": "public domain, please cite authors"}}
        (out / "overview.json").write_text(json.dumps(meta, indent=1), encoding="utf-8"); print("overview:", zz.shape, f"{px:.0f} m/px")
    sites = scan_sites(web_data); (web_data / "sites.json").write_text(json.dumps(sites, indent=1), encoding="utf-8")
    print(len(sites), "detail window(s) listed in web/data/sites.json")


if __name__ == "__main__":
    main()
