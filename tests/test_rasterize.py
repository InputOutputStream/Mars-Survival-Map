import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin  # noqa: E402

from mars_survival.rasterize import MARS_GEOG_WKT, raster_to_grid  # noqa: E402
from mars_survival.schema import Grid  # noqa: E402


def _write(path, arr, left):
    h, w = arr.shape
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=1, dtype="float32",
                       crs=MARS_GEOG_WKT, transform=from_origin(left, 90, 1, 1), nodata=-9999) as dst:
        dst.write(arr.astype("float32"), 1)


def test_lon_0_360_is_wrapped_to_minus180_180(tmp_path):
    lon_centers = np.arange(360) + 0.5                       # 0..360
    arr = np.tile(lon_centers, (180, 1))
    f = tmp_path / "lon360.tif"
    _write(f, arr, left=0)
    g = Grid(res_deg=2.0)
    out = raster_to_grid(f, g)
    expected = np.mod(g.lons(), 360)                         # value = original longitude 0..360
    assert np.allclose(out[10], expected, atol=1e-3)


def test_lon_minus180_180_kept_and_scale_nodata(tmp_path):
    lon_centers = np.arange(360) - 180 + 0.5
    arr = np.tile(lon_centers, (180, 1))
    arr[:, :10] = -9999                                      # nodata
    f = tmp_path / "lon180.tif"
    _write(f, arr, left=-180)
    g = Grid(res_deg=2.0)
    out = raster_to_grid(f, g, scale=2.0, offset=1.0)
    assert np.isnan(out[:, 0]).all()
    assert np.allclose(out[10, 20], g.lons()[20] * 2 + 1, atol=1e-3)
    out2 = raster_to_grid(f, g, valid_range=(0, 1000))
    assert np.isnan(out2[:, :90]).all() and np.isfinite(out2[:, 100:]).all()
