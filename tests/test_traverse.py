import json, subprocess, pathlib, math
import numpy as np
import pytest
from mars_survival import traverse as T, physics as P
from mars_survival import site as S


def _flat(n=40):
    return np.zeros((n, n)), np.ones((n, n), dtype=np.float32)


def test_flat_energy_matches_formula():
    dem, tm = _flat()
    w = T.Walker()
    r = T.find_route_energy(dem, tm, 2.0, (5, 5), (5, 25), w)
    expect = w.mass_kg * P.walking_cost(0.0, w.g, w.level_scale) * 40.0
    assert r["energy_j"] == pytest.approx(expect, rel=1e-9) and r["length_m"] == pytest.approx(40.0)


def test_pace_is_physical_on_flat():
    dem, tm = _flat()
    r = T.find_route_energy(dem, tm, 2.0, (5, 5), (5, 25))
    kmh = r["length_m"] / 1000 / r["time_h"]
    assert 2.5 < kmh < 4.5                       # ~ v_opt Mars (3.4 km/h) / Apollo 3.3 km/h


def test_steep_wall_is_forbidden_and_detour_taken():
    dem, tm = _flat()
    dem[:, 20] = 30.0                            # 30 m wall over a 2 m step: slope >> 0.45
    dem[20, 20] = 0.0                            # a gap
    r = T.find_route_energy(dem, tm, 2.0, (5, 5), (5, 35))
    assert r and (20, 20) in r["path"]
    dem[20, 20] = 30.0
    assert T.find_route_energy(dem, tm, 2.0, (5, 5), (5, 35)) is None


def test_gentle_ramp_zigzag_beats_straight_when_steep():
    n = 60; y, x = np.mgrid[0:n, 0:n]
    dem = 0.40 * 2.0 * x.astype(float)           # slope 0.40 (within the valid range) toward the east
    tm = np.ones((n, n), dtype=np.float32)
    r = T.find_route_energy(dem, tm, 2.0, (30, 5), (30, 50))
    straight = T.step_cost(0.40, math.hypot(2.0, 0.8), 1.0, T.Walker())[0] * 45
    assert r["energy_j"] <= straight + 1e-6


def test_rough_ground_costs_more_and_is_avoided():
    dem, tm = _flat()
    tm[:, 15:25] = 3.0
    tm[20, 15:25] = 1.0                          # smooth corridor
    r = T.find_route_energy(dem, tm, 2.0, (5, 5), (5, 35))
    assert any(rc[0] > 5 for rc in r["path"])


def test_python_js_energy_parity(tmp_path):
    s = S.synthetic_site(size=120, px_m=12.0, seed=3)
    res = S.analyse(s)
    w = T.Walker()
    tm = T.terrain_multiplier(res["rough"], w)
    dem = np.asarray(s.dem, dtype=float)
    a, b = (5, 5), (110, 112)
    py = T.find_route_energy(dem, tm, s.px_m, a, b, w)
    assert py is not None
    j = {"dem": dem.ravel().tolist(), "tmult": [None if not math.isfinite(v) else float(v) for v in tm.ravel()],
         "w": dem.shape[1], "h": dem.shape[0], "px": s.px_m, "start": list(a), "goal": list(b), "objective": "energy",
         "walker": {"massKg": w.mass_kg, "powerW": w.power_w, "g": w.g, "levelScale": w.level_scale}}
    f = tmp_path / "in.json"; f.write_text(json.dumps(j))
    out = subprocess.run(["node", str(pathlib.Path(__file__).with_name("js_energy_parity.mjs")), str(f)],
                         capture_output=True, text=True, check=True).stdout
    js = json.loads(out)
    assert js["n"] == len(py["path"])
    assert js["energy_j"] == pytest.approx(py["energy_j"], rel=1e-9)
    assert js["time_h"] == pytest.approx(py["time_h"], rel=1e-9)


def test_terrain_multiplier_anchors_to_earth_terrain_factors():
    m = lambda r: float(T.terrain_multiplier(np.array([r]))[0])
    assert m(0.0) == pytest.approx(1.0)
    assert 1.1 <= m(0.10) <= 1.2          # dirt track / light brush (Soule & Goldman 1972)
    assert 1.8 <= m(0.25) <= 2.1          # marsh / loose sand
    assert m(0.25) == pytest.approx(2.0)  # r0: the cost doubles
    assert not math.isfinite(m(1.6))      # impassable
