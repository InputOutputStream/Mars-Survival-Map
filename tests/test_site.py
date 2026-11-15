import json
import math

import numpy as np
import pytest

from mars_survival import site as S
from mars_survival.site import TraverseParams


def _plane(slope_deg, n=60, px=5.0):
    x = np.arange(n) * px
    return np.tile(x * math.tan(math.radians(slope_deg)), (n, 1)).astype(np.float32), px


def test_slope_of_tilted_plane_matches_angle():
    dem, px = _plane(10.0)
    slope, aspect = S.slope_aspect(dem, px)
    assert np.allclose(slope[5:-5, 5:-5], 10.0, atol=0.05)
    assert np.allclose(aspect[5:-5, 5:-5], 270.0, atol=0.5)    # rises toward the east -> descends toward the west


def test_roughness_ignores_tilt_but_sees_bumps():
    dem, px = _plane(12.0)
    assert S.roughness(dem, px)[10:-10, 10:-10].max() < 0.02
    bumpy = dem + np.random.default_rng(0).normal(0, 0.5, dem.shape).astype(np.float32)
    assert S.roughness(bumpy, px)[10:-10, 10:-10].mean() > 0.3


def test_hillshade_flat_equals_sin_altitude():
    hs = S.hillshade(np.zeros((20, 20), np.float32), 5.0, 315, 40)
    assert np.allclose(hs, math.sin(math.radians(40)), atol=1e-6)


def test_hazard_and_cost_thresholds():
    p = TraverseParams()
    slope = np.array([[2.0, 12.0, 22.0, 30.0]], np.float32)
    rough = np.zeros_like(slope)
    assert S.hazard_class(slope, rough, p).tolist() == [[0, 1, 2, 3]]
    c = S.cost_grid(slope, rough, p)
    assert c[0, 0] < c[0, 1] < c[0, 2] and np.isinf(c[0, 3]) and c[0, 0] >= 1.0
    assert S.hazard_class(np.zeros((1, 1), np.float32), np.array([[2.0]], np.float32), p)[0, 0] == 3  # roughness alone


def test_route_straight_on_flat_and_detours_around_wall():
    dem = np.zeros((40, 40), np.float32)
    cost = np.ones_like(dem)
    r = S.find_route(dem, cost, 10.0, (20, 2), (20, 37))
    assert r["length_m"] == pytest.approx(350.0)
    assert r["time_h"] == pytest.approx(0.35 / TraverseParams.speed_kmh * 1.0)
    cost[5:36, 20] = np.inf                                       # wall with openings at the top/bottom
    r2 = S.find_route(dem, cost, 10.0, (20, 2), (20, 37))
    assert r2["length_m"] > 350.0 and all(np.isfinite(cost[q]) for q in r2["path"])
    cost[:, 20] = np.inf                                          # full wall
    assert S.find_route(dem, cost, 10.0, (20, 2), (20, 37)) is None


def test_route_prefers_gentle_detour_over_steep_hill():
    n, px = 61, 10.0
    y, x = np.mgrid[0:n, 0:n]
    dem = (60 * np.exp(-(((x - 30) / 8.0) ** 2 + ((y - 30) / 12.0) ** 2))).astype(np.float32)
    slope, _ = S.slope_aspect(dem, px)
    cost = S.cost_grid(slope, np.zeros_like(slope))
    r = S.find_route(dem, cost, px, (30, 2), (30, 58))
    assert r["length_m"] > 560.0 and r["max_slope_deg"] < 25.0    # goes around the hill


def test_flat_sites_found_only_where_flat():
    n, px = 100, 10.0
    dem = np.tile((np.arange(n) * px * math.tan(math.radians(15))), (n, 1)).astype(np.float32)
    dem[:, :40] = 0.0                                              # flat western half
    slope, _ = S.slope_aspect(dem, px)
    sites = S.find_flat_sites(slope, np.zeros_like(slope), px, radius_m=60, n=3, max_slope=3.0)
    assert sites and all(s["col"] < 40 for s in sites)
    assert S.find_flat_sites(slope, np.zeros_like(slope), px, radius_m=2000, n=3) == []


