"""
globe_data.py - real global layers for the globe viewer, from NASA PDS files.

Three products, all on the project grid (0.5 degree, row 0 = +90 north, column 0 = -180, east positive):

1. MOLA topography, MGS MEGDR 4 pixel/degree (file megt90n000cb.img, label megt90n000cb.lbl):
   720 lines x 1440 samples, big-endian signed 16-bit integers, metres above the areoid (GMM3 potential model),
   latitude +90 at the top, longitude 0..360 east starting at the left edge. 0.25 deg pixels, so the 0.5 deg grid
   cell is the mean of 2 x 2 pixels (the label gives no missing-data value, and none is assumed).

2. Odyssey GRS "special product" ns_epithermal_020917.tab (Feldman et al. 2002, Science 297:75-78):
   259,200 text rows "lon, lat, flux", one per 0.5 x 0.5 degree cell centre, lon 0..360, flux in counts/second.
   Epithermal neutrons are slowed by hydrogen: LESS flux means MORE hydrogen near the surface (top ~1 m).
   Caveats, stated here so they are never forgotten:
     - it is the first 25.7 days of mapping only (a snapshot, not the full mission);
     - at high latitude in winter, seasonal CO2 frost also changes the flux, so water ice and CO2 frost are mixed up;
     - rows with flux exactly 0.000 are treated as "no data" (our reading: a real flux is never exactly zero).
       The fraction treated this way is reported by the build script so you can check it.
   The flux is NOT converted to water-equivalent hydrogen here: that needs a published calibration which we have
   not yet taken from a NASA dataset. The layer is a relative proxy.

3. MGS TES thermal inertia, Putzig & Mellon 2007 maps (PDS MGS-M-TES-5-TIMAP-V1.0), file global_ti_night_2007.img:
   3600 lines x 7200 samples, big-endian signed 16-bit integers, 20 pixel/degree, simple cylindrical, longitude
   -180..180 east, latitude +90 at the top, units J m-2 K-1 s-1/2 ("tiu"). The label gives no scale or missing value;
   the readme says the derived range is 5 to 5000 tiu and that values outside it were not computed, so anything outside
   5..5000 is treated as no data. Each 0.5 degree cell is the mean of the valid pixels of its 10 x 10 block.
   Night map chosen by us (nightside values are less affected by slopes and albedo than daytime ones).
   Thermal inertia says how fast the ground heats and cools: low (< ~100) means loose dust, high means rock.
"""
from __future__ import annotations

import numpy as np

from .schema import Grid

MEGDR_LINES, MEGDR_SAMPLES = 720, 1440


def topography_to_grid(raw: bytes, grid: Grid | None = None) -> np.ndarray:
    """MEGDR 4 ppd bytes -> (360, 720) float32 elevation in metres, on the project grid."""
    grid = grid or Grid()
    if grid.res_deg != 0.5:
        raise ValueError("topography_to_grid is written for the 0.5 degree grid (2 x 2 pixel mean)")
    if len(raw) != MEGDR_LINES * MEGDR_SAMPLES * 2:
        raise ValueError(f"unexpected MEGDR size {len(raw)} (expected {MEGDR_LINES * MEGDR_SAMPLES * 2})")
    a = np.frombuffer(raw, dtype=">i2").reshape(MEGDR_LINES, MEGDR_SAMPLES).astype(np.float32)
    a = a.reshape(360, 2, 720, 2).mean(axis=(1, 3))          # 2 x 2 block mean -> 0.5 degree
    return np.roll(a, 360, axis=1)                           # lon 0..360 -> -180..180 (half a turn)


def parse_ns_table(text: str) -> tuple[np.ndarray, int]:
    """ns_*.tab text -> ((360, 720) float32 flux with NaN for no data, number of zero-flux rows).

    Cells are placed by their stated centre coordinates, never by row order."""
    rows = np.array([[float(x) for x in ln.split(",")] for ln in text.splitlines() if ln.strip()], dtype=float)
    if rows.shape[1] != 3:
        raise ValueError("expected 3 comma-separated columns: lon, lat, flux")
    lon, lat, flux = rows.T
    col = np.floor(lon / 0.5).astype(int)
    row = np.floor((90.0 - lat) / 0.5).astype(int)
    if col.min() < 0 or col.max() > 719 or row.min() < 0 or row.max() > 359:
        raise ValueError("coordinates outside the 0..360 / -90..90 grid")
    out = np.full((360, 720), np.nan, dtype=np.float32)
    out[row, col] = flux
    zero = int(np.sum(out == 0.0))
    out[out == 0.0] = np.nan
    return np.roll(out, 360, axis=1), zero


TI_PIXELS_PER_DEG = 20
TI_LINES, TI_SAMPLES = 3600, 7200
TI_VALID = (5.0, 5000.0)


def thermal_inertia_to_grid(raw: bytes) -> tuple[np.ndarray, float]:
    """TES thermal inertia map bytes -> ((360, 720) float32 tiu with NaN for no data, fraction of pixels outside 5..5000)."""
    if len(raw) != TI_LINES * TI_SAMPLES * 2:
        raise ValueError(f"unexpected thermal inertia size {len(raw)} (expected {TI_LINES * TI_SAMPLES * 2})")
    a = np.frombuffer(raw, dtype=">i2").reshape(TI_LINES, TI_SAMPLES).astype(np.float32)
    bad = (a < TI_VALID[0]) | (a > TI_VALID[1])
    a[bad] = np.nan
    blocks = a.reshape(360, 10, 720, 10)
    n = np.sum(~np.isnan(blocks), axis=(1, 3))
    total = np.nansum(blocks, axis=(1, 3))
    out = np.where(n > 0, total / np.maximum(n, 1), np.nan).astype(np.float32)
    return out, float(bad.mean())
