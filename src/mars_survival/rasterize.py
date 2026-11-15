"""
rasterize.py - converts GDAL rasters (GeoTIFF, PDS3 .IMG/.LBL, PDS4...) into layers
on the project's global grid, stored as .npy (float32, NaN = no data).

Grid convention: row 0 = north (+90), column 0 = -180 (east-positive longitude).
Rasters in 0..360 longitude are automatically shifted to -180..180.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .schema import Grid

# Mars 2000 geographic (IAU sphere of radius 3,396,190 m, like MOLA)
MARS_GEOG_WKT = (
    'GEOGCS["Mars 2000",DATUM["D_Mars_2000",SPHEROID["Mars_2000_IAU_IAU",3396190,0]],'
    'PRIMEM["Reference_Meridian",0],UNIT["degree",0.0174532925199433]]'
)


def _rasterio():
    try:
        import rasterio
        return rasterio
    except ImportError as e:  # pragma: no cover
        raise SystemExit("rasterio is required for this command: pip install 'mars-survival-map[geo]'") from e


def raster_to_grid(path, grid: Grid, band: int = 1, scale: float = 1.0, offset: float = 0.0,
                   nodata: float | None = None, valid_range: tuple[float, float] | None = None,
                   resampling: str = "average", assume_geographic: bool = False) -> np.ndarray:
    """Resamples a raster onto the grid. Returns an (H, W) float32 array with NaN."""
    rasterio = _rasterio()
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject

    h, w = grid.shape
    if w % 2:
        raise ValueError("the number of columns must be even (res_deg must divide 180)")
    with rasterio.open(path) as src:
        src_nodata = nodata if nodata is not None else src.nodata
        src_crs = MARS_GEOG_WKT if (assume_geographic or src.crs is None) else src.crs
        wrap360 = (src_crs == MARS_GEOG_WKT or src.crs.is_geographic) and src.bounds.left >= -1e-6 \
            and src.bounds.right > 180.0
        left = 0.0 if wrap360 else -180.0
        dst = np.full((h, w), np.nan, dtype=np.float32)
        reproject(
            source=rasterio.band(src, band), destination=dst,
            src_crs=src_crs, src_nodata=src_nodata,
            dst_transform=from_origin(left, 90.0, grid.res_deg, grid.res_deg),
            dst_crs=MARS_GEOG_WKT, dst_nodata=np.nan,
            resampling=getattr(Resampling, resampling),
        )
    if wrap360:
        dst = np.roll(dst, w // 2, axis=1)
    out = dst * np.float32(scale) + np.float32(offset)
    if valid_range is not None:
        out = np.where((out >= valid_range[0]) & (out <= valid_range[1]), out, np.nan)
    return out.astype(np.float32)


# --------------------------------------------------------------------------- layer storage
def save_layers(layers: dict[str, np.ndarray], grid_dir: Path, grid: Grid) -> None:
    grid_dir.mkdir(parents=True, exist_ok=True)
    for old in grid_dir.glob("*.npy"):   # purge: avoids mixing layers of different resolutions
        old.unlink()
    for key, arr in layers.items():
        np.save(grid_dir / f"{key}.npy", arr.astype(np.float32))
    (grid_dir / "meta.json").write_text(json.dumps({"res_deg": grid.res_deg}, indent=2))


def load_layers(grid_dir: Path) -> tuple[Grid, dict[str, np.ndarray]]:
    meta = json.loads((grid_dir / "meta.json").read_text())
    grid = Grid(res_deg=meta["res_deg"])
    layers = {}
    for f in sorted(grid_dir.glob("*.npy")):
        arr = np.load(f)
        if arr.shape != grid.shape:
            raise ValueError(f"{f.name} : shape {arr.shape} != grid {grid.shape}")
        layers[f.stem] = arr
    return grid, layers


def ingest(config_path: Path, root: Path) -> dict[str, np.ndarray]:
    """Reads config/layers.json, rasterizes each layer whose file exists, saves as .npy."""
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    grid = Grid(res_deg=cfg.get("grid", {}).get("res_deg", 0.5))
    layers: dict[str, np.ndarray] = {}
    for key, spec in cfg["layers"].items():
        f = root / spec["file"]
        if not f.exists():
            print(f"[skip] {key:24s} file missing: {spec['file']}")
            continue
        vr = tuple(spec["valid_range"]) if spec.get("valid_range") else None
        arr = raster_to_grid(f, grid, band=spec.get("band", 1), scale=spec.get("scale", 1.0),
                             offset=spec.get("offset", 0.0), nodata=spec.get("nodata"),
                             valid_range=vr, resampling=spec.get("resampling", "average"),
                             assume_geographic=spec.get("assume_geographic", False))
        layers[key] = arr
        print(f"[ok]   {key:24s} coverage {np.isfinite(arr).mean():.0%}  <- {spec['file']}")
    if layers:
        save_layers(layers, root / "data" / "grid", grid)
    else:
        print("No layer rasterized: put your files in data/files/ and edit config/layers.json")
    return layers
