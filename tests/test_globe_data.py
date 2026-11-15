import numpy as np
import pytest
from mars_survival import globe_data as G


def test_topography_layout_and_block_mean():
    # test fixture, not Mars data: left edge (lon 0) is 100 m, everything else 0, top row (lat +90) is 400 m
    a = np.zeros((720, 1440), dtype=">i2"); a[:, 0] = 100; a[0, :] = 400
    g = G.topography_to_grid(a.tobytes())
    assert g.shape == (360, 720)
    # lon 0 is the boundary between the last and first column after the half-turn roll: first sample lands at column 360
    assert g[5, 360] == pytest.approx(50.0) and g[5, 359] == 0
    assert g[0, 10] == pytest.approx(200.0)          # (400 + 0) / 2 along the top rows
    with pytest.raises(ValueError):
        G.topography_to_grid(b"123")


def test_ns_table_placement_by_coordinates_and_zero_is_no_data():
    # test fixture, not Mars data. Rows deliberately shuffled; lon 0..360.
    txt = " 180.25, -89.75,   0.000\n   0.25,  89.75,   5.500\n 359.75, -89.75,   7.250\n 100.25,  18.25,   2.000\n"
    g, nzero = G.parse_ns_table(txt)
    assert nzero == 1
    assert g[0, 360] == pytest.approx(5.5)            # lon +0.25 -> column 360 on the -180..180 grid, lat +89.75 -> row 0
    assert g[359, 359] == pytest.approx(7.25)         # lon 359.75 = -0.25
    assert g[int((90 - 18.25) / 0.5), 360 + 200] == pytest.approx(2.0)
    assert np.isnan(g[359, 0])                        # lon 180.25 -> -179.75: zero treated as no data
    with pytest.raises(ValueError):
        G.parse_ns_table("1,2\n")


def test_thermal_inertia_block_mean_and_nodata():
    # test fixture, not Mars data: 3600 x 7200 int16; one block holds 100 (x50 valid) and 0 (x50, outside 5..5000)
    a = np.full((3600, 7200), 200, dtype=">i2"); a[0:10, 0:5] = 100; a[0:10, 5:10] = 0; a[10:20, 0:10] = 6000
    g, bad = G.thermal_inertia_to_grid(a.tobytes())
    assert g.shape == (360, 720)
    assert g[0, 0] == pytest.approx(100.0)            # mean of the valid half only
    assert np.isnan(g[1, 0])                           # everything outside the valid range -> NaN
    assert g[5, 5] == pytest.approx(200.0)
    assert bad == pytest.approx((50 + 100) / (3600 * 7200))
    with pytest.raises(ValueError):
        G.thermal_inertia_to_grid(b"12")


def _mcs_fixture(value_fn):
    # test fixture, not Mars data: the layout of the real file (MY 28..37, Ls 0..350, ltst 3/15, Lat -85..90, Lon -180..175)
    my = np.arange(28, 38.); ls = np.arange(0, 360, 10.); ltst = np.array([3., 15.])
    lat = np.arange(-85, 91, 5.); lon = np.arange(-180, 180, 5.)
    t = np.full((10, 36, 2, 36, 72), np.nan)
    for i, l in enumerate(ltst):
        t[:, :, i] = value_fn(l)
    return t, my, ls, ltst, lat, lon


def test_ls_time_weights_sum_to_one_and_are_unequal():
    w = G.ls_time_weights(np.arange(0, 360, 10.))
    assert w.sum() == pytest.approx(1.0) and w.max() / w.min() > 1.3     # Mars' seasons are unequal (about 1.45 at the extremes, from the orbit)


def test_mcs_constant_field_and_outliers_dropped():
    t, my, ls, ltst, lat, lon = _mcs_fixture(lambda l: 200.0 if l == 3 else 260.0)
    t[0, :, :, 10, 10] = 999.0                    # an outlier in one Mars year must not change the median
    t[:, :, :, 0, :] = np.nan                     # no data at lat -85
    out = G.mcs_to_grid(t, my, ls, ltst, lat, lon)
    assert out["temp_mean_k"].shape == (360, 720)
    ok = np.isfinite(out["temp_mean_k"])
    assert np.allclose(out["temp_mean_k"][ok], 230.0, atol=1e-3) and np.allclose(out["temp_diurnal_k"][np.isfinite(out["temp_diurnal_k"])], 60.0, atol=1e-3)
    assert out["outlier_fraction"] > 0
    assert np.isnan(out["temp_mean_k"][359, 0])  # lat -89.75 is south of the first latitude node (-85): not extrapolated


def test_mcs_requires_enough_of_the_year():
    t, my, ls, ltst, lat, lon = _mcs_fixture(lambda l: 220.0)
    t[:, 18:, :, 17:24, :] = np.nan               # half of the Ls bins missing over a block of 7 latitude nodes (lat 0..30)
    out = G.mcs_to_grid(t, my, ls, ltst, lat, lon)
    row_mid = int((90 - 15.0) / 0.5)              # lat 14.75, deep inside the block: no valid neighbour either
    assert np.isnan(out["temp_mean_k"][row_mid]).all()
    assert np.isfinite(out["temp_mean_k"][int((90 - 50) / 0.5)]).all()   # elsewhere untouched


def test_dust_year_orientation_scaling_and_median():
    # test fixture, not Mars data: layout of the real file (lat 88.5 -> -88.5, lon -180 -> 177, step 3), north half 0.1, south half 0.3
    lat = np.arange(88.5, -90, -3.0); lon = np.arange(-180, 180, 3.0)
    tot = np.empty((5, 60, 120)); tot[:, :30] = 0.1; tot[:, 30:] = 0.3
    g = G.dust_year_to_grid(tot, lat, lon)
    assert g.shape == (360, 720)
    assert g[100, 300] == pytest.approx(0.26, abs=1e-6)     # north (row 100 = lat 39.75): 0.1 x 2.6
    assert g[260, 300] == pytest.approx(0.78, abs=1e-6)     # south: 0.3 x 2.6
    assert np.isnan(g[0, 0]) and np.isnan(g[359, 0])        # beyond the +-88.5 nodes: not extrapolated
    assert G.DUST_FILES[29] == "dustscenario_MY29_v2-0.nc" and G.DUST_FILES[34] == "dustscenario_MY34_v2-5.nc"
