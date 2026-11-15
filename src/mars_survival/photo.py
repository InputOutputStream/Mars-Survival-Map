"""Photo level of the detail tiers: crop a window of a HiRISE orthoimage so it overlays a built site exactly.

Elevation is never finer than the 1 m HiRISE DTM. The orthoimage is a PHOTOGRAPH (up to 0.25 m/px): it is shown as a layer to see boulders
and texture, and is not used for slope, routes or hazard classes.
"""
from __future__ import annotations

import numpy as np

from .overview import MARS_R_M, _param


def spheroid_radius(crs_wkt: str, default: float = MARS_R_M) -> float:
    """Sphere radius written in the image's own CRS (the HiRISE orthoimage of Jezero says 3 394 839.8 m, not the IAU 3 396 190 m:
    using the wrong one shifts the photo by about 430 m northwards). Falls back to the IAU value if the CRS has none."""
    import re
    m = re.search(r'SPHEROID\["[^"]*",\s*([0-9.]+)', crs_wkt or "")
    return float(m.group(1)) if m else default


def lonlat_to_xy(lat: float, lon: float, crs_wkt: str, radius: float | None = None) -> tuple[float, float]:
    """Equirectangular projection used by HiRISE products (metres): x = R cos(lat_ts) (lon - lon0), y = R lat.
    R is read from the image's CRS unless given."""
    radius = spheroid_radius(crs_wkt) if radius is None else radius
    lon0 = _param(crs_wkt, "central_meridian", "Longitude of natural origin", "longitude_of_center", "Longitude of false origin")
    lat_ts = _param(crs_wkt, "standard_parallel_1", "Latitude of 1st standard parallel", "Latitude of natural origin", "latitude_of_origin")
    if lon0 is None:
        raise ValueError("cannot read the projection centre meridian from the image's CRS; run with --inspect and send us the output")
    return radius * np.cos(np.deg2rad(lat_ts or 0.0)) * np.deg2rad(lon - lon0), radius * np.deg2rad(lat)


def _read_in_strips(ds, win, out, resampling, rows_per_strip: int = 512, tries: int = 6):
    """Reads the window strip by strip. A JP2 read over HTTP can fail on one block ('opj_decode() failed') because of a dropped or short
    transfer; a strip is retried with a growing pause instead of losing the whole window, and a strip that still fails is reported with its position."""
    import time
    from rasterio.windows import Window
    a = np.zeros(out, dtype="float64"); h_out = out[0]
    for y0 in range(0, h_out, rows_per_strip):
        n = min(rows_per_strip, h_out - y0)
        print(f"  photo: rows {y0}-{y0 + n} of {h_out} ({100 * y0 // h_out}%)", flush=True)
        w = Window(win.col_off, win.row_off + win.height * y0 / h_out, win.width, win.height * n / h_out)
        for k in range(tries):
            try:
                a[y0:y0 + n] = ds.read(1, window=w, out_shape=(n, out[1]), resampling=resampling, boundless=True, fill_value=0)
                break
            except Exception as e:      # rasterio.errors.RasterioIOError and the GDAL errors under it
                if k == tries - 1:
                    raise RuntimeError(f"could not decode rows {y0}-{y0 + n} of the output after {tries} tries ({e}). "
                                       "If it is always the same rows it is the file, not the network (send us the message); if it varies, download the .JP2 once with `curl -C - -O <url>` and pass the local file instead of the URL.") from e
                time.sleep(2 * (k + 1))
    return a


def crop_photo(src, centre_lat: float, centre_lon: float, window_shape_native: tuple[int, int], native_px_m: float,
               extent_m: tuple[float, float], max_px: int = 4096):
    """Returns (uint8 image, effective m/px, (left, bottom, right, top) in the image CRS).
    The site's top-left corner is the DTM window's top-left corner = centre - half the window; its size is extent_m (width, height)."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds
    # STRICT=NO (GDAL >= 3.5, OpenJPEG >= 2.5): the HiRISE JP2 has a codeblock that OpenJPEG rejects in strict mode ('opj_decode() failed',
    # always at the same block, so retrying cannot help). Lenient mode decodes it, at worst leaving a few damaged pixels in that block.
    with rasterio.open(src, STRICT="NO") as ds:
        cx, cy = lonlat_to_xy(centre_lat, centre_lon, ds.crs.to_wkt() if ds.crs else "")
        left = cx - window_shape_native[1] * native_px_m / 2
        top = cy + window_shape_native[0] * native_px_m / 2
        right, bottom = left + extent_m[0], top - extent_m[1]
        b = ds.bounds
        if right < b.left or left > b.right or top < b.bottom or bottom > b.top:
            raise ValueError("the site window is outside this image: check the image covers it (--inspect shows its bounds)")
        win = from_bounds(left, bottom, right, top, ds.transform)
        f = min(1.0, max_px / max(win.width, win.height))
        out = (max(1, round(win.height * f)), max(1, round(win.width * f)))
        a = _read_in_strips(ds, win, out, Resampling.average)
        nd = ds.nodata
    ok = a != 0 if nd is None else (a != nd) & (a != 0)
    lo, hi = np.percentile(a[ok], [1, 99]) if ok.any() else (0.0, 1.0)
    img = np.where(ok, np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1) * 255, 0).astype("uint8")
    return img, extent_m[0] / out[1], (left, bottom, right, top)
