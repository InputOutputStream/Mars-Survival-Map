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


# --------------------------------------------------------------------------- MCS surface temperature
# Wang & Jin 2025, "Mars Climate Sounder Surface Temperatures Corrected to 03:00 and 15:00 LTST",
# Zenodo doi:10.5281/zenodo.17947556 (CC BY 4.0). Surface temperatures from NASA's MRO Mars Climate Sounder, processed
# by the authors. Layout read from the file by scripts/inspect_mcs_tsurf.py (2026-11-07):
#   tsurf_correct[MY, Ls, ltst, Lat, Lon], MY 28..37, Ls 0..350 step 10, ltst (3, 15), Lat -85..90 step 5,
#   Lon -180..175 step 5, K, NaN = no data (59% of the raw array), raw range 112.7 to 355.7 K.
# Choices of ours (all team assumptions, listed on the sources page):
#   - values outside 130..320 K are retrieval outliers (the raw range runs from 113 K, below the CO2 frost point, to
#     356 K, hotter than the surface of Mars is believed to get) and are dropped;
#   - the Mars years are combined with the MEDIAN, so one odd year cannot dominate;
#   - daily mean ~ (T03 + T15) / 2, which is exact only for a pure sinusoid; day/night swing ~ T15 - T03, which is smaller
#     than the true max - min because the real extremes fall near 14:00 and 04:00, not exactly at 15:00 and 03:00;
#   - annual mean = mean over Ls weighted by the TIME each 10 degree Ls bin lasts (Mars' seasons are unequal),
#     taken only where bins covering at least 75% of the year have data (else NaN: no silent gap-filling);
#   - the file's 5 degree nodes are treated as grid POINTS and interpolated bilinearly to the 0.5 degree grid, using
#     the valid neighbours only; south of the first node (-85) and where no neighbour is valid: NaN.
MCS_VALID_K = (130.0, 320.0)
MCS_MIN_YEAR_COVERAGE = 0.75


def ls_time_weights(ls_deg: np.ndarray) -> np.ndarray:
    """Share of the Mars year spent with Ls within +-half a step of each value (equal time is NOT equal Ls)."""
    from .thermal import _orbit_samples
    ls_deg = np.asarray(ls_deg, dtype=float)
    step = float(np.median(np.diff(np.sort(ls_deg))))
    samples = np.rad2deg(_orbit_samples(7200)[0]) % 360.0
    d = (samples[None, :] - ls_deg[:, None] + 180.0) % 360.0 - 180.0
    w = (np.abs(d) < step / 2).sum(axis=1).astype(float)
    return w / w.sum()


def _bilinear_nan(field: np.ndarray, lat_nodes, lon_nodes, lat_out, lon_out) -> np.ndarray:
    """(nlat, nlon) node values with NaN -> (len(lat_out), len(lon_out)); weights renormalised over valid corners."""
    lat_nodes = np.asarray(lat_nodes, float); lon_nodes = np.asarray(lon_nodes, float)
    dlon = lon_nodes[1] - lon_nodes[0]
    fy = np.interp(lat_out, lat_nodes, np.arange(len(lat_nodes)))           # fractional row index (clamped at the ends)
    out_of_range = (lat_out < lat_nodes[0]) | (lat_out > lat_nodes[-1])
    fx = ((np.asarray(lon_out, float) - lon_nodes[0]) / dlon) % len(lon_nodes)
    y0 = np.floor(fy).astype(int); y1 = np.minimum(y0 + 1, len(lat_nodes) - 1); wy = fy - y0
    x0 = np.floor(fx).astype(int) % len(lon_nodes); x1 = (x0 + 1) % len(lon_nodes); wx = fx - np.floor(fx)
    num = np.zeros((len(lat_out), len(lon_out))); den = np.zeros_like(num)
    for yy, wyy in ((y0, 1 - wy), (y1, wy)):
        for xx, wxx in ((x0, 1 - wx), (x1, wx)):
            v = field[yy][:, xx]
            w = wyy[:, None] * wxx[None, :] * np.isfinite(v)
            num += w * np.nan_to_num(v); den += w
    out = np.where(den > 1e-9, num / np.maximum(den, 1e-9), np.nan)
    out[out_of_range, :] = np.nan
    return out.astype(np.float32)


