import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from mars_survival.photo import crop_photo, lonlat_to_xy

WKT = ('PROJCS["Mars",GEOGCS["M",DATUM["D",SPHEROID["S",3396190,0]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
       'PROJECTION["Equirectangular"],PARAMETER["standard_parallel_1",0],PARAMETER["central_meridian",0],UNIT["metre",1]]')


def _tif(path, lat, lon, px=0.25, n=2000):
    from rasterio.crs import CRS
    from rasterio.transform import from_origin
    cx, cy = lonlat_to_xy(lat, lon, WKT)
    z = (np.add.outer(np.arange(n), np.arange(n)) % 250 + 1).astype("uint8")
    with rasterio.open(path, "w", driver="GTiff", height=n, width=n, count=1, dtype="uint8", crs=CRS.from_wkt(WKT),
                       transform=from_origin(cx - n * px / 2, cy + n * px / 2, px, px)) as d:
        d.write(z, 1)
    return cx, cy


def test_crop_is_centred_and_sized(tmp_path):
    cx, cy = _tif(tmp_path / "o.tif", 18.44, 77.52)
    img, px, box = crop_photo(str(tmp_path / "o.tif"), 18.44, 77.52, (200, 200), 1.0, (200, 200), max_px=800)
    assert img.shape == (800, 800) and abs(px - 0.25) < 1e-9
    assert abs((box[0] + box[2]) / 2 - cx) < 1e-6 and abs((box[1] + box[3]) / 2 - cy) < 1e-6 and img.max() > 0


def test_outside_image_is_refused(tmp_path):
    _tif(tmp_path / "o.tif", 18.44, 77.52)
    with pytest.raises(ValueError):
        crop_photo(str(tmp_path / "o.tif"), 10.0, 70.0, (200, 200), 1.0, (200, 200))


def test_spheroid_radius_is_read_from_the_crs():
    from mars_survival.photo import spheroid_radius, lonlat_to_xy
    wkt = 'PROJCS["Equirectangular MARS",GEOGCS["GCS_MARS",DATUM["unnamed",SPHEROID["unnamed",3394839.8133163,0]]],PROJECTION["Equirectangular"],PARAMETER["standard_parallel_1",0],PARAMETER["central_meridian",77.53]]'
    assert abs(spheroid_radius(wkt) - 3394839.8133163) < 1e-6
    assert spheroid_radius("") == 3396190.0
    x, y = lonlat_to_xy(18.4, 77.53, wkt)
    assert abs(y - 3394839.8133163 * 3.14159265358979 / 180 * 18.4) < 1e-3 and abs(x) < 1e-6


def test_strips_retry_and_match_a_single_read(tmp_path):
    import numpy as np, rasterio
    from rasterio.transform import from_origin
    from rasterio.windows import Window
    from rasterio.enums import Resampling
    from mars_survival.photo import _read_in_strips
    p = tmp_path / "t.tif"; data = (np.arange(300 * 200) % 251).astype("uint8").reshape(300, 200)
    with rasterio.open(p, "w", driver="GTiff", height=300, width=200, count=1, dtype="uint8", transform=from_origin(0, 300, 1, 1)) as d:
        d.write(data, 1)
    with rasterio.open(p) as ds:
        win = Window(10, 20, 150, 240); out = (120, 75)
        ref = ds.read(1, window=win, out_shape=out, resampling=Resampling.nearest)
        got = _read_in_strips(ds, win, out, Resampling.nearest, rows_per_strip=32)
        assert got.shape == out and np.array_equal(got, ref)
        calls = {"n": 0}; real = ds.read
        def flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1: raise IOError("opj_decode() failed")
            return real(*a, **k)
        ds.read = flaky
        import mars_survival.photo as ph; ph_time = ph.__dict__.get("time")
        got2 = _read_in_strips(ds, win, out, Resampling.nearest, rows_per_strip=60, tries=3)
        assert np.array_equal(got2, ref) and calls["n"] == 3
