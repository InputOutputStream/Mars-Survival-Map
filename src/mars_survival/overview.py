"""Overview level of the two-level map: a coarse DEM of the whole Jezero region plus the list of 1 m detail windows.

Source of the coarse level (open, no login): USGS Astrogeology, "Mars 2020 Science Investigation CTX DEM Mosaic",
20 m/px GeoTIFF covering the whole crater, public domain (cite Calef, USGS, 2021). See web/sources.json (A16).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

MARS_R_M = 3_396_190.0
CTX_URL = "https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif"


DOC_BOUNDS = (17.58, 19.29, 76.99, 78.58)           # lat_min, lat_max, lon_min, lon_max as published on the USGS product page


def _param(wkt: str, *names: str):
    import re
    for n in names:
        m = re.search(r'(?i)%s["\']?\s*,\s*(-?[0-9.]+)' % re.escape(n), wkt)
        if m:
            return float(m.group(1))
    return None


def geo_bounds(bounds, crs=None, radius: float = MARS_R_M) -> tuple[tuple[float, float, float, float], str]:
    """(lat_min, lat_max, lon_min, lon_max), source. The CTX GeoTIFF is equirectangular in METRES, so its bounds are not degrees:
    convert with the projection's centre meridian and standard parallel, and fall back to the published extent if the CRS cannot be read
    or the result is more than 0.5 degree away from it."""
    left, bottom, right, top = bounds
    if max(abs(left), abs(right), abs(top), abs(bottom)) <= 360:
        return (bottom, top, left, right), "raster (degrees)"
    wkt = ""
    try:
        wkt = crs.to_wkt() if crs is not None else ""
    except Exception:
        pass
    lon0 = _param(wkt, "central_meridian", "Longitude of natural origin", "longitude_of_center", "Longitude of false origin")
    lat_ts = _param(wkt, "standard_parallel_1", "Latitude of 1st standard parallel", "Latitude of natural origin", "latitude_of_origin")
    if lon0 is not None:
        k = radius * np.cos(np.deg2rad(lat_ts or 0.0))
        got = (np.rad2deg(bottom / radius), np.rad2deg(top / radius), lon0 + np.rad2deg(left / k), lon0 + np.rad2deg(right / k))
        if all(abs(a - b) < 0.5 for a, b in zip(got, DOC_BOUNDS)):
            return got, f"CRS (lon0 {lon0}, lat_ts {lat_ts or 0})"
    return DOC_BOUNDS, "published extent (CRS not readable here)"


def block_mean(a: np.ndarray, f: int) -> np.ndarray:
    """Average f x f blocks, ignoring NaN (nodata)."""
    if f <= 1:
        return a
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    b = a[:h, :w].reshape(h // f, f, w // f, f)
    ok = np.isfinite(b)
    n = ok.sum(axis=(1, 3))
    with np.errstate(all="ignore"):
        return np.where(n > 0, np.where(ok, b, 0.0).sum(axis=(1, 3)) / n, np.nan)


def metres_per_px(lat0: float, lat1: float, lon0: float, lon1: float, w: int, h: int) -> tuple[float, float]:
    """(x, y) pixel size in metres for an equirectangular raster (x shrinks with cos(latitude))."""
    mid = np.deg2rad((lat0 + lat1) / 2)
    return (np.deg2rad(lon1 - lon0) * MARS_R_M * np.cos(mid) / w, np.deg2rad(lat1 - lat0) * MARS_R_M / h)


def hillshade(z: np.ndarray, px: float, py: float, az: float = 315.0, alt: float = 45.0) -> np.ndarray:
    """0..1 shading, north-up raster, light from `az` (compass degrees)."""
    zf = np.where(np.isfinite(z), z, np.nanmean(z))
    gy, gx = np.gradient(zf, py, px)                      # rows grow southwards
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)                          # compass-style: 0 = faces north
    a, e = np.deg2rad(az), np.deg2rad(alt)
    return np.clip(np.sin(e) * np.cos(slope) + np.cos(e) * np.sin(slope) * np.cos(a - aspect), 0, 1)


def site_entry(folder: Path, sid: str, href: str) -> dict | None:
    f = folder / "site.json"
    if not f.exists():
        return None
    m = json.loads(f.read_text(encoding="utf-8"))
    px = float(m["px_m"])
    return {"id": sid, "name": m.get("name") or sid, "href": href, "center_lat": m["center_lat"], "center_lon": m["center_lon"],
            "width_m": m["width"] * px, "height_m": m["height"] * px, "px_m": px, "synthetic": bool(m.get("synthetic"))}


def scan_sites(web_data: Path) -> list[dict]:
    """web/data/site/ is the default window ('jezero'); web/data/sites/<id>/ are extra ones, opened with index.html?site=<id>."""
    out = []
    e = site_entry(web_data / "site", "jezero", "index.html")
    if e:
        out.append(e)
    for d in sorted((web_data / "sites").glob("*/")) if (web_data / "sites").exists() else []:
        e = site_entry(d, d.name, f"index.html?site={d.name}")
        if e:
            out.append(e)
    return out