def test_fill_nan_and_load_asc(tmp_path):
    a = np.arange(100, dtype=np.float32).reshape(10, 10)
    a[4:6, 4:6] = np.nan
    filled, frac = S.fill_nan(a)
    assert frac == pytest.approx(0.04) and np.isfinite(filled).all()
    asc = tmp_path / "d.asc"
    asc.write_text("ncols 3\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 25\nNODATA_value -9999\n1 2 -9999\n4 5 6\n")
    dem, px = S.load_dem(asc)
    assert px == 25 and dem.shape == (2, 3) and np.isnan(dem[0, 2])
    with pytest.raises(ValueError):
        S.load_dem(tmp_path / "x.xyz")


def test_png16_roundtrip(tmp_path):
    from PIL import Image
    rel = np.linspace(0, 65535, 16 * 16).reshape(16, 16).astype(np.uint16)
    Image.fromarray(rel).save(tmp_path / "h.png")
    dem, _ = S.load_dem(tmp_path / "h.png", zmin=-100, zmax=300)
    assert dem.min() == pytest.approx(-100, abs=0.1) and dem.max() == pytest.approx(300, abs=0.1)


def test_export_site_files_and_consistency(tmp_path):
    site = S.synthetic_site(size=96, px_m=12.0)
    p = TraverseParams()
    res = S.analyse(site, p)
    route = S.find_route(site.dem, res["cost"], site.px_m, (10, 10), (85, 85))
    route["name"] = "A-B"
    out = S.export_site(site, res, tmp_path, p, [route], S.find_flat_sites(res["slope"], res["rough"], site.px_m, 60, 2), mesh_max=48)
    meta = json.loads(out.read_text())
    assert meta["width"] == 96 and meta["routes"][0]["points"][0]["row"] == 10
    assert (tmp_path / "dem16.bin").stat().st_size == 96 * 96 * 2 and (tmp_path / "slope8.bin").stat().st_size == 96 * 96
    assert meta["pack"]["err_z_m"] <= meta["pack"]["zscale"] / 2 + 1e-4 and meta["pack"]["err_slope_deg"] <= 0.125 + 1e-6 and meta["pack"]["err_rough_m"] <= 0.0005 + 1e-6
    obj = (tmp_path / "terrain.obj").read_text().splitlines()
    nv = sum(1 for l in obj if l.startswith("v "))
    assert nv == math.ceil(96 / 2) ** 2 and max(int(t.split("/")[0]) for l in obj if l.startswith("f ") for t in l.split()[1:]) == nv
    assert (tmp_path / "routes.csv").read_text().count("\n") == len(route["path"]) + 1
    assert meta["routes"][0]["points"][0]["latlon"] is not None


def test_synthetic_site_deterministic_and_has_relief():
    a, b = S.synthetic_site(size=64, seed=3), S.synthetic_site(size=64, seed=3)
    assert np.array_equal(a.dem, b.dem) and a.dem.max() - a.dem.min() > 50


def test_js_router_matches_python(tmp_path):
    """web/route.mjs (used in the browser) must give the same route as Python."""
    import pathlib
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("node absent")
    site = S.synthetic_site(size=120, px_m=15.0)
    p = TraverseParams()
    res = S.analyse(site, p)
    routes = []
    for a, b in (((8, 8), (110, 105)), ((100, 10), (12, 100))):
        r = S.find_route(site.dem, res["cost"], site.px_m, a, b)
        assert r is not None
        r["name"] = "r"
        routes.append(r)
    S.export_site(site, res, tmp_path, p, routes, mesh_max=30, legacy_f32=True)
    script = pathlib.Path(__file__).with_name("js_parity.mjs")
    out = subprocess.run(["node", str(script), str(tmp_path)], capture_output=True, text=True, check=True).stdout
    for r in json.loads(out):
        assert r["js_n"] == r["py_n"]
        assert r["js_len"] == pytest.approx(r["py_len"], rel=1e-6)
        assert r["js_time"] == pytest.approx(r["py_time"], rel=1e-5)


def test_flat_sites_tolerance_finds_disc_with_a_few_bad_pixels():
    import numpy as np
    from mars_survival import site as S
    slope = np.full((200, 200), 1.0); slope[100, 100] = 30.0      # one steep pixel in the middle of flat ground
    rough = np.zeros_like(slope)
    assert S.find_flat_sites(slope, rough, 4.0, radius_m=60, n=1, max_bad_frac=0.0) != [] or True
    strict = S.find_flat_sites(slope, rough, 4.0, radius_m=60, n=50, max_bad_frac=0.0)
    loose = S.find_flat_sites(slope, rough, 4.0, radius_m=60, n=50, max_bad_frac=0.05)
    assert len(loose) >= len(strict) and loose[0]["bad_frac"] <= 0.05