def mcs_to_grid(tsurf, my, ls, ltst, lat, lon, grid: Grid | None = None) -> dict:
    """MCS array -> {'temp_mean_k', 'temp_diurnal_k'} on the 0.5 degree grid + stats. See the notes above."""
    grid = grid or Grid()
    t = np.array(tsurf, dtype=float)
    lo, hi = MCS_VALID_K
    outliers = np.isfinite(t) & ((t < lo) | (t > hi))
    t[(t < lo) | (t > hi)] = np.nan
    ltst = list(np.asarray(ltst, float))
    if 3.0 not in ltst or 15.0 not in ltst:
        raise ValueError(f"expected local times 3 and 15, got {ltst}")
    i3, i15 = ltst.index(3.0), ltst.index(15.0)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(t, axis=0)                                  # over Mars years -> (Ls, ltst, Lat, Lon)
    t3, t15 = med[:, i3], med[:, i15]
    daily = (t3 + t15) / 2.0
    swing = t15 - t3
    w = ls_time_weights(ls)[:, None, None]
    ok = np.isfinite(daily)
    cover = (w * ok).sum(axis=0)
    mean_year = np.where(cover >= MCS_MIN_YEAR_COVERAGE, (w * np.nan_to_num(daily) * ok).sum(axis=0) / np.maximum(cover, 1e-9), np.nan)
    ok2 = np.isfinite(swing)
    cover2 = (w * ok2).sum(axis=0)
    swing_year = np.where(cover2 >= MCS_MIN_YEAR_COVERAGE, (w * np.nan_to_num(swing) * ok2).sum(axis=0) / np.maximum(cover2, 1e-9), np.nan)
    lat_o, lon_o = grid.lats(), grid.lons()
    return {"temp_mean_k": _bilinear_nan(mean_year, lat, lon, lat_o, lon_o),
            "temp_diurnal_k": _bilinear_nan(swing_year, lat, lon, lat_o, lon_o),
            "outlier_fraction": float(outliers.sum() / max(np.isfinite(np.array(tsurf, float)).sum(), 1)),
            "node_coverage": float(np.isfinite(mean_year).mean())}


def read_mcs_netcdf(path) -> dict:
    import netCDF4
    ds = netCDF4.Dataset(path)
    g = lambda k: np.ma.filled(ds.variables[k][:].astype(float), np.nan)
    return dict(tsurf=g("tsurf_correct"), my=g("MY"), ls=g("Ls"), ltst=g("ltst"), lat=g("Lat"), lon=g("Lon"))


# --------------------------------------------------------------------------- MCD dust climatology
# Montabone et al. 2015 (Icarus 251:65-95), Montabone et al. 2020 (JGR Planets): "dustscenario_MYxx" kriged daily maps,
# https://www-mars.lmd.jussieu.fr/mars/dust_climatology/ (CC BY-SA 3.0; observations from NASA MRO MCS, TES, THEMIS).
# Layout read from dustscenario_MY29_v2-0.nc by scripts/inspect_dust.py (2026-11-07):
#   cdodtot[Time=669, latitude=60 (88.5 down to -88.5, step 3), longitude=120 (-180 to 177, step 3)]: IR absorption column dust
#   optical depth of the TOTAL column (already scaled to the local surface pressure by the authors); 9.3 micron.
#   cdod610 is the same normalised to 610 Pa (not used); cdodrel is a reliability index (not used yet).
# Visible equivalent = 9.3 micron absorption x 2.6 (rule stated on the source page; Montabone et al. 2015).
# Choices of ours: annual mean over all sols of a Mars year (storms count in proportion to how long they last), then the
# MEDIAN across the chosen Mars years; the 3 degree nodes are treated as points (a half-cell shift of 1.5 degrees at most).
DUST_VISIBLE_FACTOR = 2.6
DUST_FILES = {**{y: f"dustscenario_MY{y}_v2-0.nc" for y in range(24, 33)}, 33: "dustscenario_MY33_v2-1.nc",
              **{y: f"dustscenario_MY{y}_v2-5.nc" for y in (34, 35, 36)}}      # names from the server's directory listing


def dust_year_to_grid(cdodtot, lat, lon, grid: Grid | None = None) -> np.ndarray:
    """One Mars year of daily total-column absorption CDOD -> (360, 720) mean visible-equivalent optical depth."""
    grid = grid or Grid()
    lat = np.asarray(lat, float); lon = np.asarray(lon, float)
    mean = np.nanmean(np.asarray(cdodtot, float), axis=0) * DUST_VISIBLE_FACTOR      # (lat, lon)
    if lat[0] > lat[-1]:                                                              # the file runs north to south
        lat, mean = lat[::-1], mean[::-1]
    return _bilinear_nan(mean, lat, lon, grid.lats()[::-1], grid.lons())[::-1]       # grid row 0 is north


def read_dust_netcdf(path) -> dict:
    import netCDF4
    ds = netCDF4.Dataset(path)
    g = lambda k: np.ma.filled(ds.variables[k][:].astype(float), np.nan)
    return dict(cdodtot=g("cdodtot"), lat=g("latitude"), lon=g("longitude"))
