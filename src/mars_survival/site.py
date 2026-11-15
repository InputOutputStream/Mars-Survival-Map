"""
site.py - SITE-scale analysis (a "city" of 2 to 20 km), in meters.

The global grid (0.5° ≈ 30 km/cell) is used to target regions; this module takes over:
from a local DEM (HiRISE/CTX DTM, or synthetic terrain) it computes

  - slope, aspect, roughness, shading (hillshade)
  - hazard classes (safe / caution / hazardous / forbidden)
  - travel cost grid and LEAST-COST ROUTE (8-neighbour Dijkstra, slope + roughness + climb)
  - candidate flat sites (landing / habitat)
  - exports for the web (bin + PNG), Blender (16-bit heightmap, OBJ) and GIS (GeoJSON / CSV)

Dependencies: numpy + pillow only. The `TraverseParams` thresholds are ASSUMPTIONS.
"""
from __future__ import annotations

import csv
import heapq
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

MARS_RADIUS_M = 3_396_190.0
SQRT2 = math.sqrt(2.0)
HAZARD_LABELS = ["safe", "caution", "hazardous", "forbidden"]


# --------------------------------------------------------------------------- parameters
@dataclass(frozen=True)
class TraverseParams:
    """Traversability assumptions (EVA walking / small rover). To be calibrated with the team."""
    slope_caution_deg: float = 10.0   # above: caution
    slope_hazard_deg: float = 20.0    # above: hazardous
    slope_max_deg: float = 25.0       # above: impassable
    rough_caution_m: float = 0.25     # roughness (local standard deviation of the detrended relief, in m)
    rough_hazard_m: float = 0.60
    rough_max_m: float = 1.50
    climb_k: float = 8.0              # cost (in "equivalent meters") per meter of positive elevation gain
    speed_kmh: float = 2.0            # reference walking speed on easy terrain


@dataclass
class Site:
    dem: np.ndarray                   # (H, W) float32, meters, north up
    px_m: float                       # ground pixel size, in meters
    name: str = "site"
    center_lat: float | None = None   # for the solar geometry and the output coordinates
    center_lon: float | None = None
    synthetic: bool = False

    @property
    def shape(self) -> tuple[int, int]:
        return self.dem.shape

    @property
    def extent_m(self) -> tuple[float, float]:
        return self.dem.shape[1] * self.px_m, self.dem.shape[0] * self.px_m


# --------------------------------------------------------------------------- synthetic terrain
def _fractal(shape, rng, octaves=6, persistence=0.5):
    """Fractal noise as a sum of smoothed octaves (pure numpy, via FFT)."""
    h, w = shape
    fy, fx = np.fft.fftfreq(h)[:, None], np.fft.fftfreq(w)[None, :]
    f = np.sqrt(fx**2 + fy**2)
    f[0, 0] = 1.0
    spec = (rng.normal(size=shape) + 1j * rng.normal(size=shape)) / f ** (1.0 + persistence * 1.6)
    spec[0, 0] = 0
    out = np.fft.ifft2(spec).real
    return (out - out.mean()) / (out.std() + 1e-12)


