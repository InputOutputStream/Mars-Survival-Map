import json
import numpy as np
from mars_survival.overview import block_mean, hillshade, metres_per_px, scan_sites


def test_block_mean_ignores_nodata():
    a = np.array([[1., np.nan], [3., 5.]]); assert block_mean(a, 2)[0, 0] == 3.0


def test_pixel_size_shrinks_with_latitude():
    x0, y0 = metres_per_px(0, 1, 0, 1, 100, 100); x1, y1 = metres_per_px(60, 61, 0, 1, 100, 100)
    assert abs(y0 - y1) < 1 and x1 < x0 * 0.55


def test_hillshade_lit_from_north_west():
    z = np.add.outer(np.arange(30.), np.arange(30.)) * 5            # rises to the SE, so faces NW (the sun)
    assert hillshade(z, 20, 20).mean() > hillshade(z[::-1, ::-1], 20, 20).mean()


def test_scan_sites(tmp_path):
    for p, sid in (("site", None), ("sites/b", "b")):
        d = tmp_path / p; d.mkdir(parents=True)
        (d / "site.json").write_text(json.dumps({"name": p, "width": 100, "height": 50, "px_m": 4.0, "center_lat": 18.4, "center_lon": 77.5}))
    s = scan_sites(tmp_path); assert [e["id"] for e in s] == ["jezero", "b"] and s[1]["href"] == "index.html?site=b" and s[0]["width_m"] == 400


def test_geo_bounds_metres_and_degrees():
    from mars_survival.overview import geo_bounds, MARS_R_M, DOC_BOUNDS
    assert geo_bounds((76.99, 17.58, 78.58, 19.29))[0] == (17.58, 19.29, 76.99, 78.58)
    k = MARS_R_M * np.cos(np.deg2rad(0.0)); m = np.deg2rad
    wkt = 'PROJCS["Mars",PROJECTION["Equirectangular"],PARAMETER["central_meridian",0],PARAMETER["standard_parallel_1",0]]'
    class C:
        def to_wkt(self): return wkt
    b = (m(76.99) * k, m(17.58) * MARS_R_M, m(78.58) * k, m(19.29) * MARS_R_M)
    (a, c, d, e), src = geo_bounds(b, C()); assert abs(a - 17.58) < 1e-6 and abs(d - 76.99) < 1e-6 and src.startswith("CRS")
    assert geo_bounds(b, None)[0] == DOC_BOUNDS                       # unreadable CRS: published extent, never garbage
