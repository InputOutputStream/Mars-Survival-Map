import numpy as np

from mars_survival.schema import Grid, compute, derive_from_elevation, init_db, ramp


def _full(v, shape=(4, 8)):
    return np.full(shape, v, dtype=float)


def test_ramp_bounds():
    assert ramp(0, 0, 10) == 0 and ramp(10, 0, 10) == 1 and ramp(5, 0, 10) == 0.5
    assert ramp(-5, 0, 10) == 0 and ramp(50, 0, 10) == 1


def test_grid_area_sums_to_sphere():
    g = Grid(res_deg=5.0)
    total = g.cell_area_m2().sum()
    assert abs(total - 4 * np.pi * 3_396_190.0**2) / total < 1e-9


def test_favorable_cell_scores_high_and_geometric_mean_penalises_weak_factor():
    good = {"water_ice_depth_m": _full(0.0), "temp_mean_k": _full(260.0)}
    assert compute(good)["score"].mean() > 0.99
    bad = {"water_ice_depth_m": _full(0.0), "temp_mean_k": _full(150.0)}
    assert compute(bad)["score"].mean() < 0.5  # one catastrophic factor drags everything down


def test_hard_exclusion_zeroes_score():
    d = {"slope_deg": _full(30.0), "temp_mean_k": _full(260.0)}
    r = compute(d, "landing")
    assert r["excluded"].all() and (r["score"] == 0).all()


def test_missing_layer_in_cell_and_coverage():
    t = _full(260.0)
    t[0, 0] = np.nan                                   # missing temperature (weight 1 out of 4 in "landing")
    s = _full(1.0)
    r = compute({"temp_mean_k": t, "slope_deg": s}, "landing")
    assert np.isfinite(r["score"][0, 0])               # computed from the remaining layers
    assert r["coverage"][0, 0] < r["coverage"][1, 1]   # but the coverage is reduced
    assert np.isnan(compute({"temp_mean_k": t, "slope_deg": s}, "landing", min_coverage=0.99)["score"][0, 0])
    s2 = _full(1.0)
    s2[0, 0] = np.nan                                  # missing slope (weight 3/4) -> coverage 25 % < 50 %
    assert np.isnan(compute({"temp_mean_k": _full(260.0), "slope_deg": s2}, "landing")["score"][0, 0])


def test_limiting_factor_is_weakest_layer():
    d = {"temp_mean_k": _full(260.0), "water_ice_depth_m": _full(20.0)}  # deep ice -> score 0
    r = compute(d)
    assert r["limiting_keys"][int(r["limiting_idx"][0, 0])] == "water_ice_depth_m"


def test_derived_pressure_decreases_with_altitude():
    d = derive_from_elevation(np.array([-4000.0, 0.0, 6000.0]))
    assert d["pressure_pa"][0] > d["pressure_pa"][1] > d["pressure_pa"][2]
    assert d["radiation_msv_day"][0] < d["radiation_msv_day"][2]


def test_init_db_creates_tables():
    db = init_db(":memory:")
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"cell", "cell_score", "cell_value", "layer_def", "source_file", "grid_meta"} <= names