def synthetic_site(size: int = 320, px_m: float = 12.0, seed: int = 1) -> Site:
    """Crater with raised rim + alluvial fan + hills + boulder field. NOT REAL."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size].astype(float)
    cx, cy = size * 0.42, size * 0.50
    r = np.hypot(x - cx, y - cy) * px_m
    R = size * px_m * 0.26
    bowl = -170.0 * np.exp(-((r / R) ** 3))
    rim = 70.0 * np.exp(-(((r - R * 1.15) / (R * 0.22)) ** 2))
    fan = 30.0 * np.exp(-(((x - size * 0.80) / (size * 0.16)) ** 2 + ((y - size * 0.32) / (size * 0.22)) ** 2))
    ramp_ = -0.03 * (y - size / 2) * px_m                       # gentle regional slope towards the south
    dem = bowl + rim + fan + ramp_ + 14.0 * _fractal((size, size), rng, persistence=0.9) \
        + 0.2 * _fractal((size, size), rng, 8, 0.2)
    zone = np.hypot(x - size * 0.75, y - size * 0.7) < size * 0.12            # localized boulder field
    dem = dem + 0.9 * zone * (rng.random((size, size)) < 0.12) + 0.25 * zone * rng.random((size, size))
    return Site(dem.astype(np.float32), px_m, "synthetic site", 18.4, 77.5, synthetic=True)


# --------------------------------------------------------------------------- reading a DEM
def fill_nan(dem: np.ndarray, max_iter: int = 200) -> tuple[np.ndarray, float]:
    """Fill holes (nodata) by successive neighbourhood averages. Returns (dem, filled fraction)."""
    out = dem.astype(np.float64).copy()
    miss = ~np.isfinite(out)
    frac = float(miss.mean())
    if frac == 0:
        return out.astype(np.float32), 0.0
    if frac == 1:
        raise ValueError("DEM is entirely empty")
    for _ in range(max_iter):
        if not miss.any():
            break
        v = np.where(miss, 0.0, out)
        n = (~miss).astype(float)
        pv, pn = np.pad(v, 1), np.pad(n, 1)
        sv = sum(pv[1 + i:1 + i + out.shape[0], 1 + j:1 + j + out.shape[1]] for i in (-1, 0, 1) for j in (-1, 0, 1))
        sn = sum(pn[1 + i:1 + i + out.shape[0], 1 + j:1 + j + out.shape[1]] for i in (-1, 0, 1) for j in (-1, 0, 1))
        fill = miss & (sn > 0)
        out[fill] = sv[fill] / sn[fill]
        miss &= ~fill
    return out.astype(np.float32), frac


def load_dem(path: str | Path, px_m: float | None = None, zmin: float | None = None, zmax: float | None = None,
             nodata: float | None = None) -> tuple[np.ndarray, float | None]:
    """Reads .npy, .asc (ESRI ASCII), 16-bit .png (zmin/zmax required) or GeoTIFF (.tif). Returns (dem, px_m|None)."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".npy":
        arr = np.load(p).astype(np.float64)
    elif ext == ".asc":
        head, rows = {}, []
        with open(p, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2 and parts[0].lower() in {"ncols", "nrows", "xllcorner", "yllcorner", "xllcenter",
                                                            "yllcenter", "cellsize", "nodata_value"}:
                    head[parts[0].lower()] = float(parts[1])
                else:
                    rows.append(np.array(parts, dtype=np.float64))
        arr = np.vstack(rows)
        px_m = px_m or head.get("cellsize")
        nodata = head.get("nodata_value", nodata) if nodata is None else nodata
    elif ext == ".png":
        from PIL import Image
        im = Image.open(p)
        a = np.asarray(im).astype(np.float64)
        if a.ndim == 3:
            a = a[..., 0]
        if zmin is None or zmax is None:
            raise ValueError("PNG: specify --zmin and --zmax (meters corresponding to 0 and to the PNG's max value)")
        top = 65535.0 if im.mode.startswith("I") or a.max() > 255 else 255.0
        arr = zmin + a / top * (zmax - zmin)
    elif ext in (".tif", ".tiff"):
        try:
            import rasterio
            with rasterio.open(p) as src:
                arr = src.read(1).astype(np.float64)
                nodata = src.nodata if nodata is None else nodata
                if px_m is None and src.crs is not None and src.crs.is_projected:
                    px_m = abs(src.transform.a)
        except ImportError:
            from PIL import Image
            arr = np.asarray(Image.open(p)).astype(np.float64)
    else:
        raise ValueError(f"unsupported format: {ext} (npy, asc, png, tif)")
    if nodata is not None:
        arr = np.where(np.isclose(arr, nodata), np.nan, arr)
    return arr.astype(np.float32), px_m


# --------------------------------------------------------------------------- terrain derivatives
def slope_aspect(dem: np.ndarray, px_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Slope (°) and aspect (° from north, clockwise) by central differences."""
    dzdy, dzdx = np.gradient(dem.astype(np.float64), px_m)   # dzdy: towards the south (increasing rows)
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    aspect = np.degrees(np.arctan2(-dzdx, dzdy)) % 360.0             # azimuth of the steepest descent
    return slope.astype(np.float32), aspect.astype(np.float32)


def _box_mean(a: np.ndarray, k: int) -> np.ndarray:
    """Moving k×k mean (k odd) via integral image; edges handled by replication."""
    pad = k // 2
    p = np.pad(a.astype(np.float64), pad, mode="edge")
    c = np.pad(p.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    h, w = a.shape
    s = c[k:k + h, k:k + w] - c[:h, k:k + w] - c[k:k + h, :w] + c[:h, :w]
    return s / (k * k)


def roughness(dem: np.ndarray, px_m: float, window_m: float = 60.0) -> np.ndarray:
    """Local standard deviation (m) of the relief after removing the local slope (fitted plane), window ≈ window_m."""
    k = max(3, int(round(window_m / px_m)) | 1)
    d = dem.astype(np.float64)
    var = np.maximum(_box_mean(d * d, k) - _box_mean(d, k) ** 2, 0.0)
    gy, gx = np.gradient(d, px_m)
    tilt_var = (_box_mean(gx, k) ** 2 + _box_mean(gy, k) ** 2) * (k * k - 1) / 12.0 * px_m**2
    return np.sqrt(np.maximum(var - tilt_var, 0.0)).astype(np.float32)


def hillshade(dem: np.ndarray, px_m: float, azimuth_deg: float = 315.0, altitude_deg: float = 40.0) -> np.ndarray:
    """Shading 0..1 (illumination from azimuth/altitude)."""
    dzdy, dzdx = np.gradient(dem.astype(np.float64), px_m)
    az, alt = math.radians(azimuth_deg), math.radians(altitude_deg)
    nx, ny, nz = -dzdx, dzdy, np.ones_like(dzdx)       # normal; y increases towards the south
    norm = np.sqrt(nx**2 + ny**2 + nz**2)
    lx, ly, lz = math.sin(az) * math.cos(alt), math.cos(az) * math.cos(alt), math.sin(alt)
    return np.clip((nx * lx + ny * ly + nz * lz) / norm, 0, 1).astype(np.float32)


def hazard_class(slope: np.ndarray, rough: np.ndarray, p: TraverseParams = TraverseParams()) -> np.ndarray:
    """0 safe, 1 caution, 2 hazardous, 3 forbidden (the worse of the two criteria)."""
    def lvl(v, a, b, c):
        return (v > a).astype(np.uint8) + (v > b) + (v > c)
    return np.maximum(lvl(slope, p.slope_caution_deg, p.slope_hazard_deg, p.slope_max_deg),
                      lvl(rough, p.rough_caution_m, p.rough_hazard_m, p.rough_max_m)).astype(np.uint8)


def cost_grid(slope: np.ndarray, rough: np.ndarray, p: TraverseParams = TraverseParams()) -> np.ndarray:
    """Cost multiplier ≥ 1; +inf if impassable. Same formula in web/route.mjs."""
    c = 1.0 + (slope / p.slope_caution_deg) ** 2 + (rough / p.rough_caution_m) ** 2
    c = np.where((slope > p.slope_max_deg) | (rough > p.rough_max_m), np.inf, c)
    return c.astype(np.float32)


# --------------------------------------------------------------------------- routing
_NEIGH = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
          (-1, -1, SQRT2), (-1, 1, SQRT2), (1, -1, SQRT2), (1, 1, SQRT2)]


def find_route(dem: np.ndarray, cost: np.ndarray, px_m: float, start: tuple[int, int], goal: tuple[int, int],
               climb_k: float = TraverseParams.climb_k) -> dict | None:
    """8-neighbour Dijkstra. Step cost = 3D distance × mean cost of the 2 cells + climb_k × ascent.
    start/goal = (row, column). Returns None if no route exists."""
    h, w = dem.shape
    if not (0 <= start[0] < h and 0 <= start[1] < w and 0 <= goal[0] < h and 0 <= goal[1] < w):
        raise ValueError("start or goal outside the site")
    if not np.isfinite(cost[start]) or not np.isfinite(cost[goal]):
        return None
    dist = np.full((h, w), np.inf)
    prev = np.full((h, w), -1, dtype=np.int64)
    dist[start] = 0.0
    heap = [(0.0, start[0], start[1])]
    while heap:
        d, r, c = heapq.heappop(heap)
        if d > dist[r, c]:
            continue
        if (r, c) == goal:
            break
        for dr, dc, f in _NEIGH:
            rr, cc = r + dr, c + dc
            if not (0 <= rr < h and 0 <= cc < w):
                continue
            cb = cost[rr, cc]
            if not np.isfinite(cb):
                continue
            dz = float(dem[rr, cc] - dem[r, c])
            step = math.hypot(f * px_m, dz) * 0.5 * (float(cost[r, c]) + float(cb)) + climb_k * max(dz, 0.0)
            nd = d + step
            if nd < dist[rr, cc]:
                dist[rr, cc] = nd
                prev[rr, cc] = r * w + c
                heapq.heappush(heap, (nd, rr, cc))
    if not np.isfinite(dist[goal]):
        return None
    path, cur = [], goal[0] * w + goal[1]
    while cur != -1:
        path.append((cur // w, cur % w))
        cur = int(prev[cur // w, cur % w])
    path.reverse()
    return {"path": path, "cost": float(dist[goal]), **route_stats(dem, cost, px_m, path)}


def route_stats(dem, cost, px_m, path, speed_kmh: float = TraverseParams.speed_kmh) -> dict:
    """Length, elevation change, max slope, estimated duration (model: speed / mean cost multiplier)."""
    rr = np.array([q[0] for q in path])
    cc = np.array([q[1] for q in path])
    z = dem[rr, cc].astype(float)
    seg = np.hypot(np.hypot(np.diff(rr), np.diff(cc)) * px_m, np.diff(z)) if len(path) > 1 else np.zeros(0)
    flat = np.hypot(np.diff(rr), np.diff(cc)) * px_m if len(path) > 1 else np.zeros(0)
    dz = np.diff(z) if len(path) > 1 else np.zeros(0)
    mult = 0.5 * (cost[rr[:-1], cc[:-1]] + cost[rr[1:], cc[1:]]) if len(path) > 1 else np.zeros(0)
    slopes = np.degrees(np.arctan2(np.abs(dz), np.maximum(flat, 1e-9)))
    return {
        "length_m": float(seg.sum()),
        "straight_m": float(math.hypot((rr[-1] - rr[0]) * px_m, (cc[-1] - cc[0]) * px_m)),
        "ascent_m": float(dz[dz > 0].sum()), "descent_m": float(-dz[dz < 0].sum()),
        "max_slope_deg": float(slopes.max()) if len(slopes) else 0.0,
        "mean_slope_deg": float(np.average(slopes, weights=seg)) if seg.sum() > 0 else 0.0,
        "time_h": float((seg * mult).sum() / (speed_kmh * 1000.0)),
        "profile_m": [round(float(v), 2) for v in z],
        "profile_dist_m": [round(float(v), 1) for v in np.concatenate([[0], np.cumsum(seg)])],
    }


def find_flat_sites(slope: np.ndarray, rough: np.ndarray, px_m: float, radius_m: float = 100.0, n: int = 5,
                    max_slope: float = 5.0, max_rough: float = 0.25, min_sep_m: float | None = None,
                    max_bad_frac: float = 0.0) -> list[dict]:
    """Centers of "flat" discs of radius radius_m (slope ≤ max_slope and roughness ≤ max_rough).

    max_bad_frac : share of the disc allowed to exceed these limits (0 = entirely flat disc). On a real DEM, a disc 120 m across
    without a single rough pixel is rare; a small tolerance (a team assumption, not a NASA value) avoids
    finding nothing. The share actually out of limits is returned (bad_frac) so the interface can display it."""
    bad = ((slope > max_slope) | (rough > max_rough)).astype(np.float64)
    k = max(3, int(round(2 * radius_m / px_m)) | 1)
    frac_bad = _box_mean(bad, k)
    h, w = bad.shape
    pad = k // 2
    frac_bad[:pad, :] = frac_bad[-pad:, :] = 1.0
    frac_bad[:, :pad] = frac_bad[:, -pad:] = 1.0                 # incomplete disc outside the site
    min_sep_px = (min_sep_m or 3 * radius_m) / px_m
    mean_slope = _box_mean(slope, k)
    key = np.where(frac_bad <= max_bad_frac + 1e-9, mean_slope, np.inf)        # flattest first
    order = np.argsort(key, axis=None, kind="stable")
    picks: list[dict] = []
    for idx in order:
        r, c = divmod(int(idx), w)
        if not np.isfinite(key[r, c]) or len(picks) >= n:
            break
        if all(math.hypot(r - q["row"], c - q["col"]) >= min_sep_px for q in picks):
            picks.append({"rank": len(picks) + 1, "row": r, "col": c, "radius_m": radius_m,
                          "mean_slope_deg": round(float(_disk_mean(slope, r, c, radius_m / px_m)), 2),
                          "bad_frac": round(float(frac_bad[r, c]), 3)})
    return picks


def _disk_mean(a, r, c, rad_px):
    rr, cc = np.ogrid[:a.shape[0], :a.shape[1]]
    m = (rr - r) ** 2 + (cc - c) ** 2 <= rad_px**2
    return a[m].mean()


# --------------------------------------------------------------------------- coordinates
def local_to_latlon(site: Site, row: float, col: float) -> tuple[float, float] | None:
    """Local tangent plane around the site center (sufficient for a few km)."""
    if site.center_lat is None or site.center_lon is None:
        return None
    h, w = site.shape
    north = (h / 2 - row) * site.px_m
    east = (col - w / 2) * site.px_m
    lat = site.center_lat + math.degrees(north / MARS_RADIUS_M)
    lon = site.center_lon + math.degrees(east / (MARS_RADIUS_M * math.cos(math.radians(site.center_lat))))
    return round(lat, 6), round(lon, 6)


# --------------------------------------------------------------------------- full analysis + export
def analyse(site: Site, params: TraverseParams = TraverseParams()) -> dict:
    dem, _ = fill_nan(site.dem)
    site.dem = dem
    slope, aspect = slope_aspect(dem, site.px_m)
    rough = roughness(dem, site.px_m)
    return {"slope": slope, "aspect": aspect, "rough": rough, "shade": hillshade(dem, site.px_m),
            "hazard": hazard_class(slope, rough, params), "cost": cost_grid(slope, rough, params)}


# project palette: leaf #4A9A2F, yellow #F0BF2B, orange #EC7A2C, crimson #A1162F
_SLOPE_STOPS = [(0, (74, 154, 47)), (5, (74, 154, 47)), (10, (240, 191, 43)), (20, (236, 122, 44)), (30, (161, 22, 47))]
_HAZ_COLORS = np.array([[74, 154, 47, 26], [240, 191, 43, 150], [236, 122, 44, 185], [161, 22, 47, 215]], np.uint8)


def _ramp_rgba(v, stops, alpha=170):
    xs = [s[0] for s in stops]
    out = np.zeros(v.shape + (4,), np.uint8)
    for i in range(3):
        out[..., i] = np.interp(v, xs, [s[1][i] for s in stops])
    out[..., 3] = alpha
    return out


def export_site(site: Site, res: dict, out_dir: Path, params: TraverseParams, routes: list[dict] | None = None,
                flats: list[dict] | None = None, eva: dict | None = None, mesh_max: int = 192,
                walker: dict | None = None, tmult: np.ndarray | None = None, legacy_f32: bool = False) -> Path:
    from PIL import Image
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    h, w = site.shape
    zmin, zmax = float(site.dem.min()), float(site.dem.max())
    # --- binaries for the web, packed as fixed-point integers (row 0 = north, little-endian):
    #   dem16.bin   uint16, z = zmin + v * zscale   (zscale = relief / 65535: ~1.5 cm for 1 km of relief; float16 would give 2 m at -2600 m)
    #   slope8.bin  uint8, degrees = v * 0.25       (clamped at 63.75°: everything above 25° is impassable anyway)
    #   rough16.bin uint16, millimetres             (clamped at 65 m)
    # The terrain multiplier is not stored: the page computes 1 + (r/r0)² from roughness (inf above rough_max_m), exactly as traverse.py does.
    zscale = max((zmax - zmin) / 65535.0, 1e-6)
    dq = np.clip(np.rint((site.dem - zmin) / zscale), 0, 65535).astype("<u2")
    sq = np.clip(np.rint(res["slope"] / 0.25), 0, 255).astype("u1")
    rq = np.clip(np.rint(np.asarray(res["rough"]) * 1000.0), 0, 65535).astype("<u2")
    dq.tofile(out_dir / "dem16.bin"); sq.tofile(out_dir / "slope8.bin"); rq.tofile(out_dir / "rough16.bin")
    pack = {"zmin": zmin, "zscale": zscale, "slope_step_deg": 0.25, "rough_step_m": 0.001,
            "err_z_m": float(np.abs(dq * zscale + zmin - site.dem).max()),
            "err_slope_deg": float(np.abs(np.minimum(sq * 0.25, np.minimum(res["slope"], 63.75)) - np.minimum(res["slope"], 63.75)).max()),
            "err_rough_m": float(np.abs(rq / 1000.0 - np.minimum(res["rough"], 65.535)).max())}
    if legacy_f32:   # only the Python/JS parity test needs these now
        for key, arr in (("dem", site.dem), ("slope", res["slope"]), ("rough", res["rough"]), ("cost", res["cost"])):
            np.asarray(arr, dtype="<f4").tofile(out_dir / f"{key}.bin")
        if tmult is not None:
            np.asarray(tmult, dtype="<f4").tofile(out_dir / "tmult.bin")
    # --- images (web overlay + Blender textures)
    shade = (res["shade"] * 255).astype(np.uint8)
    Image.fromarray(shade, "L").save(out_dir / "hillshade.png")
    Image.fromarray(_ramp_rgba(res["slope"], _SLOPE_STOPS), "RGBA").save(out_dir / "slope.png")
    Image.fromarray(_HAZ_COLORS[res["hazard"]], "RGBA").save(out_dir / "hazard.png")
    rg = np.clip(res["rough"] / max(params.rough_max_m, 1e-6), 0, 1)
    Image.fromarray(_ramp_rgba(rg * 30, _SLOPE_STOPS), "RGBA").save(out_dir / "roughness.png")
    rel = (site.dem - zmin) / max(zmax - zmin, 1e-9)
    Image.fromarray((rel * 65535).astype(np.uint16)).save(out_dir / "heightmap16.png")   # Blender displacement
    tex = np.clip(0.35 + 0.65 * res["shade"], 0, 1)[..., None] * np.array([196, 120, 82]) / 255
    Image.fromarray((tex * 255).astype(np.uint8), "RGB").save(out_dir / "texture.png")
    # --- decimated OBJ mesh
    _write_obj(site, out_dir / "terrain.obj", out_dir / "terrain.mtl", mesh_max)
    # --- routes
    routes_json = []
    for rt in routes or []:
        pts = [{"row": r, "col": c, "x_m": round(c * site.px_m, 2), "y_m": round(r * site.px_m, 2),
                "z_m": round(float(site.dem[r, c]), 2), "latlon": local_to_latlon(site, r, c)} for r, c in rt["path"]]
        routes_json.append({"name": rt.get("name", "route"), **{k: v for k, v in rt.items() if k not in ("path", "name")},
                            "points": pts})
    _write_route_files(routes_json, site, out_dir)
    meta = {
        "name": site.name, "synthetic": site.synthetic, "width": w, "height": h, "px_m": site.px_m,
        "zmin": zmin, "zmax": zmax, "center_lat": site.center_lat, "center_lon": site.center_lon,
        "params": {k: v for k, v in asdict(params).items() if k not in ("climb_k", "speed_kmh")},   # those two only serve the legacy cost grid, not the map
        "layers": [
            {"id": "slope", "label": "Slope", "png": "slope.png"},
            {"id": "roughness", "label": "Roughness", "png": "roughness.png"},
            {"id": "hazard", "label": "Hazard classes", "png": "hazard.png"},
        ],
        "pack": pack, "routes": routes_json, "flat_sites": flats or [], "eva": eva, "walker": walker,
        "hazard_labels": HAZARD_LABELS,
        "blender_note": "heightmap16.png : 0 -> zmin, 65535 -> zmax (meters). True scale: pixel = px_m meters.",
    }
    (out_dir / "site.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    return out_dir / "site.json"


def _write_obj(site: Site, obj: Path, mtl: Path, mesh_max: int) -> None:
    h, w = site.shape
    step = max(1, math.ceil(max(h, w) / mesh_max))
    z = site.dem[::step, ::step]
    mh, mw = z.shape
    dx = site.px_m * step
    lines = [f"mtllib {mtl.name}", "o terrain", "usemtl mars"]
    for i in range(mh):
        for j in range(mw):                       # X = east, Y = north, Z = elevation (Blender: Z up)
            lines.append(f"v {j * dx:.2f} {(mh - 1 - i) * dx:.2f} {z[i, j]:.3f}")
    for i in range(mh):
        for j in range(mw):
            lines.append(f"vt {j / (mw - 1):.5f} {1 - i / (mh - 1):.5f}")
    for i in range(mh - 1):
        for j in range(mw - 1):
            a, b = i * mw + j + 1, i * mw + j + 2
            c, d = (i + 1) * mw + j + 2, (i + 1) * mw + j + 1
            lines.append(f"f {a}/{a} {d}/{d} {c}/{c} {b}/{b}")
    obj.write_text("\n".join(lines) + "\n")
    mtl.write_text("newmtl mars\nKd 1 1 1\nmap_Kd texture.png\n")


def _write_route_files(routes: list[dict], site: Site, out_dir: Path) -> None:
    feats = []
    for rt in routes:
        feats.append({"type": "Feature", "properties": {k: v for k, v in rt.items() if k not in ("points", "profile_m", "profile_dist_m")},
                      "geometry": {"type": "LineString",
                                   "coordinates": [[p["x_m"], p["y_m"], p["z_m"]] for p in rt["points"]]}})
    (out_dir / "routes_local.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "name": "routes (local meters: x=east, y=south from the NW corner)", "features": feats}))
    with open(out_dir / "routes.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["route", "idx", "x_m", "y_m", "z_m", "lat", "lon"])
        for rt in routes:
            for i, p in enumerate(rt["points"]):
                ll = p["latlon"] or (None, None)
                wr.writerow([rt["name"], i, p["x_m"], p["y_m"], p["z_m"], ll[0], ll[1]])
