"""
export.py - scoring outputs: colorized PNG (web), GeoTIFF (GIS), top sites (CSV/JSON),
manifest for the web viewer.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from .schema import Grid

# Team palette: crimson (hostile) -> ember orange -> sun yellow -> leaf green (favourable)
_STOPS = [(0.0, (161, 22, 47)), (0.25, (236, 122, 44)), (0.5, (240, 191, 43)),
          (0.75, (112, 176, 62)), (1.0, (46, 125, 26))]


def colorize(score: np.ndarray, excluded: np.ndarray | None = None) -> np.ndarray:
    """Score 0..1 -> RGBA image (NaN transparent, excluded cells in dark gray)."""
    s = np.clip(np.nan_to_num(score, nan=0.0), 0, 1)
    xs = [p for p, _ in _STOPS]
    rgba = np.zeros(score.shape + (4,), dtype=np.uint8)
    for c in range(3):
        rgba[..., c] = np.interp(s, xs, [col[c] for _, col in _STOPS])
    rgba[..., 3] = np.where(np.isnan(score), 0, 215)
    if excluded is not None:
        rgba[excluded] = (40, 40, 40, 200)
    return rgba


def save_png(score: np.ndarray, path: Path, excluded: np.ndarray | None = None) -> None:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(colorize(score, excluded), "RGBA").save(path)


def save_geotiff(arr: np.ndarray, path: Path, grid: Grid) -> None:
    try:
        import rasterio
        from rasterio.transform import from_origin
    except ImportError:
        print("[info] rasterio not installed: GeoTIFF skipped")
        return
    from .rasterize import MARS_GEOG_WKT
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w = arr.shape
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=1, dtype="float32",
                       crs=MARS_GEOG_WKT, transform=from_origin(-180, 90, grid.res_deg, grid.res_deg),
                       nodata=np.nan, compress="deflate") as dst:
        dst.write(arr.astype("float32"), 1)


def _angdist_deg(lat1, lon1, lat2, lon2):
    p1, p2 = np.deg2rad(lat1), np.deg2rad(lat2)
    dl = np.deg2rad(lon2 - lon1)
    c = np.sin(p1) * np.sin(p2) + np.cos(p1) * np.cos(p2) * np.cos(dl)
    return np.rad2deg(np.arccos(np.clip(c, -1, 1)))


def top_sites(score, limiting_idx, limiting_keys, coverage, grid: Grid, n: int = 25,
              min_sep_deg: float = 8.0, max_candidates: int = 50_000) -> list[dict]:
    """Best sites, spaced at least min_sep_deg apart (immediate neighbours are suppressed)."""
    lats, lons = grid.lats(), grid.lons()
    flat = np.where(np.isfinite(score), score, -np.inf).ravel()
    order = np.argsort(flat)[::-1][:max_candidates]
    picked: list[dict] = []
    for idx in order:
        if flat[idx] == -np.inf or len(picked) >= n:
            break
        r, c = divmod(int(idx), grid.shape[1])
        lat, lon = float(lats[r]), float(lons[c])
        if picked:
            d = _angdist_deg(lat, lon, np.array([p["lat"] for p in picked]), np.array([p["lon"] for p in picked]))
            if (d < min_sep_deg).any():
                continue
        picked.append({"rank": len(picked) + 1, "lat": round(lat, 3), "lon": round(lon, 3),
                       "score": round(float(score[r, c]), 4), "coverage": round(float(coverage[r, c]), 3),
                       "limiting_layer": limiting_keys[int(limiting_idx[r, c])]})
    return picked


def write_sites(sites: list[dict], csv_path: Path, json_path: Path | None = None) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["rank", "lat", "lon", "score", "coverage", "limiting_layer"])
        w.writeheader()
        w.writerows(sites)
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(sites, indent=1))


def save_u8(arr: np.ndarray, path: Path, lo: float = 0.0, hi: float = 1.0) -> None:
    """Quantize to uint8 (0..254; 255 = NaN) for click-to-inspect in the viewer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    q = np.clip(np.round((np.nan_to_num(arr, nan=lo) - lo) / (hi - lo) * 254), 0, 254).astype(np.uint8)
    q[np.isnan(arr)] = 255
    q.tofile(path)


def save_f32(arr: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.asarray(arr, dtype="<f4").tofile(path)


def write_manifest(web_data: Path, overlays: list[dict], sites: dict[str, str], grid: Grid, synthetic: bool,
                   extra: dict | None = None) -> None:
    web_data.mkdir(parents=True, exist_ok=True)
    h, w = grid.shape
    (web_data / "manifest.json").write_text(json.dumps(
        {"synthetic": synthetic, "res_deg": grid.res_deg, "width": w, "height": h, "overlays": overlays,
         "sites": sites, **(extra or {})}, indent=1, ensure_ascii=False))
