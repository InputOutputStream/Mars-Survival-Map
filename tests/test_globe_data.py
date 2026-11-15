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
